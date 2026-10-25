"""Deterministic parsers that turn evidence files into EvidenceRecord rows."""

from __future__ import annotations

import json
import re
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

from evidence.base import EvidenceRecord
from resource_map import system_id_for_resource


def parse_ts(value: str) -> datetime:
    """Parse an ISO-8601 timestamp, including trailing ``Z`` as UTC.

    Args:
        value: Timestamp string (e.g. ``2026-08-20T16:42:00Z``).

    Returns:
        Timezone-aware ``datetime``.
    """
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


_RESOURCE_RE = re.compile(
    r"\b("
    r"account_|search_|export_|cache_|marketing_|support_|tombstone_|"
    r"email_delivery_|analytics_|data_flow_|backup_|audit_record_|legal_hold_"
    r")\w+",
    re.IGNORECASE,
)
_KV_RE = re.compile(r'(\w+)=("([^"]*)"|(\S+))')
_IDENT_KEYS = {
    "email",
    "owner_email",
    "requester_email",
    "customer_email",
    "user_id",
    "customer_reference",
    "subject_reference",
    "subject_selector",
    "phone",
    "requester_phone",
    "email_hash",
    "full_name",
    "display_name",
    "requester_name",
    "lookup_key",
    "match_key",
    "subject_key",
    "scan_key",
    "subject_ref",
    "owner_key",
    "correlation_key",
    "query",
}


def _norm_ident(value: str) -> str:
    value = value.strip()
    if "@" in value:
        return value.lower()
    return value


def _collect_idents(obj: Any, into: set[str]) -> None:
    if isinstance(obj, dict):
        for key, value in obj.items():
            if key in _IDENT_KEYS and isinstance(value, str) and value and value != "null":
                if value.lower() != "no direct identifier":
                    into.add(_norm_ident(value))
            else:
                _collect_idents(value, into)
    elif isinstance(obj, list):
        for item in obj:
            _collect_idents(item, into)


def _state_from_signals(obj: dict[str, Any], default: str = "PRESENT") -> str:
    if obj.get("status_code") == 404 or obj.get("profile") is None and "status_code" in obj:
        if obj.get("status_code") == 404:
            return "ABSENT"
    if obj.get("enabled") is True or obj.get("enabled") == 1:
        return "ACTIVE"
    if obj.get("enabled") is False or obj.get("enabled") == 0:
        return "DISABLED"
    if obj.get("restore_allowed") is True or obj.get("restore_allowed") == 1:
        return "ACTIVE"
    if obj.get("restore_allowed") is False or obj.get("restore_allowed") == 0:
        return "BLOCKED"
    if obj.get("download_available") is False:
        return "ABSENT"
    msg = obj.get("message_text") or obj.get("message_excerpt")
    if msg == "[REDACTED]":
        return "REDACTED"
    if (
        obj.get("email") is None
        and obj.get("phone") is None
        and obj.get("email_hash") is None
        and obj.get("user_id") is None
        and "email" in obj
    ):
        return "ANONYMIZED"
    if (
        obj.get("requester_email") is None
        and obj.get("requester_name") is None
        and obj.get("requester_phone") is None
        and "requester_email" in obj
    ):
        return "REDACTED"
    return default


def _record(
    *,
    file_id: str,
    captured_at: str,
    resource_id: str,
    state: str,
    identifiers: Iterable[str],
    data_category: str = "",
    snippet: str = "",
) -> EvidenceRecord | None:
    try:
        system_id = system_id_for_resource(resource_id)
    except KeyError:
        return None
    idents = tuple(sorted({_norm_ident(x) for x in identifiers if x}))
    return EvidenceRecord(
        file_id=file_id,
        captured_at=captured_at,
        system_id=system_id,
        resource_id=resource_id,
        data_category=data_category,
        state=state,
        identifiers=idents,
        raw_snippet=snippet[:300],
    )


