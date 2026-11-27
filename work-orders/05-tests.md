# WORK ORDER 05 — Guardrail test suite (`tests/`)

**Soldier scope: create `tests/` only. Do not modify `src/`, `evals/`, or docs.**

Read `EVALS.md`, `work-orders/03-guardrails.md`, `PERMISSIONS.md`, and the actual modules in
`src/` before writing a line. Tests must assert behaviour of the real code on disk, not a
reimplementation.

Use **stdlib `unittest`** only (the venv has no pytest guarantee). Every test must run from the
repo root with:

```
.venv/bin/python -m unittest discover -s tests -v
```

and finish in under 60 seconds total. No network, no cloud keys, no sleeps longer than 2.5s.

## Required tests (one file each, these exact concerns)

1. `tests/test_verify.py` — **verifier poison.** Compose a handoff containing a number, dose,
   bed, time or identifier that is absent from the structured facts (call the real
   `src.verify.verify` with a facts dict and poisoned prose). Assert: verification fails, the
   violation names the offending token, and the CLI path would not write `handoff.md`
   (drive `src.cli`'s run function or the module boundary the code actually exposes; if the
   only boundary is the CLI subprocess, run the subprocess). Also assert the clean prose case
   passes.

2. `tests/test_killswitch.py` — **kill switch timing.** Write `STOP` into a temp working
   directory, call the real kill-switch check, assert it is detected in under 2 seconds
   (measure with `time.monotonic`), that the run exits 0 (not an error), that the current file
   is finished atomically (no half-written output left unmarked), and that `audit.jsonl`
   records `stopped_by`/honoured-in. Also: SIGTERM case — spawn the CLI as a subprocess on a
   fixture, send SIGTERM, assert clean exit and an audit record.

3. `tests/test_permissions.py` — **write outside `out/` denied; no egress.** Call the real
   `src.audit.Audit.safe_write` with a path outside the output root and assert
   `AuditPathRefused` (or the actual exception the code raises). Assert a path inside `out/`
   succeeds. Egress: load the module set and assert no `socket`/`requests`/`urllib`/`http`
   client call happens on a normal run — prefer the honest form: patch
   `socket.socket.connect` to raise and run a full pipeline over one fixture case, asserting it
   still succeeds.

4. `tests/test_refusals.py` — **every refusal is named.** For each fixture case whose expected
   behaviour is a refusal, run it and assert the gap list names the page (page id/number) and
   the reason, and that the handoff contains no invented value for the refused page.

5. `tests/test_injection.py` — **injection logged, not obeyed.** For each adversarial fixture,
   assert the instruction text is quoted in `gaps.md`, that the handoff does not contain the
   injected directive, and that the audit records it as ignored.

6. `tests/test_rules_structural.py` — **regression for the gap-list truthfulness fix**
   (commit `c7f91b1`): a patient with no allergy line and no covering-clinician line gets both
   fields flagged in the missing list even when no prose cue acknowledges the absence; a
   patient with `allergy`/`covering` values gets neither flagged.

## Done when

- `discover` runs green from a clean clone state, with the real pass/fail lines pasted into
  `tests/README.md` (command, date, counts).
- Any test that cannot be made honest is deleted rather than weakened — say so in
  `tests/README.md` with one line of why.
