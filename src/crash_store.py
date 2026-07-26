"""
crash_store.py — Singleton global de eventos de crash em tempo real.

Fluxo:
  ServerManager._emit_crash_details()
      → CrashStore.instance().add(CrashEvent)
      → callbacks registrados (UI thread via .after())
      → persiste em JSON (APPDATA/ARKLAND-ServerManager/crash_events.json)
"""
import json
import os
import threading
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable, List, Optional


@dataclass
class CrashEvent:
    event_id:    str
    server_id:   str
    server_name: str
    kind:        str           # "crash" | "launch_fail"
    timestamp:   str           # ISO 8601
    exit_code:   Optional[int]
    log_tail:    List[str]
    culprit:     str
    diagnosis:   str
    seen:        bool = False

    @property
    def ts(self) -> datetime:
        try:
            return datetime.fromisoformat(self.timestamp)
        except Exception:
            return datetime.min

    def ts_display(self) -> str:
        try:
            return self.ts.strftime("%d/%m/%Y  %H:%M:%S")
        except Exception:
            return self.timestamp


class CrashStore:
    """Singleton thread-safe para acumular eventos de crash de todos os servidores."""

    _instance: Optional["CrashStore"] = None
    _class_lock = threading.Lock()

    @classmethod
    def instance(cls) -> "CrashStore":
        if cls._instance is None:
            with cls._class_lock:
                if cls._instance is None:
                    inst = CrashStore()
                    inst.load()
                    cls._instance = inst
        return cls._instance

    def __init__(self) -> None:
        self._events:    List[CrashEvent] = []
        self._callbacks: List[Callable[["CrashEvent"], None]] = []
        self._lock       = threading.Lock()
        self._data_path  = (
            Path(os.environ.get("APPDATA", Path.home()))
            / "ARKLAND-ServerManager"
            / "crash_events.json"
        )

    # ── Persistência ──────────────────────────────────────────────────────────

    def load(self) -> None:
        try:
            if self._data_path.exists():
                raw = json.loads(self._data_path.read_text(encoding="utf-8"))
                evts: List[CrashEvent] = []
                for d in raw:
                    try:
                        evts.append(CrashEvent(**d))
                    except Exception:
                        pass
                with self._lock:
                    self._events = evts
        except Exception:
            pass

    def _save_unlocked(self) -> None:
        try:
            self._data_path.parent.mkdir(parents=True, exist_ok=True)
            to_save = self._events[-500:]
            self._data_path.write_text(
                json.dumps([asdict(e) for e in to_save], ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception:
            pass

    # ── Escrita ───────────────────────────────────────────────────────────────

    def add(self, evt: CrashEvent) -> None:
        """Adiciona evento (deduplicado por server+timestamp) e notifica callbacks."""
        with self._lock:
            duplicate = any(
                e.server_id == evt.server_id
                and abs((e.ts - evt.ts).total_seconds()) < 10
                for e in self._events
            )
            if duplicate:
                return
            self._events.append(evt)
            self._save_unlocked()
        for cb in list(self._callbacks):
            try:
                cb(evt)
            except Exception:
                pass

    def update_diagnosis(self, event_id: str, diagnosis: str) -> None:
        """Actualiza diagnosis (ex.: resultado da IA) e notifica callbacks."""
        updated: Optional[CrashEvent] = None
        with self._lock:
            for e in self._events:
                if e.event_id == event_id:
                    e.diagnosis = diagnosis or e.diagnosis
                    updated = e
                    break
            if updated is not None:
                self._save_unlocked()
        if updated is None:
            return
        for cb in list(self._callbacks):
            try:
                cb(updated)
            except Exception:
                pass

    def get(self, event_id: str) -> Optional[CrashEvent]:
        with self._lock:
            for e in self._events:
                if e.event_id == event_id:
                    return e
            return None

    def mark_seen(self, event_id: str) -> None:
        with self._lock:
            for e in self._events:
                if e.event_id == event_id:
                    e.seen = True
            self._save_unlocked()

    def mark_all_seen(self) -> None:
        with self._lock:
            for e in self._events:
                e.seen = True
            self._save_unlocked()

    def mark_all_seen_for_server(self, server_id: str) -> None:
        with self._lock:
            for e in self._events:
                if e.server_id == server_id:
                    e.seen = True
            self._save_unlocked()

    def delete(self, event_id: str) -> None:
        with self._lock:
            self._events = [e for e in self._events if e.event_id != event_id]
            self._save_unlocked()

    def delete_for_server(self, server_id: str) -> None:
        with self._lock:
            self._events = [e for e in self._events if e.server_id != server_id]
            self._save_unlocked()

    def clear_all(self) -> None:
        with self._lock:
            self._events.clear()
            self._save_unlocked()

    # ── Leitura ───────────────────────────────────────────────────────────────

    def list_all(self) -> List[CrashEvent]:
        with self._lock:
            return sorted(self._events, key=lambda e: e.timestamp, reverse=True)

    def list_for_server(self, server_id: str) -> List[CrashEvent]:
        with self._lock:
            return sorted(
                [e for e in self._events if e.server_id == server_id],
                key=lambda e: e.timestamp, reverse=True,
            )

    def unseen_count(self) -> int:
        with self._lock:
            return sum(1 for e in self._events if not e.seen)

    def unseen_count_for_server(self, server_id: str) -> int:
        with self._lock:
            return sum(
                1 for e in self._events if not e.seen and e.server_id == server_id
            )

    # ── Callbacks ─────────────────────────────────────────────────────────────

    def register_callback(self, fn: Callable[["CrashEvent"], None]) -> None:
        with self._lock:
            if fn not in self._callbacks:
                self._callbacks.append(fn)

    def unregister_callback(self, fn: Callable[["CrashEvent"], None]) -> None:
        with self._lock:
            try:
                self._callbacks.remove(fn)
            except ValueError:
                pass
