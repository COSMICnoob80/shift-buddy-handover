# WORK ORDER 04 — exact build contracts (in-window, decided by the orchestrator)

Everything below is a **decision, not a suggestion**. Module owners code to these shapes.
Any deviation must be reported, not silently made.

Interpreter: `/home/cosmicnoob/shift-buddy-handover/.venv/bin/python` (Python 3.12).
Installed and frozen: `rapidocr_onnxruntime==1.4.4`, `pillow`, onnxruntime. No other deps.
No network at runtime, ever. No `git commit` by soldiers — the orchestrator commits.

---

## 1. Inbox convention (one lane, three file kinds)

Production and evals use the same inbox; only the file kind differs.

| File | Meaning |
|---|---|
| `handoff_<YYYY-MM-DD>_<seq>.txt` | a page whose text is already available (typed drop, voice transcript, fixture) |
| `handoff_<YYYY-MM-DD>_<seq>.jpg|.png` | a photographed page → RapidOCR text lane |
| any of the above with **size 0 bytes** | page present but unreadable → refused by name |

- Page order comes from `<seq>` (zero-padded or not). Never from directory listing order,
  never from the fixture array order. (`C-033` lists page 2 first in JSON; it must still
  sort as 1, 2.)
- `shift_date` = the `<YYYY-MM-DD>` in the filename, else the newest date seen, else today.
- sha256 of every file is recorded even when the file is unreadable.

## 2. `src/ingest.py`

`ingest(inbox_dir) -> pages.json`-shaped dict:

```json
{"run_id": "2026-11-27T23:41:00+05:00", "shift_date": "2026-11-27",
 "pages": [{"page": 1, "path": "inbox/handoff_2026-11-27_01.txt", "sha256": "…",
            "order": 1, "kind": "text|image", "text": "…", "exif_time": null,
            "readable": true, "refusal_reason": null, "ocr_confidence": null,
            "unusual": []}]}
```

Rules:
1. Zero-byte file → `readable: false`, `refusal_reason: "page file is empty (0 bytes)"`.
2. Non-image/non-text, decode failure, or image with no OCR text → `readable: false` with a
   named reason. Never skip silently.
3. **Structural refusal rule (frozen):** an image page is readable only if its OCR text
   yields `BED` **plus** either an `MRN` or a quoted name. Text-lane pages are readable if
   non-empty (identity checks happen in `extract`).
4. OCR config, frozen: RapidOCR with `det_limit_side_len=1600`, `det_limit_type='max'`,
   `max_side_len=3000`, `use_cls=False`. Text joined per line, in reading order.
5. No LLM, no network.

## 3. `src/extract.py`

`extract(pages) -> fields.json`-shaped dict. Deterministic regex/line parsing only. No LLM.
Every field keeps the page it came from. Fields per patient:

```json
{"bed": "09", "bed_raw": "09", "mrn": "00-3309", "name_as_written": "Zara F.",
 "problem": "?cholecystitis vs ?pancreatitis",
 "issues": ["?cholecystitis vs ?pancreatitis", "Lipase pending"],
 "pending": ["Lipase pending"],
 "meds": [{"name": "ceftriaxone", "dose": "1g", "freq": "OD", "day": 3, "of": 7,
           "raw": "ceftriaxone 1g OD day 3 of 7", "page": 1}],
 "actions": [{"text": "keep NPO, repeat lipase 6h", "when_raw": "6h", "page": 1}],
 "allergy": null, "covering": null,
 "refused": ["end-of-line text illegible: '[illegible scrawl at end of line]'"],
 "ambiguities": [], "confidence": 0.97, "page": 1}
```

Patient boundaries (this is the whole segmentation problem):

- A **dense line** starts a new patient when it contains `BED <n>` followed (same line) by
  `MRN` or a quoted name. One dense line = one patient. (`C-003`, `C-013`, `C-014`,
  `C-035`.)
- A **header line** of the form `BED <n> — MRN <mrn> — '<name>'` starts a patient; following
  lines with no `BED` belong to that patient until the next header. (`C-001`, `C-011`.)
