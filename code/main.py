"""Ghost Data Still Exists — tracer-bullet entry point."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Allow `python code/main.py` without installing a package.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from loaders import load_deletion_request


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

    print(f"case_id:          {request.case_id}")
    print(f"email:            {request.email}")
    print(f"requested_at:     {request.requested_at}")
    print(f"reported_status:  {request.reported_status}")
    print(f"reported_at:      {request.reported_at}")
    print(f"audit_at:         {request.audit_at}")
    print(f"request_text:     {request.request_text}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
