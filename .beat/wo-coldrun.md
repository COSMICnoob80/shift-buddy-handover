> Ship gate: this serves the send to Agentware 2026 judges. No new scope, no new dependency.
> Output is two scripts that run on a stranger's cold clone with plain `python3`.

# WORK ORDER — cold-run blocker: tools hardcode .venv/bin/python

Repo: /home/cosmicnoob/shift-buddy-handover (branch master, clean at 3e93850)

## The defect (verified, reproduce it first)

A fresh clone with no virtualenv breaks on the exact commands README gives a judge:

```
$ bash tools/make_demo.sh
tools/make_demo.sh: line 37: .venv/bin/python: No such file or directory

$ bash tools/scorecard.sh
tools/scorecard.sh: line 29: .venv/bin/python: No such file or directory
```

Both scripts hardcode `PY=".venv/bin/python"`. The project has ZERO third-party
dependencies (stdlib only, verified: every import in src/, tools/, evals/, tests/ is
stdlib). So a venv is not required to run anything — it is only a preference.

## Your task

1. In `tools/make_demo.sh` and `tools/scorecard.sh`, replace the hardcoded interpreter
   with a resolver that prefers the repo venv when it exists and falls back to the
   system interpreter otherwise. Recommended shape, in both files:

   ```bash
   if [ -x "$REPO_ROOT/.venv/bin/python" ]; then
     PY="$REPO_ROOT/.venv/bin/python"
   else
     PY="$(command -v python3 || command -v python)"
   fi
   if [ -z "${PY:-}" ]; then
     echo "FAIL: no python interpreter found (tried .venv/bin/python, python3, python)" >&2
     exit 1
   fi
   ```

   Keep `set -euo pipefail` behaviour. Do not change anything else in the scripts:
   no new flags, no new files, no changes to output text, no new dependencies.

2. Check `tools/render_sheets.py` for the same hardcoded-interpreter problem in any
   shebang or subprocess call and fix only that, if present.

3. Do NOT touch README.md, docs, src/, tests/, or fixtures. README prose is owned by
   the orchestrator.

## Verification you must actually run and paste

Run each from a COLD clone that has no venv, not from the working repo:

```bash
rm -r /tmp/sbh-wo 2>/dev/null
git clone -q . /tmp/sbh-wo
cd /tmp/sbh-wo && cp .env.example .env && mkdir -p inbox out
bash tools/make_demo.sh        # must reach "=== done ===" and print the kill-switch result
bash tools/scorecard.sh        # must end "GREEN: every quoted number above is reproduced"
python3 -m unittest discover -s tests   # must report OK (50 tests)
```

Also run `bash tools/make_demo.sh` once in the real repo (where .venv DOES exist) to
prove the venv path still wins and nothing regressed.

## Commit

Commit ONLY the tools/ files you changed, message:
`tools: resolve the python interpreter instead of hardcoding .venv`

Report, in plain prose: the exact diff, the three verification outputs (paste the
tail of each), and anything you found that you did NOT fix.
