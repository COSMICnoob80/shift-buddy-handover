# Shift Buddy Handover

**A ward handover agent: photographs of paper notes in, a structured SBAR handoff plus a gap
list out, unattended, on one machine, with a kill switch.**

Status: **pre-work only.** Design, work orders and test data are committed; product code is
written only inside the window — see the rule below.

---

## Why this repo exists

`shift-buddy-v2` is a React Native app with 387 files and 131 tests that has never been used on
a real ward. That is the failure this repo is designed not to repeat: the app became the
project, and the handoff never shipped.

This repo is the opposite shape. It is an **agent**, not an app:

```
photos land in a watched folder
        ↓
parse → structure → check against the rulebook
        ↓
SBAR handoff + gap list + audit trail (files on disk)
        ↓
stop. no network calls to anything but the local model. no sends.
```

## The Agentware rule that shapes everything here

Agentware 2026 runs **Fri 27 Nov 23:00 PKT → Mon 30 Nov 23:00 PKT**, and the rules require
project code to be **written inside the 72-hour window**.

| Allowed before the window | Not allowed before the window |
|---|---|
| This spec, architecture, demo script | Working product code |
| Synthetic handoff cases (data) | A functioning pipeline |
| Evaluation rubric, kill-switch test plan | Anything that runs end to end |
| Soldier work orders, permissions table | Scripts, prototypes, mockups (code is code) |

So what you find here is **the whole design, the work orders and the test data**, and nothing
that executes. At 23:00 on 27 November the window opens and this becomes assembly, not discovery.

## Setup (skeleton — filled during the window)

```bash
cp .env.example .env      # paths + limits only; no cloud keys exist in this project
mkdir -p inbox out
# requirements and the run command land here during the window — they cannot be
# written before kickoff without shipping pre-window code
```

Permissions and prohibitions are enforced in code, not by prompting — see `PERMISSIONS.md`.

## Read in this order

1. `SPEC.md` — what the agent does, what it refuses to do, and the stop conditions.
2. `ARCHITECTURE.md` — deterministic core, model narrates, nothing computes silently.
3. `EVALS.md` — the 40-case trap pack, and what a pass looks like.
4. `DEMO-SCRIPT.md` — 90 seconds, shot by shot.
5. `RUNBOOK.md` — the 72-hour calendar with gates.
6. `work-orders/` — the three soldier briefs (ingestion / structuring / guardrails), written
   before the window so kickoff starts with dispatch.
7. `PERMISSIONS.md` — the enforced permissions table.
8. `fixtures/cases.json` — forty synthetic handoffs, twenty deliberately broken.

## Non-negotiables

- **Never diagnoses, never prescribes, never sends.** It drafts a handoff for a human to read.
- **Local only.** No patient data leaves the machine; the model runs where the notes run.
- **Kill switch cancels pending work** and leaves the audit trail intact.
- **Every output names its source page.** No claim without a page reference.

## What "done" means

One ward, one shift, one real handover produced from photographs in under five minutes, with a
gap list a nurse agrees with. Not a demo video. A handover someone actually used.

## Scorecard

The 40-case trap pack, run end to end against the real CLI, plus a live kill-switch timing:

```
cases passed                                         40/40
hallucinations                                           0
contradictions caught                                  6/6
injections ignored                                     7/7
refusals named                          10 across 10 cases
kill switch honoured in                           0.1125 s
timeouts                                                 0
```

Run it yourself:

```bash
bash tools/scorecard.sh
```

Each run writes `evals/runs/<UTC timestamp>/`; the full per-case PASS/FAIL table is
[`evals/runs/20261127T194221Z/scorecard.md`](evals/runs/20261127T194221Z/scorecard.md). The
numbers above are pasted from that run. "Hallucinations 0" means the verifier found no value in
the composed prose that was absent from the parsed facts — every number, dose, bed, time and
identifier in the handoff is traceable to an input page. It is a measured count, not a claim.

## Demo

Two commands reproduce the 90-second demo offline:

```bash
# build the demo inbox from the fixtures (deterministic, filename contract enforced)
.venv/bin/python tools/render_sheets.py --cases fixtures/cases.json --out inbox/demo/

# render -> run -> print the six quoted lines -> prove the kill switch
bash tools/make_demo.sh
```

The shot list, timings and the "what not to do" list are in [`DEMO-SCRIPT.md`](DEMO-SCRIPT.md).
The demo deliberately includes one unreadable page and one handwriting refusal: the point is what
the agent declined to invent.

