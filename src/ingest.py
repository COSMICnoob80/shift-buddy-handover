"""Page ingestion — one inbox, three file kinds, no silent skips.

Contract: work-orders/04-build-contracts.md §1-§2.

    handoff_<YYYY-MM-DD>_<seq>.txt        text lane (typed drop, transcript, fixture)
    handoff_<YYYY-MM-DD>_<seq>.jpg|.png   photographed page -> RapidOCR lane
    ... with size 0 bytes                 page present, unreadable, refused by name

Page order comes from ``<seq>``, never from directory order.  Every file is
hashed even when it cannot be read.  No network, no model.
"""

from __future__ import annotations

import hashlib
import os
import re
from datetime import datetime

_FILENAME_RE = re.compile(
    r"^handoff_(?P<date>\d{4}-\d{2}-\d{2})_(?P<seq>\d+)(?:\.(?P<ext>[A-Za-z0-9]+))?$"
)

_TEXT_EXTS = {"txt"}
_IMAGE_EXTS = {"jpg", "jpeg", "png"}

_QUOTED_RE = re.compile(r"['\"][^'\"\n]{1,80}['\"]")
_BED_RE = re.compile(r"\bBED\b", re.I)
_MRN_RE = re.compile(r"\bMRN\b", re.I)

_OCR_ENGINE = None


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _sha256(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 256), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _engine():
    """RapidOCR with the frozen config of §2.4.  Built once, lazily."""
    global _OCR_ENGINE
    if _OCR_ENGINE is None:
        from rapidocr_onnxruntime import RapidOCR

        _OCR_ENGINE = RapidOCR(
            det_limit_side_len=1600,
            det_limit_type="max",
            max_side_len=3000,
            use_cls=False,
        )
    return _OCR_ENGINE


def _join_boxes(boxes: list) -> str:
    """Reading order: cluster boxes into visual lines, then left to right."""
    lines: list = []
    for box in sorted(boxes, key=lambda b: (b["y0"] + b["y1"]) / 2.0):
        centre = (box["y0"] + box["y1"]) / 2.0
        for line in lines:
            line_centre = (line["y0"] + line["y1"]) / 2.0
            height = max(line["y1"] - line["y0"], box["y1"] - box["y0"], 1.0)
            if abs(centre - line_centre) <= height * 0.6:
                line["boxes"].append(box)
                line["y0"] = min(line["y0"], box["y0"])
                line["y1"] = max(line["y1"], box["y1"])
                break
        else:
            lines.append({"y0": box["y0"], "y1": box["y1"], "boxes": [box]})
    return "\n".join(
        " ".join(b["text"] for b in sorted(line["boxes"], key=lambda b: b["x0"]))
        for line in lines
    )


def _ocr(path: str) -> tuple[str, float | None]:
    """Return (text, mean confidence).  Raises on engine failure."""
    result, _elapse = _engine()(str(path))
    if not result:
        return "", None
    boxes = []
    scores = []
    for item in result:
        box, text, score = item[0], item[1], item[2]
        xs = [float(point[0]) for point in box]
        ys = [float(point[1]) for point in box]
        boxes.append(
            {
                "x0": min(xs),
                "y0": min(ys),
                "y1": max(ys),
                "text": str(text),
            }
        )
        try:
            scores.append(float(score))
        except (TypeError, ValueError):
            pass
    text = _join_boxes(boxes)
    mean = round(sum(scores) / len(scores), 4) if scores else None
    return text, mean


