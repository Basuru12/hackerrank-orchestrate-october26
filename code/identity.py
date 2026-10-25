"""Resolve request emails to current user identity snapshots."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from functools import lru_cache

from loaders import DATASET_DIR


@dataclass(frozen=True)
class UserIdentity:
    """Current identity snapshot from user_identities.csv.

    Attributes:
        user_id: Stable internal subject id (e.g. ``user_01``).
        name: Display name.
        email: Current email address.
        phone: Current phone number.
        email_hash: Current email hash (hex).
        updated_at: Snapshot update time (ISO-8601).
    """

    user_id: str
    name: str
    email: str
    phone: str
    email_hash: str
    updated_at: str


@lru_cache(maxsize=1)
def _identity_by_email() -> dict[str, UserIdentity]:
    """Build a lowercase-email → identity index from user_identities.csv.

    Returns:
        Mapping of normalized email to ``UserIdentity``.
    """
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
    """Map a request email to the current identity snapshot.

    Matching is exact after ``strip().lower()``. Historical emails from
    ``user_audit_log.csv`` are not resolved yet.

    Args:
        email: Request email (any casing / surrounding whitespace).

    Returns:
        Matching ``UserIdentity``.

    Raises:
        KeyError: If no current identity uses that email.
    """
    key = email.strip().lower()
    try:
        return _identity_by_email()[key]
    except KeyError as exc:
        raise KeyError(f"no identity for email: {email}") from exc
