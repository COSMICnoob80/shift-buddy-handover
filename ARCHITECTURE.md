# ARCHITECTURE — how it is built, and why this shape

Version 0.1 · pre-window design

---

## 1. The one principle

**The model extracts and narrates; the rules decide and check.** Nothing that can be computed
is left to a language model, and no value is printed that cannot be traced to a page.

This is the same discipline as a lab report: the analyser produces numbers, the clinician
interprets. Reversed, it becomes an improvisation engine.

## 2. Components

```
inbox/                     photos land here (handoff_2026-11-08_*.jpg)
   │
   ▼
ingest.py            page detection, ordering, hash, EXIF time
   │
   ▼
extract.py           OCR + local NER (GLiNER-class model) → raw fields per page
   │                 every field carries: value, page, bbox, confidence
   ▼
structure.py         deterministic: bed/ID normalisation, drug-day arithmetic,
   │                 action extraction ("repeat troponin 6h" → due 14:00)
   ▼
rules.py             contradictions, duplicates, missing mandatory fields
   │
   ▼
compose.py           LLM writes SBAR prose FROM structured facts only
   │                 (facts passed as JSON; model may not add a fact)
   ▼
verify.py            re-reads the composed text and checks every number
   │                 still appears in the structured facts. Fails the run if not.
   ▼
out/<date>/{handoff.md, gaps.md, audit.jsonl, summary.json}
```

## 3. Why a verify step exists

An LLM asked to "write a handoff" will smooth over gaps — that is what language models do. The
verifier is the counterweight: it extracts every quantity and identifier from the generated
prose and asserts each one exists in the structured facts. **A number that appears in prose but
not in the facts fails the build.** This is the single most important component in the repo and
the first thing to implement in the window.

## 4. Data contract (`summary.json`)

```json
{
  "run_id": "2026-11-27T23:41:00+05:00",
  "shift": {"date": "2026-11-27", "ward": "RO", "handover_to": "night"},
  "patients": [
    {"id": "B12", "name_as_written": "…", "pages": [1,2],
     "issues": ["…"], "pending": ["…"], "actions": [
        {"text": "repeat troponin", "due": "2026-11-28T06:00", "page": 2, "confidence": 0.93}
     ],
     "refused_fields": ["allergy (page 2 unreadable)"]}
  ],
  "unreadable_pages": [3],
  "contradictions": [{"field": "dose", "values": ["1g", "2g"], "pages": [1,2]}]
}
```

## 5. Model choice, and the honest trade

- **Primary:** a local instruction model (GGUF) for narrative composition, because the data
  cannot leave the machine.
- **Extraction:** a small NER model plus OCR, not the LLM. Cheaper, faster, auditable.
- **Fallback:** if the local model is too slow during the window, the SBAR text is templated
  from the structured facts with no model at all. **A templated handoff that is correct beats a
  fluent one that invents a bed number.** This decision is pre-approved.

## 6. What is deliberately absent

No database, no API server, no auth, no scheduler daemon, no mobile client. Files on disk and
one CLI. Every one of those absences is a choice to protect the 72-hour window, and each can be
added later without changing the core.