def parse_json_file(path: Path, file_id: str, captured_at: str) -> list[EvidenceRecord]:
    """Parse JSON evidence into records (bundles, exports, ledgers)."""
    data = json.loads(path.read_text(encoding="utf-8"))
    out: list[EvidenceRecord] = []

    def emit(resource_id: str, state: str, idents: set[str], snap_at: str, obj: Any) -> None:
        rec = _record(
            file_id=file_id,
            captured_at=snap_at or captured_at,
            resource_id=resource_id,
            state=state,
            identifiers=idents,
            snippet=json.dumps(obj, ensure_ascii=False)[:300],
        )
        if rec:
            out.append(rec)

    def walk_records(records: list[Any], snap_at: str) -> None:
        for item in records:
            if not isinstance(item, dict):
                continue
            resource_id = item.get("resource_id")
            if not isinstance(resource_id, str):
                continue
            idents: set[str] = set()
            _collect_idents(item, idents)
            result = item.get("result")
            if result == "NOT_FOUND":
                state = "ABSENT"
            elif result == "ANONYMIZED":
                state = "ANONYMIZED"
            elif result == "REDACTED":
                state = "REDACTED"
            elif result in {"ACTIVE", "DISABLED", "BLOCKED", "FOUND", "IDENTIFIABLE"}:
                state = "ACTIVE" if result == "ACTIVE" else (
                    "DISABLED" if result == "DISABLED" else (
                        "BLOCKED" if result == "BLOCKED" else "PRESENT"
                    )
                )
            else:
                state = _state_from_signals(item)
            emit(resource_id, state, idents, snap_at, item)

    if isinstance(data, dict) and "snapshots" in data:
        for snap in data.get("snapshots") or []:
            if not isinstance(snap, dict):
                continue
            snap_at = snap.get("captured_at") or captured_at
            walk_records(snap.get("records") or [], snap_at)
    elif isinstance(data, dict) and "service_exports" in data:
        exports = data.get("service_exports") or {}
        for _system, payload in exports.items():
            if not isinstance(payload, dict):
                continue
            for _key, rows in payload.items():
                if not isinstance(rows, list):
                    continue
                for item in rows:
                    if not isinstance(item, dict):
                        continue
                    resource_id = item.get("resource_id")
                    if not isinstance(resource_id, str):
                        continue
                    idents: set[str] = set()
                    _collect_idents(item, idents)
                    if item.get("status_code") == 404:
                        state = "ABSENT"
                    elif isinstance(item.get("hits"), dict):
                        state = "PRESENT" if item["hits"].get("total", 0) else "ABSENT"
                    else:
                        state = _state_from_signals(item)
                    snap_at = item.get("observed_at") or captured_at
                    emit(resource_id, state, idents, snap_at, item)
    elif isinstance(data, dict) and "records" in data:
        walk_records(data.get("records") or [], data.get("captured_at") or captured_at)
    else:
        # Generic walk for resource_id dicts.
        def walk(obj: Any) -> None:
            if isinstance(obj, dict):
                rid = obj.get("resource_id")
                if isinstance(rid, str) and _RESOURCE_RE.match(rid):
                    idents: set[str] = set()
                    _collect_idents(obj, idents)
                    emit(rid, _state_from_signals(obj), idents, captured_at, obj)
                for value in obj.values():
                    walk(value)
            elif isinstance(obj, list):
                for item in obj:
                    walk(item)

        walk(data)
    return out


def parse_txt_handover(path: Path, file_id: str, captured_at: str) -> list[EvidenceRecord]:
    """Parse pipe-delimited handover lines."""
    out: list[EvidenceRecord] = []
    state_map = {
        "NOT_FOUND": "ABSENT",
        "FOUND": "PRESENT",
        "IDENTIFIABLE": "PRESENT",
        "ANONYMIZED": "ANONYMIZED",
        "REDACTED": "REDACTED",
        "ACTIVE": "ACTIVE",
        "DISABLED": "DISABLED",
        "BLOCKED": "BLOCKED",
    }
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip().lstrip("- ").strip()
        if "|" not in line:
            continue
        parts = [p.strip() for p in line.split("|")]
        if len(parts) < 6:
            continue
        _ts, _system, resource_id, category, raw_state, ident = parts[:6]
        if not _RESOURCE_RE.match(resource_id):
            continue
        idents = [] if ident.lower() == "no direct identifier" else [_norm_ident(ident)]
        rec = _record(
            file_id=file_id,
            captured_at=captured_at,
            resource_id=resource_id,
            state=state_map.get(raw_state, "PRESENT"),
            identifiers=idents,
            data_category=category,
            snippet=line,
        )
        if rec:
            out.append(rec)
    return out


