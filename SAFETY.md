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

## Failure behaviour
Model unavailable → deterministic extraction only, narrative marked `UNAVAILABLE`, exit 0,
never hang. Unreadable page → recorded, run continues, surfaced in the gap list.
