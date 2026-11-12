"""Content-addressed, append-only evidence catalog for research reproduction."""

from .store import EvidenceStore, EvidenceError

__all__ = ["EvidenceStore", "EvidenceError"]
