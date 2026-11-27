# WORK ORDER 06 — Demo tooling and scorecard (`tools/`, `README.md` scorecard section)

**Soldier scope: create `tools/` only, plus append one "Scorecard" section to `README.md`.
Do not modify `src/`, `evals/`, `tests/`, or the design docs.**

Read `DEMO-SCRIPT.md`, `EVALS.md`, `RUNBOOK.md`, `src/cli.py`, `conftest`-free `evals/run.py`,
and `fixtures/cases.json` first.

## Deliverables

1. `tools/render_sheets.py` — build the demo inbox from fixtures **deterministically**:
   ```
   .venv/bin/python tools/render_sheets.py --cases fixtures/cases.json --out inbox/demo/
   ```
   **Filename contract is not negotiable**: `src/ingest.py` only accepts
   `handoff_<YYYY-MM-DD>_<seq>.<ext>` (regex `^handoff_(date)_(seq)(.ext)?$`) and orders pages
   by `<seq>`. Any other name is ignored, so the run reports 0 patients. Emit
   `handoff_<date>_<seq>.txt` (e.g. `handoff_2026-11-28_01.txt`), not `page-01-*.txt`. For a
   case with several pages, use consecutive seq numbers. Verify by running the CLI and seeing
   the patient count you expect.
   For a given case the script writes plain-text page files using the exact page text in the
   fixture. For cases the fixtures mark as an image/photo category, write a `.txt` transcript variant AND document in
   the script header why text pages are used for the demo (v1 refuses handwriting — that is
   the point of the demo, so also emit one deliberately cropped/unreadable page from the
   refusal fixtures). Idempotent: re-running produces byte-identical files (no timestamps in
   content).

2. `tools/make_demo.sh` — one command that reproduces the demo end to end:
   ```
   bash tools/make_demo.sh
   ```
   Steps, each echoing a progress line: clean `out/`, render sheets into a temp inbox dir,
   run `.venv/bin/python -m src.cli run` against it, then print (a) the SBAR page-reference
   count from `handoff.md`, (b) the "could not be read" lines from `gaps.md`, (c) the
   contradiction lines from `gaps.md`, (d) the hallucination counter line, and (e) the tail of
   `audit.jsonl`. Then run the kill-switch half: start a second run, `touch STOP`, and print
   the honoured-in time and the `stopped_by` audit field. `set -euo pipefail`, no network.

3. `tools/scorecard.sh` — runs the full 40-case pack into `evals/runs/<UTC timestamp>/` and
   prints the one-screen summary the submission quotes (cases passed, hallucinations,
   contradictions caught, injections ignored, refusals named, kill-switch honoured-in).

4. `README.md` — append a `## Scorecard` section: the real numbers produced by running
   `tools/scorecard.sh` (paste actual output, not placeholders), the run command, and one line
   pointing at `evals/runs/<latest>/scorecard.md`. Also add a `## Demo` section with the two
   commands (`render_sheets.py`, `make_demo.sh`) and the shot list reference. Do not touch any
   existing README prose above the new sections.

## Done when

- All three commands run green from the repo root and you have pasted their real output into
  `tools/README.md` (command, date, key lines).
- Nothing outside `tools/` and the new README sections changed.