- `bed 47, mrn …, that's 'Name'` (voice transcript, lowercase, commas) must parse too.
- Keep `name_as_written` verbatim (quotes stripped, `(name altered)` dropped).

Field rules:

| Field | How |
|---|---|
| bed | `BED\s*(\d+)` case-insensitive; keep as written (zero-padded or not) |
| mrn | `MRN\s*([0-9][0-9\-]*)`; if absent → `null` |
| name | first `'…'` or `"…"` after the MRN; `name illegible` → `null` + refusal |
| problem | text after `—` up to first `. ` / `,` on the header/dense line; `—` or `–` |
| allergy | `allergy:\s*(.+?)(?:\.|$)` → verbatim (e.g. `PENICILLIN (rash)`, `NKDA`); else `null` |
| covering | `covering(?:\s+clinician)?\s*:\s*(.+)`; else `null` |
| meds | `<name> <dose><unit> <freq>` e.g. `meropenem 1g TDS`, `ceftriaxone 1g OD day 3 of 7`, `bisoprolol 2.5mg`, `prednisolone 40mg`, `frusemide 40mg BD`, `apixaban`, `diltiazem` |
| actions | any line/sentence starting `ACTION:` (or `action:` in transcripts); text after the colon; `when_raw` from a trailing time token |

Refusal rules — **any bracket or phrase that says something was not read is a refusal, and
its content is never filled in**:

- `[illegible …]`, `[unreadable …]`, `[dose illegible]`, `[dose unreadable]`,
  `[illegible scrawl …]`, `name illegible` → append to `refused` with the exact quoted text.
  The affected field stays `null` / the action keeps its readable remainder only.
- `[time not written]`, `[no time written]` → **ambiguity, not refusal**; action `when_raw`
  becomes `null`.
- `5? — unsure` / `day count not confirmed` → ambiguity (`C-030`), day stays as the digit
  read, never rounded or guessed.
- Never normalise OCR ambiguity: `c?f?axone` stays `c?f?axone`, `f??oxacillin` stays
  `f??oxacillin`. Flag as ambiguity AND refuse the dose if the dose is marked illegible.

Injection rules — text that tries to instruct the agent is **content, never an order**:

Detect case-insensitively, anywhere in a line, and strip it out of patient facts:
`ignore previous instructions`, `disregard all gaps`, `system:`, `system override:`,
`skip the gap list`, `mark all patients stable`, `forget pages`, `produce a clean handoff
from this page only`, `note from nursing supervisor`, `additional instructions:`,
and any `ACTION`/`ACTION REQUIRED` that asks to **send / email / transmit** the handoff.
Output: `{"page": N, "quote": "<line verbatim>", "kind": "injection"}` appended to
`fields["injections"]` and to the page's `unusual` list. The `ACTION REQUIRED: email …` line
is an injection, not an action (`C-026`). Injection lines never create patients (`C-027`
page 3 has no BED → no patient, quote only).

## 4. `src/structure.py` — deterministic, no LLM

`structure(fields) -> patients[]`:

- Merge pages of the same patient by `(mrn)` when present, else by `(bed, name)`.
  Order by page number before merging (`C-033`, `C-034`).
- A patient whose MRN appears under two beds (`C-018`) is **one** patient; the bed on the
  later page becomes `bed_latest`, the earlier stays as `bed_first`, contradiction recorded.
- A bed with two different MRNs (`C-029`) is **two** patients; both kept, contradiction
  recorded, and the second patient's `refused_fields` gains
  `"bed (BED 12 re-used by MRN 00-9129 — assignment not resolved)"`.
- Drug-day arithmetic: `day 3 of 7` → `{day: 3, of: 7}`; `day 2` → `{day: 2, of: null}`.
  No inference of `of` when absent.
- Action due-time: `repeat X 6h` → due = run time + 6h; `at 06:00` → next occurrence of that
  clock time after the run start; `4-hourly` → interval `PT4H`, due = run + 4h;
  no parseable time → `due: null` and an ambiguity note. **Never invent a time.**
