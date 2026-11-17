# PERMISSIONS — what the agent may and may not do

Enforced in code (Work Order 03), not by prompting. Judges: each row is demonstrated by a
test committed in `tests/`.

| # | Action | Allowed? | Enforcement |
|---|---|---|---|
| 1 | Read `inbox/` (photos, text drops) | yes | code path only |
| 2 | Read local model directory | yes | code path only |
| 3 | Write `out/<shift-date>/` (handoff, gaps, summary) | yes | code path only |
| 4 | Append `audit.jsonl` | yes | append-only |
| 5 | Write anywhere else on disk | **no** | permission check denies |
| 6 | Any network call (cloud APIs, email, chat, telemetry) | **no** | no network code exists; egress test asserts 0 bytes |
| 7 | Send a handoff to any person or service | **no** | no send path exists |
| 8 | State a diagnosis / suggest a drug or dose | **no** | composer receives facts only; verifier fails any number not traceable to a page |
| 9 | Print a field it could not read | **no** | refusals are recorded, never guessed |
| 10 | Continue after kill switch (`STOP` file / SIGTERM) | **no** | exit ≤ 2 s, pending work cancelled, audit intact |

Model: local GGUF only (`SBH_MODEL_PATH`). OCR: local tesseract. There is no API key for
this project; `.env.example` contains paths and limits, not credentials.
