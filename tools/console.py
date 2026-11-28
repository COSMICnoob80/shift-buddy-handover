#!/usr/bin/env python3
"""Launch the live monitoring console.

    .venv/bin/python tools/console.py [--port 8777] [--pad 9000] [--host 127.0.0.1]

The console starts the real pipeline on demand and tails its real audit trail.
Standard library only; no network beyond localhost.

Hosted demo (Render) reads platform env vars instead of flags:
    PORT         listening port when --port is not passed
    CONSOLE_PAD  default inbox pages when --pad is not passed (420 on the free tier)
    HOSTED=1     bind 0.0.0.0 so the platform proxy can reach the service
A hosted instance runs the text lane on synthetic fixtures only; see DEPLOY.md.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from src.console import server  # noqa: E402

LOCAL_HOST = "127.0.0.1"
HOSTED_HOST = "0.0.0.0"


def _env_int(name: str) -> int | None:
    raw = (os.environ.get(name) or "").strip()
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def main(argv: list[str] | None = None) -> int:
    hosted = (os.environ.get("HOSTED") or "").strip() == "1"
    parser = argparse.ArgumentParser(prog="tools/console.py", description=__doc__)
    parser.add_argument("--host", default=HOSTED_HOST if hosted else LOCAL_HOST)
    parser.add_argument("--port", type=int, default=_env_int("PORT") or 8777)
    parser.add_argument("--pad", type=int, default=None,
                        help="total inbox pages for a watchable run (default 9000)")
    args = parser.parse_args(argv)
    pad = args.pad if args.pad is not None else _env_int("CONSOLE_PAD")
    if pad is not None:
        server.DEFAULT_PAD = max(10, pad)
    server.serve(args.host, args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