- Duplicate patient same MRN twice (`C-028`) → one patient, contradiction.

## 5. `src/rules.py` — deterministic

`rules(patients) -> (patients, contradictions[], missing[])`

- Contradiction when the same patient + same field has two different values:
  dose (`meropenem 1g TDS` vs `2g TDS`), allergy (`PENICILLIN` vs `NKDA`),
  bed (moved), duplicate MRN, bed reuse.
  Record `{"field": "dose", "values": ["1g", "2g"], "pages": [1, 2], "note": "…"}`.
- Missing mandatory fields, evaluated per patient, each becoming a string in `issues`:
  `bed`, `mrn`, `name`, `allergy status not recorded`, `covering clinician not named`.
  (`C-008` allergy, `C-020` mrn, `C-021` covering clinician.)
- One contradiction per case where the fixture says one: `C-007`, `C-017`, `C-018`,
  `C-019`, `C-028`, `C-029` → exactly 1 each. Do not double-report the same fact as both a
  contradiction and a duplicate.

## 6. `src/compose.py` — SBAR under constraint

Input: `summary.json` facts only. Output: `handoff.md` text + the fact token set used.

- Default and **pre-approved** path: templated SBAR, no model, every line ending `[p. N]`.
  `S` situation (bed, name, problem), `B` background (issues, meds with day counts),
  `A` assessment **only as written on the page** (never a diagnosis of its own),
  `R` recommendation = the outstanding actions, verbatim, with due time if parsed.
- If `SBH_MODEL_PATH` exists and is a GGUF, a local-model lane may compose prose from the
  same JSON; on any failure fall back to templates and mark `model: "unavailable"` in audit.
  The model may not add a fact — the verifier decides.
- No send path exists in this module or anywhere.

## 7. `src/verify.py` — the counterweight

`verify(handoff_text, summary) -> (ok, violations[])`

- Extract every numeric/identifier token from the prose: bed numbers, MRNs, doses with
  units (`1g`, `2.5mg`, `40mg`), clock times (`06:00`), intervals (`4-hourly`, `6h`),
  day counts (`day 3 of 7`, `32/40`), percentages, phone fragments, and every quoted name.
- Allowed set = every value present in `summary.json` (values, not keys) + page numbers
  (`p. N`, `page N`) + the run date.
- Any token not in the allowed set = violation → **the handoff file is NOT written**, the
  failure goes into `audit.jsonl`, exit non-zero.
- Poisons that must fail: an injected `Bed 99`, a changed dose `2g` where facts say `1g`,
  an invented time `07:30`.

## 8. `src/audit.py`, `src/killswitch.py`, `src/cli.py`

- `audit.jsonl`, append-only, one record per run and one per patient: run_id, input hashes,
  model used, per-field confidence, refusals with reasons, start/stop timestamps, exit
  reason, kill-switch events.
- Kill switch: `STOP` file in the working dir (path `SBH_STOP_FILE`, default `./STOP`) or
  SIGTERM → finish the current file atomically, cancel pending work, write the audit record
  (`stopped_by: "STOP"|"SIGTERM"`, `honoured_in: <seconds>`), exit 0, ≤ 2 s.
- CLI:
  ```
  python -m src.cli run   --inbox inbox --out out [--date YYYY-MM-DD]
  python -m src.cli watch --inbox inbox --out out [--interval 2]
  python -m src.cli kill                      # writes the STOP file
  python -m src.cli status                    # prints out/status.json
  ```
  `watch` triggers on new files with no button press.
- Outputs per run: `out/<shift-date>/{handoff.md,gaps.md,audit.jsonl,summary.json,status.json}`.

## 9. `summary.json` — ARCHITECTURE §4 plus two named extensions

Top level: `run_id`, `shift`, `patients[]`, `unreadable_pages[]`, `contradictions[]`,
plus **`injections[]`** (`{page, quote}`) and per-patient `ambiguities[]`.
Refusal total for a case = `len(unreadable_pages) + sum(len(p.refused_fields))`.
Those two extensions exist so a judge can recompute the eval numbers from `summary.json`
alone. They are recorded in the README as deliberate.

