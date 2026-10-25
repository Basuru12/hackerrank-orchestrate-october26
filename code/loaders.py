"""CSV loaders for the deletion-audit agent."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DATASET_DIR = REPO_ROOT / "dataset"


@dataclass(frozen=True)
class DeletionRequest:
    """One row from sample_deletion_requests.csv or deletion_requests.csv.

    Attributes:
        case_id: Unique case key (e.g. ``case_01``).
        email: Request email (current or historical).
        requested_at: When the request was submitted (ISO-8601).
        reported_status: Workflow claim (``COMPLETE``, ``PARTIALLY_COMPLETE``,
            ``NOT_STARTED``) — not proof of true state.
        reported_at: When that claim was reported (ISO-8601).
        audit_at: Cutoff for evidence/activity used in the answer (ISO-8601).
        request_text: Multilingual free-text request body.
    """

    case_id: str
    email: str
    requested_at: str
    reported_status: str
    reported_at: str
    audit_at: str
    request_text: str


def _request_from_row(row: dict[str, str]) -> DeletionRequest:
    """Map a CSV row dict to ``DeletionRequest``.

    Args:
        row: Dict with the standard deletion-request columns.

    Returns:
        Parsed ``DeletionRequest``.
    """
    return DeletionRequest(
        case_id=row["case_id"],
        email=row["email"],
        requested_at=row["requested_at"],
        reported_status=row["reported_status"],
        reported_at=row["reported_at"],
        audit_at=row["audit_at"],
        request_text=row["request_text"],
    )


def load_deletion_requests(*, sample: bool = True) -> list[DeletionRequest]:
    """Load all deletion requests from the sample or evaluation CSV.

    Args:
        sample: If True, read ``sample_deletion_requests.csv`` (32 rows).
            If False, read ``deletion_requests.csv`` (518 rows).

    Returns:
        All requests in file order.
    """
    filename = "sample_deletion_requests.csv" if sample else "deletion_requests.csv"
    path = DATASET_DIR / filename
    with path.open(newline="", encoding="utf-8") as fh:
        return [_request_from_row(row) for row in csv.DictReader(fh)]


def load_deletion_request(case_id: str, *, sample: bool = True) -> DeletionRequest:
    """Load a single deletion request by ``case_id``.

    Args:
        case_id: Case to find (e.g. ``case_01``).
        sample: Which CSV to search (see ``load_deletion_requests``).

    Returns:
        The matching ``DeletionRequest``.

    Raises:
        KeyError: If ``case_id`` is not in the chosen file.
    """
    for request in load_deletion_requests(sample=sample):
        if request.case_id == case_id:
            return request
    filename = "sample_deletion_requests.csv" if sample else "deletion_requests.csv"
    raise KeyError(f"case_id not found in {filename}: {case_id}")


@lru_cache(maxsize=1)
def load_user_identity_rows() -> tuple[dict[str, str], ...]:
    """Load all rows from user_identities.csv (cached).

    Returns:
        Tuple of row dicts with keys ``user_id``, ``name``, ``email``,
        ``phone``, ``email_hash``, ``updated_at``.
    """
    path = DATASET_DIR / "user_identities.csv"
    with path.open(newline="", encoding="utf-8") as fh:
        return tuple(csv.DictReader(fh))


@lru_cache(maxsize=1)
def load_user_audit_log() -> tuple[dict[str, str], ...]:
    """Load all rows from user_audit_log.csv (cached).

    Returns:
        Tuple of row dicts with keys ``audit_id``, ``user_id``, ``event_time``,
        ``field_name``, ``old_value``, ``new_value``.
    """
    path = DATASET_DIR / "user_audit_log.csv"
    with path.open(newline="", encoding="utf-8") as fh:
        return tuple(csv.DictReader(fh))
