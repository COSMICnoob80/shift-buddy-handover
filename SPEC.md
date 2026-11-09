# SPEC — Shift Buddy Handover agent

Version 0.1 · 2026-11-08 · status: draft, pre-window

---

## 1. The problem, stated without decoration

At shift change, a doctor hands over 20–30 patients using paper notes, a ward register and
memory. What gets lost is not the diagnosis — it is the *action*: the repeat troponin at 6am,
the consent form still unsigned, the family that was promised a call, the antibiotic day count.

Lost actions become incidents. The handoff is the highest-risk document in the hospital and it
is usually a scrap of paper.

## 2. What the agent does

**Trigger.** Photographs of the paper notes are placed in `inbox/` (or a watched folder). No
button press. The agent runs unattended on its own schedule.

1. **Ingest** — read each image, detect page count, order pages, refuse unreadable pages by
   name rather than guessing.
2. **Extract** — per patient: bed/ID as written, presenting problem, active issues, pending
   results, medications with day counts, outstanding actions, who is covering.
3. **Reconcile** — flag contradictions between pages (two different drug doses, a patient
   appearing twice, a bed number reused).
4. **Compose** — write an **SBAR** handoff per patient plus a single **shift summary** of every
   outstanding action, each line carrying its source page.
5. **Audit** — append a JSONL record: input hashes, model used, per-field confidence, what was
   refused, when it started and stopped.
6. **Stop.** No transmission. No diagnosis. No prescription. Exit clean.

## 3. What it must never do

| Prohibited | Why |
|---|---|
| State or imply a diagnosis | Not a clinical decision-support tool; liability without a regulatory pathway |
| Suggest a drug, dose or change | Same, and it invites silent acceptance |
| Send anything anywhere (email, chat, cloud) | Patient data must not leave the machine |
| Present a field it could not read as if it read it | A hallucinated bed number is worse than a blank |
| Continue after a kill signal | The stop must be honoured mid-run, not at the next checkpoint |

## 4. Stop conditions (explicit)

- `STOP` file appears in the working directory → finish the current file atomically, write the
  audit record, exit 0.
- Kill switch invoked from the UI/CLI → same, within 2 seconds.
- Model unavailable → write what was extracted deterministically, mark the narrative sections
  `UNAVAILABLE`, exit 0. Never hang.
- Unreadable page → record it, continue with the rest, surface it in the gap list.

## 5. Output contract

```
out/<shift-date>/
  handoff.md            one SBAR block per patient, source page per line
  gaps.md               unresolved actions, unreadable pages, contradictions
  audit.jsonl           one record per patient + one per run
  summary.json          machine-readable, schema in ARCHITECTURE.md §4
```

## 6. Success criteria

| Measure | Threshold |
|---|---|
| Patients correctly identified from 3 test sheets | 100% of legible entries |
| Hallucinated fields (a value not on the page) | **0** — a single one fails the run |
| Unreadable pages surfaced, not guessed | 100% |
| Time from photos to handoff | < 5 minutes for 20 patients |
| Kill switch honoured | < 2 seconds, audit intact |
| Data leaving the machine | 0 bytes |

## 7. Out of scope, explicitly

Live hospital system integration, multi-user accounts, mobile app, cloud sync, scheduling,
billing, and anything requiring a regulatory submission. Each of those kills the 72-hour window.
