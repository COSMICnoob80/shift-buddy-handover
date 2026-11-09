# Shift Buddy Handover

**A ward handover agent: photographs of paper notes in, a structured SBAR handoff plus a gap
list out, unattended, on one machine, with a kill switch.**

Status: **pre-work only.** No product code lives here yet, deliberately — see the rule below.

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

So what you find here is **the whole design and the test data**, and nothing that executes.
At 23:00 on 27 November the window opens and this becomes assembly, not discovery.

## Read in this order

1. `SPEC.md` — what the agent does, what it refuses to do, and the stop conditions.
2. `ARCHITECTURE.md` — deterministic core, model narrates, nothing computes silently.
3. `EVALS.md` — the 40-case trap pack, and what a pass looks like.
4. `DEMO-SCRIPT.md` — 90 seconds, shot by shot.
5. `RUNBOOK.md` — the 72-hour calendar with gates.
6. `fixtures/cases.json` — ten synthetic handoffs, three deliberately broken.

## Non-negotiables

- **Never diagnoses, never prescribes, never sends.** It drafts a handoff for a human to read.
- **Local only.** No patient data leaves the machine; the model runs where the notes run.
- **Kill switch cancels pending work** and leaves the audit trail intact.
- **Every output names its source page.** No claim without a page reference.

## What "done" means

One ward, one shift, one real handover produced from photographs in under five minutes, with a
gap list a nurse agrees with. Not a demo video. A handover someone actually used.
