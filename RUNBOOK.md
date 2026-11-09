# RUNBOOK — the 72 hours

Window: **Fri 27 Nov 23:00 PKT → Mon 30 Nov 23:00 PKT**. Code is written inside it; everything
else in this repo is already done.

---

## Pre-window checklist (by 26 Nov)

- [ ] 40 fixture cases complete (10 today, 30 to author)
- [ ] Trap pack read the hour it drops (released at kickoff — do not plan around it, plan to adapt)
- [ ] Local model downloaded and benchmarked once (speed on this laptop, not on a spec sheet)
- [ ] OCR path tested on handwriting, honestly — if it fails, the demo is "refusal quality"
- [ ] Submission form, repo link, demo capture tool all ready
- [ ] Sleep scheduled: 6 hours on Sat night, not "later"

## The 72 hours

**Fri 23:00–24:00 — Read, do not code.**
Read the trap pack, the rubric, and this RUNBOOK. Write the one-page checklist of what changed
versus this plan. Only then open an editor.

**Fri 00:00–06:00 — The spine.**
`ingest → extract → structure → compose → verify → out`, each as a function with a fixture
test. Hardcoded paths, no config. **Gate: one case end to end, handoff.md exists.**

**Sat 06:00–10:00 — Sleep.**

**Sat 10:00–18:00 — Verification and refusals.**
The verifier (no invented numbers), unreadable-page handling, contradiction reporting.
**Gate: three cases pass, hallucination count 0.**

**Sat 18:00–22:00 — Kill switch + audit.**
STOP file, timing, audit record completeness. **Gate: kill in < 2s, audit intact.**

**Sat 22:00–06:00 — Sleep (6h) then buffer.**

**Sun 06:00–14:00 — Run all 40 cases.**
No new features. Fix only what the table shows. **Gate: written scorecard, failures named.**

**Sun 14:00–18:00 — Demo capture.**
Record the 90 seconds exactly as scripted. Two takes maximum; polish is not a feature.

**Sun 18:00–22:00 — Submission text.**
README opens with the problem, one screenshot, the scorecard, the kill-switch proof.

**Sun 22:00–Mon 12:00 — Sleep, then final verification pass.**

**Mon 12:00–18:00 — Buffer. Re-run evals from a clean clone.**

**Mon 18:00–20:00 — Submit.**
Not at 22:59. Submission failures at the deadline are the most common way good work dies.

## Hard gates — if a gate fails, cut scope, never the gate

1. One case end to end.
2. Zero hallucinations on three cases.
3. Kill switch under 2 seconds with audit intact.
4. All 40 cases scored, including the failures.

## If it goes wrong

| Failure | Response |
|---|---|
| OCR unusable on handwriting | Pivot the demo to **refusal quality**: "it tells you what it can't read" |
| Local model too slow | Templated SBAR from structured facts (pre-approved in ARCHITECTURE §5) |
| Verifier too strict / too loose | Tighten to exact-match on numbers only; identifiers are the danger |
| Time lost to setup | Cut contradiction detection; keep refusals and the verifier |
