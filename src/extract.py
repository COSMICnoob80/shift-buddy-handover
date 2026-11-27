"""Deterministic field extraction — regex and line parsing only, no model.

Contract: work-orders/04-build-contracts.md §3.

Two rules govern everything here:

    a field is filled only from text that was read on the page, and
    anything that says something was not read becomes a refusal, never a value.

Injected instructions are content, never orders: they are recorded verbatim as
injections, stripped from patient facts, and never create a patient.
"""

from __future__ import annotations

import re

_BED = re.compile(r"\bBED\s*(\d+)", re.I)
_MRN = re.compile(r"\bMRN\s*([0-9][0-9\-]*)", re.I)
_QUOTED = re.compile(
    r"(?<![A-Za-z0-9])['\"\u2018\u2019\u201c\u201d]"
    r"([^'\"\u2018\u2019\u201c\u201d\n]{1,80})"
    r"['\"\u2018\u2019\u201c\u201d]"
)
_DASH = re.compile(r"\s*[\u2014\u2013]\s*")
_NAME_ALTERED = re.compile(r"\s*\(name altered\)", re.I)
_RAW_NAME_ALTERED = re.compile(r"\(name altered\)", re.I)

_REFUSAL_BRACKET = re.compile(r"\[([^\]\n]*?)\b(?:illegible|unreadable)\b([^\]\n]*?)\]", re.I)
_NAME_ILLEGIBLE = re.compile(r"\bname\s+(?:is\s+)?illegible\b[^.\n]*", re.I)
_TIME_MISSING = re.compile(r"\[\s*(?:no\s+)?time\s+(?:not\s+)?written\s*\]", re.I)
_DAY_UNSURE = re.compile(r"\bday\s+(\d+)\s*\?", re.I)

_IDENTITY_CLAUSE = re.compile(
    r"^(?:bed|mrn|that'?s|name\s+altered|name\s+illegible)\b", re.I
)

_INJECTION_PATTERNS = [
    re.compile(r"ignore\s+(?:all\s+)?previous\s+instructions", re.I),
    re.compile(r"disregard\s+all\s+gaps", re.I),
    re.compile(r"system\s+override\s*:", re.I),
    re.compile(r"\bsystem\s*:", re.I),
    re.compile(r"skip\s+the\s+gap\s+list", re.I),
    re.compile(r"mark\s+all\s+patients\s+stable", re.I),
    re.compile(r"forget\s+pages?", re.I),
    re.compile(r"produce\s+a\s+clean\s+handoff\s+from\s+this\s+page\s+only", re.I),
    re.compile(r"note\s+from\s+(?:the\s+)?nursing\s+supervisor", re.I),
    re.compile(r"additional\s+instructions\s*:", re.I),
    re.compile(
        r"\bACTION(?:\s+REQUIRED)?\s*:[^\n]*?\b(?:send|e-?mail|transmit|forward)\b",
        re.I,
    ),
]

_ALLERGY = re.compile(r"\ballergy\s*:\s*(.+?)(?:\.|$)", re.I)
_COVERING = re.compile(r"\bcovering(?:\s+clinician)?\s*:\s*(.+)", re.I)
_ACTION = re.compile(r"\bACTION(?:\s+REQUIRED)?\s*:", re.I)

_CLOCK = re.compile(r"\b\d{1,2}:\d{2}\b")
_INTERVAL = re.compile(r"\b\d+\s*-\s*hourly\b", re.I)
_HOURS = re.compile(r"\b\d+(?:\.\d+)?\s*(?:hrs|hr|hours|hour|h)\b", re.I)
_MINUTES = re.compile(r"\b\d+\s*(?:mins|min|minutes|minute)\b", re.I)
_BARE_HOURLY = re.compile(r"\bhourly\b", re.I)

_DOSE = re.compile(r"\b\d+(?:\.\d+)?\s*(?:mg|mcg|\u00b5g|units?|iu|g)\b", re.I)
_FREQ = re.compile(r"\b(?:OD|BD|TDS|QDS|PRN|mane|nocte|hourly)\b", re.I)
_DAY = re.compile(r"\bday\s+(\d+)(?:\s+of\s+(\d+))?", re.I)
_PENDING = re.compile(r"\bpending\b|\bawaiting\b", re.I)

