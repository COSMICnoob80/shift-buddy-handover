#!/usr/bin/env bash
# Reproduce the demo end to end: render -> run -> show the six lines the video
# quotes -> then prove the kill switch. No network. Deterministic where it can
# be; the only wall-clock number is `honoured_in`, which is the point.
#
#   bash tools/make_demo.sh
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

if [ -x "$REPO_ROOT/.venv/bin/python" ]; then
  PY="$REPO_ROOT/.venv/bin/python"
else
  PY="$(command -v python3 || command -v python)"
fi
if [ -z "${PY:-}" ]; then
  echo "FAIL: no python interpreter found (tried .venv/bin/python, python3, python)" >&2
  exit 1
fi
DATE="2026-11-28"
OUT_ROOT="out/demo"
STOP_PATH="$REPO_ROOT/STOP"
TMP_INBOX="$(mktemp -d "${TMPDIR:-/tmp}/sbh-inbox.XXXXXX")"
KS_INBOX="$(mktemp -d "${TMPDIR:-/tmp}/sbh-ks-inbox.XXXXXX")"
KS_OUT="$(mktemp -d "${TMPDIR:-/tmp}/sbh-ks-out.XXXXXX")"

cleanup() {
  # A stray STOP would stop the very next run, so it must never outlive us.
  rm -f "$STOP_PATH"
  rm -r -- "$TMP_INBOX" "$KS_INBOX" "$KS_OUT" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

section() { printf '\n=== %s ===\n' "$1"; }

# --------------------------------------------------------------------- 1. run
section "clean $OUT_ROOT/"
if [ -d "$OUT_ROOT" ]; then
  find "$OUT_ROOT" -mindepth 1 -delete
fi
mkdir -p "$OUT_ROOT"

section "render demo inbox into a temp dir"
"$PY" tools/render_sheets.py --cases fixtures/cases.json --out "$TMP_INBOX" --date "$DATE"

section "run the pipeline (text lane, unattended)"
rm -f "$STOP_PATH"
SBH_STOP_FILE="$STOP_PATH" "$PY" -m src.cli run --inbox "$TMP_INBOX" --out "$OUT_ROOT" --date "$DATE"

RUN_DIR="$OUT_ROOT/$DATE"
HANDOFF="$RUN_DIR/handoff.md"
GAPS="$RUN_DIR/gaps.md"
STATUS="$RUN_DIR/status.json"
AUDIT="$RUN_DIR/audit.jsonl"

# (a) every SBAR line carries a page reference
section "(a) SBAR page-reference count in handoff.md"
printf '[p. N] references: %s\n' "$(grep -c '\[p\.' "$HANDOFF" || true)"
printf 'SBAR body lines  : %s\n' "$(grep -cE '^(S|B|A|R): ' "$HANDOFF" || true)"

# (b) what could not be read -- the refusal is the product
section "(b) could-not-be-read lines in gaps.md"
awk '/^## Unreadable pages/{f=1;next} /^## /{f=0} f && NF' "$GAPS"

# (c) contradictions, both pages cited
section "(c) contradiction lines in gaps.md"
awk '/^## Contradictions/{f=1;next} /^## /{f=0} f && NF' "$GAPS"

# (d) the hallucination counter -- verify() refuses any token not on a page
section "(d) hallucination counter"
"$PY" - "$STATUS" <<'PY'
import json, sys
status = json.load(open(sys.argv[1], encoding="utf-8"))
verify = status.get("verify") or {}
violations = verify.get("violations") or []
patients = status.get("patients") or 0
print(
    f"hallucinated fields: {len(violations)} / {patients} patients "
    f"(verify ok={verify.get('ok')}, exit_reason={status.get('exit_reason')})"
)
PY

# (e) the audit trail tail
section "(e) audit.jsonl tail"
tail -n 2 "$AUDIT"

# ----------------------------------------------------------- 2. kill switch
section "kill-switch half: start a second run, then touch STOP"
# The 9-page demo finishes in ~0.15 s, too fast to trip without racing Python
# startup. Pad the inbox with valid pages so the run is provably long enough to
# interrupt: 500 pages keeps the pipeline busy ~0.9 s (verify dominates), which
# leaves a wide, honest window for STOP to land in the middle of real work.
for i in $(seq 1 500); do
  printf 'BED %s MRN 00-%s "Killswitch P%s." — stable, awaiting sign-out.\n' \
    "$i" "$i" "$i" > "$KS_INBOX/handoff_${DATE}_$(printf '%04d' "$i").txt"
done

rm -f "$STOP_PATH"
SBH_STOP_FILE="$STOP_PATH" "$PY" -m src.cli run \
  --inbox "$KS_INBOX" --out "$KS_OUT" --date "$DATE" >/dev/null 2>&1 &
RUN_PID=$!

# Deterministic trigger, no sleep race: audit.jsonl is opened at run_start, so
# its appearance proves the pipeline is live. Touch STOP only then.
for _ in $(seq 1 500); do
  [ -f "$KS_OUT/$DATE/audit.jsonl" ] && break
  sleep 0.01
done
if [ ! -f "$KS_OUT/$DATE/audit.jsonl" ]; then
  kill "$RUN_PID" 2>/dev/null || true
  echo "FAIL: run never started (no audit.jsonl)" >&2
  exit 1
fi
touch "$STOP_PATH"
printf 'touched STOP while pid %s was running\n' "$RUN_PID"

set +e
wait "$RUN_PID"
set -e

section "kill-switch result"
"$PY" - "$KS_OUT/$DATE/status.json" "$KS_OUT/$DATE/audit.jsonl" <<'PY'
import json, sys
status = json.load(open(sys.argv[1], encoding="utf-8"))
print(f"exit_reason : {status.get('exit_reason')}")
print(f"stopped_by  : {status.get('stopped_by')}")
print(f"honoured_in : {status.get('honoured_in')}s")
print(f"pages ingested before the stop: {len(status.get('inputs') or [])}")
if status.get("stopped_by") != "STOP":
    raise SystemExit("FAIL: STOP was not the thing that stopped the run")
if status.get("exit_reason") == "completed":
    raise SystemExit("FAIL: the run completed before STOP was honoured")
for line in open(sys.argv[2], encoding="utf-8"):
    rec = json.loads(line)
    if rec.get("kind") == "run_end":
        print(
            "audit run_end: "
            f"stopped_by={rec.get('stopped_by')} "
            f"honoured_in={rec.get('honoured_in')} "
            f"exit_reason={rec.get('exit_reason')}"
        )
PY

section "done"
printf 'handoff: %s\ngaps:    %s\naudit:   %s\n' "$HANDOFF" "$GAPS" "$AUDIT"
