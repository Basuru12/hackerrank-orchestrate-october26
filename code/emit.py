"""Write output.csv, validate schema, and score against sample_output."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from loaders import DATASET_DIR, REPO_ROOT
from policy import OPERATION_ORDER, PHASE_ORDER

OUTPUT_FIELDS = ("case_id", "deletion_status", "steps_json")
ALLOWED_STATUSES = frozenset({"COMPLETE", "INCOMPLETE", "NOT_APPLICABLE"})
ALLOWED_PHASES = frozenset(PHASE_ORDER)
ALLOWED_OPS = frozenset(OPERATION_ORDER)


def write_output_csv(rows: list[dict[str, Any]], path: Path | None = None) -> Path:
    """Write sorted prediction rows to root output.csv.

    Args:
        rows: Case results with ``case_id``, ``deletion_status``, ``steps_json`` (list).
        path: Destination CSV path (defaults to repo-root ``output.csv``).

    Returns:
        Path written.
    """
    dest = path or (REPO_ROOT / "output.csv")
    ordered = sorted(rows, key=lambda r: r["case_id"])
    with dest.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(OUTPUT_FIELDS))
        writer.writeheader()
        for row in ordered:
            writer.writerow(
                {
                    "case_id": row["case_id"],
                    "deletion_status": row["deletion_status"],
                    "steps_json": json.dumps(row["steps_json"], separators=(",", ":")),
                }
            )
    return dest


def validate_result(row: dict[str, Any]) -> list[str]:
    """Return schema/order problems for one case result (empty if valid).

    Args:
        row: Dict with ``case_id``, ``deletion_status``, ``steps_json`` (list).

    Returns:
        Human-readable error strings (empty list means OK).
    """
    errors: list[str] = []
    status = row.get("deletion_status")
    steps = row.get("steps_json")
    if status not in ALLOWED_STATUSES:
        errors.append(f"bad status: {status}")
    if not isinstance(steps, list):
        errors.append("steps_json must be a list")
        return errors

    if status == "NOT_APPLICABLE":
        if steps:
            errors.append("NOT_APPLICABLE must have empty steps")
        return errors

    prev_key: tuple | None = None
    for i, step in enumerate(steps, start=1):
        if step.get("step_no") != i:
            errors.append(f"step_no gap at index {i}: {step.get('step_no')}")
        phase = step.get("phase")
        op = step.get("operation")
        if phase not in ALLOWED_PHASES:
            errors.append(f"bad phase: {phase}")
        if op not in ALLOWED_OPS:
            errors.append(f"bad operation: {op}")
        key = (
            PHASE_ORDER.get(phase, 99),
            OPERATION_ORDER.get(op, 99),
            step.get("system_id", ""),
            step.get("resource_id", ""),
        )
        if prev_key is not None and key < prev_key:
            errors.append(f"step order violation at step_no={i}")
        prev_key = key

        if status == "COMPLETE":
            if phase != "VERIFICATION":
                errors.append("COMPLETE may only include VERIFICATION")
            if not step.get("evidence_id"):
                errors.append(f"COMPLETE step missing evidence_id at {i}")
        if status == "INCOMPLETE":
            if phase == "FINDING" and not step.get("evidence_id"):
                errors.append(f"INCOMPLETE FINDING missing evidence_id at {i}")
            if phase in {"REMEDIATION", "VERIFICATION"} and step.get("evidence_id") != "":
                errors.append(f"INCOMPLETE {phase} must have empty evidence_id at {i}")
    return errors


def score_against_sample(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Compare predicted rows to dataset/sample_output.csv.

    Args:
        rows: Predicted case results (need not include all samples).

    Returns:
        Metrics dict: ``n``, ``status_correct``, ``steps_exact``, rates, and
        ``mismatches`` (first few case ids).
    """
    with (DATASET_DIR / "sample_output.csv").open(newline="", encoding="utf-8") as fh:
        expected_by_id = {
            row["case_id"]: {
                "case_id": row["case_id"],
                "deletion_status": row["deletion_status"],
                "steps_json": json.loads(row["steps_json"]),
            }
            for row in csv.DictReader(fh)
        }

    status_ok = 0
    steps_ok = 0
    mismatches: list[str] = []
    compared = 0
    for row in rows:
        case_id = row["case_id"]
        if case_id not in expected_by_id:
            continue
        compared += 1
        exp = expected_by_id[case_id]
        if row["deletion_status"] == exp["deletion_status"]:
            status_ok += 1
        if row["steps_json"] == exp["steps_json"]:
            steps_ok += 1
        else:
            mismatches.append(case_id)

    return {
        "n": compared,
        "status_correct": status_ok,
        "steps_exact": steps_ok,
        "status_accuracy": (status_ok / compared) if compared else 0.0,
        "step_exact_match": (steps_ok / compared) if compared else 0.0,
        "mismatches": mismatches[:10],
    }