_DRUGS = [
    "ceftriaxone", "cefazolin", "cefuroxime", "ceftazidime", "meropenem",
    "ertapenem", "piperacillin", "tazobactam", "amoxicillin", "clavulanate",
    "flucloxacillin", "oxacillin", "vancomycin", "teicoplanin", "gentamicin",
    "nitrofurantoin", "trimethoprim", "clarithromycin", "azithromycin",
    "doxycycline", "metronidazole", "ciprofloxacin", "levofloxacin",
    "bisoprolol", "atenolol", "metoprolol", "carvedilol", "ramipril",
    "lisinopril", "amlodipine", "diltiazem", "verapamil", "furosemide",
    "frusemide", "spironolactone", "apixaban", "rivaroxaban", "warfarin",
    "enoxaparin", "heparin", "aspirin", "clopidogrel", "atorvastatin",
    "simvastatin", "insulin", "gliclazide", "metformin", "prednisolone",
    "hydrocortisone", "dexamethasone", "paracetamol", "acetaminophen",
    "ibuprofen", "diclofenac", "morphine", "oxycodone", "fentanyl", "tramadol",
    "codeine", "ondansetron", "metoclopramide", "omeprazole", "pantoprazole",
    "lansoprazole", "levothyroxine", "carbimazole", "salbutamol",
    "ipratropium", "lactulose", "senna", "movicol", "ppi",
]
_DRUG_RE = re.compile(r"\b(" + "|".join(_DRUGS) + r")\b", re.I)
_NAME_MENTION = re.compile(
    r"\b(?:on|started|start|continued|continuing|continue|rx|wean\w*|taking|given|running)\b",
    re.I,
)
_QNAME = re.compile(r"\b[A-Za-z][A-Za-z?]{3,}\?[A-Za-z?]*\b")

_REFUSAL_PHRASE = re.compile(r"illegible|unreadable", re.I)


def _sentences(line: str) -> list[str]:
    return [part for part in re.split(r"(?<=[.!?])\s+", line) if part.strip()]


def _dedupe(values: list) -> list:
    out: list = []
    for value in values:
        if value not in out:
            out.append(value)
    return out


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _injection_hit(sentence: str) -> bool:
    return any(pattern.search(sentence) for pattern in _INJECTION_PATTERNS)


def _split_injections(line: str) -> tuple[str, bool]:
    """Return (line minus injected sentences, whether anything matched)."""
    pieces = _sentences(line)
    if not pieces:
        return line, False
    kept = [piece for piece in pieces if not _injection_hit(piece)]
    return " ".join(kept).strip(), len(kept) != len(pieces)


def _refusal_kind(token: str) -> str:
    lowered = token.lower()
    if lowered.startswith("[dose"):
        return "dose not read"
    if "scrawl" in lowered:
        return "end-of-line text illegible"
    if "unreadable" in lowered:
        return "text unreadable"
    return "text illegible"


def _scan_refusals(patient: dict, line: str) -> None:
    for match in _REFUSAL_BRACKET.finditer(line):
        token = match.group(0)
        entry = f"{_refusal_kind(token)}: '{token}'"
        if entry not in patient["refused"]:
            patient["refused"].append(entry)
    phrase = _NAME_ILLEGIBLE.search(line)
    if phrase and not patient["name_as_written"]:
        entry = f"patient name illegible: '{_clean(phrase.group(0))}'"
        if entry not in patient["refused"]:
            patient["refused"].append(entry)


def _scan_ambiguities(patient: dict, line: str) -> None:
    for match in _TIME_MISSING.finditer(line):
        entry = f"action time not written: '{match.group(0)}'"
        if entry not in patient["ambiguities"]:
            patient["ambiguities"].append(entry)
    for match in _DAY_UNSURE.finditer(line):
        entry = f"day count unconfirmed as written: 'day {match.group(1)}?'"
        if entry not in patient["ambiguities"]:
            patient["ambiguities"].append(entry)


def _find_name(line: str, start: int) -> tuple[str | None, int]:
    """First quoted name at/after ``start``.  Returns (name, end offset).

    A closing quote lost to OCR is tolerated only when the fragment ends at an
    em dash or the end of the line and looks like a name; otherwise nothing is
    claimed rather than guessed at.
    """
    quote = _QUOTED.search(line, start)
    if quote:
        name = _NAME_ALTERED.sub("", _clean(quote.group(1))).strip()
        return (name or None), quote.end()

    opening = re.search(r"['\"\u2018\u201c]", line[start:])
    if not opening:
        return None, start
    offset = start + opening.end()
    tail = line[offset:]
    boundary = re.search(r"\s*[\u2014\u2013]|$", tail)
    if not boundary:
        return None, start
    fragment = _NAME_ALTERED.sub("", _clean(tail[: boundary.start()])).strip()
    if not fragment or len(fragment) > 80:
        return None, start
    if not re.match(r"^[A-Z][A-Za-z.'\- ]*$", fragment):
        return None, start
    return fragment, offset + boundary.start()


