"""Deterministic rules: contradictions, gaps and missing mandatory fields.

Nothing here guesses.  A contradiction is emitted only when two pages actually
disagree about the same patient and the same field; a gap is a named absence,
not something the page left unsaid silently.
"""

from __future__ import annotations

import re

_ALLERGY_CUE = re.compile(
    r"(?:no allergy(?: field)?[^.]{0,60}(?:recorded|written|documented)"
    r"|allergy(?: status)?[^.]{0,40}(?:not|n't)\s+(?:recorded|written|documented))",
    re.I,
)
_COVERING_CUE = re.compile(
    r"(?:no covering(?: clinician)?[^.]{0,60}(?:named|recorded|documented)"
    r"|covering(?: clinician)?[^.]{0,40}(?:not|n't)\s+(?:named|recorded|documented))",
    re.I,
)
_MRN_CUE = re.compile(r"mrn[^.]{0,40}(?:not|n't)\s+(?:written|recorded|documented)", re.I)
_NAME_CUE = re.compile(r"name[^.]{0,20}(?:illegible|not\s+readable)", re.I)
_BED_CUE = re.compile(r"bed[^.]{0,30}(?:not|n't)\s+(?:written|recorded|documented)", re.I)


def _unique(values):
    out = []
    for value in values:
        if value not in out:
            out.append(value)
    return out


def _patient_label(patient: dict) -> str:
    bed = patient.get("bed")
    name = patient.get("name_as_written")
    if bed is not None and name:
        return f"BED {bed} ({name})"
    if bed is not None:
        return f"BED {bed}"
    if name:
        return str(name)
    return "patient"


def _dose_contradictions(patient: dict) -> list:
    grouped: dict = {}
    order: list = []
    for med in patient.get("meds") or []:
        dose = med.get("dose")
        if dose in (None, ""):
            continue
        name = str(med.get("name") or "").strip().lower()
        if not name:
            continue
        if name not in grouped:
            grouped[name] = []
            order.append(name)
        entry = (str(dose), med.get("page"))
        if entry not in grouped[name]:
            grouped[name].append(entry)

    results = []
    for name in order:
        entries = grouped[name]
        values = _unique(value for value, _ in entries)
        if len(values) < 2:
            continue
        pages = _unique(page for _, page in entries if page is not None)
        results.append(
            {
                "field": "dose",
                "values": values,
                "pages": pages,
                "note": f"dose conflict for {name}: {' vs '.join(values)}",
            }
        )
    return results


def _allergy_contradictions(patient: dict) -> list:
    history = patient.get("allergy_history") or []
    entries = []
    for item in history:
        if isinstance(item, dict):
            value, page = item.get("value"), item.get("page")
        else:
            value, page = item, patient.get("page")
        if value in (None, ""):
            continue
        entry = (str(value), page)
        if entry not in entries:
            entries.append(entry)
    values = _unique(value for value, _ in entries)
    if len(values) < 2:
        return []
    pages = _unique(page for _, page in entries if page is not None)
    return [
        {
            "field": "allergy",
            "values": values,
            "pages": pages,
            "note": f"allergy conflict: {' vs '.join(values)}",
        }
    ]


def _bed_contradictions(patient: dict) -> list:
    kind = patient.get("merge_kind")
    history = patient.get("bed_history") or []
    if kind == "duplicate":
        beds = _unique(str(item.get("bed")) for item in history if isinstance(item, dict) and item.get("bed") is not None)
        values = [patient.get("mrn")] if patient.get("mrn") else []
        values.extend(beds)
        pages = _unique(item.get("page") for item in history if isinstance(item, dict) and item.get("page") is not None)
        return [
            {
                "field": "duplicate",
                "values": values,
                "pages": pages,
                "note": "duplicate patient: same MRN under two beds",
            }
        ]
    if kind == "bed_move":
        beds = [item for item in history if isinstance(item, dict) and item.get("bed") is not None]
        if len(beds) < 2:
            return []
        first, latest = beds[0], beds[-1]
        return [
            {
                "field": "bed",
                "values": [str(first["bed"]), str(latest["bed"])],
                "pages": _unique(
                    [first.get("page"), latest.get("page")]
                ),
                "note": f"bed moved from BED {first['bed']} to BED {latest['bed']}",
            }
        ]
    return []


