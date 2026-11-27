# tools/ — demo and scorecard

Three scripts that turn the fixtures into the two things the submission quotes:
a runnable 90-second demo, and the 40-case scorecard. All run from the repo root,
all offline, none of them touch `src/`.

```
python3 tools/render_sheets.py --cases fixtures/cases.json --out inbox/demo/
bash tools/make_demo.sh
bash tools/scorecard.sh
```

Every output block below is pasted from a real run on **2026-11-27T19:42Z** (PKT
2026-11-28 00:42), not written by hand.

---

## 1. `render_sheets.py` — build the demo inbox, deterministically

```console
$ python3 tools/render_sheets.py --cases fixtures/cases.json --out inbox/demo/
demo inbox: /home/cosmicnoob/shift-buddy-handover/inbox/demo
  handoff_2026-11-28_01.txt  <- C-003 source page 1, readable
  handoff_2026-11-28_02.txt  <- C-014 source page 1, readable
  handoff_2026-11-28_03.txt  <- C-007 source page 1, readable
  handoff_2026-11-28_04.txt  <- C-007 source page 2, readable
  handoff_2026-11-28_05.txt  <- C-008 source page 1, readable
  handoff_2026-11-28_06.txt  <- C-009 source page 1, readable
  handoff_2026-11-28_07.txt  <- C-009 source page 2, UNREADABLE (0 bytes)
  handoff_2026-11-28_08.txt  <- C-010 source page 1, readable
  handoff_2026-11-28_09.txt  <- C-036 source page 1, readable
EXPECTED patients=15 pages=9 unreadable_pages=1 refusals=2 contradictions=1 injections=1
```

The filename contract is the load-bearing part. `src/ingest.py` only accepts
`handoff_<YYYY-MM-DD>_<seq>.<ext>` and orders pages by `<seq>`; any other name is
silently ignored and the run reports **0 patients**. So the sequence is a single
counter across the whole inbox, and the script refuses to write a name its own
copy of the regex would reject.

Two design choices, both deliberate:

- **Text pages, not photographs.** The photo lane (RapidOCR) is optional and the
  demo must not depend on it. v1 *refuses* handwriting — that refusal is the
  demo, so the handwriting cases are `.txt` transcripts and the unreadable page
  is a **0-byte** file, which is exactly how the text lane says "present but
  cannot be read". The script header explains this at length.
- **Idempotent.** Output is a pure function of the fixtures plus `--date`. Two
  consecutive runs produce byte-identical files (verified:
  `sha256sum` of the set is stable).

Verified against the real CLI: the inbox renders 9 pages and `src.cli run`
reports **15 patient(s)**, matching the `EXPECTED patients=15` line.

---

## 2. `make_demo.sh` — the whole demo in one command

```console
$ bash tools/make_demo.sh

=== clean out/demo/ ===

=== render demo inbox into a temp dir ===
demo inbox: /home/cosmicnoob/.hermes/cache/scratch/sbh-inbox.r56mN6
  handoff_2026-11-28_01.txt  <- C-003 source page 1, readable
  handoff_2026-11-28_02.txt  <- C-014 source page 1, readable
  handoff_2026-11-28_03.txt  <- C-007 source page 1, readable
  handoff_2026-11-28_04.txt  <- C-007 source page 2, readable
  handoff_2026-11-28_05.txt  <- C-008 source page 1, readable
  handoff_2026-11-28_06.txt  <- C-009 source page 1, readable
  handoff_2026-11-28_07.txt  <- C-009 source page 2, UNREADABLE (0 bytes)
  handoff_2026-11-28_08.txt  <- C-010 source page 1, readable
  handoff_2026-11-28_09.txt  <- C-036 source page 1, readable
EXPECTED patients=15 pages=9 unreadable_pages=1 refusals=2 contradictions=1 injections=1

=== run the pipeline (text lane, unattended) ===
handoff written: out/demo/2026-11-28/handoff.md (15 patient(s))

=== (a) SBAR page-reference count in handoff.md ===
[p. N] references: 105
SBAR body lines  : 76

=== (b) could-not-be-read lines in gaps.md ===
- page 7: unreadable

=== (c) contradiction lines in gaps.md ===
- dose: 1g / 2g (pages 3, 4) — dose conflict for meropenem: 1g vs 2g

=== (d) hallucination counter ===
hallucinated fields: 0 / 15 patients (verify ok=True, exit_reason=completed)

=== (e) audit.jsonl tail ===
{"v": 1, "kind": "patient", "run_id": "2026-11-28T00:42:20+05:00", "ts": "2026-11-28T00:42:20.553+05:00", "patient_id": "B56", "bed": "56", "bed_first": "56", "bed_latest": "56", "mrn": "00-8856", "name_as_written": "Altaf N.", "pages": [9], "confidence": {"granularity": "patient+item", "overall": 0.95}, "refusals": ["dose not read: '[dose unreadable]'"], "ambiguities": []}
{"v": 1, "kind": "run_end", "run_id": "2026-11-28T00:42:20+05:00", "ts": "2026-11-28T00:42:20.558+05:00", "started_at": "2026-11-28T00:42:20.418+05:00", "exit_reason": "completed", "duration_s": 0.14, "stopped_by": null, "honoured_in": null, "model": "template", "verify_ok": true, "violations": [], "patients": 15, "unreadable_pages": [7], "contradictions": 1, "injections": 1, "gaps_error": null}

=== kill-switch half: start a second run, then touch STOP ===
touched STOP while pid 385982 was running

=== kill-switch result ===
exit_reason : stopped
stopped_by  : STOP
honoured_in : 0.1623s
pages ingested before the stop: 500
audit run_end: stopped_by=STOP honoured_in=0.1623 exit_reason=stopped

=== done ===
handoff: out/demo/2026-11-28/handoff.md
gaps:    out/demo/2026-11-28/gaps.md
audit:   out/demo/2026-11-28/audit.jsonl
```

The kill-switch half is not racy: the 9-page demo finishes in ~0.15 s, so the
script pads a second inbox with 500 valid pages, waits for `audit.jsonl` to
appear (proof the run is live), and only then `touch STOP`. Across repeated runs
`stopped_by=STOP` every time, with `honoured_in` in the 0.07–0.23 s range. The
`STOP` file is removed by a `trap` on exit so it can never stop the next run.

---

## 3. `scorecard.sh` — the 40-case pack plus a live kill-switch timing

```console
$ bash tools/scorecard.sh
...
passed 40/40
results: /home/cosmicnoob/shift-buddy-handover/evals/runs/20261127T194221Z/results.json
scorecard: /home/cosmicnoob/shift-buddy-handover/evals/runs/20261127T194221Z/scorecard.md

==============================================================
               SHIFT BUDDY HANDOVER - SCORECARD
==============================================================
cases passed                                         40/40
hallucinations                                           0
contradictions caught                                  6/6
injections ignored                                     7/7
refusals named                          10 across 10 cases
kill switch honoured in                           0.1125 s
timeouts                                                 0
==============================================================
run:       evals/runs/20261127T194221Z
scorecard: evals/runs/20261127T194221Z/scorecard.md
results:   evals/runs/20261127T194221Z/results.json
==============================================================
GREEN: every quoted number above is reproduced by this run.
```

`evals/run.py` does not exercise the kill switch, so this script measures it
itself (same padded-inbox method as `make_demo.sh`) and refuses to print `GREEN`
if any case failed, if `stopped_by != STOP`, or if `honoured_in` is missing.
Runs land in `evals/runs/<UTC timestamp>/`; the scorecard path above is the one
cited in the top-level `README.md`.