def _problem_clause(segment: str) -> str | None:
    segment = _RAW_NAME_ALTERED.sub("", segment)
    segment = _DASH.sub(" ", segment)
    clauses = [_clean(part) for part in re.split(r",|\.\s|\.$", segment)]
    clauses = [
        part
        for part in clauses
        if part
        and not _REFUSAL_PHRASE.search(part)
        and not _IDENTITY_CLAUSE.search(part)
    ]
    if not clauses:
        return None
    return clauses[0]


def _dash_problem(line: str, anchor: int) -> str | None:
    rest = line[anchor:]
    if not rest.strip():
        return None
    for segment in _DASH.split(rest):
        candidate = _problem_clause(segment)
        if candidate:
            return candidate
    return None


def _body_problem(lines: list[str]) -> str | None:
    for line in lines:
        stripped = line.strip()
        if not stripped or _ACTION.search(stripped) or stripped.startswith("["):
            continue
        sentences = _sentences(stripped)
        sentence = sentences[0] if sentences else stripped
        sentence = _RAW_NAME_ALTERED.sub("", sentence)
        clauses = [
            _clean(part)
            for part in re.split(r",|\.\s|\.$", sentence)
            if _clean(part)
        ]
        if not clauses:
            continue
        if len(clauses) > 1 and re.match(r"^admitted\b", clauses[0], re.I):
            return clauses[1]
        return clauses[0]
    return None


def _time_token(text: str) -> str | None:
    for pattern in (_CLOCK, _INTERVAL, _HOURS, _MINUTES):
        match = pattern.search(text)
        if match:
            return _clean(match.group(0))
    if _BARE_HOURLY.search(text):
        return "hourly"
    return None


def _meds(line: str, page: int, patient: dict) -> list[dict]:
    found: list[tuple[int, str]] = [
        (match.start(), match.group(0)) for match in _DRUG_RE.finditer(line)
    ]
    if _FREQ.search(line) or _DOSE.search(line) or _REFUSAL_BRACKET.search(line):
        found.extend((match.start(), match.group(0)) for match in _QNAME.finditer(line))
    if not found:
        return []

    meds: list[dict] = []
    seen: set = set()
    for position, name in sorted(found):
        key = (position, name.lower())
        if key in seen:
            continue
        seen.add(key)

        rest = line[position + len(name):]
        sentences = _sentences(rest)
        sentence = sentences[0] if sentences else rest
        dose_match = _DOSE.search(sentence)
        freq_match = _FREQ.search(sentence)
        day_match = _DAY.search(sentence)
        dose = _clean(dose_match.group(0)) if dose_match else None
        freq = _clean(freq_match.group(0)) if freq_match else None
        day = int(day_match.group(1)) if day_match else None
        of = int(day_match.group(2)) if day_match and day_match.group(2) else None

        if not (dose or freq or day is not None or _NAME_MENTION.search(line)):
            continue

        if "?" in name and f"drug name ambiguous as written: '{name}'" not in patient["ambiguities"]:
            patient["ambiguities"].append(f"drug name ambiguous as written: '{name}'")

        raw = _clean(sentence) or name
        meds.append(
            {
                "name": name,
                "dose": dose,
                "freq": freq,
                "day": day,
                "of": of,
                "raw": raw if raw.startswith(name) else f"{name} {raw}".strip(),
                "page": page,
            }
        )
    return meds


def _actions(line: str, page: int) -> list[dict]:
    parts = _ACTION.split(line)
    if len(parts) < 2:
        return []
    actions: list[dict] = []
    for chunk in parts[1:]:
        text = _TIME_MISSING.sub("", _REFUSAL_BRACKET.sub("", chunk))
        text = _clean(text).strip(" ,;.").strip()
        if not text:
            continue
        actions.append({"text": text, "when_raw": _time_token(text), "page": page})
    return actions


def _starts_patient(line: str) -> bool:
    if not _BED.search(line):
        return False
    return bool(_MRN.search(line) or _QUOTED.search(line))


