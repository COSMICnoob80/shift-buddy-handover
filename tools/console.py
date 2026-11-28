#!/usr/bin/env python3
"""Launch the live monitoring console.

    .venv/bin/python tools/console.py [--port 8777] [--pad 9000] [--host 127.0.0.1]

The console starts the real pipeline on demand and tails its real audit trail.
Standard library only; no network beyond localhost.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from src.console import server  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="tools/console.py", description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8777)
    parser.add_argument("--pad", type=int, default=None,
                        help="total inbox pages for a watchable run (default 9000)")
    args = parser.parse_args(argv)
    if args.pad is not None:
        server.DEFAULT_PAD = max(10, args.pad)
    server.serve(args.host, args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
