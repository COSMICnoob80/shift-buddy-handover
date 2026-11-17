# WORK ORDER 02 — Structuring & Rules (`structure.py` + `rules.py`)

**Soldier scope: ONLY these two files.** Read `SPEC.md` and `ARCHITECTURE.md` §2 and §4 first.

## Inputs
`fields.json` from Work Order 01 (per-page field records with provenance).

## What to build

### `structure.py` — deterministic, no LLM
- Normalise bed/ID (keep `name_as_written` alongside the normalised form).
- Drug-day arithmetic: parse "day 3 of 7", "day 2", "3/7 days" into day counts.
- Action extraction with due-time parsing: "repeat troponin 6h" → due now+6h; "06:00" → that
  time; "4-hourly" → interval, next due = last documented + 4h. **An action with no
  parseable time gets `due: null` — never an invented time.**
- Attach every field's source page.

### `rules.py` — contradiction & gap detection, deterministic
- Contradictions: same patient + same field with different values on different pages
  (e.g. dose 1g TDS vs 2g TDS). Record `{field, values, pages}`.
- Duplicate patient: same MRN under two beds; same name+MRN twice.
- Bed reuse: one bed number attached to two different MRNs.
- Missing mandatory fields: bed, MRN, name, allergy status, covering clinician.
- Cross-page consistency check on page ordering (a later page referencing an earlier
  admission date is fine; a *later* date on an *earlier* page is flagged).

## Output
`summary.json` — **exactly** the schema in `ARCHITECTURE.md` §4: run_id, shift block,
patients[] with issues/pending/actions/confidence/refused_fields, unreadable_pages[],
contradictions[]. No extra top-level keys.

## Hard rules
1. No LLM anywhere in this stage. If a rule cannot be computed deterministically, the field
   stays unstructured and lands in the gap list.
2. Every value in `summary.json` must trace to a page number in `fields.json`.

## Done when
- Running against Work Order 01's output for the 40 rendered cases produces `summary.json`
  whose `contradictions` / refusal / patient counts match each fixture case's `expected`
  block. Report verified-on-disk results per case.
