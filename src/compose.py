"""Templated SBAR composition under constraint.

The templated lane is the pre-approved path: no model, no added fact, and every
fact line carries the page it came from.  Assessment is only ever the problem
as written on the page -- never a diagnosis of this module's own.
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
_DOSE = re.compile(r"\b\d+(?:\.\d+)?\s*(?:mg|mcg|µg|kg|g|ml|l|units?|iu|%)\b", re.I)
_FRACTION = re.compile(r"\b\d+/\d+\b")
_DAY = re.compile(r"\bday\s+(\d+)(?:\s+of\s+(\d+))?\b", re.I)
_BED = re.compile(r"\b(?:bed|bay)\s*(\d+)\b", re.I)
_NUMBER = re.compile(r"\b\d+(?:\.\d+)?\b")
_QUOTED = re.compile(r"['\"“”]([^'\"“”]{2,60})['\"“”]")


def scan_tokens(text: str) -> set[str]:
    """Extract every numeric/identifier token a verifier would check."""
    tokens: set[str] = set()
    remaining = str(text or "")

    def take(pattern, normalise=None, group=0):
        nonlocal remaining
        for match in pattern.finditer(remaining):
            value = match.group(group)
            value = normalise(value) if normalise else value
            tokens.add(str(value).strip().lower())
        remaining = pattern.sub(" ", remaining)

    remaining = _PAGE_REF.sub(" ", remaining)
    take(_ISO)
    take(_MRN)
    take(_CLOCK)
    take(_HOURLY, lambda v: re.sub(r"\s*", "", v).lower())
    take(_INTERVAL, lambda v: v.lower())
    take(_HOURS, lambda v: re.sub(r"\s*", "", v).lower())
    take(_MINUTES, lambda v: re.sub(r"\s*", "", v).lower())
    take(_DOSE, lambda v: re.sub(r"\s*", "", v).lower())
    take(_FRACTION)
    take(_DAY, group=1)
    take(_DAY, group=2)
    take(_BED, group=1)
    take(_NUMBER)
    take(_QUOTED, group=1)
    return {token for token in tokens if token}


def _leaves(value):
    if isinstance(value, dict):
        for item in value.values():
            yield from _leaves(item)
    elif isinstance(value, (list, tuple, set)):
        for item in value:
            yield from _leaves(item)
    elif value is not None:
        yield str(value)


def allowed_tokens(*sources) -> set[str]:
    tokens: set[str] = set()
    for source in sources:
        for leaf in _leaves(source):
            tokens.add(leaf.strip().lower())
            tokens.update(scan_tokens(leaf))
    return tokens


def _page(patient: dict, fallback=None):
    pages = patient.get("pages") or []
    if pages:
        return pages[-1]
    return patient.get("page", fallback)


_NAME_REFUSED = "name not readable"


def _heading_name(patient: dict) -> str:
    """The name for the patient heading, or an explicit refusal marker.

    A refused name must never be presented as if it were read, so an absent
    name becomes ``NAME_REFUSED`` instead of the literal ``None``.
    """
    name = patient.get("name_as_written")
    if name is None or not str(name).strip():
        return _NAME_REFUSED
    return str(name)


def _patient_lines(patient: dict, shift: dict) -> list:
    bed = patient.get("bed")
    name = patient.get("name_as_written")
    page = _page(patient)
    problem = patient.get("problem")
    problem_page = patient.get("problem_page") or page
    lines = []
    bed_label = f"Bed {bed}" if bed is not None else "Bed not recorded"
    lines.append(f"## {bed_label} — {_heading_name(patient)} [p. {page}]")

    who = []
    if bed is not None:
        who.append(f"Bed {bed}")
    if name:
        who.append(str(name))
    situation = f"S: {', '.join(who) if who else 'Patient'}"
    if problem:
        situation += f"; {problem}"
    lines.append(f"{situation} [p. {problem_page}]")

    issues = patient.get("issues") or []
    issue_text = "; ".join(str(item) for item in issues) if issues else "none recorded"
    lines.append(f"B: Issues: {issue_text} [p. {page}]")

    meds = patient.get("meds") or []
    if meds:
        for med in meds:
            parts = [str(med.get("name") or "medication")]
            if med.get("dose"):
                parts.append(str(med["dose"]))
            if med.get("freq"):
                parts.append(str(med["freq"]))
            if med.get("day") is not None:
                day = f"day {med['day']}"
                if med.get("of") is not None:
                    day += f" of {med['of']}"
                parts.append(day)
            lines.append(f"B: Med: {' '.join(parts)} [p. {med.get('page', page)}]")
    else:
        lines.append(f"B: Meds: none documented [p. {page}]")

    if problem:
        lines.append(f"A: {problem} — as written on the page [p. {problem_page}]")
    else:
        lines.append(f"A: No problem documented on the page [p. {page}]")

    actions = patient.get("actions") or []
    if actions:
        for action in actions:
            text = action.get("text") or "action"
            if action.get("due"):
                lines.append(f"R: {text} — due {action['due']} [p. {action.get('page', page)}]")
            else:
                lines.append(
                    f"R: {text} — due time not documented [p. {action.get('page', page)}]"
                )
    else:
        lines.append(f"R: No outstanding actions documented [p. {page}]")
    return lines


def compose(patients: list, contradictions: list, shift: dict) -> tuple[str, set[str]]:
    """Return (handoff markdown, allowed fact-token set)."""
    shift = shift or {}
    date = shift.get("date") or "date not recorded"
    ward = shift.get("ward") or "ward"
    handover_to = shift.get("handover_to") or "next shift"

    lines = [f"# Handoff — {date} — {ward} to {handover_to}"]
    first_page = None
    for patient in patients:
        page = _page(patient)
        if first_page is None:
            first_page = page
        lines.append("")
        lines.extend(_patient_lines(patient, shift))

    first_page = first_page or 1
    lines.append("")
    lines.append(f"## Actions this shift [p. {first_page}]")
    action_count = 0
    for patient in patients:
        bed = patient.get("bed")
        name = patient.get("name_as_written")
        for action in patient.get("actions") or []:
            action_count += 1
            text = action.get("text") or "action"
            who = f"Bed {bed} {name}".strip() if name else f"Bed {bed}"
            if action.get("due"):
                lines.append(f"- {who}: {text} — due {action['due']} [p. {action.get('page', _page(patient))}]")
            else:
                lines.append(f"- {who}: {text} — due time not documented [p. {action.get('page', _page(patient))}]")
    if action_count == 0:
        lines.append(f"- No outstanding actions documented [p. {first_page}]")

    text = "\n".join(lines) + "\n"
    allowed = allowed_tokens(patients, contradictions, shift)
    return text, allowed


def _unreadable_line(page) -> str:
    if isinstance(page, dict):
        number = page.get("page")
        reason = page.get("reason") or page.get("refusal_reason") or "unreadable"
        return f"- page {number}: {reason}"
    return f"- page {page}: unreadable"


def compose_gaps(
    patients: list,
    contradictions: list,
    unreadable_pages: list,
    injections: list,
    gaps: list,
) -> str:
    """Gaps, every refusal, every contradiction and every injection quote."""
    lines = ["# Gaps and refusals", ""]

    lines.append("## Unreadable pages")
    if unreadable_pages:
        for page in unreadable_pages:
            lines.append(_unreadable_line(page))
    else:
        lines.append("- none")
    lines.append("")

    lines.append("## Refusals (content was not read; never filled in)")
    refusal_count = 0
    for patient in patients:
        label = f"BED {patient.get('bed')}" if patient.get("bed") is not None else "patient"
        if patient.get("name_as_written"):
            label += f" ({patient['name_as_written']})"
        for refusal in patient.get("refused_fields") or []:
            refusal_count += 1
            lines.append(f"- {label}: {refusal}")
    if refusal_count == 0:
        lines.append("- none")
    lines.append("")

    lines.append("## Contradictions (both pages shown)")
    if contradictions:
        for item in contradictions:
            pages = ", ".join(str(p) for p in item.get("pages") or [])
            values = " / ".join(str(v) for v in item.get("values") or [])
            lines.append(
                f"- {item.get('field')}: {values} (pages {pages}) — {item.get('note') or 'values disagree'}"
            )
    else:
        lines.append("- none")
    lines.append("")

    lines.append("## Missing mandatory fields")
    if gaps:
        for gap in gaps:
            lines.append(f"- {gap}")
    else:
        lines.append("- none")
    lines.append("")

    lines.append("## Unusual text (quoted verbatim, not acted on)")
    if injections:
        for item in injections:
            page = item.get("page")
            quote = item.get("quote")
            lines.append(f'- page {page}: "{quote}"')
    else:
        lines.append("- none")

    return "\n".join(lines) + "\n"
