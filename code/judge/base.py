"""StateJudge plugin contract and registry."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from evidence.base import EvidenceRecord

ALLOWED_FINDING_OPS = frozenset(
    {
        "REPORT_REMAINING_RECORD",
        "REPORT_EXPOSED_PII",
        "REPORT_ACTIVE_DATA_FLOW",
        "REPORT_RESTORE_RISK",
    }
)


@dataclass(frozen=True)
class Judgment:
    """Stage 7 decision for one resource under a policy action.

    Attributes:
        compliant: True if the resource already satisfies policy.
        finding_op: FINDING operation when non-compliant; must be None when
            ``compliant`` is True. Allowed values are in ``ALLOWED_FINDING_OPS``.
        evidence_id: Proving ``file_id`` / activity id, or ``""`` if unknown.
        confidence: How sure the judge is (``high``, ``medium``, ``low``, ``stub``).
    """

    compliant: bool
    finding_op: str | None
    evidence_id: str
    confidence: str  # high | medium | low | stub

    def validate(self) -> None:
        """Reject inconsistent or illegal judgment combinations.

        Raises:
            ValueError: If ``finding_op`` is unknown, set while compliant, or
                missing while non-compliant.
        """
        if self.finding_op is not None and self.finding_op not in ALLOWED_FINDING_OPS:
            raise ValueError(f"invalid finding_op: {self.finding_op}")
        if self.compliant and self.finding_op is not None:
            raise ValueError("compliant judgment cannot include finding_op")
        if not self.compliant and not self.finding_op:
            raise ValueError("non-compliant judgment requires finding_op")


class StateJudge(Protocol):
    """Stage 7 plugin: decide compliant vs violation for one resource."""

    name: str

    def judge(
        self,
        resource_id: str,
        policy_action: str,
        snippets: list[EvidenceRecord],
        activity_ctx: dict,
    ) -> Judgment:
        """Decide whether ``resource_id`` satisfies ``policy_action``.

        Args:
            resource_id: Resource under review (e.g. ``account_001``).
            policy_action: Required treatment from deletion_rules
                (``DELETE``, ``REDACT``, ``ANONYMIZE``, ``RETAIN``, or flow/restore
                actions such as disable/block).
            snippets: Evidence records for this resource (already time-filtered).
            activity_ctx: Related activity facts (e.g. sync/restore flags). Keys are
                implementation-defined; may be empty.

        Returns:
            A ``Judgment`` describing compliance and optional finding.
        """


_REGISTRY: dict[str, type] = {}


def register_state_judge(name: str):
    """Decorator that registers a StateJudge implementation.

    Args:
        name: Plugin id used with ``get_state_judge`` / ``--state-judge``
            (e.g. ``"mock"``).

    Returns:
        A class decorator that stores the class in the registry and returns it.
    """

    def decorator(cls: type):
        _REGISTRY[name] = cls
        return cls

    return decorator


def get_state_judge(name: str = "mock") -> StateJudge:
    """Construct a registered StateJudge plugin by name.

    Args:
        name: Registered plugin id. Defaults to ``"mock"``.

    Returns:
        A new instance of the registered judge class.

    Raises:
        KeyError: If ``name`` is not registered (lists known names).
    """
    try:
        cls = _REGISTRY[name]
    except KeyError as exc:
        known = ", ".join(sorted(_REGISTRY)) or "(none)"
        raise KeyError(f"unknown state judge {name!r}; known: {known}") from exc
    return cls()


def available_state_judges() -> list[str]:
    """Return sorted registered Stage 7 plugin names."""
    return sorted(_REGISTRY)
