"""Build, write, and verify tracer output."""

from __future__ import annotations

import csv
import json

from loaders import DATASET_DIR, REPO_ROOT


def complete_account_result(
    case_id: str, resource_id: str, evidence_id: str
) -> dict[str, object]:
    """Build a COMPLETE one-step VERIFY_RECORD_ABSENT result for an account.

    Args:
        case_id: Case key written to output (e.g. ``case_01``).
        resource_id: Account resource verified absent (e.g. ``account_001``).
        evidence_id: Proving evidence file id (e.g. ``evidence_54``).

    Returns:
        Dict with ``case_id``, ``deletion_status`` (``COMPLETE``), and
        ``steps_json`` as a Python list of one verification step.
    """
    step = {
        "step_no": 1,
        "phase": "VERIFICATION",
        "system_id": "account_service",
        "resource_id": resource_id,
        "operation": "VERIFY_RECORD_ABSENT",
        "state": "ABSENT",
        "evidence_id": evidence_id,
    }
    return {"case_id": case_id, "deletion_status": "COMPLETE", "steps_json": [step]}


def write_and_verify_sample(result: dict[str, object]) -> None:
    """Write one-row root output.csv and assert it matches sample_output.

    Args:
        result: Dict from ``complete_account_result`` (or equivalent) with keys
            ``case_id``, ``deletion_status``, and ``steps_json`` (list).

    Raises:
        AssertionError: If status or parsed steps differ from sample_output.csv
            for the same ``case_id``.
        StopIteration: If ``case_id`` is missing from sample_output.csv.
    """
    serialized = json.dumps(result["steps_json"], separators=(",", ":"))
    with (REPO_ROOT / "output.csv").open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=["case_id", "deletion_status", "steps_json"])
        writer.writeheader()
        writer.writerow({**result, "steps_json": serialized})

    with (DATASET_DIR / "sample_output.csv").open(newline="", encoding="utf-8") as fh:
        expected = next(row for row in csv.DictReader(fh) if row["case_id"] == result["case_id"])
    actual = {**result, "steps_json": json.loads(serialized)}
    expected["steps_json"] = json.loads(expected["steps_json"])
    assert actual == expected, f"tracer output mismatch:\nactual={actual}\nexpected={expected}"
