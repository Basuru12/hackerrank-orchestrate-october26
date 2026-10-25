"""CSV loaders for the deletion-audit agent."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DATASET_DIR = REPO_ROOT / "dataset"


@dataclass(frozen=True)
class DeletionRequest:
    case_id: str
    email: str
    requested_at: str
    reported_status: str
    reported_at: str
    audit_at: str
    request_text: str


def load_deletion_request(case_id: str, *, sample: bool = True) -> DeletionRequest:
    """Load a single deletion request by case_id."""
    filename = "sample_deletion_requests.csv" if sample else "deletion_requests.csv"
    path = DATASET_DIR / filename
    with path.open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            if row["case_id"] == case_id:
                return DeletionRequest(
                    case_id=row["case_id"],
                    email=row["email"],
                    requested_at=row["requested_at"],
                    reported_status=row["reported_status"],
                    reported_at=row["reported_at"],
                    audit_at=row["audit_at"],
                    request_text=row["request_text"],
                )
    raise KeyError(f"case_id not found in {filename}: {case_id}")