def _exif_time(path: str) -> str | None:
    from PIL import Image

    with Image.open(path) as image:
        exif = image.getexif()
        raw = exif.get(36867) or exif.get(306)
    if not raw:
        return None
    value = str(raw).strip()
    for fmt in ("%Y:%m:%d %H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(value, fmt).isoformat(timespec="seconds")
        except ValueError:
            continue
    return value


def _structural_readable(text: str) -> tuple[bool, str | None]:
    """§2.3 structural rule: BED plus (MRN or a quoted name)."""
    if not text.strip():
        return False, "image OCR produced no text"
    if not _BED_RE.search(text):
        return False, "image OCR text has no BED token (structural identity rule)"
    if not (_MRN_RE.search(text) or _QUOTED_RE.search(text)):
        return (
            False,
            "image OCR text has BED but no MRN or quoted name (structural identity rule)",
        )
    return True, None


def _page_record(path: str, name: str, page_no: int, order: int, inbox_dir: str) -> dict:
    record = {
        "page": page_no,
        "path": os.path.join(inbox_dir, name),
        "sha256": None,
        "order": order,
        "kind": None,
        "text": "",
        "exif_time": None,
        "readable": False,
        "refusal_reason": None,
        "ocr_confidence": None,
        "unusual": [],
    }

    try:
        record["sha256"] = _sha256(path)
    except OSError as exc:
        record["refusal_reason"] = f"file could not be read: {exc.__class__.__name__}: {exc}"
        return record

    size = os.path.getsize(path)
    if size == 0:
        record["refusal_reason"] = "page file is empty (0 bytes)"
        return record

    ext = os.path.splitext(name)[1].lower().lstrip(".")
    if ext in _TEXT_EXTS:
        record["kind"] = "text"
        try:
            with open(path, "rb") as handle:
                payload = handle.read()
        except OSError as exc:
            record["refusal_reason"] = (
                f"text file could not be read: {exc.__class__.__name__}: {exc}"
            )
            return record
        text = None
        for encoding in ("utf-8", "utf-8-sig"):
            try:
                text = payload.decode(encoding)
                break
            except UnicodeDecodeError:
                continue
        if text is None:
            record["refusal_reason"] = "text file is not valid UTF-8 (decode failed)"
            return record
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        record["text"] = text
        if not text.strip():
            record["refusal_reason"] = "text file contains no text (whitespace only)"
            return record
        record["readable"] = True
        return record

    if ext in _IMAGE_EXTS:
        record["kind"] = "image"
        try:
            record["exif_time"] = _exif_time(path)
        except Exception:
            record["exif_time"] = None
        try:
            text, confidence = _ocr(path)
        except Exception as exc:
            record["refusal_reason"] = f"OCR failed: {exc.__class__.__name__}: {exc}"
            return record
        record["text"] = text
        record["ocr_confidence"] = confidence
        readable, reason = _structural_readable(text)
        record["readable"] = readable
        record["refusal_reason"] = reason
        return record

    record["refusal_reason"] = f"unsupported page file type '.{ext}' (text or image expected)"
    return record


def ingest(inbox_dir: str, *, stop=None) -> dict:
    """Enumerate the inbox and return the pages document of §2."""
    if not os.path.isdir(inbox_dir):
        raise FileNotFoundError(f"inbox directory not found: {inbox_dir}")

    matched: list[tuple[int, str, str, str]] = []
    ignored: list[dict] = []

    for entry in sorted(os.scandir(inbox_dir), key=lambda item: item.name):
        if not entry.is_file():
            continue
        match = _FILENAME_RE.match(entry.name)
        if not match:
            item = {"path": os.path.join(inbox_dir, entry.name)}
            try:
                item["sha256"] = _sha256(entry.path)
            except OSError:
                item["sha256"] = None
            item["reason"] = "filename does not match handoff_<date>_<seq>.<ext>"
            ignored.append(item)
            continue
        matched.append(
            (
                int(match.group("seq")),
                match.group("date"),
                entry.name,
                entry.path,
            )
        )

    matched.sort(key=lambda item: (item[0], item[1], item[2]))

    dates = [item[1] for item in matched]
    shift_date = max(dates) if dates else datetime.now().astimezone().date().isoformat()

    pages: list[dict] = []
    unprocessed: list[str] = []
    stopped = False

    for index, (seq, _date, name, path) in enumerate(matched):
        if stop is not None:
            try:
                if stop():
                    stopped = True
                    unprocessed = [item[2] for item in matched[index:]]
                    break
            except Exception:
                pass
        pages.append(_page_record(path, name, seq, index + 1, inbox_dir))

    document = {
        "run_id": _now(),
        "shift_date": shift_date,
        "pages": pages,
    }
    if ignored:
        document["ignored_files"] = ignored
    if stopped:
        document["stopped"] = True
        document["unprocessed_files"] = unprocessed
    return document
