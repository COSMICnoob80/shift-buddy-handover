# WORK ORDER 01 — Ingestion & Extraction (`ingest.py` + `extract.py`)

**Soldier scope: ONLY these two files.** Read `SPEC.md` and `ARCHITECTURE.md` §2 first.

## Inputs
Photos land in `inbox/` named `handoff_<YYYY-MM-DD>_<seq>.jpg` (seq = page order as
photographed). No button press; a runner feeds the directory.

## What to build

### `ingest.py`
- Enumerate `inbox/`, sha256-hash every file, read EXIF capture time.
- Order pages by filename `seq`. Flag: zero-byte files, non-images, files that fail decode.
- Output `pages.json`: one record per page — `{path, sha256, exif_time, order, readable, refusal_reason}`.
- An unreadable page is **refused by name**, never skipped silently.

### `extract.py`
- OCR each readable page (tesseract, `eng`). **No LLM in this stage** — OCR + deterministic
  matching only, so every extraction is auditable.
- Extract per patient, every field carrying `{value, page, confidence, bbox}`:
  bed, MRN, name_as_written, presenting problem, active issues, pending results,
  medications (name, dose, frequency, day count), outstanding actions, covering clinician.
- Output `fields.json`: per-page field records, patients keyed by (bed, MRN) as written.

## Hard rules
1. A field the OCR could not read becomes a `refused_fields` entry with a reason.
   **A blank is always better than a guess.** Hallucinated fields: 0 tolerance.
2. No network calls. Local files only.
3. Never state or imply a diagnosis; never suggest a drug or dose. Extraction copies what is
   written; it does not interpret it.
4. Prohibited per SPEC §3: sends, diagnosis, dose advice, fabricated values, running past a
   kill signal.

## Done when
- Both files exist, run against the 40 rendered fixture cases, and produce `pages.json` +
  `fields.json` whose refusal counts match each case's `expected` block.
- Report what you verified on disk, not what you intended.
