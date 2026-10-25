"""Resolve request emails to current + historical subject identifiers."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

from loaders import load_user_audit_log, load_user_identity_rows


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


@dataclass(frozen=True)
class SubjectIdentifiers:
    """Expanded exact identifiers for one subject at audit time.

    Attributes:
        user_id: Stable internal id.
        name: Current display name.
        emails: Current + historical emails (lowercase).
        phones: Current + historical phones.
        email_hashes: Current + historical email hashes.
    """

    user_id: str
    name: str
    emails: frozenset[str]
    phones: frozenset[str]
    email_hashes: frozenset[str]

    def as_match_set(self) -> set[str]:
        """Return exact identifiers for evidence matching (no display name).

        Name is omitted to avoid colliding with unrelated people who share a
        similar name string in evidence.
        """
        keys = {self.user_id, *self.emails, *self.phones, *self.email_hashes}
        return {k for k in keys if k}


@lru_cache(maxsize=1)
def _identities() -> tuple[dict[str, UserIdentity], dict[str, UserIdentity]]:
    """Index loaded identity rows by user_id and lowercase email.

    Returns:
        ``(by_user_id, by_email)`` maps built from ``load_user_identity_rows``.
    """
    by_user: dict[str, UserIdentity] = {}
    by_email: dict[str, UserIdentity] = {}
    for row in load_user_identity_rows():
        identity = UserIdentity(
            user_id=row["user_id"],
            name=row["name"],
            email=row["email"],
            phone=row["phone"],
            email_hash=row["email_hash"],
            updated_at=row["updated_at"],
        )
        by_user[identity.user_id] = identity
        by_email[identity.email.strip().lower()] = identity
    return by_user, by_email


@lru_cache(maxsize=1)
def _email_to_user_id() -> dict[str, str]:
    """Map lowercase emails (current + historical) to user_id."""
    by_user, by_email = _identities()
    mapping = {email: ident.user_id for email, ident in by_email.items()}
    for row in load_user_audit_log():
        if row["field_name"] != "email":
            continue
        user_id = row["user_id"]
        if user_id not in by_user:
            continue
        for value in (row["old_value"], row["new_value"]):
            if value:
                mapping[value.strip().lower()] = user_id
    return mapping


def resolve_identity(email: str) -> UserIdentity:
    """Map a request email to the current identity snapshot.

    Accepts current or historical emails via user_audit_log.

    Args:
        email: Request email (any casing / surrounding whitespace).

    Returns:
        Current ``UserIdentity`` for the resolved ``user_id``.

    Raises:
        KeyError: If the email cannot be linked to any user.
    """
    key = email.strip().lower()
    _, by_email = _identities()
    if key in by_email:
        return by_email[key]
    user_id = _email_to_user_id().get(key)
    if user_id is None:
        raise KeyError(f"no identity for email: {email}")
    return _identities()[0][user_id]


def expand_identifiers(email: str, *, audit_at: str | None = None) -> SubjectIdentifiers:
    """Resolve email and expand current + historical exact identifiers.

    Args:
        email: Request email (current or historical).
        audit_at: Optional ISO-8601 cutoff; audit events after this are ignored.
            When None, all audit history is included.

    Returns:
        ``SubjectIdentifiers`` for evidence matching.

    Raises:
        KeyError: If the email cannot be linked to any user.
    """
    identity = resolve_identity(email)
    emails = {identity.email.strip().lower()}
    phones = {identity.phone} if identity.phone else set()
    hashes = {identity.email_hash} if identity.email_hash else set()

    for row in load_user_audit_log():
        if row["user_id"] != identity.user_id:
            continue
        if audit_at is not None and row["event_time"] > audit_at:
            continue
        field = row["field_name"]
        values = [v for v in (row["old_value"], row["new_value"]) if v]
        if field == "email":
            emails.update(v.strip().lower() for v in values)
        elif field == "phone":
            phones.update(values)
        elif field == "email_hash":
            hashes.update(values)

    return SubjectIdentifiers(
        user_id=identity.user_id,
        name=identity.name,
        emails=frozenset(emails),
        phones=frozenset(phones),
        email_hashes=frozenset(hashes),
    )
