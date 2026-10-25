"""Map resource_id prefixes to canonical system_id values for output steps."""

from __future__ import annotations

# Prefix → system_id derived from sample_output + system_activity.
_PREFIX_TO_SYSTEM: tuple[tuple[str, str], ...] = (
    ("account_", "account_service"),
    ("search_", "search_service"),
    ("export_", "export_service"),
    ("cache_", "cache_service"),
    ("marketing_", "marketing_platform"),
    ("support_", "support_platform"),
    ("tombstone_", "identity_service"),
    ("email_delivery_", "email_delivery_service"),
    ("analytics_", "analytics_platform"),
    ("data_flow_", "integration_service"),
    ("backup_", "backup_service"),
    ("audit_record_", "security_service"),
    ("legal_hold_", "legal_service"),
)


def system_id_for_resource(resource_id: str) -> str:
    """Return the canonical system_id for a resource_id.

    Args:
        resource_id: Resource key (e.g. ``account_001``, ``data_flow_1121``).

    Returns:
        Matching ``system_id`` from the prefix table.

    Raises:
        KeyError: If no known prefix matches ``resource_id``.
    """
    for prefix, system_id in _PREFIX_TO_SYSTEM:
        if resource_id.startswith(prefix):
            return system_id
    raise KeyError(f"unknown resource_id prefix: {resource_id}")


def default_policy_action(resource_id: str) -> str:
    """Return the default deletion_rules action for a resource prefix.

    Args:
        resource_id: Resource key.

    Returns:
        One of ``DELETE``, ``REDACT``, ``ANONYMIZE``, ``RETAIN``,
        ``DISABLE_DATA_FLOW``, or ``BLOCK_RESTORE``.

    Notes:
        ``support_*`` defaults to ``REDACT`` (SUPPORT_MESSAGE). Callers may
        override to ``DELETE`` for SUPPORT_ATTACHMENT. ``analytics_*`` defaults
        to ``ANONYMIZE``.
    """
    system_id = system_id_for_resource(resource_id)
    return {
        "account_service": "DELETE",
        "search_service": "DELETE",
        "export_service": "DELETE",
        "cache_service": "DELETE",
        "marketing_platform": "DELETE",
        "support_platform": "REDACT",
        "identity_service": "REDACT",
        "email_delivery_service": "REDACT",
        "analytics_platform": "ANONYMIZE",
        "integration_service": "DISABLE_DATA_FLOW",
        "backup_service": "BLOCK_RESTORE",
        "security_service": "RETAIN",
        "legal_service": "RETAIN",
    }[system_id]
