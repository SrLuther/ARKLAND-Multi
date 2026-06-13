"""Instrumentação leve de performance da UI — logs em memória e opcionalmente em arquivo."""
from __future__ import annotations

import json
import logging
import time
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
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
        self._entries: list[PerfEntry] = []

    def record(self, operation: str, ms: float, detail: str = "") -> None:
        entry = PerfEntry(operation=operation, ms=round(ms, 2), detail=detail)
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
        return list(self._entries)

    def save_baseline(self, path: Optional[Path] = None) -> None:
        target = path or _BASELINE_PATH
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "entries": [asdict(e) for e in self._entries],
        }
        target.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    def clear(self) -> None:
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
