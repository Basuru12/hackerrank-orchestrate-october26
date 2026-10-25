"""Link case subjects to resource_ids via system_activity.csv."""

from __future__ import annotations

from datetime import timedelta

from evidence.parsers import parse_ts
from identity import SubjectIdentifiers
from link_parse import parse_link_details
from loaders import DeletionRequest, load_system_activity


def resources_for_case(
    request: DeletionRequest, subject: SubjectIdentifiers
) -> set[str]:
    """Return resource_ids attributable to the subject for this case.

    Includes LINK_RESOURCE_IDENTITY matches on subject identifiers and
    deletion_worker resources in the request's reported time window.

    Args:
        request: Case request (uses requested_at / reported_at / audit_at).
        subject: Expanded subject identifiers.

    Returns:
        Set of resource_id strings.
    """
    id_set = {x.lower() for x in subject.as_match_set()}
    id_set.add(subject.user_id.lower())
    for email in subject.emails:
        id_set.add(email.lower())

    # Deletion-worker burst is tightly clustered around reported_at.
    reported_at = parse_ts(request.reported_at)
    window_start = reported_at - timedelta(hours=2)
    window_end = reported_at + timedelta(hours=2)
    audit_at = parse_ts(request.audit_at)

    resources: set[str] = set()
    for row in load_system_activity():
        event_time = parse_ts(row["event_time"])
        if event_time > audit_at:
            continue
        resource_id = row.get("resource_id") or ""
        if not resource_id:
            continue

        if row["event_type"] == "LINK_RESOURCE_IDENTITY":
            parsed = parse_link_details(row.get("details") or "")
            if not parsed:
                continue
            _rid, _alias, email, user_id = parsed
            if email in id_set or user_id.lower() in id_set:
                resources.add(resource_id)
            continue

        if row.get("source_system") == "deletion_worker" and (
            window_start <= event_time <= window_end
        ):
            resources.add(resource_id)

    return resources
