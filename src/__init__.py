"""Shift Buddy Handover — local, deterministic handover pipeline.

Modules (fixed public API, see work-orders/04-build-contracts.md §12):
    ingest    page enumeration, "<seq>" ordering, sha256, text/OCR lanes
    extract   deterministic regex/line field extraction, refusals, injections
"""

__all__ = ["ingest", "extract"]
