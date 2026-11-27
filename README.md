# Shift Buddy Handover

**A ward handover agent: photographs of paper notes in, a structured SBAR handoff plus a gap
list out, unattended, on one machine, with a kill switch.**

Agentware 2026 · open track · solo. All product code in this repo was written inside the
72-hour window (kickoff Fri 27 Nov 2026 23:00 PKT).

**Demo video (2 minutes, real terminal run):** [demo/shift-buddy-handover-demo.mp4](https://github.com/COSMICnoob80/shift-buddy-handover/blob/master/demo/shift-buddy-handover-demo.mp4)

**One committed run, unedited (the trace):** [`traces/2026-11-28-demo/`](traces/2026-11-28-demo/) — 9 pages in,
15 patients out, `audit.jsonl` with a sha256 per input page, `handoff.md`, `gaps.md`, `summary.json`.
Read [`traces/README.md`](traces/README.md) first; reproduce it in three seconds with `bash tools/make_demo.sh`.

---

## What it does, in one paragraph

On a hospital ward, the night handover is often a scrap of paper: crossed-out doses, a phone
number in the margin, an action someone meant to chase. Shift Buddy takes photographs of those
sheets, drops them in a watched folder, and — with nobody at the keyboard — writes three files:
`handoff.md` (one SBAR block per patient, every line ending in the page it came from),
`gaps.md` (what could not be read, what was never recorded, and every contradiction with both
pages cited), and `audit.jsonl` (every decision, every refusal, replayable). It never diagnoses,
never prescribes, never sends, and never leaves the machine. A `STOP` file stops it mid-run.

The design rule is the one that matters for a medical tool: **it refuses rather than guesses.**
A page it cannot read is named, with the reason. A dose it cannot parse is left blank and
listed. Two pages that disagree are both quoted. The verifier then re-reads the composed prose
and fails the run if any value in it is absent from the parsed facts — that is what
"hallucinations 0" measures.

## Requirements

Python 3.10 or newer, **standard library only** — no `pip install`, no API keys, no network, no
GPU, no model download. Verified cold on Linux with Python 3.14.

The photographed-page (OCR) lane is optional and needs one extra package; see
[Photographed pages](#photographed-pages-optional) below. Everything else runs on a bare
Python.

## Quick start

```bash
git clone https://github.com/COSMICnoob80/shift-buddy-handover.git
cd shift-buddy-handover
cp .env.example .env          # paths and limits only; there are no cloud keys in this project
mkdir -p inbox out

python3 -m unittest discover -s tests     # 50 tests, ~4 s
bash tools/scorecard.sh                   # the 40-case trap pack + a live kill-switch timing
bash tools/make_demo.sh                   # the full demo, end to end, in ~3 s
```

Those four commands are the whole cold run. Measured on a fresh clone: clone 0.06 s, tests
4.1 s, scorecard ~11 s, demo ~3 s.

## The numbers, and where they come from

```
cases passed                                         40/40
hallucinations                                           0
contradictions caught                                  6/6
injections ignored                                     7/7
refusals named                          10 across 10 cases
kill switch honoured in                            0.1113 s
timeouts                                                 0
```

`bash tools/scorecard.sh` reproduces every line above and exits non-zero if any of them fails.
Each run writes `evals/runs/<UTC stamp>/`; the commits carry the run that produced the numbers
in the submitted tree — [`evals/runs/20261127T194221Z/scorecard.md`](evals/runs/20261127T194221Z/scorecard.md)
is the per-case PASS/FAIL table, and
[`evals/runs/final-check/scorecard.md`](evals/runs/final-check/scorecard.md) is the same pack
re-run after the last three defect fixes. The kill-switch figure is wall-clock on this machine
and moves between runs (0.08 s – 0.12 s); it is measured live by the script, not stored, so the
0.1113 s above is the figure from the run immediately before freeze, not a constant.

The 40 cases in [`fixtures/cases.json`](fixtures/cases.json) are synthetic handoffs, twenty of
them deliberately broken: unreadable pages, conflicting doses, prompt injections, missing
mandatory fields, refusals. They are data, not real patients. See [`EVALS.md`](EVALS.md) for
the rubric each case is scored against.

## Run it on real pages

```bash
# the fixture pages, rendered as a demo inbox (deterministic, filename contract enforced)
python3 tools/render_sheets.py --cases fixtures/cases.json --out inbox

# one run over whatever is in inbox/
python3 -m src.cli run --inbox inbox --out out

# or watch the folder and run on new pages as they land
python3 -m src.cli watch --inbox inbox --out out
```

Output lands in `out/<YYYY-MM-DD>/`: `handoff.md`, `gaps.md`, `summary.json`, `status.json`,
`audit.jsonl`.

Page files must follow the filename contract `handoff_<YYYY-MM-DD>_<seq>.txt` (page order comes
from `<seq>`, never from directory order). For example:

```
inbox/handoff_2026-11-28_01.txt
inbox/handoff_2026-11-28_02.txt
inbox/handoff_2026-11-28_03.png
```

## Photographed pages (optional)

The `.txt` lane is a typed drop, a voice transcript or a fixture — it needs nothing. The
`.jpg` / `.png` lane runs RapidOCR:

```bash
python3 -m pip install rapidocr_onnxruntime onnxruntime
```

If that package is missing, the agent does **not** crash and does **not** invent text: the page
is refused by name in `gaps.md` —

```
## Unreadable pages
- page 1: OCR failed: ModuleNotFoundError: No module named 'rapidocr_onnxruntime'
```

That is the intended failure. Note that v1 refuses **handwriting** by design; the OCR lane is
for printed or typed pages. The measured evidence for that decision, including the residual
risk in the assisted lane, is in [`STACK-FREEZE.md`](STACK-FREEZE.md) and
[`SAFETY.md`](SAFETY.md).

## The kill switch

```bash
python3 -m src.cli run --inbox inbox --out out &   # a run in flight
python3 -m src.cli kill                            # or: touch STOP
```

The run stops at the next checkpoint (between pages, between stages), marks itself
`stopped_by: STOP` with the `honoured_in` seconds it actually took, and leaves the audit trail
intact — nothing partial is left unmarked. Measured 0.09–0.12 s from the file appearing to the
process exiting. The demo script proves it on a 500-page inbox, because a nine-page run
finishes in 0.16 s and there is nothing to interrupt.

## What is enforced in code, not by prompting

| Rule | Where it is enforced |
|---|---|
| Every value in the handoff appears on a source page | `src/verify.py`, gates every run, violations fail the run |
| Never diagnoses, prescribes or sends | no such tool exists; `PERMISSIONS.md` is the table, `AGENT.md` the manifest |
| Read-only on the inbox, writes only under `--out` | `src/cli.py` path checks |
| Injected instructions are quoted, never followed | `src/structure.py` treats page text as data; the injection lands in `gaps.md` verbatim |
| Stops within a bounded time of `STOP` | `src/killswitch.py`, polled between pages |

Details, including the audit-trail format and the monitored fields, are in
[`SAFETY.md`](SAFETY.md).

## Honest limits

- **v1 does not read handwriting.** It refuses the page and says so. That is the largest real
  constraint, and it is the Near Miss write-up: a tool for a ward full of pen-and-paper is only
  as good as its camera lane, and the camera lane is the part that is not finished.
- **The demo pages are fixtures, not photographs.** They exercise the text lane plus one
  0-byte unreadable page. The OCR lane is real code but is not what the demo video shows.
- **The composer is a deterministic template, not an LLM.** `model: template` in `status.json`.
  The local-GGUF narrative lane is specified and frozen in `STACK-FREEZE.md` but not wired into
  the submitted path, so a judge's run has no model to download and no variance to explain.
- **The kill-switch number is a wall-clock measurement on one laptop** (i5-1235U). It will
  differ on yours. The guarantee is "bounded and recorded", not the exact figure.
- **Not clinically validated.** No real patient data has ever been through this code. It drafts
  a handoff for a clinician to read; it is not a medical device.

## What is in here

| File | What it is |
|---|---|
| `AGENT.md` | the manifest: what runs, which tools, which permissions, which track |
| `SAFETY.md` | guardrails, kill switch, monitoring, audit trail — what is enforced in code |
| `SPEC.md` · `ARCHITECTURE.md` | what it does, what it refuses, how the pieces fit |
| `EVALS.md` · `tests/` · `fixtures/` | the 40-case trap pack, the 50 guardrail tests, the data |
| `STACK-FREEZE.md` · `COST.md` | frozen stack and config; what a run costs (nothing) |
| `tools/` | `scorecard.sh`, `make_demo.sh`, `render_sheets.py` — every claim, reproducible |
| `out/` · `inbox/` | the watched folder and the results (git-ignored) |

## Licence

MIT — see [`LICENSE`](LICENSE).
