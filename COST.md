# COST — what a run costs

Measured on the build machine (Lenovo V14 G3 IAP, 12th-gen i5, CPU only, no GPU).
Commands and numbers are reproduced verbatim from the runs of 2026-11-28.

## 1. Money

| Line item | Cost per run |
|---|---|
| Cloud API calls | **$0.00** — no cloud client exists in the codebase |
| OCR | **$0.00** — local RapidOCR (ONNX, bundled models), CPU |
| Narration model | **$0.00 marginal** — local GGUF (`SBH_MODEL_PATH`), CPU-only; absent by default, in which case the templated composer writes the handoff |
| Storage | ~40 KB per run (`handoff.md`, `gaps.md`, `summary.json`, `status.json`, `audit.jsonl`) |

There is no API key in this project. `.env.example` holds paths and limits only.

## 2. Machine time

| Measurement | Command | Result |
|---|---|---|
| One two-page run, end to end | `/usr/bin/time -v .venv/bin/python -m src.cli run --inbox … --out …` | **0.40 s wall**, 0.16 s user CPU, 17.8 MB peak RSS |
| The 40-case trap pack | `/usr/bin/time .venv/bin/python -m evals.run --cases fixtures/cases.json` | **11.7 s wall**, 18.2 MB peak RSS, 0.03 s per case average |
| Kill switch, detected to exit | `tests/test_killswitch.py` | measured in the test; requirement < 2 s |

A night-shift handover is 2–8 pages, so a real run is sub-second on this hardware without the
local model. With a small local GGUF on the same CPU the narration step dominates; the
composer falls back to templates when the model exceeds its time budget, so the wall clock is
bounded by design (ARCHITECTURE §5).

## 3. Human time

| Step | Time |
|---|---|
| Drag photos into `inbox/` | seconds |
| Read `handoff.md` + `gaps.md` | 2–4 minutes (that reading is the point; the agent does not replace it) |
| Resolve a refused page by photographing it again | one page, one photo |

## 4. What is deliberately not optimised

Throughput. This is one ward, one shift, one machine. A run that finishes in half a second is
already faster than the person who has to read it, and every added dependency is a new way for
the tool to fail at 03:00.
