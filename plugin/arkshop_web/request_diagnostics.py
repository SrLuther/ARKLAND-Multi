"""Diagnóstico HTTP — logs estruturados por request e eventos operacionais.

Complementa db_diagnostics.py (pool/query) com visibilidade de rota, steam/admin,
duração total, falhas de API e eventos de catálogo/config.
"""
from __future__ import annotations

import json
import logging
import os
import threading
import time
from collections import Counter, deque
from typing import Any

log = logging.getLogger("arkshop_web.request")

# slow: só requests lentos ou com erro (default produção TEK)
# api: todas as rotas /api/* (sucesso rápido em DEBUG)
# all: todo request HTTP
# off: nunca loga http_request (eventos explícitos mantêm-se)
REQUEST_LOG_MODE = (os.environ.get("ARKSHOP_LOG_REQUESTS", "slow") or "slow").lower()
SLOW_REQUEST_MS = max(100, int(os.environ.get("ARKSHOP_SLOW_REQUEST_MS", "2000") or 2000))

_MAX_RECENT = 60
_MAX_EVENTS = 50

_lock = threading.Lock()
_recent_requests: deque[dict[str, Any]] = deque(maxlen=_MAX_RECENT)
_recent_events: deque[dict[str, Any]] = deque(maxlen=_MAX_EVENTS)
_event_counters: Counter[str] = Counter()

_ctx = threading.local()


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _safe_path(path: str) -> str:
    """Path sem segredos — só basename se parecer absoluto longo."""
    p = str(path or "").strip()
    if not p:
        return ""
    if len(p) > 200:
        from pathlib import Path

        return str(Path(p).name) or p[:80]
    return p


def begin_request(
    *,
    request_id: str,
    route: str,
    method: str = "GET",
    steam_id: str | None = None,
    is_admin: bool | None = None,
) -> None:
    _ctx.request_id = request_id
    _ctx.route = route or ""
    _ctx.method = (method or "GET").upper()
    _ctx.steam_id = (steam_id or "").strip() or None
    _ctx.is_admin = bool(is_admin) if is_admin is not None else None
    _ctx.started = time.perf_counter()
    _ctx.db_wait_ms = 0.0
    _ctx.status_code = 200
    _ctx.outcome = "ok"
    _ctx.api_error: str | None = None
    _ctx.http_error: str | None = None


def add_db_wait_ms(ms: float) -> None:
    if ms <= 0:
        return
    _ctx.db_wait_ms = float(getattr(_ctx, "db_wait_ms", 0.0) or 0.0) + ms


def set_request_actor(*, steam_id: str | None = None, is_admin: bool | None = None) -> None:
    if steam_id:
        _ctx.steam_id = str(steam_id).strip() or None
    if is_admin is not None:
        _ctx.is_admin = bool(is_admin)


def set_request_error(*, http_error: str | None = None, api_error: str | None = None) -> None:
    if http_error:
        _ctx.http_error = str(http_error)[:300]
        _ctx.outcome = "error"
    if api_error:
        _ctx.api_error = str(api_error)[:300]
        _ctx.outcome = "error"


def record_event(event_type: str, *, level: str = "info", **fields: Any) -> None:
    """Evento operacional explícito (catálogo, pool, boot, long_transaction)."""
    entry: dict[str, Any] = {
        "at": _now_iso(),
        "event": event_type,
        "request_id": str(getattr(_ctx, "request_id", "") or ""),
        "route": str(getattr(_ctx, "route", "") or ""),
    }
    for key, val in fields.items():
        if val is None:
            continue
        if key.endswith("_path") or key == "config_path":
            entry[key] = _safe_path(str(val))
        elif isinstance(val, (str, int, float, bool)):
            entry[key] = val
        else:
            entry[key] = str(val)[:300]

    with _lock:
        _event_counters[event_type] += 1
        _recent_events.appendleft(dict(entry))

    parts = " ".join(f"{k}={json.dumps(v)}" for k, v in entry.items() if k not in ("at", "event"))
    msg = f'"{event_type}" {parts}'.strip()
    if level == "warning":
        log.warning(msg)
    elif level == "error":
        log.error(msg)
    else:
        log.info(msg)


