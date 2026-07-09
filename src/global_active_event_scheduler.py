"""Agendamento de eventos ARK oficiais (ActiveEvent) com broadcast e restart automático."""
from __future__ import annotations

import json
import logging
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, List, Optional

from .buff_manager import now_brasilia
from .rcon_client import RconClient
from .server_config import SERVER_STATUS_RUNNING, SERVER_STATUS_STOPPED
from .ui_constants import _ARK_EVENT_ID_TO_LABEL, normalize_active_event

_log = logging.getLogger("arkland")

ARK_EVENT_STATUS_SCHEDULED = "scheduled"
ARK_EVENT_STATUS_APPLYING = "applying"
ARK_EVENT_STATUS_NOTIFYING = "notifying"
ARK_EVENT_STATUS_COMPLETED = "completed"
ARK_EVENT_STATUS_CANCELLED = "cancelled"
ARK_EVENT_STATUS_FAILED = "failed"

COUNTDOWN_THRESHOLDS: list[tuple[int, str]] = [
    (600, "10 minutos"),
    (300, "5 minutos"),
    (180, "3 minutos"),
    (120, "2 minutos"),
    (60, "1 minuto"),
]
POST_NOTIFY_INTERVAL_SEC = 600
POST_NOTIFY_DURATION_SEC = 3600
_SAVEWORLD_WAIT_SEC = 15
_DATETIME_FMT = "%d/%m/%Y %H:%M"


