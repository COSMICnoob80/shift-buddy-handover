#!/usr/bin/env python3
"""Render the demo inbox from the synthetic fixtures. Deterministic, no network.

    .venv/bin/python tools/render_sheets.py --cases fixtures/cases.json --out inbox/demo/

Why text pages and not photographs
----------------------------------
``src/ingest.py`` has two lanes: a text lane (``.txt``) and a photo lane
(``.jpg|.png``, RapidOCR). The demo runs the **text lane** on purpose:

* the photo lane needs RapidOCR installed, and the demo must not depend on an
  optional OCR wheel being present on the judging machine;
* v1 **refuses handwriting**. That refusal is the point of the demo, not a gap
  in it: a photographed scrawl would come back as "OCR produced no text" and be
  named in ``gaps.md``. Rendering the same content as a ``.txt`` transcript keeps
  the refusal visible at the field level (``[dose unreadable]`` -> "dose not
  read") instead of collapsing the whole page to one line.

So fixture cases in a photographic family (``handwriting-heavy``,
``unreadable-page``) are written as ``.txt`` transcript variants here. A page the
fixture marks ``readable: false`` (the cropped / blurred / torn refusal pages) is
written as a **zero-byte** file, which is exactly how the text lane represents a
page that is present but cannot be read: ``gaps.md`` then names that page.

Filename contract
-----------------
``src/ingest.py`` only accepts ``handoff_<YYYY-MM-DD>_<seq>.<ext>`` and orders
pages by ``<seq>``. Anything else is silently ignored, so a run over it reports
0 patients. Sequence numbers are therefore consecutive **across the whole demo
inbox** (not restarted per case), which keeps page order stable when several
cases are rendered into one folder.

Idempotent: output is a pure function of the fixtures plus ``--date``. No
timestamps, no host paths; re-running produces byte-identical files.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

DEFAULT_DATE = "2026-11-28"

# Curated roster: two dense pages, one cross-page dose contradiction, one missing
# mandatory field, one unreadable page, one prompt-injection page, and one
# handwriting transcript that must be refused field-by-field.
DEMO_ROSTER = (
    "C-003",  # dense multi-patient sheet, 4 patients
    "C-014",  # dense multi-patient sheet, 6 patients
    "C-007",  # contradiction: meropenem 1g on p1 vs 2g on p2
    "C-008",  # missing mandatory field: allergy
    "C-009",  # unreadable page (cropped) -> zero-byte page file
    "C-010",  # adversarial: IGNORE PREVIOUS INSTRUCTIONS ...
    "C-036",  # handwriting: "[dose unreadable]" refused by name
)

# Same pattern src/ingest.py accepts. Kept in sync on purpose: a mismatch here
# means a silent zero-patient run, so it is asserted before anything is written.
FILENAME_RE = re.compile(
    r"^handoff_(?P<date>\d{4}-\d{2}-\d{2})_(?P<seq>\d+)(?:\.(?P<ext>[A-Za-z0-9]+))?$"
)


def load_cases(path: Path) -> list[dict]:
    doc = json.loads(path.read_text(encoding="utf-8"))
    cases = doc.get("cases") if isinstance(doc, dict) else doc
    if not isinstance(cases, list):
        raise SystemExit(f"{path}: no case list found")
    return cases


def select(cases: list[dict], only: list[str]) -> list[dict]:
    by_id = {case.get("id"): case for case in cases}
    missing = [case_id for case_id in only if case_id not in by_id]
    if missing:
        raise SystemExit(f"cases not in fixtures: {', '.join(missing)}")
    return [by_id[case_id] for case_id in only]


def render(cases: list[dict], out_dir: Path, date: str) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)

    # Drop only our own products; leave anything else the user put there.
    for stale in out_dir.glob("handoff_*.txt"):
        stale.unlink()

    totals = {
        "pages": 0,
        "patients": 0,
        "refusals": 0,
        "unreadable_pages": 0,
        "contradictions": 0,
        "injections": 0,
    }
    written: list[tuple[str, str, int, bool]] = []
    seq = 0

    for case in cases:
        case_id = str(case.get("id"))
        expected = case.get("expected") or {}
        pages = sorted(
            case.get("pages") or [], key=lambda page: int(page.get("page") or 1)
        )

        totals["patients"] += int(expected.get("patients") or 0)
        totals["refusals"] += int(expected.get("refusals") or 0)
        totals["contradictions"] += int(expected.get("contradictions") or 0)
        totals["injections"] += int(expected.get("injection_ignored") or 0)

        for page in pages:
            seq += 1
            name = f"handoff_{date}_{seq:02d}.txt"
            if not FILENAME_RE.match(name):  # cannot happen; guarded so a
                raise SystemExit(  # silent 0-patient run is impossible
                    f"filename breaks the ingest contract: {name}"
                )

            readable = page.get("readable") is not False
            if readable:
                text = str(page.get("text") or "")
                payload = text if text.endswith("\n") else text + "\n"
            else:
                # Present but unreadable: zero bytes, never invented text.
                payload = ""
                totals["unreadable_pages"] += 1

            target = out_dir / name
            with open(target, "w", encoding="utf-8", newline="\n") as handle:
                handle.write(payload)
            written.append((name, case_id, int(page.get("page") or 1), readable))
            totals["pages"] += 1

    return {"written": written, "totals": totals}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="tools/render_sheets.py",
        description="Build the demo inbox from fixtures, deterministically.",
    )
    parser.add_argument("--cases", default="fixtures/cases.json")
    parser.add_argument("--out", default="inbox/demo/")
    parser.add_argument("--date", default=DEFAULT_DATE)
    parser.add_argument(
        "--only",
        default=None,
        help="comma-separated case ids (default: the curated demo roster)",
    )
    args = parser.parse_args(argv)

    cases_path = Path(args.cases).expanduser()
    if not cases_path.is_file():
        raise SystemExit(f"cases file not found: {cases_path}")
    only = (
        [part.strip() for part in args.only.split(",") if part.strip()]
        if args.only
        else list(DEMO_ROSTER)
    )

    result = render(select(load_cases(cases_path), only), Path(args.out), args.date)
    totals = result["totals"]

    print(f"demo inbox: {Path(args.out).resolve()}")
    for name, case_id, source_page, readable in result["written"]:
        state = "readable" if readable else "UNREADABLE (0 bytes)"
        print(f"  {name}  <- {case_id} source page {source_page}, {state}")
    print(
        "EXPECTED "
        f"patients={totals['patients']} "
        f"pages={totals['pages']} "
        f"unreadable_pages={totals['unreadable_pages']} "
        f"refusals={totals['refusals']} "
        f"contradictions={totals['contradictions']} "
        f"injections={totals['injections']}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
