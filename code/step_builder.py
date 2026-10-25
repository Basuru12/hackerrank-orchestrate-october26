"""Build ordered FINDING / REMEDIATION / VERIFICATION steps for a case."""

from __future__ import annotations

from typing import Any

from policy import (
    OPERATION_ORDER,
    PHASE_ORDER,
    ResourceAssessment,
    finding_for_action,
    remediation_for_action,
    verification_for_action,
)


def _step(
    *,
    phase: str,
    system_id: str,
    resource_id: str,
    operation: str,
    state: str,
    evidence_id: str,
) -> dict[str, Any]:
    return {
        "phase": phase,
        "system_id": system_id,
        "resource_id": resource_id,
        "operation": operation,
        "state": state,
        "evidence_id": evidence_id,
    }


def build_case_result(
    case_id: str,
    assessments: list[ResourceAssessment],
    *,
    authorizes_deletion: bool = True,
) -> dict[str, Any]:
    """Build ``deletion_status`` and ordered ``steps_json`` for one case.

    Args:
        case_id: Case key for the output row.
        assessments: Per-resource policy+judgment results.
        authorizes_deletion: False → ``NOT_APPLICABLE`` with empty steps.

    Returns:
        Dict with ``case_id``, ``deletion_status``, and ``steps_json`` (list).
    """
    if not authorizes_deletion:
        return {"case_id": case_id, "deletion_status": "NOT_APPLICABLE", "steps_json": []}

    violations = [a for a in assessments if not a.judgment.compliant]
    # RETAIN resources are never "violations" via finding; they only verify present.
    actionable = [
        a
        for a in violations
        if a.policy_action in {
            "DELETE",
            "REDACT",
            "ANONYMIZE",
            "DISABLE_DATA_FLOW",
            "BLOCK_RESTORE",
        }
    ]

    steps: list[dict[str, Any]] = []
    if actionable:
        status = "INCOMPLETE"
        for a in actionable:
            op, state = finding_for_action(a.policy_action)
            steps.append(
                _step(
                    phase="FINDING",
                    system_id=a.system_id,
                    resource_id=a.resource_id,
                    operation=op,
                    state=state,
                    evidence_id=a.judgment.evidence_id,
                )
            )
        for a in actionable:
            op, state = remediation_for_action(a.policy_action)
            steps.append(
                _step(
                    phase="REMEDIATION",
                    system_id=a.system_id,
                    resource_id=a.resource_id,
                    operation=op,
                    state=state,
                    evidence_id="",
                )
            )
        # Verification covers all known assessments for the case.
        for a in assessments:
            op, state = verification_for_action(a.policy_action)
            steps.append(
                _step(
                    phase="VERIFICATION",
                    system_id=a.system_id,
                    resource_id=a.resource_id,
                    operation=op,
                    state=state,
                    evidence_id="",
                )
            )
    else:
        status = "COMPLETE"
        for a in assessments:
            op, state = verification_for_action(a.policy_action)
            steps.append(
                _step(
                    phase="VERIFICATION",
                    system_id=a.system_id,
                    resource_id=a.resource_id,
                    operation=op,
                    state=state,
                    evidence_id=a.judgment.evidence_id,
                )
            )

    steps.sort(
        key=lambda s: (
            PHASE_ORDER[s["phase"]],
            OPERATION_ORDER[s["operation"]],
            s["system_id"],
            s["resource_id"],
        )
    )
    for i, step in enumerate(steps, start=1):
        step["step_no"] = i

    return {"case_id": case_id, "deletion_status": status, "steps_json": steps}
