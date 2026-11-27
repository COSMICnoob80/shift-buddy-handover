"""Deterministic structuring: merge page-level fields into patients.

No model, no inference.  Every value that leaves this module is traceable to a
page; drug-day arithmetic is parsed, never guessed, and an action due time is
computed from the run start only when the page gave enough information to do so.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta

_CLOCK = re.compile(r"\b(\d{1,2}):(\d{2})\b")
_HOURLY = re.compile(r"\b(\d+)\s*-\s*hourly\b", re.I)
_INTERVAL = re.compile(r"\bPT(\d+)H\b", re.I)
_HOURS = re.compile(r"\b(\d+(?:\.\d+)?)\s*(?:h|hr|hrs|hour|hours)\b", re.I)
_MINUTES = re.compile(r"\b(\d+)\s*(?:min|mins|minute|minutes)\b", re.I)
_DAY = re.compile(r"\bday\s+(\d+)\b", re.I)
_DAY_OF = re.compile(r"\bday\s+(\d+)\s+of\s+(\d+)\b", re.I)


def _as_datetime(raw: str | None) -> datetime:
    """Parse an ISO-ish run start, falling back to local now."""
    if raw:
        try:
            return datetime.fromisoformat(str(raw))
        except (TypeError, ValueError):
            pass
    return datetime.now().astimezone()


def _next_clock(start: datetime, hour: int, minute: int) -> datetime:
    candidate = start.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if candidate <= start:
        candidate += timedelta(days=1)
    return candidate


def _due(when_raw, start: datetime):
    """Return (due_iso|None, interval|None) for an action's raw time token."""
    if when_raw is None:
        return None, None
    raw = str(when_raw).strip()
    if not raw:
        return None, None

    clock = _CLOCK.search(raw)
    if clock:
        due = _next_clock(start, int(clock.group(1)), int(clock.group(2)))
        return due.isoformat(), None

    hourly = _HOURLY.search(raw)
    if hourly:
        hours = int(hourly.group(1))
        return (start + timedelta(hours=hours)).isoformat(), f"PT{hours}H"

    interval = _INTERVAL.search(raw)
    if interval:
        hours = int(interval.group(1))
        return (start + timedelta(hours=hours)).isoformat(), f"PT{hours}H"

    hours = _HOURS.search(raw)
    if hours:
        value = float(hours.group(1))
        return (start + timedelta(hours=value)).isoformat(), None

    minutes = _MINUTES.search(raw)
    if minutes:
        value = int(minutes.group(1))
        return (start + timedelta(minutes=value)).isoformat(), None

    return None, None


def _prepare_med(med: dict, page: int) -> dict:
    out = dict(med)
    out.setdefault("page", page)
    out.setdefault("day", None)
    out.setdefault("of", None)
    raw = str(out.get("raw") or "")
    if out.get("day") is None and raw:
        match = _DAY.search(raw)
        if match:
            out["day"] = int(match.group(1))
    if out.get("of") is None and raw:
        match = _DAY_OF.search(raw)
        if match:
            out["of"] = int(match.group(2))
    if out.get("dose") is not None:
        out["dose"] = str(out["dose"]).strip()
    return out


def _prepare_action(action: dict, page: int, start: datetime) -> dict:
    out = dict(action)
    out.setdefault("page", page)
    due, interval = _due(out.get("when_raw"), start)
    out["due"] = due
    out["interval"] = interval
    return out


def _prepare_patient(raw: dict, page: int, start: datetime) -> dict:
    pat = dict(raw)
    pat["page"] = pat.get("page", page)
    pat["pages"] = [pat["page"]]
    if pat.get("bed") is None:
        pat["bed"] = pat.get("bed_raw")
    pat["mrn"] = pat.get("mrn") or None
    pat["name_as_written"] = pat.get("name_as_written") or pat.get("name") or None
    pat["meds"] = [_prepare_med(m, pat["page"]) for m in (pat.get("meds") or [])]
    pat["actions"] = [_prepare_action(a, pat["page"], start) for a in (pat.get("actions") or [])]
    for key in ("issues", "pending", "ambiguities"):
        pat[key] = list(pat.get(key) or [])
    pat["refused"] = list(pat.get("refused") or pat.get("refused_fields") or [])
    return pat


def _key(pat: dict):
    if pat.get("mrn"):
        return ("mrn", str(pat["mrn"]).strip().lower())
    return ("bed_name", str(pat.get("bed") or ""), str(pat.get("name_as_written") or "").lower())


def _new_group(pat: dict) -> dict:
    return {
        "base": pat,
        "pages": set(),
        "bed_history": [],
        "mrn_history": [],
        "name_history": [],
        "allergy_history": [],
        "covering_history": [],
        "meds": [],
        "actions": [],
        "issues": [],
        "pending": [],
        "refused": [],
        "ambiguities": [],
        "source_text": [],
        "problem": None,
        "problem_page": None,
        "allergy": None,
        "covering": None,
        "confidence": None,
    }


def _append_unique(target: list, value) -> None:
    if value not in target:
        target.append(value)


