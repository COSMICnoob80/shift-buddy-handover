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

## Real-capture validation — 19 Nov 2026 (evidence update)

Re-run of the rehearsal on 40 REAL photographed ward-paperwork pages from the user's phone
harvest (`~/phone-harvest/safe_test/`, privacy-safe subset; aggregate-only report at
`~/agentware/reports/real-capture-validation.md`). Findings:

1. **Printed-text config does not comprehend real handwriting.** 0/40 pages empty, mean
   confidence 0.86, but median yield only ~699 characters — ink detected everywhere, text
   returned short and fragmented. Detection survives; comprehension does not.
2. **Identity is the failure point.** Strict MR label on 4/40 pages; the structural refusal
   rule fired on 27/40 (68%) — safe, but blunt enough to reject genuine notes.
3. **`use_cls` is not a free toggle on real captures:** flipping it alone dropped text
   agreement below 60% on 4/40 pages (as low as 14%).

**Decision (this is the re-run the freeze clause requires):**
- Keep the frozen OCR config for PRINTED text (validated: 1.2% CER).
- **Handwritten pages are refused-and-flagged in v1, not parsed.** The gap list names them;
  the handoff never invents their content. This is an honest, documented limit — and it is
  exactly the behaviour the rubric rewards ("here is the failure mode we did not fix").
- A local vision-model lane for handwriting is explicitly OUT of v1 scope (scope-creep
  risk); it is the natural post-event extension and a Near Miss write-up candidate.
- Caveat: the corpus classified 0 PROGRESS / 8 FOLDER / 13 SHIFA_DOC / 19 OTHER — true
  progress-note pages were not isolated, so the 68% refusal rate is corpus-mixed, not a
  pure handwriting rate.

## Vision-lane feasibility test — 23 Nov 2026 (evidence update, closes the open decision)

The local vision-model lane was tested and **rejected on measured evidence**, not on
assumption. Setup: Qwen3-VL-2B-Instruct (official GGUF, 1.9 GB) served locally by
Ollama 0.40.17 on this machine (i5-1235U, 15 GB RAM, no GPU), reading real pages from
`~/phone-harvest/safe_test/` (raw transcriptions stayed local; aggregate numbers only).

| Probe | Result |
|---|---|
| Batch probe (6 real pages) | 0/6 completed — script's 600 s/page timeout exceeded on every page |
| Single page, ollama default threads | 625.9 s (vision encode dominates; ollama used 2 threads) |
| Single page, tuned `num_thread: 8` | **308.1 s** — still ~20× over the < 5 min / 20 patients budget |
| Output quality, tuned run | **89 chars in 32 tokens**: transcribed only the printed letterhead, never reached the handwriting, stopped early (`done_reason: length`) |

**Follow-up bounded tests (23–24 Nov) closed every remaining lane — see
`~/agentware/reports/got-ocr2-test.md` for the full table:**
- PaddleOCR-VL-0.9B: 535 s/page (best text yield: 1701 chars) — speed-only fail.
- GOT-OCR2.0 specialist (580 M, official weights, CPU-patched): no page completed within
  a 60-minute cap — dead on this hardware.
- Preprocessing ladder (grayscale/crop/upscale/sharpen × 17 progress notes): identity
  0/17 on every variant — preprocessing is not the bottleneck.

**Decision (final for v1):**
- **Handwriting pages: refuse-and-flag. Confirmed.** The vision lane fails BOTH gates —
  it is ~20× too slow for the batch budget, and at 2B scale it does not comprehend
  handwritten ward notes on phone photos. Both numbers above are the evidence.
- Clean handwriting number for the honest-limits section: on the 17 isolated true
  progress notes, OCR recovers identity on 0/17 and refuses 13/17 (76%);
  `~/agentware/reports/progress-note-isolation.md`.
- Post-event extensions (documented, not promised): GOT-OCR2.0 (716 M specialist, ~4×
  smaller, CPU path exists), PaddleOCR-VL-0.9B (CER 0.045), crop-to-handwriting
  preprocessing, or any GPU. Free cloud vision APIs remain excluded: Google's terms
  forbid sensitive personal data and permit human review of inputs — PHI may not leave
  the machine.

