# Hosted demo — one-click deploy (Render, plain Web Service)

This is the **look-and-run demo**, not the product. It is the same console and the same
pipeline as the local one, running on synthetic fixture pages. One thing is different: on a
hosted instance **only the text lane exists** (standard library only — no OCR install, no cloud
keys), and the assisted lane stays **off**, as it is everywhere in v1.

Do **not** use a Render Blueprint / `render.yaml` — that path asks for a card. A plain Web
Service on the Free instance type is enough and needs no payment details.

---

## The checklist (six fields)

Dashboard → **New +** → **Web Service** → connect the `shift-buddy-handover` repo, then fill
these six fields exactly:

| # | Field | Value |
|---|-------|-------|
| 1 | **Name** | `shift-buddy-handover` (any name) |
| 2 | **Language / Runtime** | `Python 3` |
| 3 | **Build Command** | *(leave empty)* |
| 4 | **Start Command** | `python tools/console.py --host 0.0.0.0 --port $PORT` |
| 5 | **Instance Type** | `Free` |
| 6 | **Environment Variables** | *(none required)* |

Then **Create Web Service**. First deploy takes a couple of minutes; the log ends with
`Shift Buddy console on http://0.0.0.0:<port>/  (pad=9000)` and the health check passes.

There is nothing to install: this project is standard library only, so the empty Build Command
is correct, not an oversight. `requirements.txt` deliberately does not exist.

**Optional env var.** `CONSOLE_PAD=400` makes each demo run short and watchable. Leave it unset
and a run pads to 9000 neutral pages — fine for a click-through, slower to finish. The console's
`--pad` flag still wins over the env var if both are given.

**No other env vars.** No database, no object storage, no secrets. `PORT` is injected by Render
and read by `tools/console.py`; you never set it yourself.

---

## What the free tier does

- The service **sleeps after ~15 minutes without traffic**, and the next request pays a
  **~50 s cold start** (image start plus the first HTML response). Open the link a minute
  before you present, so the judge's first click is warm.
- Free instances have limited CPU, so a padded run is slower than on your laptop. Keep
  `CONSOLE_PAD` small for demos.
- Writes go to the instance's ephemeral disk. Each run's artefacts live under `out/console/`
  (gitignored) and disappear on redeploy or restart. That is intended: the demo is disposable.
- The `/healthz` endpoint returns `{"ok": true, "mode": "hosted-demo", "data": "synthetic-only"}`
  and is what the platform's health check hits.

---

## Privacy — three honest lines

1. **The hosted instance contains zero real patient data.** The text lane runs on synthetic
   fixtures only (`fixtures/cases.json` — every name, bed number and MRN is invented), and the
   assisted lane is disabled on the host. Assisted reading stays a local-only feature.
2. **Transport security is Render's HTTPS.** The service speaks plain HTTP behind Render's TLS
   termination; no extra certificate or auth layer is added by this repo.
3. **The real product never leaves the operator's machine.** The hosted instance is a
   look-and-run demo of the same pipeline on synthetic pages — not a service that receives
   anyone's handover sheets.

---

## Verify the same start command locally

Before clicking anything, prove the exact Start Command works on your machine:

```bash
PORT=8799 python3 tools/console.py --host 0.0.0.0 --port $PORT
curl -sS -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8799/          # 200
curl -sS http://127.0.0.1:8799/healthz                                    # {"ok": true, ...}
```

Stop it with `Ctrl-C`. Omitting `--host` binds `127.0.0.1` instead, which is the safe local
default and will **not** be reachable from a container's proxy — that is the one flag the
hosted Start Command must set.
