# Agentware 2026 — submission form fields (paste-ready)

Deadline (authoritative, from agentwarehack.com/brief/): **Mon 30 Nov 2026, 18:00 UTC = 23:00 PKT**.
Freeze Sun 29 Nov 21:00 PKT. Submit with a day of buffer — do not plan for 23:00.
The submission form is sent by email and posted on the event Discord at kickoff; it is not a
public URL. Everything below is written so it can be pasted field by field.

---

## Discord post (if the submission is a Discord message)

```
Shift Buddy Handover — Open track — solo

Repo: https://github.com/COSMICnoob80/shift-buddy-handover  (MIT)
Video (1:52, real terminal run): https://github.com/COSMICnoob80/shift-buddy-handover/blob/master/demo/shift-buddy-handover-demo.mp4
Trace (one committed run): https://github.com/COSMICnoob80/shift-buddy-handover/tree/master/traces/2026-11-28-demo

Photographs of a night-shift paper handoff land in a watched folder; with nobody at the
keyboard the agent writes a structured SBAR handoff (every line ending in the page it came
from), a gap list (unreadable pages named with the reason, contradictions quoted from both
pages, missing mandatory fields listed), and a replayable audit trail. It refuses rather than
guesses, never diagnoses, never prescribes, never sends, never touches the network.

Numbers from `bash tools/scorecard.sh`, reproduced on a clean clone:
40/40 trap-pack cases · 0 hallucinations · 6/6 contradictions · 7/7 injections ignored ·
10 refusals named across 10 cases · kill switch honoured in 0.11 s · 0 timeouts ·
50 guardrail tests green.

Not fixed, and said in the README: v1 does not read handwriting — it refuses the page by name
and lists it. The demo pages are rendered sheets plus one 0-byte unreadable page, not camera
photos. The composer is a deterministic template, not an LLM, so a judge's run has no model to
download and no variance to explain.
```


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
The kill switch is a file, not a prompt. A cheap poll runs between pages and between stages, so whatever is in flight finishes atomically before the run unwinds. `touch STOP` (or `python3 -m src.cli kill`) stops the run, marks status.json with stopped_by: STOP and the honoured_in seconds it actually took, and leaves the audit trail intact — nothing partial is left unmarked. Measured on this machine at 0.08–0.15 s from the file appearing to the process exiting, and the demo video shows it firing mid-run on a 500-page inbox (a nine-page run finishes in about 0.2 s, so there is nothing to interrupt).
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
