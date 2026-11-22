"""Instrumentação leve de performance da UI — logs em memória e opcionalmente em arquivo."""
from __future__ import annotations

import json
import logging
import os
import threading
import time
from collections import deque
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterator, Optional

_log = logging.getLogger("arkland.perf")

_BASELINE_PATH = Path(__file__).resolve().parents[2] / "docs" / "perf_baseline.json"


@dataclass
class PerfEntry:
    operation: str
    ms: float
    detail: str = ""


class PerfMonitor:
    """Coleta tempos de operações de UI para comparação antes/depois."""

    def __init__(self) -> None:
        self._entries: deque[PerfEntry] = deque(maxlen=2000)
        self._lock = threading.Lock()
        self._save_running = False
        self._save_requested = False

    def record(self, operation: str, ms: float, detail: str = "") -> None:
        entry = PerfEntry(operation=operation, ms=round(ms, 2), detail=detail)
        with self._lock:
            self._entries.append(entry)
        _log.info("perf %s %.1fms %s", operation, ms, detail)

    @contextmanager
    def timed(self, operation: str, detail: str = "") -> Iterator[None]:
        t0 = time.perf_counter()
        try:
            yield
        finally:
            self.record(operation, (time.perf_counter() - t0) * 1000, detail)

    def entries(self) -> list[PerfEntry]:
        with self._lock:
            return list(self._entries)

    def save_baseline(self, path: Optional[Path] = None) -> None:
        target = path or _BASELINE_PATH
        with self._lock:
            self._save_requested = True
            if self._save_running:
                return
            self._save_running = True

        def _writer() -> None:
            while True:
                with self._lock:
                    if not self._save_requested:
                        self._save_running = False
                        return
                    self._save_requested = False
                    entries = list(self._entries)

                payload = {
                    "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                    "entries": [asdict(e) for e in entries],
                }
                temp = target.with_name(target.name + ".tmp")
                try:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    temp.write_text(
                        json.dumps(payload, indent=2, ensure_ascii=False),
                        encoding="utf-8",
                    )
                    os.replace(temp, target)
                except Exception:
                    _log.exception("Falha ao salvar baseline de performance em %s", target)
                    try:
                        temp.unlink(missing_ok=True)
                    except OSError:
                        pass
                    with self._lock:
                        self._save_running = False
                    return

        threading.Thread(target=_writer, daemon=True, name="PerfBaselineWriter").start()

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()


_monitor = PerfMonitor()


def get_perf_monitor() -> PerfMonitor:
    return _monitor


@contextmanager
def timed_build(operation: str, detail: str = "") -> Iterator[None]:
    with _monitor.timed(operation, detail):
        yield


def record_build(operation: str, ms: float, detail: str = "") -> None:
    _monitor.record(operation, ms, detail)
