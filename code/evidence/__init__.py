"""Evidence index plugins.

Public exports:
    EvidenceIndex: Stage 6 plugin protocol.
    EvidenceRecord: One attributable evidence hit.
    get_evidence_index: Construct a registered plugin by name.
"""

from evidence.base import EvidenceIndex, EvidenceRecord, get_evidence_index

__all__ = ["EvidenceIndex", "EvidenceRecord", "get_evidence_index"]
