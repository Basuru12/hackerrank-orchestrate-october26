"""Resolve request emails to current user identity snapshots."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from functools import lru_cache

from loaders import DATASET_DIR


@dataclass(frozen=True)
class UserIdentity:
    user_id: str
    name: str
    email: str
    phone: str
    email_hash: str
    updated_at: str


@lru_cache(maxsize=1)
def _identity_by_email() -> dict[str, UserIdentity]:
    path = DATASET_DIR / "user_identities.csv"
    index: dict[str, UserIdentity] = {}
    with path.open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            identity = UserIdentity(
                user_id=row["user_id"],
                name=row["name"],
                email=row["email"],
                phone=row["phone"],
                email_hash=row["email_hash"],
                updated_at=row["updated_at"],
            )
            index[identity.email.strip().lower()] = identity
    return index


def resolve_identity(email: str) -> UserIdentity:
    """Map a request email to the current identity snapshot (exact, case-insensitive)."""
    key = email.strip().lower()
    try:
        return _identity_by_email()[key]
    except KeyError as exc:
        raise KeyError(f"no identity for email: {email}") from exc