def _absorb(group: dict, pat: dict, page: int) -> None:
    group["pages"].add(pat.get("page", page))
    bed = pat.get("bed")
    if bed is not None:
        group["bed_history"].append((str(bed), pat.get("page", page)))
    if pat.get("mrn"):
        group["mrn_history"].append((str(pat["mrn"]), pat.get("page", page)))
    if pat.get("name_as_written"):
        group["name_history"].append((str(pat["name_as_written"]), pat.get("page", page)))
    if pat.get("allergy") not in (None, ""):
        group["allergy_history"].append((str(pat["allergy"]), pat.get("page", page)))
        group["allergy"] = str(pat["allergy"])
    if pat.get("covering") not in (None, ""):
        group["covering_history"].append((str(pat["covering"]), pat.get("page", page)))
        group["covering"] = str(pat["covering"])
    if pat.get("problem") not in (None, "") and group["problem"] is None:
        group["problem"] = str(pat["problem"])
        group["problem_page"] = pat.get("page", page)
    for med in pat.get("meds") or []:
        group["meds"].append(med)
    for action in pat.get("actions") or []:
        group["actions"].append(action)
    for key in ("issues", "pending", "refused", "ambiguities"):
        for item in pat.get(key) or []:
            _append_unique(group[key], item)
    for key in ("source_text", "text", "notes"):
        value = pat.get(key)
        if value:
            if isinstance(value, (list, tuple)):
                group["source_text"].extend(str(v) for v in value)
            else:
                group["source_text"].append(str(value))
    confidence = pat.get("confidence")
    if isinstance(confidence, (int, float)):
        group["confidence"] = confidence if group["confidence"] is None else min(group["confidence"], confidence)


def _merge_kind(group: dict):
    """duplicate | bed_move | None, based on where the beds were seen.

    The same bed continuing across two pages is normal and is *not* a
    contradiction.  A duplicate needs the same bed twice on one page, or two
    different beds on one page; two different beds on different pages is a
    bed move.
    """
    beds = group["bed_history"]
    if len(beds) < 2:
        return None
    bed_values = {bed for bed, _ in beds}
    pages = {page for _, page in beds}
    if len(bed_values) == 1:
        counts: dict = {}
        for entry in beds:
            counts[entry] = counts.get(entry, 0) + 1
        return "duplicate" if any(count > 1 for count in counts.values()) else None
    return "duplicate" if len(pages) == 1 else "bed_move"


def _finalize(group: dict) -> dict:
    base = group["base"]
    beds = group["bed_history"]
    bed_first = beds[0][0] if beds else None
    bed_latest = beds[-1][0] if beds else None
    mrns = group["mrn_history"]
    names = group["name_history"]
    patient = dict(base)
    patient["bed"] = bed_latest
    patient["bed_first"] = bed_first
    patient["bed_latest"] = bed_latest
    patient["mrn"] = mrns[0][0] if mrns else None
    patient["name_as_written"] = names[0][0] if names else None
    patient["allergy"] = group["allergy"]
    patient["covering"] = group["covering"]
    patient["problem"] = group["problem"]
    patient["problem_page"] = group["problem_page"]
    patient["pages"] = sorted(group["pages"])
    patient["page"] = patient["pages"][0] if patient["pages"] else base.get("page")
    patient["meds"] = group["meds"]
    patient["actions"] = group["actions"]
    patient["issues"] = group["issues"]
    patient["pending"] = group["pending"]
    patient["refused_fields"] = group["refused"]
    patient["ambiguities"] = group["ambiguities"]
    patient["source_text"] = group["source_text"]
    if group["confidence"] is not None:
        patient["confidence"] = group["confidence"]
    patient["merge_kind"] = _merge_kind(group)
    patient["bed_history"] = [{"bed": bed, "page": page} for bed, page in beds]
    patient["allergy_history"] = [{"value": value, "page": page} for value, page in group["allergy_history"]]
    patient["mrn_history"] = [{"mrn": mrn, "page": page} for mrn, page in mrns]
    patient["id"] = f"B{bed_latest}" if bed_latest is not None else "B?"
    return patient


def _apply_bed_reuse(patients: list) -> None:
    by_bed: dict = {}
    for patient in patients:
        bed = patient.get("bed")
        if bed is None:
            continue
        by_bed.setdefault(str(bed), []).append(patient)

    for bed, group in by_bed.items():
        mrns = []
        for patient in group:
            mrn = patient.get("mrn")
            if mrn and mrn not in mrns:
                mrns.append(mrn)
        if len(group) < 2 or len(mrns) < 2:
            continue
        first_mrn = mrns[0]
        for patient in group:
            patient["bed_reuse"] = {"bed": bed, "mrns": mrns}
        for patient in group[1:]:
            message = (
                f"bed (BED {bed} re-used by MRN {first_mrn} — "
                "assignment not resolved)"
            )
            if message not in patient["refused_fields"]:
                patient["refused_fields"].append(message)

    used: dict = {}
    for patient in patients:
        base_id = patient.get("id") or "B?"
        used[base_id] = used.get(base_id, 0) + 1
        if used[base_id] > 1:
            patient["id"] = f"{base_id}-{used[base_id]}"


def structure(fields_doc: dict, *, run_start: str | None = None) -> dict:
    """Merge page-level patient facts into one patient per identity.

    Returns ``{"patients": [...], "injections": [...]}``.  Identity is MRN when
    present, otherwise (bed, name).  Pages are ordered before merging.
    """
    start = _as_datetime(
        run_start or fields_doc.get("run_start") or fields_doc.get("run_id")
    )
    pages = sorted(
        fields_doc.get("pages") or [],
        key=lambda p: (p.get("page") is None, p.get("page")),
    )

    groups: dict = {}
    order: list = []
    for index, page in enumerate(pages, start=1):
        page_no = page.get("page")
        if page_no is None:
            page_no = index
        for raw_patient in page.get("patients") or []:
            prepared = _prepare_patient(raw_patient, page_no, start)
            key = _key(prepared)
            if key not in groups:
                groups[key] = _new_group(prepared)
                order.append(key)
            _absorb(groups[key], prepared, page_no)

    patients = [_finalize(groups[key]) for key in order]
    _apply_bed_reuse(patients)
    return {"patients": patients, "injections": list(fields_doc.get("injections") or [])}
