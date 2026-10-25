"""Build, write, and verify tracer output."""

from __future__ import annotations

import csv
import json

from loaders import DATASET_DIR, REPO_ROOT


def complete_account_result(
    case_id: str, resource_id: str, evidence_id: str
) -> dict[str, object]:
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
