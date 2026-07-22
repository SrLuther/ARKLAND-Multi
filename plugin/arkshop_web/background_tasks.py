"""Fila mínima de background (Fase 2) — threading/queue, sem Celery/Redis.

Alinhado ao padrão já usado no projeto (`ThreadPoolExecutor`, threads daemon,
single-flight). Use para RCON, Mercado Pago, Steam e manutenção que não
devem segurar o worker Waitress nem a sessão MySQL.
"""
from __future__ import annotations

import logging
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable

log = logging.getLogger("arkshop_web.background_tasks")

_MAX_WORKERS = max(1, min(8, int(os.environ.get("ARKSHOP_BG_WORKERS", "4") or 4)))
_INLINE_RAW = os.environ.get("ARKSHOP_BG_INLINE", "").strip().lower() in ("1", "true", "yes")
_INLINE = _INLINE_RAW

_executor = ThreadPoolExecutor(max_workers=_MAX_WORKERS, thread_name_prefix="arkshop-bg")
_inflight: set[str] = set()
_inflight_lock = threading.Lock()

_interval_threads: dict[str, threading.Thread] = {}
_interval_stops: dict[str, threading.Event] = {}
_interval_lock = threading.Lock()
_inline_prod_warned = False


def _production_env() -> bool:
    return (os.environ.get("ARKSHOP_ENV", "") or "").strip().lower() == "production"


def _warn_inline_ignored_once(*, context: str) -> None:
    global _inline_prod_warned
    if _inline_prod_warned:
        return
    _inline_prod_warned = True
    log.error(
        "ARKSHOP_BG_INLINE ignorado (%s): ARKSHOP_ENV=production "
        "(schedulers/pagamento ficariam síncronos ou mortos)",
        context,
    )


def _effective_inline() -> bool:
    """INLINE só em testes/dev — em production ignora (senão schedulers 'OK' mas mortos)."""
    if not _INLINE:
        return False
    if _production_env():
        return False
    return True


def set_inline_mode(enabled: bool) -> None:
    """Força execução síncrona (testes). Prefira monkeypatch de submit."""
    global _INLINE
    _INLINE = bool(enabled)


def is_inline_mode() -> bool:
    return _effective_inline()


def submit(
    fn: Callable[..., Any],
    *args: Any,
    dedupe_key: str | None = None,
    name: str | None = None,
    **kwargs: Any,
) -> bool:
    """Enfileira fn(*args, **kwargs). Retorna False se dedupe_key já está a correr.

    Em ARKSHOP_BG_INLINE=1 (ou set_inline_mode) corre no caller — útil em testes.
    Em ARKSHOP_ENV=production o INLINE é ignorado (evita HTTP sync + schedulers mortos).
    """
    if _INLINE and _production_env():
        _warn_inline_ignored_once(context="submit")

    key = str(dedupe_key).strip() if dedupe_key else ""
    if key:
        with _inflight_lock:
            if key in _inflight:
                return False
            _inflight.add(key)

    def _run() -> None:
        try:
            fn(*args, **kwargs)
        except Exception:
            log.exception("background task failed name=%s key=%s", name or getattr(fn, "__name__", "?"), key or "-")
        finally:
            if key:
                with _inflight_lock:
                    _inflight.discard(key)

    if _effective_inline():
        _run()
        return True

    _executor.submit(_run)
    return True


def spawn_daemon(fn: Callable[[], Any], *, name: str) -> threading.Thread:
    """Thread daemon fire-and-forget (mesmo padrão de _rcon_permission_fanout_background)."""
    t = threading.Thread(target=fn, name=name, daemon=True)
    if _effective_inline():
        fn()
        return t
    t.start()
    return t


def start_interval_worker(
    fn: Callable[[], Any],
    *,
    interval_sec: float,
    name: str,
    run_immediately: bool = False,
) -> threading.Thread:
    """Agenda fn a cada interval_sec (idempotente por name)."""
    if _INLINE and _production_env():
        _warn_inline_ignored_once(context=f"interval:{name}")
    interval = max(1.0, float(interval_sec))
    with _interval_lock:
        existing = _interval_threads.get(name)
        if existing is not None and existing.is_alive():
            return existing
        old_stop = _interval_stops.pop(name, None)
        if old_stop is not None:
            old_stop.set()
        stop = threading.Event()
        _interval_stops[name] = stop

        def _loop() -> None:
            if run_immediately and not stop.is_set():
                try:
                    fn()
                except Exception:
                    log.exception("interval worker first tick failed name=%s", name)
            while not stop.wait(interval):
                try:
                    fn()
                except Exception:
                    log.exception("interval worker tick failed name=%s", name)

        t = threading.Thread(target=_loop, name=name, daemon=True)
        _interval_threads[name] = t
        if _effective_inline():
            # Em inline (só testes/dev) não arranca loop infinito.
            return t
        t.start()
        return t


def stop_interval_worker(name: str) -> None:
    with _interval_lock:
        stop = _interval_stops.pop(name, None)
        _interval_threads.pop(name, None)
    if stop is not None:
        stop.set()


def is_interval_worker_alive(name: str) -> bool:
    with _interval_lock:
        t = _interval_threads.get(name)
    return t is not None and t.is_alive()


def wait_idle(timeout: float = 5.0) -> bool:
    """Espera inflight esvaziar (testes). Não usar em produção."""
    deadline = time.monotonic() + max(0.1, float(timeout))
    while time.monotonic() < deadline:
        with _inflight_lock:
            if not _inflight:
                return True
        time.sleep(0.02)
    with _inflight_lock:
        return not _inflight