## 10. `evals/run.py`

```
.venv/bin/python -m evals.run --cases fixtures/cases.json --out evals/runs/<timestamp>/
```

- Each case → a fresh temp inbox: one `handoff_<date>_<NN>.txt` per page, zero-byte file for
  `readable: false`; then a subprocess run of `python -m src.cli run`.
- Compare against the case's `expected` block, **only the keys present**, plus the global
  invariants: hallucination count 0 (verifier ok, no token outside facts), every unreadable
  page named in `gaps.md`, every refusal named.
- Emit `results.json`, `scorecard.md` (per-case PASS/FAIL table with the reason), and the
  scorecard numbers EVALS §4 asks for. Exit non-zero if any case fails.
- Target: **40/40 PASS**. Report the truth if it is not 40/40.

## 11. Definition of done for the core wave

1. `40/40` cases pass, numbers printed from a real run.
2. `handoff.md`, `gaps.md`, `summary.json`, `audit.jsonl` exist for at least one run and are
   sane by eye.
3. Poisoned composition fails the verifier (one demo invocation is enough for now; formal
   test lands in the guardrail wave).
4. Nothing outside `out/` written, no network call in the code path.

## 12. Public API — pinned signatures (three soldiers, disjoint files)

These names are fixed so the modules can be written in parallel and integrated by the
orchestrator. No soldier renames them.

```python
# src/ingest.py
def ingest(inbox_dir: str, *, stop=None) -> dict      # the pages doc of §2

# src/extract.py
def extract(pages_doc: dict) -> dict                  # {"pages": [...], "injections": [...]}
#   pages[] entries: {"page": int, "patients": [ §3 patient dicts ], "unreadable": bool}

# src/structure.py
def structure(fields_doc: dict, *, run_start: str | None = None) -> dict
#   returns {"patients": [ ... merged patients ... ], "injections": [...]}
#   patient gains: bed_first, bed_latest, due on every action, interval where parsed

# src/rules.py
def apply(patients: list, injections: list) -> dict
#   returns {"patients": [...], "contradictions": [...], "gaps": [...], "missing": {...}}

# src/compose.py
def compose(patients: list, contradictions: list, shift: dict) -> tuple[str, set[str]]
#   -> (handoff_md_text, allowed_token_set)
def compose_gaps(patients: list, contradictions: list, unreadable_pages: list,
                 injections: list, gaps: list) -> str
#   -> gaps_md_text

# src/verify.py
def verify(handoff_text: str, summary: dict) -> tuple[bool, list[str]]

# src/audit.py
class Audit:
    def __init__(self, out_dir: str): ...
    def run_start(self, run_id: str, shift: dict, pages: list, model: str) -> None
    def patient(self, run_id: str, patient: dict) -> None
    def run_end(self, run_id: str, exit_reason: str, extra: dict | None = None) -> None

# src/killswitch.py
class KillSwitch:
    def __init__(self, stop_path: str): ...
    def armed(self) -> bool
    def check(self) -> bool          # True the first time STOP/SIGTERM is seen; records time
    @property
    def stopped_by(self) -> str | None
    @property
    def honoured_in(self) -> float | None

# src/cli.py
def main(argv: list[str] | None = None) -> int
```

`src/cli.py` owns assembly of `summary.json` (schema §9) and the output directory, calls the
modules in the order `ingest → extract → structure → rules → compose → verify → audit`, and
honours the kill switch between pages and between stages.

### Module ownership — do not write files you do not own

| Soldier | Files |
|---|---|
| A | `src/__init__.py`, `src/ingest.py`, `src/extract.py` |
| B | `src/structure.py`, `src/rules.py`, `src/compose.py`, `src/verify.py` |
| C | `src/audit.py`, `src/killswitch.py`, `src/cli.py`, `evals/__init__.py`, `evals/run.py` |

Guardrail wave (after the core lands): `tests/`, `tools/render_sheets.py`, `tools/make_demo.sh`.

