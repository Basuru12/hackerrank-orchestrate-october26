"""Ghost Data Still Exists — tracer-bullet entry point."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Allow `python code/main.py` without installing a package.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from evidence_sql import (
    account_profile_state,
    evidence_usable_at,
    find_account_profile_hits,
    load_evidence_file,
)
from identity import resolve_identity
from loaders import load_deletion_request
from output import complete_account_result, write_and_verify_sample

# Tracer: case_01 account resource cited by sample_output / evidence_54 audit.
TRACER_ACCOUNT_RESOURCE = {
    "case_01": "account_001",
}
TRACER_EVIDENCE_ID = {
    "case_01": "evidence_54",
}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Deletion-audit agent")
    parser.add_argument(
        "--case",
        default="case_01",
        help="Case id to audit (default: case_01)",
    )
    parser.add_argument(
        "--sample",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Read from sample_deletion_requests.csv (default: true)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    args = parse_args(argv)
    request = load_deletion_request(args.case, sample=args.sample)
    identity = resolve_identity(request.email)

    print(f"case_id:          {request.case_id}")
    print(f"email:            {request.email}")
    print(f"requested_at:     {request.requested_at}")
    print(f"reported_status:  {request.reported_status}")
    print(f"reported_at:      {request.reported_at}")
    print(f"audit_at:         {request.audit_at}")
    print(f"request_text:     {request.request_text}")
    print(f"user_id:          {identity.user_id}")
    print(f"name:             {identity.name}")
    print(f"phone:            {identity.phone}")
    print(f"email_hash:       {identity.email_hash}")
    print(f"updated_at:       {identity.updated_at}")

    evidence_id = TRACER_EVIDENCE_ID.get(request.case_id)
    resource_id = TRACER_ACCOUNT_RESOURCE.get(request.case_id)
    if evidence_id is None or resource_id is None:
        print(f"tracer evidence not configured for {request.case_id}")
        return 1

    evidence = load_evidence_file(evidence_id)
    usable = evidence_usable_at(evidence, request.audit_at)
    print(f"evidence_id:      {evidence.file_id}")
    print(f"evidence_path:    {evidence.file_path}")
    print(f"captured_at:      {evidence.captured_at}")
    print(f"usable_at_audit:  {usable}")

    if not usable:
        print("evidence captured after audit_at; refusing to use it")
        return 1

    hits = find_account_profile_hits(
        evidence.absolute_path,
        resource_id=resource_id,
        email=identity.email,
        user_id=identity.user_id,
    )
    state = account_profile_state(
        evidence.absolute_path,
        resource_id=resource_id,
        email=identity.email,
        user_id=identity.user_id,
    )
    print(f"resource_id:      {resource_id}")
    print(f"profile_state:    {state}")
    print(f"profile_hits:     {hits if hits else '[]'}")

    if state != "ABSENT":
        print("tracer expected an absent account profile")
        return 1

    result = complete_account_result(request.case_id, resource_id, evidence_id)
    write_and_verify_sample(result)
    print("output_csv:       output.csv")
    print("sample_match:     True")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
