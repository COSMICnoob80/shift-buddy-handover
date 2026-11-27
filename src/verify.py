"""The counterweight: no number or identifier in prose outside the facts.

This module re-reads the composed text and asserts every numeric/identifier
token appears in the structured summary, in a page reference, or in the run
date.  A token it cannot place is a violation and the handoff must not ship.
"""

from __future__ import annotations

import re

_PAGE_REF = re.compile(r"\[p\.\s*[\d,\s]+\]|\bpages?\s+\d+\b", re.I)
_ISO = re.compile(
    r"\b\d{4}-\d{2}-\d{2}(?:[T ]\d{2}:\d{2}(?::\d{2})?(?:\.\d+)?(?:[+-]\d{2}:?\d{2}|Z)?)?"
)
_MRN = re.compile(r"\b\d{2,4}-\d{2,6}\b")
_CLOCK = re.compile(r"\b\d{1,2}:\d{2}\b")
_HOURLY = re.compile(r"\b(\d+)\s*-\s*hourly\b", re.I)
_INTERVAL = re.compile(r"\bPT(\d+)H\b", re.I)
_HOURS = re.compile(r"\b(\d+(?:\.\d+)?)\s*(?:h|hr|hrs|hour|hours)\b", re.I)
_MINUTES = re.compile(r"\b(\d+)\s*(?:min|mins|minute|minutes)\b", re.I)
_DOSE = re.compile(r"\b\d+(?:\.\d+)?\s*(?:mg|mcg|µg|kg|g|ml|l|units?|iu|%)", re.I)
_FRACTION = re.compile(r"\b\d+/\d+\b")
_DAY = re.compile(r"\bday\s+(\d+)(?:\s+of\s+(\d+))?\b", re.I)
_BED = re.compile(r"\b(?:bed|bay)\s*(\d+)\b", re.I)
_NUMBER = re.compile(r"\b\d+(?:\.\d+)?\b")
_QUOTED = re.compile(r"['\"“”]([^'\"“”]{2,60})['\"“”]")

_TOKEN_KINDS = (
    ("date/time", _ISO),
    ("MRN", _MRN),
    ("clock time", _CLOCK),
    ("interval", _HOURLY),
    ("interval", _INTERVAL),
    ("duration", _HOURS),
    ("duration", _MINUTES),
    ("dose", _DOSE),
    ("fraction", _FRACTION),
    ("day count", _DAY),
    ("bed", _BED),
    ("number", _NUMBER),
    ("quoted name", _QUOTED),
)


def _normalise(value: str) -> str:
    return str(value).strip().lower()


def _tokens_with_kind(text: str) -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []
    remaining = _PAGE_REF.sub(" ", str(text or ""))

    def take(pattern, kind, normalise=None, group=0):
        nonlocal remaining
        for match in pattern.finditer(remaining):
            value = match.group(group)
            if value is None:
                continue
            value = normalise(value) if normalise else value
            token = _normalise(value)
            if token:
                found.append((token, kind))
        remaining = pattern.sub(" ", remaining)

    take(_ISO, "date/time")
    take(_MRN, "MRN")
    take(_CLOCK, "clock time")
    take(_HOURLY, "interval", lambda v: re.sub(r"\s*", "", v))
    take(_INTERVAL, "interval")
    take(_HOURS, "duration", lambda v: re.sub(r"\s*", "", v))
    take(_MINUTES, "duration", lambda v: re.sub(r"\s*", "", v))
    take(_DOSE, "dose", lambda v: re.sub(r"\s*", "", v))
    take(_FRACTION, "fraction")
    for group in (1, 2):
        take(_DAY, "day count", group=group)
    take(_BED, "bed", group=1)
    take(_NUMBER, "number")
    take(_QUOTED, "quoted name", group=1)
    return found


def _leaves(value):
    if isinstance(value, dict):
        for item in value.values():
            yield from _leaves(item)
    elif isinstance(value, (list, tuple, set)):
        for item in value:
            yield from _leaves(item)
    elif value is not None:
        yield str(value)


def _allowed(summary: dict) -> set[str]:
    allowed: set[str] = set()
    for leaf in _leaves(summary or {}):
        allowed.add(_normalise(leaf))
        for token, _ in _tokens_with_kind(leaf):
            allowed.add(token)
    return allowed


def verify(handoff_text: str, summary: dict) -> tuple[bool, list[str]]:
    """Return (ok, violations).  ok is True only when every token is a fact."""
    allowed = _allowed(summary)
    violations: list[str] = []
    seen: set[str] = set()
    for token, kind in _tokens_with_kind(handoff_text or ""):
        if token in allowed or token in seen:
            continue
        seen.add(token)
        violations.append(f"{kind} '{token}' is not present in the facts")
    return (not violations), violations
