# SAFETY.md — guardrails, enforced in code

The rule: **what is enforced in code, not in the prompt.** Each line below names the test
that proves it (tests land in `tests/` during the window).

## Guardrails
- **Verifier gate** (`verify.py`): every quantity and identifier in the composed prose must
  exist in the structured facts. One number that appears only in prose fails the run and the
  handoff file is not written. Test: a deliberately poisoned composition is rejected.
- **Facts-only composer**: the model receives `summary.json` as JSON and no instruction that
  permits adding facts. Test: composer output re-parsed, all values trace to pages.
- **Refusal over guesswork**: unreadable fields become `refused_fields` with a reason.
  Zero fabricated values tolerated. Test: the 20 broken fixture cases produce refusals,
  never guesses.
- **Permissions**: process may read `inbox/` + model dir, write `out/` + audit only; every
  other write and any egress denied. Tests: out-of-scope write denied; network egress 0 bytes.

## Kill switch
`STOP` file in the working directory (path in `.env`) or SIGTERM: finish the current file
atomically, cancel pending work, write the audit record, exit ≤ 2 seconds. Demonstrated on
camera in the demo. Test: timing + audit-integrity proof.

## Monitoring
One live status view: current step, last tool action, pages processed, cost so far, and a
kill-switch button that writes the `STOP` file.

## Audit trail
`audit.jsonl`, append-only, one record per run and per patient — input hashes, model used,
per-field confidence, refusals with reasons, start/stop timestamps, kill-switch events.
A human can reconstruct and replay any run from it alone.

## Assisted mode — opt-in gap resolution (added 24 Nov, after the vision-lane evidence)

The **unattended path remains 100% local**: no network egress, enforced by the permission
test (network egress 0 bytes). Assisted mode is a separate, human-initiated lane:

- A refused page surfaces in the gap list with its crop beside the flag.
- **Identity stays local:** BED / MRN / printed name are read locally from the printed
  header (100% recall, rehearsal-verified). A deterministic mask blacks out identity
  regions by stored coordinates before anything leaves the machine.
- Only with **one explicit human tap** may a single body crop be sent to a cloud vision
  model (the operator's own provider account). Batch sends are prohibited; the default
  state is OFF; the test proves zero network calls when the toggle is untouched.
- Results re-associate deterministically by `page_id` + region map. The audit records
  `resolved_by: human` — never `machine_read` — and the handoff marks those fields as
  human-confirmed, not OCR-extracted.
- Honest residual risk (stated, not hidden): text written inside the handwriting body
  cannot be pre-masked, because finding it requires reading it. First real-page test
  (P27, 25 Nov) proved this cuts both ways: **no patient identifier leaked**, but
  **clinician identifiers did** (doctor names, an internal extension, staff number,
  signature scribbles). Mitigation: the human sees the crop before tapping (consent is
  per-page and informed), the transcription pass reports leaks after the fact, and the
  audit records the leak class alongside `resolved_by: human`.
- Capability evidence: the operator's provider vision read two synthetic handwriting
  fixtures verbatim-exact including the `[?]`-for-illegible discipline (2026-11-24,
  transcriptions match fixture ground truth; logs in the rehearsal directory).

## Failure behaviour
Model unavailable → deterministic extraction only, narrative marked `UNAVAILABLE`, exit 0,
never hang. Unreadable page → recorded, run continues, surfaced in the gap list.