def parse_brasilia_datetime(raw: str) -> datetime:
    text = (raw or "").strip()
    for fmt in (_DATETIME_FMT, "%d/%m/%Y %H:%M:%S"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    raise ValueError(f"Data/hora inválida: {raw!r} (use dd/mm/aaaa HH:MM)")


def format_brasilia_datetime(dt: datetime) -> str:
    return dt.strftime(_DATETIME_FMT)


def event_display_name(event_id: str) -> str:
    eid = normalize_active_event(event_id)
    if not eid:
        return "(nenhum evento)"
    label = _ARK_EVENT_ID_TO_LABEL.get(eid, eid)
    if "—" in label:
        return label.split("—", 1)[0].strip()
    return label


@dataclass
class ScheduledArkEvent:
    id: str
    event_id: str
    scheduled_at: str  # ISO local Brasília (naive)
    server_ids: List[str]
    status: str = ARK_EVENT_STATUS_SCHEDULED
    warnings_sent: List[str] = field(default_factory=list)
    activated_at: str = ""
    last_notify_at: float = 0.0
    created_at: str = ""
    error_message: str = ""

    def scheduled_datetime(self) -> datetime:
        return datetime.fromisoformat(self.scheduled_at)

    def activated_datetime(self) -> Optional[datetime]:
        if not self.activated_at:
            return None
        return datetime.fromisoformat(self.activated_at)

    def display_event(self) -> str:
        return event_display_name(self.event_id)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "ScheduledArkEvent":
        valid = {f.name for f in cls.__dataclass_fields__.values()}
        kwargs = {k: v for k, v in data.items() if k in valid}
        if "warnings_sent" not in kwargs:
            kwargs["warnings_sent"] = []
        return cls(**kwargs)


class GlobalActiveEventScheduler:
    """Scheduler de ActiveEvent com avisos RCON, restart e notificações pós-início."""

    def __init__(
        self,
        data_dir: Path,
        *,
        get_server_config: Callable[[str], Any],
        get_server_status: Callable[[str], str],
        stop_server: Callable[[str], None],
        start_server: Callable[[str], None],
        apply_active_event: Callable[[list[str], str], list[Any]],
        on_log: Optional[Callable[[str, str], None]] = None,
        on_change: Optional[Callable[[], None]] = None,
    ) -> None:
        self._file = data_dir / "global_ark_events.json"
        self._get_server_config = get_server_config
        self._get_server_status = get_server_status
        self._stop_server = stop_server
        self._start_server = start_server
        self._apply_active_event = apply_active_event
        self._on_log = on_log or (lambda _m, _l="info": None)
        self._on_change = on_change or (lambda: None)
        self._events: list[ScheduledArkEvent] = []
        self._lock = threading.Lock()
        self._stop_evt = threading.Event()
        self._applying: set[str] = set()
        self.load()
        self._thread = threading.Thread(
            target=self._scheduler_loop, daemon=True, name="ARKGlobalEventScheduler",
        )
        self._thread.start()

    # ── Persistência ──────────────────────────────────────────────────────

    def load(self) -> None:
        if not self._file.exists():
            self._events = []
            return
        try:
            with open(self._file, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            self._events = [ScheduledArkEvent.from_dict(x) for x in data]
        except Exception as exc:
            _log.warning("global_ark_events load: %s", exc)
            self._events = []

    def save(self) -> None:
        self._file.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._file.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump([e.to_dict() for e in self._events], fh, indent=2, ensure_ascii=False)
        tmp.replace(self._file)

    def list_events(self) -> list[ScheduledArkEvent]:
        with self._lock:
            return list(self._events)

    def get_scheduled(self) -> list[ScheduledArkEvent]:
        with self._lock:
            return [
                e for e in self._events
                if e.status in (ARK_EVENT_STATUS_SCHEDULED, ARK_EVENT_STATUS_APPLYING, ARK_EVENT_STATUS_NOTIFYING)
            ]

    def schedule_event(
        self,
        event_id: str,
        when: datetime,
        server_ids: list[str],
    ) -> tuple[Optional[ScheduledArkEvent], str]:
        event_id = normalize_active_event(event_id)
        ids = [s for s in server_ids if s]
        if not ids:
            return None, "Selecione ao menos um servidor."
        if when <= now_brasilia():
            return None, "A data/hora deve ser no futuro."

        ev = ScheduledArkEvent(
            id=str(uuid.uuid4()),
            event_id=event_id,
            scheduled_at=when.isoformat(timespec="minutes"),
            server_ids=ids,
            status=ARK_EVENT_STATUS_SCHEDULED,
            created_at=now_brasilia().isoformat(timespec="seconds"),
        )
        with self._lock:
            self._events.append(ev)
        self.save()
        self._on_change()
        self._log(
            f"[Eventos Globais] Agendado: {ev.display_event()} em "
            f"{format_brasilia_datetime(when)} ({len(ids)} servidor(es))",
            "info",
        )
        return ev, ""

    def cancel_event(self, event_id: str) -> str:
        with self._lock:
            for e in self._events:
                if e.id == event_id and e.status == ARK_EVENT_STATUS_SCHEDULED:
                    e.status = ARK_EVENT_STATUS_CANCELLED
                    self.save()
                    self._on_change()
                    return ""
            return "Evento não encontrado ou já em execução."

    # ── RCON ──────────────────────────────────────────────────────────────

    def _rcon_password(self, cfg: Any) -> str:
        return (
            getattr(cfg, "admin_password", "") or getattr(cfg, "rcon_password", "") or ""
        ).strip()

    def _broadcast(self, server_ids: list[str], message: str) -> None:
        for sid in server_ids:
            cfg = self._get_server_config(sid)
            if not cfg or not getattr(cfg, "rcon_enabled", False):
                continue
            pwd = self._rcon_password(cfg)
            if not pwd:
                continue
            if self._get_server_status(sid) != SERVER_STATUS_RUNNING:
                continue
            host = (getattr(cfg, "server_ip", "") or "").strip() or "127.0.0.1"
            port = int(getattr(cfg, "rcon_port", 0) or 0)
            if port <= 0:
                continue
            try:
                rc = RconClient(host, port, pwd)
                rc.connect()
                rc.send_command_safe(f"broadcast {message}")
                rc.disconnect()
            except Exception as exc:
                self._log(f"[Eventos Globais] Broadcast falhou ({sid}): {exc}", "warning")

    def _saveworld(self, server_id: str) -> None:
        cfg = self._get_server_config(server_id)
        if not cfg or not getattr(cfg, "rcon_enabled", False):
            return
        pwd = self._rcon_password(cfg)
        if not pwd or self._get_server_status(server_id) != SERVER_STATUS_RUNNING:
            return
        host = (getattr(cfg, "server_ip", "") or "").strip() or "127.0.0.1"
        port = int(getattr(cfg, "rcon_port", 0) or 0)
        try:
            rc = RconClient(host, port, pwd)
            rc.connect()
            rc.send_command_safe("SaveWorld")
            rc.disconnect()
        except Exception as exc:
            self._log(f"[Eventos Globais] SaveWorld falhou ({server_id}): {exc}", "warning")

    def _wait_status(self, server_id: str, want: str, timeout: int) -> bool:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self._get_server_status(server_id) == want:
                return True
            time.sleep(2)
        return False

    # ── Aplicação ─────────────────────────────────────────────────────────

    def _apply_worker(self, event: ScheduledArkEvent) -> None:
        name = event.display_event()
        sids = list(event.server_ids)

        with self._lock:
            if event.id in self._applying:
                return
            self._applying.add(event.id)
            event.status = ARK_EVENT_STATUS_APPLYING
        self.save()
        self._on_change()

        try:
            self._broadcast(
                sids,
                f"[ARKLAND] Reiniciando para aplicar o evento {name}.",
            )
            time.sleep(3)

            for sid in sids:
                if self._get_server_status(sid) == SERVER_STATUS_RUNNING:
                    self._saveworld(sid)
            time.sleep(_SAVEWORLD_WAIT_SEC)

            for sid in sids:
                if self._get_server_status(sid) == SERVER_STATUS_RUNNING:
                    self._stop_server(sid)

            for sid in sids:
                if not self._wait_status(sid, SERVER_STATUS_STOPPED, 180):
                    self._log(f"[Eventos Globais] Timeout parando {sid}", "warning")

            results = self._apply_active_event(sids, event.event_id)
            failed = [r for r in results if not getattr(r, "ok", False)]
            if failed:
                names = ", ".join(getattr(r, "server_name", "?") for r in failed[:5])
                raise RuntimeError(f"Falha ao gravar INI: {names}")

            for sid in sids:
                self._start_server(sid)

            for sid in sids:
                if not self._wait_status(sid, SERVER_STATUS_RUNNING, 300):
                    self._log(f"[Eventos Globais] Timeout iniciando {sid}", "warning")

            activated = now_brasilia()
            with self._lock:
                event.status = ARK_EVENT_STATUS_NOTIFYING
                event.activated_at = activated.isoformat(timespec="seconds")
                event.last_notify_at = time.time()
                event.error_message = ""
            self.save()
            self._on_change()

            self._broadcast(
                sids,
                f"[ARKLAND] O evento {name} está ativo neste mapa!",
            )
            self._log(f"[Eventos Globais] Evento {name} aplicado em {len(sids)} servidor(es).", "info")

        except Exception as exc:
            with self._lock:
                event.status = ARK_EVENT_STATUS_FAILED
                event.error_message = str(exc)
            self.save()
            self._on_change()
            self._log(f"[Eventos Globais] Falha ao aplicar {name}: {exc}", "error")
        finally:
            with self._lock:
                self._applying.discard(event.id)

    # ── Tick ──────────────────────────────────────────────────────────────

    def _scheduler_loop(self) -> None:
        while not self._stop_evt.is_set():
            try:
                self._tick()
            except Exception as exc:
                self._log(f"[Eventos Globais] Erro no scheduler: {exc}", "error")
            self._stop_evt.wait(30)

    def _tick(self) -> None:
        now = now_brasilia()
        to_apply: list[ScheduledArkEvent] = []
        to_warn: list[tuple[ScheduledArkEvent, str, str]] = []
        to_notify: list[ScheduledArkEvent] = []
        to_complete: list[ScheduledArkEvent] = []

        with self._lock:
            for e in self._events:
                if e.status == ARK_EVENT_STATUS_SCHEDULED:
                    start = e.scheduled_datetime()
                    if start <= now:
                        to_apply.append(e)
                    else:
                        secs_left = (start - now).total_seconds()
                        sent = set(e.warnings_sent)
                        for threshold, label in COUNTDOWN_THRESHOLDS:
                            key = f"pre:{threshold}"
                            if secs_left <= threshold and key not in sent:
                                to_warn.append((e, label, key))
                elif e.status == ARK_EVENT_STATUS_NOTIFYING:
                    activated = e.activated_datetime()
                    if not activated:
                        to_complete.append(e)
                        continue
                    elapsed = (now - activated).total_seconds()
                    if elapsed >= POST_NOTIFY_DURATION_SEC:
                        to_complete.append(e)
                    elif time.time() - e.last_notify_at >= POST_NOTIFY_INTERVAL_SEC:
                        to_notify.append(e)

        for e, label, key in to_warn:
            with self._lock:
                if key not in e.warnings_sent:
                    e.warnings_sent.append(key)
            self.save()
            self._broadcast(
                e.server_ids,
                f"[ARKLAND] O servidor reiniciará em {label} para aplicar o evento {e.display_event()}.",
            )

        for e in to_apply:
            with self._lock:
                if e.id in self._applying:
                    continue
            threading.Thread(
                target=self._apply_worker,
                args=(e,),
                daemon=True,
                name=f"ARKGlobalEvent-{e.id[:8]}",
            ).start()

        for e in to_notify:
            with self._lock:
                e.last_notify_at = time.time()
            self.save()
            self._broadcast(
                e.server_ids,
                f"[ARKLAND] O evento {e.display_event()} está ativo neste mapa!",
            )

        if to_complete:
            with self._lock:
                for e in to_complete:
                    if e.status == ARK_EVENT_STATUS_NOTIFYING:
                        e.status = ARK_EVENT_STATUS_COMPLETED
            self.save()
            self._on_change()

    def _log(self, msg: str, level: str = "info") -> None:
        self._on_log(msg, level)

    def stop(self) -> None:
        self._stop_evt.set()
