"""Mock StateJudge stub — heuristics land in a later increment."""

from __future__ import annotations

from evidence.base import EvidenceRecord
from judge.base import Judgment, register_state_judge


@register_state_judge("mock")
class MockStateJudge:
    """Placeholder Stage 7 plugin that always marks the resource compliant."""

    name = "mock"

    def judge(
        self,
        resource_id: str,
        policy_action: str,
        snippets: list[EvidenceRecord],
        activity_ctx: dict,
    ) -> Judgment:
        """Return a stub compliant judgment.

        Args:
            resource_id: Resource under review (ignored by stub).
            policy_action: Required policy action (ignored by stub).
            snippets: Evidence for the resource; first ``file_id`` is copied into
                ``Judgment.evidence_id`` when present.
            activity_ctx: Activity context (ignored by stub).

        Returns:
            ``Judgment(compliant=True, finding_op=None, ...)`` with
            ``confidence="stub"``.
        """
        _ = resource_id, policy_action, activity_ctx
        evidence_id = snippets[0].file_id if snippets else ""
        judgment = Judgment(
            compliant=True,
            finding_op=None,
            evidence_id=evidence_id,
            confidence="stub",
        )
        judgment.validate()
        return judgment
