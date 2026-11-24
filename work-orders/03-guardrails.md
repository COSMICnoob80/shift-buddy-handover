# WORK ORDER 03 — Guardrails (`verify.py`, kill switch, audit, permissions)

**Soldier scope: ONLY the files named here.** Read `SPEC.md` §3–§5 and `EVALS.md` first.
This work order carries the safety bonus. **What is enforced in code, not in a prompt.**

## 1. `compose.py` — narration under constraint
- Input: `summary.json` facts, passed as JSON. The local GGUF model writes SBAR prose
  **from the facts only**. The prompt may not instruct it to add anything.
- **Templated fallback is pre-approved** (ARCHITECTURE §5): if the model is unavailable or
  slower than the budget, emit the handoff from templates with no model. Correct and plain
  beats fluent and invented.

## 2. `verify.py` — the verifier (build this FIRST, per ARCHITECTURE §3)
- Re-read the composed prose. Extract every number, dose, bed, time and identifier it
  contains. Assert each one exists in the structured facts.
- **A number in prose but not in the facts fails the run**: write the failure into
  `audit.jsonl`, mark the run failed, exit non-zero. The handoff file is not written.

## 3. Kill switch (in code)
- `STOP` file appears in the working directory → finish the current file atomically, write
  the audit record, exit 0. Tested **within 2 seconds**.
- SIGTERM → same behaviour. Pending work is cancelled, not finished.
- Model unavailable → deterministic extraction only, narrative sections marked
  `UNAVAILABLE`, exit 0. Never hang, never retry forever.

## 4. `audit.jsonl` — the audit trail
One record per run + one per patient: input hashes, model used, per-field confidence, what
was refused and why, start/stop timestamps, kill-switch invocations.

## 5. Permissions, enforced
The process may: read `inbox/` and the model directory; write `out/` and the audit file.
Nothing else. Demonstrate it: a test that shows a write outside `out/` is denied, and a
network call attempt is denied. List the table in `PERMISSIONS.md` (already drafted).

## 6. Monitoring
A single status view (file or tiny local page) showing: current step, last tool action,
pages processed, cost so far, and a live kill-switch button that writes the `STOP` file.

## Prohibited, always (SPEC §3)
No diagnosis, no dose suggestion, no sending anywhere, no fabricated field, no running past
a kill signal, no patient data leaving the machine.

## 6. Assisted mode (opt-in, gap resolution) — build AFTER core, if window time allows

The unattended path stays 100% local — assisted mode is a separate, explicit lane:
- A refused page appears in the gap list with its crop beside the flag.
- One human tap resolves it: either the user types/corrects the fields themselves
  (preferred, zero egress), or the user explicitly triggers a single-page cloud call
  with their own key. The audit entry records `resolved_by: human` — never
  `machine_read`. The handoff marks those fields as human-confirmed, not OCR-extracted.
- Default state: OFF. Nothing may auto-send anything, ever. No batch cloud calls.
- Verify: a test proves that with assisted mode untouched, zero network calls occur.

## Done when
- The verifier fails a deliberately poisoned composition (prove it with a test).
- The kill switch is proven < 2s with the audit intact (prove it with a test).
- The permission denial tests pass. Report verified-on-disk evidence for each.