def finish_request(*, status_code: int, outcome: str | None = None) -> dict[str, Any] | None:
    """Finaliza request — log estruturado + ring buffer se lento/erro."""
    started = getattr(_ctx, "started", None)
    if started is None:
        return None

    duration_ms = round((time.perf_counter() - started) * 1000.0, 2)
    db_wait_ms = round(float(getattr(_ctx, "db_wait_ms", 0.0) or 0.0), 2)
    route = str(getattr(_ctx, "route", "") or "")
    method = str(getattr(_ctx, "method", "GET") or "GET")
    request_id = str(getattr(_ctx, "request_id", "") or "")
    steam_id = getattr(_ctx, "steam_id", None)
    is_admin = getattr(_ctx, "is_admin", None)
    api_error = getattr(_ctx, "api_error", None)
    http_error = getattr(_ctx, "http_error", None)

    final_outcome = outcome or str(getattr(_ctx, "outcome", "ok") or "ok")
    if status_code >= 500:
        final_outcome = "error"
    elif status_code >= 400 and final_outcome == "ok":
        final_outcome = "error"

    entry: dict[str, Any] = {
        "at": _now_iso(),
        "request_id": request_id,
        "route": route,
        "method": method,
        "duration_ms": duration_ms,
        "db_wait_ms": db_wait_ms,
        "status": status_code,
        "outcome": final_outcome,
    }
    if steam_id:
        entry["steam_id"] = steam_id
    if is_admin is not None:
        entry["is_admin"] = is_admin
    if api_error:
        entry["api_error"] = api_error
    if http_error:
        entry["http_error"] = http_error

    is_slow = duration_ms >= SLOW_REQUEST_MS
    is_error = final_outcome != "ok"
    is_api = route.startswith("/api/")

    if is_slow or is_error:
        with _lock:
            _recent_requests.appendleft(dict(entry))

    should_log = REQUEST_LOG_MODE != "off"
    if should_log:
        log_level = logging.INFO
        if REQUEST_LOG_MODE == "slow" and not is_slow and not is_error:
            log_level = logging.DEBUG
        elif REQUEST_LOG_MODE == "api" and is_api and not is_slow and not is_error:
            log_level = logging.DEBUG
        elif REQUEST_LOG_MODE == "all":
            log_level = logging.DEBUG if not is_slow and not is_error else logging.INFO
        elif REQUEST_LOG_MODE not in ("slow", "api", "all"):
            log_level = logging.DEBUG

        if log_level >= logging.INFO or (log_level == logging.DEBUG and log.isEnabledFor(logging.DEBUG)):
            parts = " ".join(f"{k}={json.dumps(v)}" for k, v in entry.items() if k != "at")
            log.log(log_level, '"http_request" %s', parts)

    return entry


def recent_slow_requests(limit: int = 20) -> list[dict[str, Any]]:
    with _lock:
        return list(_recent_requests)[:limit]


def recent_events(limit: int = 20) -> list[dict[str, Any]]:
    with _lock:
        return list(_recent_events)[:limit]


def event_counters() -> dict[str, int]:
    with _lock:
        return dict(_event_counters)


def diagnostics_snapshot() -> dict[str, Any]:
    return {
        "log_mode": REQUEST_LOG_MODE,
        "slow_request_ms": SLOW_REQUEST_MS,
        "recent_slow_requests": recent_slow_requests(15),
        "recent_events": recent_events(15),
        "event_counters": event_counters(),
    }


def reset_for_tests() -> None:
    with _lock:
        _recent_requests.clear()
        _recent_events.clear()
        _event_counters.clear()
    for attr in (
        "request_id",
        "route",
        "method",
        "steam_id",
        "is_admin",
        "started",
        "db_wait_ms",
        "status_code",
        "outcome",
        "api_error",
        "http_error",
    ):
        try:
            delattr(_ctx, attr)
        except AttributeError:
            pass
