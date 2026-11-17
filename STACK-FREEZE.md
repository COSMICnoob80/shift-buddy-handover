# STACK FREEZE — decided 17 Nov 2026, from rehearsal evidence

Frozen 3 days ahead of the 20 Nov deadline. Nothing on this page changes without a
re-run of the rehearsal experiments. Source: `~/agentware/reports/rehearsal-report.md`
(throwaway rehearsal — 40 fixture cases / 51 pages rendered as photographed sheets,
OCR'd offline).

## The frozen stack

| Layer | Choice | Why (rehearsal evidence) |
|---|---|---|
| OCR engine | **RapidOCR 1.4.4** (PP-OCRv4 ONNX models, offline) | Tesseract unavailable and unnecessary: mean CER 1.2%, BED/MRN/ACTION recall 100%, names 96.9% on the degraded corpus |
| OCR config | `det_limit_side_len: 1600, det_limit_type: max, max_side_len: 3000, use_cls: false` | Turning OFF the orientation classifier cut mean CER 4.7% → 1.2% and raised BED recall 90.8% → 100%; upright-but-tilted lines were being dropped/flipped |
| Local LLM | One GGUF instruction model, narrative composition only | Data may not leave the machine; templated fallback pre-approved (ARCHITECTURE §5) |
| Python | Project venv, OCR + Pillow + stdlib only | No new libraries after freeze (20 Nov) |

## Rules the rehearsal forced (build these into the window code)

1. **Refusal test is structural, not confidence-based.** Glare and tear pages produced
   140–371 characters at 0.94–0.96 confidence with no patient identity. A page is refused
   unless it yields BED plus either an MRN or a quoted name.
2. **Minimum photo quality:** ~1000 px page width / 30 px text height. At 800 px MRN and
   names start dropping; at 700 px names are gone. Gaussian blur radius ≥8 or motion
   kernel ≥17 destroys text with no recovery — those photos must be re-shot, not parsed.
3. **Never silently normalise** OCR ambiguities: `I` vs `1` in MRNs stays as read, with
   the ambiguity flagged in the gap list.

## Validated / unvalidated

- Validated: print rendering under tilt, grain, crop, motion blur, glare, tear (40/40
  cases; 4/4 unreadable refused; 0 readable pages falsely refused).
- **Unvalidated: real handwriting.** The handwriting-heavy family was simulated with
  italic serif — closest available proxy. Real photographed cursive remains the known
  open risk; the refusal-first design is the mitigation.
- Optional upgrade, needs the user's phone: photograph 5 printed fixture sheets under bad
  ward lighting and re-run `measure.py` on the real captures.

## What this unlocks

Work orders 01–03 are now dispatchable with exact engine settings. The event's first
session can start with `ingest.py` against a known-good configuration instead of tuning.
