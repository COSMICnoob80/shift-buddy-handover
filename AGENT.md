# AGENT.md — the agent, in the format judges read

Track: Open · Pitch: turns photographed night-shift paper notes into a structured, signed
SBAR handoff and a gap list — unattended, local-only, with a kill switch.

## Architecture
Deterministic core, model narrates. Full pipeline in `ARCHITECTURE.md`:
`inbox/ → ingest (hash, order, refuse unreadable) → extract (OCR + deterministic matching,
no LLM) → structure (bed/ID, drug-day arithmetic, action due-times) → rules (contradictions,
duplicates, missing fields) → compose (local GGUF writes SBAR from facts only; templated
fallback pre-approved) → verify (every number in prose must exist in the facts, else the run
fails) → out/<date>/ + audit.jsonl`.

## Tools
Local files, tesseract OCR, one local GGUF model. No cloud services, no API keys.

## Permissions
Enforced table in `PERMISSIONS.md`. Read inbox + model dir; write out/ + audit; nothing else;
zero network egress.

## Limits (what it will not do)
No diagnosis, no dose advice, no sending, no hospital integration, no multi-user, no cloud
sync. It drafts a handoff for a human to read and stops.

## Trace
Every run leaves `audit.jsonl` (input hashes, model, per-field confidence, refusals,
kill-switch events) plus `summary.json`. Judge-replayable from the trace alone.
