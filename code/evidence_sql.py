"""Load SQL evidence snapshots and check account profile presence."""

from __future__ import annotations

import csv
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from loaders import DATASET_DIR, REPO_ROOT


@dataclass(frozen=True)
class EvidenceFile:
    """One row from evidence_files.csv.

    Attributes:
        file_id: Manifest id (e.g. ``evidence_54``).
        file_path: Path relative to ``dataset/``.
        origin: Capture origin label from the manifest.
        captured_at: ISO-8601 capture timestamp.
    """

    file_id: str
    file_path: str
    origin: str
    captured_at: str

    @property
    def absolute_path(self) -> Path:
        """Absolute filesystem path to the evidence file under ``dataset/``."""
        return REPO_ROOT / "dataset" / self.file_path


def load_evidence_file(file_id: str) -> EvidenceFile:
    """Load one evidence manifest row by ``file_id``.

    Args:
        file_id: Manifest key (e.g. ``evidence_54``).

    Returns:
        Matching ``EvidenceFile``.

    Raises:
        KeyError: If ``file_id`` is not in evidence_files.csv.
    """
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
    """Return whether evidence may be used for a case audit cutoff.

    Args:
        evidence: Manifest row with ``captured_at``.
        audit_at: Case ``audit_at`` (ISO-8601).

    Returns:
        True when ``evidence.captured_at <= audit_at``.
    """
    return evidence.captured_at <= audit_at


def _load_sql_connection(sql_path: Path) -> sqlite3.Connection:
    """Execute a SQLite-compatible SQL dump into an in-memory database.

    Args:
        sql_path: Path to a ``.sql`` evidence file.

    Returns:
        Open ``sqlite3.Connection`` (caller must close).
    """
    sql_text = sql_path.read_text(encoding="utf-8")
    conn = sqlite3.connect(":memory:")
    conn.executescript(sql_text)
    return conn


def _profile_tables(conn: sqlite3.Connection) -> list[str]:
    """List ``customer_profiles*`` table names in an open connection.

    Args:
        conn: SQLite connection with the evidence schema loaded.

    Returns:
        Table names such as ``customer_profiles_primary``.
    """
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
    """Find account profile rows for a subject across primary/replica tables.

    Matching is exact on ``resource_id``, ``user_id``, or case-insensitive email.

    Args:
        sql_path: Path to the SQL snapshot file.
        resource_id: Expected account resource (e.g. ``account_001``).
        email: Subject email to match.
        user_id: Subject user id to match.

    Returns:
        List of ``(table_name, matched_resource_id)`` hits (may be empty).
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
    """Classify account profile presence in a SQL snapshot.

    Args:
        sql_path: Path to the SQL snapshot file.
        resource_id: Expected account resource id.
        email: Subject email.
        user_id: Subject user id.

    Returns:
        ``"PRESENT"`` if any profile hit exists, otherwise ``"ABSENT"``.
    """
    hits = find_account_profile_hits(
        sql_path, resource_id=resource_id, email=email, user_id=user_id
    )
    return "PRESENT" if hits else "ABSENT"