def _bed_reuse_contradictions(patients: list) -> list:
    seen: dict = {}
    results = []
    for patient in patients:
        reuse = patient.get("bed_reuse")
        if isinstance(reuse, dict):
            bed = str(reuse.get("bed"))
            mrns = list(reuse.get("mrns") or [])
        else:
            bed = str(patient.get("bed"))
            mrns = [patient.get("mrn")] if patient.get("mrn") else []
        if bed not in seen:
            seen[bed] = {"mrns": [], "pages": []}
        for mrn in mrns:
            if mrn and mrn not in seen[bed]["mrns"]:
                seen[bed]["mrns"].append(mrn)
        for page in patient.get("pages") or []:
            if page not in seen[bed]["pages"]:
                seen[bed]["pages"].append(page)

    for bed, info in seen.items():
        if len(info["mrns"]) < 2:
            continue
        results.append(
            {
                "field": "bed",
                "values": info["mrns"],
                "pages": sorted(info["pages"]),
                "note": f"bed reuse: BED {bed} carries two MRNs",
            }
        )
    return results


def _cue_text(patient: dict) -> str:
    parts = []
    for key in ("issues", "source_text", "notes"):
        value = patient.get(key)
        if isinstance(value, (list, tuple)):
            parts.extend(str(item) for item in value)
        elif value:
            parts.append(str(value))
    return " ".join(parts)


def _missing_for(patient: dict) -> list:
    text = _cue_text(patient)
    absent = []
    if patient.get("bed") in (None, ""):
        absent.append("bed")
    if patient.get("mrn") in (None, ""):
        absent.append("mrn")
    if patient.get("name_as_written") in (None, ""):
        absent.append("name")

    allergy_missing = patient.get("allergy") in (None, "")
    covering_missing = patient.get("covering") in (None, "")

    if allergy_missing and _ALLERGY_CUE.search(text):
        absent.append("allergy")
    if covering_missing and _COVERING_CUE.search(text):
        absent.append("covering_clinician")

    # An explicit hard-field statement is also a gap even if another field is
    # simply blank: blank is not the same as documented absence.
    if "mrn" not in absent and _MRN_CUE.search(text):
        absent.append("mrn")
    if "name" not in absent and _NAME_CUE.search(text):
        absent.append("name")
    if "bed" not in absent and _BED_CUE.search(text):
        absent.append("bed")
    return absent


def _gap_message(patient: dict, field_name: str) -> str:
    label = _patient_label(patient)
    page = patient.get("page")
    suffix = f" [p. {page}]" if page is not None else ""
    messages = {
        "bed": "bed number not recorded",
        "mrn": "MRN not recorded",
        "name": "patient name not recorded",
        "allergy": "allergy status not recorded",
        "covering_clinician": "covering clinician not named",
    }
    return f"{label}: {messages.get(field_name, field_name)}{suffix}"


def apply(patients: list, injections: list) -> dict:
    """Return patients enriched with gaps, plus contradictions and missing."""
    patients = [dict(patient) for patient in patients]
    contradictions: list = []
    gaps: list = []
    missing: dict = {}

    for patient in patients:
        contradictions.extend(_dose_contradictions(patient))
        contradictions.extend(_allergy_contradictions(patient))
        contradictions.extend(_bed_contradictions(patient))

        absent = _missing_for(patient)
        if absent:
            missing[patient.get("id") or _patient_label(patient)] = absent
            issues = patient.get("issues")
            if not isinstance(issues, list):
                issues = list(issues or [])
            for field_name in absent:
                message = _gap_message(patient, field_name)
                if message not in gaps:
                    gaps.append(message)
                if message not in issues:
                    issues.append(message)
            patient["issues"] = issues

    contradictions.extend(_bed_reuse_contradictions(patients))

    return {
        "patients": patients,
        "contradictions": contradictions,
        "gaps": gaps,
        "missing": missing,
        "injections": list(injections or []),
    }
