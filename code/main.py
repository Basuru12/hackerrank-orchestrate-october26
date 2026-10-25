"""Ghost Data Still Exists — pipeline entry with swappable Stage 6/7 plugins."""

from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from pathlib import Path

# Allow `python code/main.py` without installing a package.
sys.path.insert(0, str(Path(__file__).resolve().parent))

# Register mock plugins via side-effect imports.
import evidence.mock_index  # noqa: F401
import judge.mock_judge  # noqa: F401

from activity import resources_for_case
from emit import score_against_sample, validate_result, write_output_csv
from evidence.base import EvidenceRecord, get_evidence_index
from identity import expand_identifiers
from judge.base import get_state_judge
from loaders import DATASET_DIR, DeletionRequest, load_deletion_request, load_deletion_requests
from policy import ResourceAssessment
from resource_map import default_policy_action, system_id_for_resource
from step_builder import build_case_result


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI flags for case/sample/full runs and plugin selection.

    Args:
        argv: Optional argument list (defaults to ``sys.argv[1:]``).

    Returns:
        Parsed ``argparse.Namespace`` with ``case``, ``sample``, ``full``,
        ``evidence_index``, and ``state_judge``.
    """
    parser = argparse.ArgumentParser(description="Deletion-audit agent")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--case",
        help="Audit a single case id",
    )
    mode.add_argument(
        "--sample",
        action="store_true",
        help="Audit all sample_deletion_requests.csv cases",
    )
    mode.add_argument(
        "--full",
        action="store_true",
        help="Audit all deletion_requests.csv cases",
    )
    parser.add_argument(
        "--evidence-index",
        default="mock",
        help="Stage 6 plugin name (default: mock)",
    )
    parser.add_argument(
        "--state-judge",
        default="mock",
        help="Stage 7 plugin name (default: mock)",
    )
    return parser.parse_args(argv)


def _assessments_from_records(
    records: list[EvidenceRecord],
    *,
    state_judge,
) -> list[ResourceAssessment]:
    """Group evidence by resource_id, judge each, and attach policy metadata."""
    by_resource: dict[str, list[EvidenceRecord]] = defaultdict(list)
    for record in records:
        if not record.resource_id:
            continue
        by_resource[record.resource_id].append(record)

    assessments: list[ResourceAssessment] = []
    for resource_id, snippets in sorted(by_resource.items()):
        try:
            system_id = system_id_for_resource(resource_id)
            policy_action = default_policy_action(resource_id)
        except KeyError:
            continue
        # Newest first, then stable-sort ABSENT proofs first for DELETE resources.
        snippets.sort(key=lambda s: s.captured_at, reverse=True)
        snippets.sort(
            key=lambda s: 0 if (s.state == "ABSENT" and policy_action == "DELETE") else 1
        )
        judgment = state_judge.judge(
            resource_id=resource_id,
            policy_action=policy_action,
            snippets=snippets,
            activity_ctx={},
        )
        judgment.validate()
        assessments.append(
            ResourceAssessment(
                resource_id=resource_id,
                system_id=system_id,
                policy_action=policy_action,
                judgment=judgment,
            )
        )
    return assessments


def audit_case(
    request: DeletionRequest,
    *,
    evidence_index,
    state_judge,
    authorizes_deletion: bool = True,
) -> dict[str, object]:
    """Audit one request through identity → evidence → judge → steps.

    Args:
        request: Loaded deletion request for the case.
        evidence_index: Built Stage 6 plugin (``build`` already called).
        state_judge: Stage 7 plugin instance.
        authorizes_deletion: False yields ``NOT_APPLICABLE`` (intent later).

    Returns:
        Dict with ``case_id``, ``deletion_status``, ``steps_json``, plus
        diagnostic ``user_id`` / ``evidence_hits``.

    Raises:
        KeyError: If ``request.email`` cannot be resolved to an identity.
    """
    subject = expand_identifiers(request.email, audit_at=request.audit_at)
    linked_resources = resources_for_case(request, subject)
    records = evidence_index.query(
        subject.as_match_set(),
        request.audit_at,
        resource_ids=linked_resources,
    )
    assessments = _assessments_from_records(records, state_judge=state_judge)
    result = build_case_result(
        request.case_id,
        assessments,
        authorizes_deletion=authorizes_deletion,
    )
    result["user_id"] = subject.user_id
    result["evidence_hits"] = len(records)
    return result


def main(argv: list[str] | None = None) -> int:
    """CLI entry: select plugins, audit one case or a batch, emit CSV.

    Args:
        argv: Optional CLI args (see ``parse_args``). Defaults to
            ``--case case_01`` when no mode flag is given.

    Returns:
        Process exit code (``0`` on success).
    """
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    args = parse_args(argv)
    if not args.case and not args.sample and not args.full:
        args.case = "case_01"

    evidence_index = get_evidence_index(args.evidence_index)
    state_judge = get_state_judge(args.state_judge)
    evidence_index.build(DATASET_DIR)

    print(f"evidence_index:   {evidence_index.name}")
    print(f"state_judge:      {state_judge.name}")

    if args.case:
        try:
            request = load_deletion_request(args.case, sample=True)
        except KeyError:
            request = load_deletion_request(args.case, sample=False)
        result = audit_case(
            request, evidence_index=evidence_index, state_judge=state_judge
        )
        errors = validate_result(result)
        print(f"case_id:          {result['case_id']}")
        print(f"user_id:          {result['user_id']}")
        print(f"evidence_hits:    {result['evidence_hits']}")
        print(f"deletion_status:  {result['deletion_status']}")
        print(f"steps:            {len(result['steps_json'])}")
        print(f"schema_errors:    {errors if errors else '[]'}")
        return 0

    sample = bool(args.sample)
    requests = load_deletion_requests(sample=sample)
    print(f"cases:            {len(requests)} ({'sample' if sample else 'full'})")

    rows: list[dict[str, object]] = []
    skipped = 0
    for request in requests:
        try:
            result = audit_case(
                request, evidence_index=evidence_index, state_judge=state_judge
            )
        except KeyError as exc:
            skipped += 1
            print(f"{request.case_id}: SKIP identity ({exc})")
            continue
        rows.append(result)
        print(
            f"{result['case_id']}: user={result['user_id']} "
            f"hits={result['evidence_hits']} status={result['deletion_status']} "
            f"steps={len(result['steps_json'])}"
        )

    if rows:
        path = write_output_csv(rows)
        print(f"wrote:            {path} ({len(rows)} rows)")
    if sample and rows:
        metrics = score_against_sample(rows)
        print(
            f"sample_score:     status={metrics['status_correct']}/{metrics['n']} "
            f"steps_exact={metrics['steps_exact']}/{metrics['n']}"
        )
    print(f"summary: audited={len(rows)} skipped_identity={skipped}")
    print("note: Stage 6 mock parses evidence; Stage 7 judge still stub (always compliant)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
