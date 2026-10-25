"""Mock EvidenceIndex stub — filled in a later increment."""

from __future__ import annotations

from pathlib import Path

from evidence.base import EvidenceRecord, register_evidence_index


@register_evidence_index("mock")
class MockEvidenceIndex:
    """Placeholder Stage 6 plugin that returns no evidence.

    Call ``build`` once before ``query``. Real parsers replace this stub later.
    """

    name = "mock"

    def __init__(self) -> None:
        self._built = False
        self._records: list[EvidenceRecord] = []

    def build(self, dataset_dir: Path) -> None:
        """Mark the index ready without parsing files.

        Args:
            dataset_dir: Path to ``dataset/`` (unused by this stub).
        """
        self._built = True
        self._records = []

    def query(self, identifiers: set[str], audit_at: str) -> list[EvidenceRecord]:
        """Return an empty hit list (stub).

        Args:
            identifiers: Subject keys (ignored by stub).
            audit_at: Audit cutoff (ignored by stub).

        Returns:
            Always ``[]``.

        Raises:
            RuntimeError: If ``build`` was not called first.
        """
        if not self._built:
            raise RuntimeError("MockEvidenceIndex.build() must be called first")
        _ = identifiers, audit_at
        return []