def parse_log_file(path: Path, file_id: str, captured_at: str) -> list[EvidenceRecord]:
    """Parse observability / readback logs into resource observations."""
    lines = path.read_text(encoding="utf-8").splitlines()
    by_trace: dict[str, dict[str, str]] = {}
    out: list[EvidenceRecord] = []

    for line in lines:
        fields = {m.group(1): (m.group(3) if m.group(3) is not None else m.group(4)) for m in _KV_RE.finditer(line)}
        trace = fields.get("trace_id")
        if trace:
            by_trace.setdefault(trace, {}).update({k: v for k, v in fields.items() if v})

        resource_id = fields.get("resource_id")
        if not resource_id or not _RESOURCE_RE.match(resource_id):
            continue

        idents: set[str] = set()
        for key in _IDENT_KEYS:
            if key in fields and fields[key] not in {None, "", "null"}:
                idents.add(_norm_ident(fields[key]))
        if trace and trace in by_trace:
            for key in _IDENT_KEYS:
                if key in by_trace[trace]:
                    idents.add(_norm_ident(by_trace[trace][key]))

        state = "PRESENT"
        if fields.get("http_status") == "404" or fields.get("rows") == "0":
            state = "ABSENT"
        elif fields.get("result") in {"miss", "NOT_FOUND"}:
            state = "ABSENT"
        elif fields.get("result") in {"hit", "FOUND", "IDENTIFIABLE"}:
            state = "PRESENT"
        elif fields.get("result") == "ANONYMIZED":
            state = "ANONYMIZED"
        elif fields.get("result") == "REDACTED":
            state = "REDACTED"
        elif fields.get("enabled") == "true":
            state = "ACTIVE"
        elif fields.get("enabled") == "false":
            state = "DISABLED"
        elif fields.get("eligible") == "true" or fields.get("restore_allowed") == "true":
            state = "ACTIVE"
        elif fields.get("eligible") == "false" or fields.get("restore_allowed") == "false":
            state = "BLOCKED"
        elif fields.get("available") == "true":
            state = "PRESENT"
        elif fields.get("available") == "false":
            state = "ABSENT"

        ts = line.split(" ", 1)[0] if line else captured_at
        rec = _record(
            file_id=file_id,
            captured_at=ts if "T" in ts else captured_at,
            resource_id=resource_id,
            state=state,
            identifiers=idents,
            snippet=line[:300],
        )
        if rec:
            out.append(rec)
    return out


def parse_sql_file(path: Path, file_id: str, captured_at: str) -> list[EvidenceRecord]:
    """Parse SQLite-compatible SQL dumps into PRESENT profile/resource rows."""
    sql_text = path.read_text(encoding="utf-8")
    conn = sqlite3.connect(":memory:")
    out: list[EvidenceRecord] = []
    try:
        conn.executescript(sql_text)
        tables = [
            r[0]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        ]
        for table in tables:
            cols = [r[1] for r in conn.execute(f'PRAGMA table_info("{table}")').fetchall()]
            colset = {c.lower() for c in cols}
            if "resource_id" not in colset:
                continue
            rows = conn.execute(f'SELECT * FROM "{table}"').fetchall()
            col_index = {c.lower(): i for i, c in enumerate(cols)}
            for row in rows:
                resource_id = row[col_index["resource_id"]]
                if not isinstance(resource_id, str) or not _RESOURCE_RE.match(resource_id):
                    continue
                idents: set[str] = set()
                payload = None
                if "record_json" in col_index:
                    raw = row[col_index["record_json"]]
                    try:
                        payload = json.loads(raw) if isinstance(raw, str) else None
                    except json.JSONDecodeError:
                        payload = None
                    if isinstance(payload, dict):
                        _collect_idents(payload, idents)
                for key in ("email", "user_id", "full_name", "phone", "email_hash"):
                    if key in col_index:
                        value = row[col_index[key]]
                        if isinstance(value, str) and value:
                            idents.add(_norm_ident(value))
                state = "PRESENT"
                if payload and isinstance(payload, dict):
                    state = _state_from_signals(payload)
                if "enabled" in col_index:
                    state = "ACTIVE" if row[col_index["enabled"]] in (1, "1", True) else "DISABLED"
                if "restore_allowed" in col_index:
                    state = (
                        "ACTIVE"
                        if row[col_index["restore_allowed"]] in (1, "1", True)
                        else "BLOCKED"
                    )
                rec = _record(
                    file_id=file_id,
                    captured_at=captured_at,
                    resource_id=resource_id,
                    state=state,
                    identifiers=idents,
                    snippet=str(payload or row)[:300],
                )
                if rec:
                    out.append(rec)
    finally:
        conn.close()
    return out


def sql_absent_records(
    path: Path,
    file_id: str,
    captured_at: str,
    resource_ids: set[str],
) -> list[EvidenceRecord]:
    """Emit ABSENT records for account/search resources missing from a SQL snapshot."""
    if not resource_ids:
        return []
    sql_text = path.read_text(encoding="utf-8")
    conn = sqlite3.connect(":memory:")
    present: set[str] = set()
    try:
        conn.executescript(sql_text)
        tables = [
            r[0]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        ]
        for table in tables:
            cols = [r[1].lower() for r in conn.execute(f'PRAGMA table_info("{table}")').fetchall()]
            if "resource_id" not in cols:
                continue
            for (rid,) in conn.execute(f'SELECT resource_id FROM "{table}"'):
                if isinstance(rid, str):
                    present.add(rid)
    finally:
        conn.close()

    out: list[EvidenceRecord] = []
    for resource_id in resource_ids:
        if resource_id in present:
            continue
        if not (
            resource_id.startswith("account_")
            or resource_id.startswith("search_")
            or resource_id.startswith("export_")
        ):
            continue
        rec = _record(
            file_id=file_id,
            captured_at=captured_at,
            resource_id=resource_id,
            state="ABSENT",
            identifiers=[],
            snippet=f"missing from {path.name}",
        )
        if rec:
            out.append(rec)
    return out