def _start_patient(line: str, page: int) -> dict:
    patient = {
        "bed": None,
        "bed_raw": None,
        "mrn": None,
        "name_as_written": None,
        "problem": None,
        "issues": [],
        "pending": [],
        "meds": [],
        "actions": [],
        "allergy": None,
        "covering": None,
        "refused": [],
        "refused_fields": [],
        "ambiguities": [],
        "confidence": 1.0,
        "page": page,
        "source_text": [],
    }
    bed = _BED.search(line)
    if bed:
        patient["bed"] = bed.group(1)
        patient["bed_raw"] = bed.group(1)
    mrn = _MRN.search(line)
    if mrn:
        patient["mrn"] = mrn.group(1)
    name, anchor = _find_name(line, mrn.end() if mrn else 0)
    if name:
        patient["name_as_written"] = name
    patient["problem"] = _dash_problem(line, anchor)
    return patient


def _parse_fields(patient: dict, line: str, page: int) -> None:
    _scan_refusals(patient, line)
    _scan_ambiguities(patient, line)

    allergy = _ALLERGY.search(line)
    if allergy and patient["allergy"] is None:
        value = _clean(allergy.group(1)).rstrip(".").strip()
        if value and not _REFUSAL_PHRASE.search(value):
            patient["allergy"] = value

    covering = _COVERING.search(line)
    if covering and patient["covering"] is None:
        value = _clean(covering.group(1)).rstrip(".").strip()
        if value and not _REFUSAL_PHRASE.search(value):
            patient["covering"] = value

    patient["meds"].extend(_meds(line, page, patient))
    patient["actions"].extend(_actions(line, page))

    for sentence in _sentences(line):
        if _PENDING.search(sentence) and not _ACTION.search(sentence):
            for clause in re.split(r",", sentence):
                if not _PENDING.search(clause):
                    continue
                entry = _clean(clause).rstrip(".").strip()
                entry = re.sub(r"^.*?[\u2014\u2013]\s*", "", entry).strip()
                if entry and entry not in patient["pending"]:
                    patient["pending"].append(entry)


def _finalize(patient: dict) -> dict:
    if patient["problem"] is None and patient["source_text"]:
        patient["problem"] = _body_problem(patient["source_text"][1:])

    issues = []
    if patient["problem"]:
        issues.append(patient["problem"])
    issues.extend(patient["pending"])
    patient["issues"] = _dedupe(issues)
    patient["pending"] = _dedupe(patient["pending"])
    patient["refused_fields"] = list(patient["refused"])
    patient["ambiguities"] = _dedupe(patient["ambiguities"])
    confidence = 1.0 - 0.05 * len(patient["refused"]) - 0.02 * len(patient["ambiguities"])
    patient["confidence"] = round(max(0.0, min(1.0, confidence)), 2)
    return patient


def _parse_page(page_record: dict) -> dict:
    page_no = page_record.get("page")
    if page_record.get("readable") is False:
        return {
            "page": page_no,
            "patients": [],
            "unreadable": True,
            "refusal_reason": page_record.get("refusal_reason"),
            "unusual": [],
        }

    text = page_record.get("text") or ""
    patients: list[dict] = []
    unusual: list[dict] = []
    current: dict | None = None

    for raw_line in text.split("\n"):
        line = raw_line.strip()
        if not line:
            continue

        cleaned, matched = _split_injections(line)
        if matched:
            item = {"page": page_no, "quote": line, "kind": "injection"}
            unusual.append(item)
            existing = page_record.get("unusual")
            if isinstance(existing, list) and item not in existing:
                existing.append(item)
            if not cleaned:
                continue

        if _starts_patient(cleaned):
            current = _start_patient(cleaned, page_no)
            current["source_text"].append(cleaned)
            patients.append(current)
            _parse_fields(current, cleaned, page_no)
            continue

        if current is None:
            continue

        current["source_text"].append(cleaned)
        _parse_fields(current, cleaned, page_no)

    return {
        "page": page_no,
        "patients": [_finalize(patient) for patient in patients],
        "unreadable": False,
        "unusual": unusual,
    }


def extract(pages_doc: dict) -> dict:
    """Parse every readable page into patient field dicts plus injections."""
    pages: list[dict] = []
    injections: list[dict] = []

    ordered = sorted(
        pages_doc.get("pages") or [],
        key=lambda item: (item.get("page") is None, item.get("page")),
    )
    for page_record in ordered:
        parsed = _parse_page(page_record)
        pages.append(parsed)
        for item in parsed.get("unusual") or []:
            key = (item.get("page"), item.get("quote"))
            if not any((i.get("page"), i.get("quote")) == key for i in injections):
                injections.append(item)

    document = {"pages": pages, "injections": injections}
    for key in ("run_id", "shift_date"):
        if key in pages_doc:
            document[key] = pages_doc[key]
    return document
