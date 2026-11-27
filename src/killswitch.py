"""Stop conditions: a STOP file, and SIGTERM. Both latched, both timed.

Nothing here aborts work in flight.  ``check()`` is a cheap poll the pipeline
calls between pages and between stages, so the current file always finishes
atomically before the run unwinds.
"""

from __future__ import annotations

import os
import signal
import time
from datetime import datetime

DEFAULT_STOP_FILE = "./STOP"
STOP_ENV = "SBH_STOP_FILE"


class KillSwitch:
    """Cheap STOP-file poll plus a SIGTERM flag. Triggers exactly once."""

    def __init__(self, stop_path: str | None = None):
        self.stop_path = stop_path or os.environ.get(STOP_ENV) or DEFAULT_STOP_FILE
        self._armed_at = time.monotonic()
        self._armed_wall = datetime.now().astimezone().isoformat(timespec="milliseconds")
        self._signal_seen = False
        self._stopped_by: str | None = None
        self._honoured_in: float | None = None
        self._detected_at: str | None = None
        self._previous_term = None
        self._install()

    # ---------------------------------------------------------------- signals

    def _install(self) -> None:
        try:
            self._previous_term = signal.getsignal(signal.SIGTERM)
            signal.signal(signal.SIGTERM, self._on_term)
        except (ValueError, OSError):
            self._previous_term = None

    def _on_term(self, signum, frame) -> None:
        self._signal_seen = True

    def restore(self) -> None:
        if self._previous_term is not None:
            try:
                signal.signal(signal.SIGTERM, self._previous_term)
            except (ValueError, OSError):
                pass
            self._previous_term = None

    # ---------------------------------------------------------------- polling

    def _stop_file_present(self) -> bool:
        try:
            os.stat(self.stop_path)
        except OSError:
            return False
        return True

    def armed(self) -> bool:
        return self._stopped_by is not None or self._stop_file_present() or self._signal_seen

    def _latch(self, source: str) -> bool:
        self._stopped_by = source
        self._honoured_in = round(time.monotonic() - self._armed_at, 4)
        self._detected_at = datetime.now().astimezone().isoformat(timespec="milliseconds")
        return True

    def check(self) -> bool:
        """True the first time STOP/SIGTERM is seen. Later calls return False."""
        if self._stopped_by is not None:
            return False
        if self._signal_seen:
            return self._latch("SIGTERM")
        if self._stop_file_present():
            return self._latch("STOP")
        return False

    # ----------------------------------------------------------------- report

    @property
    def stopped_by(self) -> str | None:
        return self._stopped_by

    @property
    def honoured_in(self) -> float | None:
        return self._honoured_in

    def audit_fields(self) -> dict:
        return {
            "stopped_by": self._stopped_by,
            "honoured_in": self._honoured_in,
            "kill_switch_armed_at": self._armed_wall,
            "kill_switch_detected_at": self._detected_at,
        }


def stop_file_path() -> str:
    return os.environ.get(STOP_ENV) or DEFAULT_STOP_FILE


def trip(stop_path: str | None = None) -> str:
    """Create the STOP file. Used by ``python -m src.cli kill``."""
    path = stop_path or stop_file_path()
    with open(path, "a", encoding="utf-8"):
        pass
    return path
