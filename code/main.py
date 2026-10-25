"""Ghost Data Still Exists — pipeline entry with swappable Stage 6/7 plugins."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Allow `python code/main.py` without installing a package.
sys.path.insert(0, str(Path(__file__).resolve().parent))

# Register mock plugins via side-effect imports.
import evidence.mock_index  # noqa: F401
import judge.mock_judge  # noqa: F401

from evidence.base import get_evidence_index
from identity import resolve_identity
from judge.base import get_state_judge
from loaders import DATASET_DIR, DeletionRequest, load_deletion_request, load_deletion_requests


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


def audit_case(
    request: DeletionRequest,
    *,
    evidence_index,
    state_judge,
) -> dict[str, object]:
    """Run the skeleton audit for one request (identity → index → judge).

    Policy / step emit are not implemented yet; returns diagnostic fields only.

    Args:
        request: Loaded deletion request for the case.
        evidence_index: Built Stage 6 plugin (``build`` already called).
        state_judge: Stage 7 plugin instance.

    Returns:
        Dict with ``case_id``, ``user_id``, ``evidence_hits``, judge fields, and
        plugin names.

    Raises:
        KeyError: If ``request.email`` cannot be resolved to an identity.
    """
    identity = resolve_identity(request.email)
    identifiers = {
        identity.user_id,
        identity.email.strip().lower(),
        identity.phone,
        identity.email_hash,
        identity.name,
    }
    records = evidence_index.query(identifiers, request.audit_at)

    # Stub resource loop: judge once with empty policy until spine lands.
    judgment = state_judge.judge(
        resource_id="",
        policy_action="DELETE",
        snippets=records,
        activity_ctx={},
    )

    return {
        "case_id": request.case_id,
        "user_id": identity.user_id,
        "evidence_hits": len(records),
        "judge_compliant": judgment.compliant,
        "judge_confidence": judgment.confidence,
        "plugin_evidence": evidence_index.name,
        "plugin_judge": state_judge.name,
    }


def main(argv: list[str] | None = None) -> int:
    """CLI entry: select plugins, audit one case or a batch.

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
        for key, value in result.items():
            print(f"{key}: {value}")
        return 0

    sample = bool(args.sample)
    requests = load_deletion_requests(sample=sample)
    print(f"cases:            {len(requests)} ({'sample' if sample else 'full'})")

    ok = 0
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
        ok += 1
        print(
            f"{result['case_id']}: user={result['user_id']} "
            f"hits={result['evidence_hits']} compliant={result['judge_compliant']}"
        )

    print(f"summary: audited={ok} skipped_identity={skipped}")
    print("note: Stage 6/7 mocks are stubs; spine/policy/emit land in next increments")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
