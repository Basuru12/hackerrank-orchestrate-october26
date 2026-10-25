"""EvidenceIndex plugin contract and registry."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class EvidenceRecord:
    """One attributable evidence hit for a subject resource.

    Attributes:
        file_id: Manifest id from evidence_files.csv (e.g. ``evidence_54``).
        captured_at: ISO-8601 capture time of the source file.
        system_id: Canonical system for the resource (e.g. ``account_service``).
        resource_id: Resource key (e.g. ``account_001``, ``search_428``).
        data_category: Policy category when known (e.g. ``USER_PROFILE``), else ``""``.
        state: Observed state label (e.g. ``PRESENT``, ``ABSENT``, ``ACTIVE``, ``REDACTED``).
        identifiers: Exact subject identifiers found on this record.
        raw_snippet: Short supporting text for judges / debugging.
    """

    file_id: str
    captured_at: str
    system_id: str
    resource_id: str
    data_category: str
    state: str
    identifiers: tuple[str, ...] = ()
    raw_snippet: str = ""


class EvidenceIndex(Protocol):
    """Stage 6 plugin: build a global evidence index, then query per case."""

    name: str

    def build(self, dataset_dir: Path) -> None:
        """Load and parse participant evidence under ``dataset_dir`` once.

        Args:
            dataset_dir: Path to the ``dataset/`` directory (contains
                ``evidence_files.csv`` and ``evidence/``).
        """

    def query(self, identifiers: set[str], audit_at: str) -> list[EvidenceRecord]:
        """Return records attributable to ``identifiers`` at or before ``audit_at``.

        Args:
            identifiers: Exact subject keys to match (``user_id``, emails, phones,
                email hashes, name). Matching must be exact, not substring.
            audit_at: Case audit cutoff (ISO-8601). Only records with
                ``captured_at <= audit_at`` may be returned.

        Returns:
            Zero or more ``EvidenceRecord`` rows for this subject.
        """


_REGISTRY: dict[str, type] = {}


def register_evidence_index(name: str):
    """Decorator that registers an EvidenceIndex implementation.

    Args:
        name: Plugin id used with ``get_evidence_index`` / ``--evidence-index``
            (e.g. ``"mock"``).

    Returns:
        A class decorator that stores the class in the registry and returns it.
    """

    def decorator(cls: type):
        _REGISTRY[name] = cls
        return cls

    return decorator


def get_evidence_index(name: str = "mock") -> EvidenceIndex:
    """Construct a registered EvidenceIndex plugin by name.

    Args:
        name: Registered plugin id. Defaults to ``"mock"``.

    Returns:
        A new instance of the registered index class.

    Raises:
        KeyError: If ``name`` is not registered (lists known names).
    """
    try:
        cls = _REGISTRY[name]
    except KeyError as exc:
        known = ", ".join(sorted(_REGISTRY)) or "(none)"
        raise KeyError(f"unknown evidence index {name!r}; known: {known}") from exc
    return cls()


def available_evidence_indexes() -> list[str]:
    """Return sorted registered Stage 6 plugin names."""
    return sorted(_REGISTRY)
