"""Parse LINK_RESOURCE_IDENTITY activity detail strings."""

from __future__ import annotations

import re

_LINK_RE = re.compile(
    r"(?:linked|confirmed)\s+(\S+)\s+\(([^)]+)\)\s+(?:to|belongs only to)\s+(\S+)\s+and\s+(user_\d+)",
    re.IGNORECASE,
)


def parse_link_details(details: str) -> tuple[str, str, str, str] | None:
    """Parse a LINK_RESOURCE_IDENTITY details string.

    Args:
        details: Activity ``details`` text.

    Returns:
        ``(resource_id, alias, email, user_id)`` or ``None`` if unmatched.
        Email is lowercased.
    """
    match = _LINK_RE.search(details or "")
    if not match:
        return None
    return (
        match.group(1).strip(),
        match.group(2).strip(),
        match.group(3).strip().lower(),
        match.group(4).strip(),
    )
