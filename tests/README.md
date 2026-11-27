# Guardrail test suite (`tests/`)

Stdlib `unittest` only. No network, no cloud keys, no sleeps beyond 2.5 s.
Everything below asserts behaviour of the real code on disk — `src.verify`,
`src.killswitch`, `src.audit`, `src.ingest`, `src.compose`, `src.extract`,
`src.structure`, `src.rules`, and `src.cli` both in-process and as a subprocess.

Fixtures are loaded through `evals.run.load_cases` and built with
`evals.run.build_inbox`, so the suite scores the same 40-case pack the eval
harness scores.

## Run

From the repo root:

```
.venv/bin/python -m unittest discover -s tests -v
```

## Last verified run

Command, verbatim output tail, and counts below are from a real run on
**2026-11-28** with **Python 3.12.3** (`.venv/bin/python`).

```
Ran 50 tests in 3.141s

OK (expected failures=2)
```

Per-file counts (each file run on its own):

| File | Tests | Result |
|---|---:|---|
| `test_verify.py` | 6 | OK |
| `test_killswitch.py` | 8 | OK |
| `test_permissions.py` | 9 | OK |
| `test_refusals.py` | 10 | OK (expected failures=2) |
| `test_injection.py` | 9 | OK |
| `test_rules_structural.py` | 8 | OK |
| **total** | **50** | **OK (expected failures=2)** |

Wall time for the whole suite is ~3 s, well inside the 60 s budget. The
kill-switch file is the slowest at ~1.3 s because it drives real subprocesses.

## What each file proves

- **`test_verify.py` — verifier poison.** Calls the real `src.verify.verify`
  with a facts dict and poisoned prose containing a dose (`50mg`), a bare number
  (`3750`), a bed (`99`), a clock time (`12:45`), and an identifier (`99-1234`).
  Each fails and the violation names the token and its kind. The clean prose case
  passes. The CLI path is driven through `src.cli._run_once` with
  `src.compose.compose` poisoned, and the run exits 1, writes **no**
  `handoff.md`, records `verify_failed` in `audit.jsonl`, and carries the
  violation into `status.json`.
- **`test_killswitch.py` — kill-switch timing.** Writes `STOP` into a temp
  working directory and asserts `KillSwitch.check()` detects it in under 2 s
  (measured with `time.monotonic`). Proves the in-flight page finishes whole and
  the remainder is *named* in `unprocessed_files` rather than silently dropped
  (`src.ingest.ingest(stop=...)`). Drives the real CLI: STOP present before the
  run, STOP arriving mid-run, and SIGTERM against an 800-page inbox. All assert
  exit 0 (not an error), `exit_reason`/`stopped_by`/`honoured_in` in
  `audit.jsonl`, no `handoff.md`, and no half-written `.json` or `.tmp` artifact.
- **`test_permissions.py` — write outside `out/` denied; no egress.**
  `Audit.safe_write` refuses an absolute escape, a `..` traversal, and an audit
  directory anchored outside the root, all raising `AuditPathRefused`; a path
  inside `out/` succeeds atomically with no temp file left behind. Egress is
  tested honestly: `socket.socket.connect`, `connect_ex`, and
  `socket.create_connection` are patched to raise, a full pipeline runs over a
  real fixture case, and it still succeeds with the patch never firing. A static
  AST check asserts no `socket`/`requests`/`urllib`/`http` client import exists in
  `src/`, and a snapshot proves a run writes nothing outside `out/`.
- **`test_refusals.py` — every refusal is named.** Runs all 10 fixture cases
  that declare a refusal and asserts each recorded refusal reason is quoted in
  `gaps.md`, each unreadable page number is named, the refusal count matches
  EVALS §9, no refusal marker leaks into `handoff.md`, and every shipped handoff
  still passes its own verifier.
- **`test_injection.py` — injection logged, not obeyed.** For all 7 adversarial
  fixture cases: the instruction text is quoted verbatim in `gaps.md` under the
  unusual-text section with its page, the quote and its directive phrases never
  reach `handoff.md`, the run trace records the injection while ending
  `completed` with `verify_ok` true, the gap list is **not** suppressed, and for
  C-027 the facts from the pages it asked to "forget" are still in the handoff.
- **`test_rules_structural.py` — regression lock for `c7f91b1`.** A patient with
  no allergy line and no covering-clinician line is flagged for both even with no
  prose cue acknowledging the absence; cue text and silent text produce identical
  missing lists; a patient with both values is flagged for neither; each field is
  judged independently; and `allergy: [illegible]` still counts as absent.

## Defects found in `src/` (kept as failing tests, `src/` not touched)

These two tests are real assertions that currently fail. They are marked
`@unittest.expectedFailure` so `discover` stays green while the defect is
recorded and the moment either is fixed the test turns into an unexpected
success, which is the signal to delete the marker.

1. **`test_refusals.RefusalNamingTests.test_recorded_reason_for_an_unreadable_page_survives_into_gaps`**
   — the reason `ingest` records for an unreadable page never reaches `gaps.md`.
   `src.ingest` stores an exact reason (e.g. `page file is empty (0 bytes)`) and
   `audit.run_start` keeps it in `refusal_reason`, but `src.cli._unreadable_pages`
   reduces those pages to bare integers, so `src.compose._unreadable_line` can
   only print `- page N: unreadable`. The page is named; *why* it could not be
   read is lost, which is the part of EVALS §3.2 ("say what could not be read")
   that is still unmet.
2. **`test_refusals.RefusalInventionTests.test_a_refused_name_is_not_rendered_as_the_string_none`**
   — C-016 ("name illegible on this sheet") reaches `handoff.md` as
   `## Bed 36 — None` and `- Bed 36 None: remove drain 18:00`. The refusal is
   correctly recorded and correctly named in `gaps.md`, but
   `src.compose._patient_lines` interpolates `name_as_written` directly, so an
   absent name prints as the literal `None` in the clinician-facing document.

## Assertions deliberately not made

- The injection quote is **not** asserted to appear inside `audit.jsonl` itself.
  `audit.run_end` records an injection *count*, and the quote and page live in
  `summary.json` and `gaps.md`. EVALS §5 requires that injections be "logged, not
  obeyed", and both are satisfied; asserting per-quote records in `audit.jsonl`
  would have invented a requirement the repo does not state. No test was deleted
  for dishonesty — every attempted assertion either held or was kept as the
  defect-marked failure above.
