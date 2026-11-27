# Agentware 2026 — submission form fields (paste-ready)

Deadline: submissions due **Mon 30 Nov 2026, 18:00 UTC = 23:00 PKT**. Freeze Sun 29 Nov 21:00 PKT.
Write it as if the form asks; each block below is one field.

---

## Track

```
Open
```

## Project name

```
Shift Buddy Handover
```

## One-line pitch

```
Photographed night-shift paper notes become a structured, signed SBAR handoff and a gap list — unattended, local-only, kill-switched.
```

## Repo URL (public, MIT)

```
https://github.com/COSMICnoob80/shift-buddy-handover
```

## Demo video URL (2 min, under the 3-minute cap)

```
https://github.com/COSMICnoob80/shift-buddy-handover/blob/master/demo/shift-buddy-handover-demo.mp4
```

## What it does (one paragraph)

```
On a hospital ward the night handover is often a scrap of paper: crossed-out doses, a phone number in the margin, an action someone meant to chase. Shift Buddy Handover takes photographs of those sheets, drops them in a watched folder, and — with nobody at the keyboard — writes a structured SBAR handoff, a gap list, and a replayable audit trail. Every line of the handoff ends in the page it came from. Every page it could not read is named with its reason. Every contradiction is quoted from both pages rather than resolved by guessing. A verifier re-reads the composed prose and fails the run if any value in it is absent from the parsed facts. It never diagnoses, never prescribes, never sends, and never touches the network.
```

## How the numbers were produced (paste the scorecard block verbatim)

```
cases passed                                         40/40
hallucinations                                           0
contradictions caught                                  6/6
injections ignored                                     7/7
refusals named                          10 across 10 cases
kill switch honoured in                            0.1113 s
timeouts                                                 0
```

```
Reproduce: git clone, cp .env.example .env, mkdir -p inbox out, bash tools/scorecard.sh
Per-case table: evals/runs/20261127T194221Z/scorecard.md (and the post-fix re-run in evals/runs/final-check/)
50 guardrail tests: python3 -m unittest discover -s tests
Requirements: Python 3.10+, standard library only. No keys, no network, no GPU, no model download.
```

## The kill switch paragraph

```
The kill switch is a file, not a prompt. A cheap poll runs between pages and between stages, so whatever is in flight finishes atomically before the run unwinds. `touch STOP` (or `python3 -m src.cli kill`) stops the run, marks status.json with stopped_by: STOP and the honoured_in seconds it actually took, and leaves the audit trail intact — nothing partial is left unmarked. Measured on this machine at 0.09–0.12 s from the file appearing to the process exiting, and the demo video shows it firing mid-run on a 500-page inbox (a nine-page run finishes in 0.16 s, so there is nothing to interrupt).
```

## Safety, one line per bonus criterion

```
Guardrails in code — every value in the handoff must appear on a source page (src/verify.py gates the run); no diagnose/prescribe/send tool exists; writes are confined to --out.
Live monitoring — status.json exposes state, exit_reason, patients, unreadable pages, contradictions, injections and verifier violations while the run is going; out/<date>/audit.jsonl carries one JSON record per decision and refusal, replayable.
Kill switch — STOP file, polled between pages and stages, timed and recorded (see above).
Audit trail — audit.jsonl: run_start, per-page ingest with sha256, per-patient record with refusals/ambiguities, run_end with exit_reason, stopped_by, honoured_in, verify result.
```

## What I did not fix (honest limits — paste as-is)

```
v1 does not read handwriting. It refuses the page by name and lists it in the gap list. That is the real constraint: a tool for a ward full of pen-and-paper is only as good as its camera lane, and the camera lane is the part that is not finished.
The demo pages are fixtures exercising the text lane plus one 0-byte unreadable page — not camera photographs.
The composer is a deterministic template, not an LLM (model: template in status.json). The local-GGUF narrative lane is specified in STACK-FREEZE.md but not wired into the submitted path, so a judge's run has no model to download and no variance to explain.
No real patient data has ever been through this code. It drafts a handoff for a clinician to read; it is not a medical device.
```

## Cost statement (paste if a field asks)

```
Zero. No API keys, no cloud calls, no model download. A full 40-case trap-pack run plus a live kill-switch timing takes ~11 s of one CPU core and costs nothing. See COST.md.
```
