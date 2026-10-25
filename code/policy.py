"""Map policy actions and judgments to step operations/states."""

from __future__ import annotations

from dataclasses import dataclass

from judge.base import Judgment

# Finding / remediation / verification tables aligned with problem_statement.md.
_FINDING_OPS = (
    "REPORT_REMAINING_RECORD",
    "REPORT_EXPOSED_PII",
    "REPORT_ACTIVE_DATA_FLOW",
    "REPORT_RESTORE_RISK",
)
_REMEDIATION_OPS = (
    "DISABLE_DATA_FLOW",
    "BLOCK_RESTORE",
    "DELETE_RECORD",
    "REDACT_RECORD",
    "ANONYMIZE_RECORD",
)
_VERIFICATION_OPS = (
    "VERIFY_RECORD_ABSENT",
    "VERIFY_RECORD_PRESENT",
    "VERIFY_RECORD_REDACTED",
    "VERIFY_RECORD_ANONYMIZED",
    "VERIFY_DATA_FLOW_DISABLED",
    "VERIFY_RESTORE_BLOCKED",
)

PHASE_ORDER = {"FINDING": 0, "REMEDIATION": 1, "VERIFICATION": 2}
OPERATION_ORDER = {
    **{op: i for i, op in enumerate(_FINDING_OPS)},
    **{op: i for i, op in enumerate(_REMEDIATION_OPS)},
    **{op: i for i, op in enumerate(_VERIFICATION_OPS)},
}


@dataclass(frozen=True)
class ResourceAssessment:
    """Policy view of one resource after Stage 7 judgment.

    Attributes:
        resource_id: Resource under review.
        system_id: Canonical system id for output steps.
        policy_action: Required treatment (DELETE/REDACT/...).
        judgment: Stage 7 decision for this resource.
    """

    resource_id: str
    system_id: str
    policy_action: str
    judgment: Judgment


def finding_for_action(policy_action: str) -> tuple[str, str]:
    """Return ``(operation, state)`` for an INCOMPLETE finding.

    Args:
        policy_action: Required policy action for the resource.

    Returns:
        Finding operation and state.
    """
    return {
        "DELETE": ("REPORT_REMAINING_RECORD", "PRESENT"),
        "REDACT": ("REPORT_EXPOSED_PII", "PRESENT"),
        "ANONYMIZE": ("REPORT_EXPOSED_PII", "PRESENT"),
        "DISABLE_DATA_FLOW": ("REPORT_ACTIVE_DATA_FLOW", "ACTIVE"),
        "BLOCK_RESTORE": ("REPORT_RESTORE_RISK", "ACTIVE"),
    }[policy_action]


def remediation_for_action(policy_action: str) -> tuple[str, str]:
    """Return ``(operation, state)`` for remediation.

    Args:
        policy_action: Required policy action for the resource.

    Returns:
        Remediation operation and target state.
    """
    return {
        "DELETE": ("DELETE_RECORD", "ABSENT"),
        "REDACT": ("REDACT_RECORD", "REDACTED"),
        "ANONYMIZE": ("ANONYMIZE_RECORD", "ANONYMIZED"),
        "DISABLE_DATA_FLOW": ("DISABLE_DATA_FLOW", "DISABLED"),
        "BLOCK_RESTORE": ("BLOCK_RESTORE", "BLOCKED"),
    }[policy_action]


def verification_for_action(policy_action: str) -> tuple[str, str]:
    """Return ``(operation, state)`` for verification of final policy state.

    Args:
        policy_action: Required policy action for the resource.

    Returns:
        Verification operation and expected state.
    """
    return {
        "DELETE": ("VERIFY_RECORD_ABSENT", "ABSENT"),
        "REDACT": ("VERIFY_RECORD_REDACTED", "REDACTED"),
        "ANONYMIZE": ("VERIFY_RECORD_ANONYMIZED", "ANONYMIZED"),
        "RETAIN": ("VERIFY_RECORD_PRESENT", "PRESENT"),
        "DISABLE_DATA_FLOW": ("VERIFY_DATA_FLOW_DISABLED", "DISABLED"),
        "BLOCK_RESTORE": ("VERIFY_RESTORE_BLOCKED", "BLOCKED"),
    }[policy_action]
