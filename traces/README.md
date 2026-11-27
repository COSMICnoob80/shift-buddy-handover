# traces/ — the receipts

One committed run, unedited, straight out of `bash tools/make_demo.sh` on 2026-11-28 at
01:22 PKT (run_id `2026-11-28T01:22:06+05:00`). Nothing here was written by hand.

| File | What it is |
|---|---|
| `audit.jsonl` | 17 records: `run_start` (every input page with its sha256), one `patient` record per bed with pages, confidence, refusals and ambiguities, then `run_end` (exit_reason, duration, verify result, counts). One JSON object per line, append-only, replayable. |
| `handoff.md` | The SBAR handoff the run wrote. Every clinical line ends in the page it came from. |
| `gaps.md` | What could not be read, what was never recorded, and every contradiction with both pages cited. |
| `status.json` | The live state file the run keeps during execution (state, exit_reason, patients, unreadable pages, contradictions, injections, verifier result). |
| `summary.json` | The parsed facts per patient with per-item confidence — what the run *saw*, before anything was composed into prose. |

The run: 9 fixture pages in `inbox/` → 15 patients, 1 unreadable page (page 7 is a 0-byte
file, named with that reason), 1 contradiction (meropenem 1 g on page 3, 2 g on page 4, both
quoted), 2 refusals, 1 prompt injection quoted and acted on nowhere, verifier `ok: true`,
0 hallucinated fields.

Reproduce it on your own clone in about three seconds: `bash tools/make_demo.sh`, then read
`out/demo/<date>/`. The kill-switch half of that script starts a second run and touches
`STOP` mid-ingest; its timing is printed, not stored, so it cannot go stale in this repo.
