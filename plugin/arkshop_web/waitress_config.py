"""Configuração Waitress alinhada ao pool MySQL (Fase 5).

Waitress neste projeto corre **1 processo** (sem multi-worker gunicorn).
O plano pede workers ≈ (CPU×2)+1 e threads 4–8; aqui a fórmula de workers
define o número de **threads** do único processo, limitado a 4–8.

Alinhamento Fase 1 (`db_pool`): threads HTTP ≤ pool_size (default 20).
Total teórico threads ≪ pool_size+max_overflow (30) ≪ max_connections MariaDB.
"""
from __future__ import annotations

import os
from typing import Any


THREADS_MIN = 4
THREADS_MAX = 8
# Reserva no pool para arkshop-bg + retry scheduler + pending-stale (pool_timeout=5).
DEFAULT_POOL_HEADROOM = 6
DEFAULT_CHANNEL_TIMEOUT = 180
DEFAULT_CONNECTION_LIMIT = 500
DEFAULT_BACKLOG = 2048


def cpu_count_safe() -> int:
    try:
        n = os.cpu_count()
    except Exception:
        n = None
    return max(1, int(n or 2))


def workers_formula(cpus: int | None = None) -> int:
    """(CPU × 2) + 1 — fórmula do plano (usada como threads no Waitress)."""
    return (int(cpus if cpus is not None else cpu_count_safe()) * 2) + 1


def default_http_threads(cpus: int | None = None) -> int:
    """Threads default: fórmula de workers, clamp 4–8."""
    return max(THREADS_MIN, min(THREADS_MAX, workers_formula(cpus)))


def resolve_http_threads(
    *,
    pool_size: int | None = None,
    cpus: int | None = None,
) -> dict[str, Any]:
    """Resolve threads Waitress a partir de env + CPU + cap ao pool.

    Env:
      ARKSHOP_HTTP_THREADS — override explícito (ainda clampado a ≥4)
      ARKSHOP_HTTP_THREADS_FORCE=1 — não capar ao pool_size
      ARKSHOP_HTTP_THREADS_CAP_TO_POOL=0 — desliga cap (legado; default=cap on)
    """
    formula = workers_formula(cpus)
    default_threads = default_http_threads(cpus)
    raw_env = os.environ.get("ARKSHOP_HTTP_THREADS")
    if raw_env is not None and str(raw_env).strip() != "":
        threads_raw = max(THREADS_MIN, int(raw_env))
        source = "env"
    else:
        threads_raw = default_threads
        source = "cpu_formula"

    force = os.environ.get("ARKSHOP_HTTP_THREADS_FORCE") == "1"
    # Default: CAP ligado (threads ≤ pool−headroom). Legado: CAP_TO_POOL=0 desliga.
    cap_off = os.environ.get("ARKSHOP_HTTP_THREADS_CAP_TO_POOL") == "0"
    pool = int(pool_size) if pool_size is not None else None
    try:
        headroom = max(
            0,
            int(
                os.environ.get("ARKSHOP_HTTP_POOL_HEADROOM", str(DEFAULT_POOL_HEADROOM))
                or DEFAULT_POOL_HEADROOM
            ),
        )
    except (TypeError, ValueError):
        headroom = DEFAULT_POOL_HEADROOM

    capped = False
    threads = threads_raw
    pool_cap: int | None = None
    if not force and not cap_off and pool is not None and pool > 0:
        # Nunca threads > pool; com headroom deixa margem p/ workers bg (timeout 5s).
        pool_cap = max(1, int(pool) - headroom)
        if pool_cap < THREADS_MIN and pool >= THREADS_MIN:
            pool_cap = THREADS_MIN
        if threads > pool_cap:
            threads = pool_cap
            capped = True

    # Sem FORCE, nunca exagerar além de THREADS_MAX no default/auto
    if not force and source == "cpu_formula":
        threads = max(THREADS_MIN, min(THREADS_MAX, threads))

    # Floor THREADS_MIN sem re-ultrapassar o cap do pool (bug: max(4, pool_cap) quando pool<4).
    result_threads = max(THREADS_MIN, int(threads))
    if not force and pool_cap is not None and pool_cap > 0:
        result_threads = min(result_threads, max(1, pool_cap))
        if pool is not None and pool > 0:
            result_threads = min(result_threads, int(pool))

    return {
        "threads": int(result_threads),
        "threads_raw": int(threads_raw),
        "workers_formula": formula,
        "cpus": int(cpus if cpus is not None else cpu_count_safe()),
        "pool_size": pool,
        "pool_headroom": headroom,
        "pool_cap": pool_cap,
        "capped_to_pool": capped,
        "source": source,
        "channel_timeout": max(
            30, int(os.environ.get("ARKSHOP_CHANNEL_TIMEOUT", str(DEFAULT_CHANNEL_TIMEOUT)) or DEFAULT_CHANNEL_TIMEOUT)
        ),
        "connection_limit": max(
            50,
            int(
                os.environ.get("ARKSHOP_CONNECTION_LIMIT", str(DEFAULT_CONNECTION_LIMIT))
                or DEFAULT_CONNECTION_LIMIT
            ),
        ),
        "backlog": max(
            64, int(os.environ.get("ARKSHOP_HTTP_BACKLOG", str(DEFAULT_BACKLOG)) or DEFAULT_BACKLOG)
        ),
    }
