"""Mock EvidenceIndex: deterministic parsers + LINK_RESOURCE_IDENTITY enrichment."""

from __future__ import annotations

from pathlib import Path

from evidence.base import EvidenceRecord, register_evidence_index
from evidence.parsers import (
    parse_json_file,
    parse_log_file,
    parse_sql_file,
    parse_txt_handover,
    sql_absent_records,
)
from link_parse import parse_link_details
from loaders import load_evidence_manifest, load_system_activity


@register_evidence_index("mock")
class MockEvidenceIndex:
    """Stage 6 mock: parse JSON/SQL/log/TXT; link multimodal via activity.

    PDF/PNG bytes are not OCR'd; ``LINK_RESOURCE_IDENTITY`` supplies those links.
    """

    name = "mock"

    def __init__(self) -> None:
        self._built = False
        self._records: list[EvidenceRecord] = []
        self._sql_files: list[tuple[str, str, Path]] = []  # file_id, captured_at, path
        self._resource_idents: dict[str, set[str]] = {}

    def build(self, dataset_dir: Path) -> None:
        """Parse participant evidence under ``dataset_dir`` once.

        Args:
            dataset_dir: Path to ``dataset/``.
        """
        self._records = []
        self._sql_files = []
        self._resource_idents = {}

        for row in load_evidence_manifest():
            file_id = row["file_id"]
            captured_at = row["captured_at"]
            path = dataset_dir / row["file_path"]
            if not path.exists():
                continue
            suffix = path.suffix.lower()
            if suffix == ".json":
                self._records.extend(parse_json_file(path, file_id, captured_at))
            elif suffix == ".txt":
                self._records.extend(parse_txt_handover(path, file_id, captured_at))
            elif suffix == ".log":
                self._records.extend(parse_log_file(path, file_id, captured_at))
            elif suffix == ".sql":
                self._sql_files.append((file_id, captured_at, path))
                self._records.extend(parse_sql_file(path, file_id, captured_at))
            # .png / .pdf skipped — linked via activity below

        for row in load_system_activity():
            if row["event_type"] != "LINK_RESOURCE_IDENTITY":
                continue
            parsed = parse_link_details(row.get("details") or "")
            if not parsed:
                continue
            linked_resource_id, _alias, email, user_id = parsed
            resource_id = row["resource_id"] or linked_resource_id
            idents = {email, user_id}
            self._resource_idents.setdefault(resource_id, set()).update(idents)
            # Synthetic link record so multimodal resources are queryable.
            self._records.append(
                EvidenceRecord(
                    file_id=row["activity_id"],
                    captured_at=row["event_time"],
                    system_id=row["target_system"],
                    resource_id=resource_id,
                    data_category="",
                    state="PRESENT",
                    identifiers=tuple(sorted(idents)),
                    raw_snippet=(row.get("details") or "")[:300],
                )
            )

        # Enrich parsed rows that lack identifiers but share a linked resource_id.
        enriched: list[EvidenceRecord] = []
        for rec in self._records:
            if rec.identifiers:
                for ident in rec.identifiers:
                    self._resource_idents.setdefault(rec.resource_id, set()).add(ident)
                enriched.append(rec)
                continue
            linked = self._resource_idents.get(rec.resource_id)
            if linked:
                enriched.append(
                    EvidenceRecord(
                        file_id=rec.file_id,
                        captured_at=rec.captured_at,
                        system_id=rec.system_id,
                        resource_id=rec.resource_id,
                        data_category=rec.data_category,
                        state=rec.state,
                        identifiers=tuple(sorted(linked)),
                        raw_snippet=rec.raw_snippet,
                    )
                )
            else:
                enriched.append(rec)
        self._records = enriched
        self._built = True

    def query(
        self,
        identifiers: set[str],
        audit_at: str,
        resource_ids: set[str] | None = None,
    ) -> list[EvidenceRecord]:
        """Return records for identifiers/resources with captured_at <= audit_at.

        Args:
            identifiers: Exact subject keys to match.
            audit_at: Case audit cutoff (ISO-8601).
            resource_ids: Optional extra resource ids (e.g. from deletion_worker
                window). Used to synthesize SQL ABSENT proofs.

        Returns:
            Matching ``EvidenceRecord`` rows.

        Raises:
            RuntimeError: If ``build`` was not called first.
        """
        if not self._built:
            raise RuntimeError("MockEvidenceIndex.build() must be called first")

        id_norm = {i.strip().lower() if "@" in i else i.strip() for i in identifiers if i}
        wanted_resources = set(resource_ids or ())
        for resource_id, linked in self._resource_idents.items():
            if any((x.lower() if "@" in x else x) in id_norm for x in linked):
                wanted_resources.add(resource_id)

        hits: list[EvidenceRecord] = []
        for rec in self._records:
            if rec.captured_at > audit_at:
                continue
            rec_idents = {
                (x.lower() if "@" in x else x) for x in rec.identifiers
            }
            if rec_idents & id_norm or rec.resource_id in wanted_resources:
                hits.append(rec)

        # SQL absence proofs for requested resources not present in snapshot tables.
        for file_id, captured_at, path in self._sql_files:
            if captured_at > audit_at:
                continue
            hits.extend(
                sql_absent_records(path, file_id, captured_at, wanted_resources)
            )

        # De-dupe by (file_id, resource_id, state)
        seen: set[tuple[str, str, str]] = set()
        unique: list[EvidenceRecord] = []
        for rec in hits:
            key = (rec.file_id, rec.resource_id, rec.state)
            if key in seen:
                continue
            seen.add(key)
            unique.append(rec)
        return unique
