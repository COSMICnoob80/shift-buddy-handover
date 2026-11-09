# src/ — intentionally empty until the window opens

No product code lives here before **Fri 27 Nov 2026, 23:00 PKT**.

That is not laziness; it is the Agentware eligibility rule. Project code must be written inside
the 72-hour window, and a pre-built pipeline would disqualify the entry.

What lands here at 23:00, in this order (see `RUNBOOK.md`):

```
src/
  ingest.py        page detection, ordering, hashing
  extract.py       OCR + local NER, every field with page + bbox + confidence
  structure.py     deterministic normalisation and action extraction
  rules.py         contradictions, duplicates, missing mandatory fields
  compose.py       SBAR prose from structured facts only
  verify.py        the counterweight: no number in prose that is not in the facts
  cli.py           watch inbox/, run, honour STOP
evals/
  run.py           the 40-case runner and scorecard
```

If you are reading this after 30 November and the files are absent, the entry was not built —
and that is the honest record, not something to retro-fill.
