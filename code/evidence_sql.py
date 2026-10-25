"""Load SQL evidence snapshots and check account profile presence."""

from __future__ import annotations

import csv
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from loaders import DATASET_DIR, REPO_ROOT


@dataclass(frozen=True)
class EvidenceFile:
    file_id: str
    file_path: str
    origin: str
    captured_at: str

    @property
    def absolute_path(self) -> Path:
        return REPO_ROOT / "dataset" / self.file_path


def load_evidence_file(file_id: str) -> EvidenceFile:
    path = DATASET_DIR / "evidence_files.csv"
    with path.open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            if row["file_id"] == file_id:
                return EvidenceFile(
                    file_id=row["file_id"],
                    file_path=row["file_path"],
                    origin=row["origin"],
                    captured_at=row["captured_at"],
                )
    raise KeyError(f"file_id not found: {file_id}")


def evidence_usable_at(evidence: EvidenceFile, audit_at: str) -> bool:
    """True when the evidence was captured at or before the case audit cutoff."""
    return evidence.captured_at <= audit_at


def _load_sql_connection(sql_path: Path) -> sqlite3.Connection:
    sql_text = sql_path.read_text(encoding="utf-8")
    conn = sqlite3.connect(":memory:")
    conn.executescript(sql_text)
    return conn


def _profile_tables(conn: sqlite3.Connection) -> list[str]:
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'customer_profiles%'"
    ).fetchall()
    return [name for (name,) in rows]


def find_account_profile_hits(
    sql_path: Path,
    *,
    resource_id: str,
    email: str,
    user_id: str,
) -> list[tuple[str, str]]:
    """
    Return (table_name, resource_id) hits for the subject across primary/replica tables.
    Exact match on resource_id, email (case-insensitive), or user_id.
    """
    email_key = email.strip().lower()
    hits: list[tuple[str, str]] = []
    conn = _load_sql_connection(sql_path)
    try:
        for table in _profile_tables(conn):
            rows = conn.execute(
                f'SELECT resource_id, user_id, email FROM "{table}"'
            ).fetchall()
            for rid, uid, row_email in rows:
                if (
                    rid == resource_id
                    or uid == user_id
                    or (row_email or "").strip().lower() == email_key
                ):
                    hits.append((table, rid))
    finally:
        conn.close()
    return hits


def account_profile_state(
    sql_path: Path,
    *,
    resource_id: str,
    email: str,
    user_id: str,
) -> str:
    """Return ABSENT or PRESENT for the account profile in this SQL snapshot."""
    hits = find_account_profile_hits(
        sql_path, resource_id=resource_id, email=email, user_id=user_id
    )
    return "PRESENT" if hits else "ABSENT"
