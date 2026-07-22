"""Defaults e helpers do pool SQLAlchemy (Fase 1 — conexões DB).

Parâmetros finais (defaults; override via env):

| Parâmetro       | Valor | Env                        | Porquê |
|-----------------|-------|----------------------------|--------|
| pool_size       | 20    | ARKSHOP_DB_POOL_SIZE       | Meio da faixa 10–30: cabe Waitress 4–8 threads + workers bg (RCON/admin) sem esgotar MariaDB portable |
| max_overflow    | 10    | ARKSHOP_DB_MAX_OVERFLOW    | Faixa 5–15; pico total ≈ 30 conexões (abaixo de max_connections 150–200 do TEK) |
| pool_recycle    | 1800  | ARKSHOP_DB_POOL_RECYCLE    | Plano Fase 1; com pool_pre_ping stale pós-wait_timeout=600 é detectado no checkout |
| pool_timeout    | 5     | ARKSHOP_DB_POOL_TIMEOUT    | Falha rápido em vez de empilhar workers Waitress |

Alinhamento Waitress (outro agente): threads HTTP devem ser ≤ pool_size (ideal 4–8).
Total teórico pool_size+max_overflow=30 << max_connections MariaDB (180).

PROIBIDO: manter sessão/conexão aberta durante RCON, Steam ou Mercado Pago.
Use `db_session()` para abrir→query→fechar; ou `release_before_external_io()`
antes de qualquer I/O externo.
"""
from __future__ import annotations

import logging
import os
from contextlib import contextmanager
from typing import Any, Callable, Generator

log = logging.getLogger("arkshop_web.db_pool")

# Faixas do plano (Fase 1)
POOL_SIZE_MIN, POOL_SIZE_MAX = 10, 30
MAX_OVERFLOW_MIN, MAX_OVERFLOW_MAX = 5, 15

DEFAULT_DB_POOL_SIZE = 20
DEFAULT_DB_MAX_OVERFLOW = 10
DEFAULT_DB_POOL_RECYCLE = 1800
DEFAULT_DB_POOL_TIMEOUT = 5
# MariaDB portable TEK — orçamento duro; N instâncias × pico_pool ≤ isto.
DEFAULT_MARIADB_MAX_CONNECTIONS = 180


def pool_peak_connections(
    *,
    pool_size: int | None = None,
    max_overflow: int | None = None,
) -> int:
    """Pico teórico de conexões dum processo (pool_size + max_overflow)."""
    cfg = resolve_pool_settings(pool_size=pool_size, max_overflow=max_overflow)
    return int(cfg["pool_size"]) + int(cfg["max_overflow"])


def max_safe_app_instances(
    *,
    mariadb_max_connections: int | None = None,
    pool_size: int | None = None,
    max_overflow: int | None = None,
    reserve: int = 20,
) -> int:
    """Quantas instâncias Web Store cabem sem esgotar max_connections.

    reserve: margem p/ admin MariaDB, TEK, mapas, outros clientes.
    """
    peak = pool_peak_connections(pool_size=pool_size, max_overflow=max_overflow)
    budget = int(
        mariadb_max_connections
        if mariadb_max_connections is not None
        else int(
            os.environ.get(
                "ARKSHOP_MARIADB_MAX_CONNECTIONS",
                str(DEFAULT_MARIADB_MAX_CONNECTIONS),
            )
            or DEFAULT_MARIADB_MAX_CONNECTIONS
        )
    )
    usable = max(0, budget - max(0, int(reserve)))
    if peak <= 0:
        return 0
    return max(1, usable // peak)


def resolve_pool_settings(
    *,
    pool_size: int | None = None,
    max_overflow: int | None = None,
    pool_recycle: int | None = None,
    pool_timeout: int | None = None,
) -> dict[str, int]:
    """Resolve tamanhos do pool a partir de args ou env (com floors seguros)."""
    size = pool_size
    if size is None:
        size = int(
            os.environ.get("ARKSHOP_DB_POOL_SIZE", str(DEFAULT_DB_POOL_SIZE))
            or DEFAULT_DB_POOL_SIZE
        )
    overflow = max_overflow
    if overflow is None:
        overflow = int(
            os.environ.get("ARKSHOP_DB_MAX_OVERFLOW", str(DEFAULT_DB_MAX_OVERFLOW))
            or DEFAULT_DB_MAX_OVERFLOW
        )
    recycle = pool_recycle
    if recycle is None:
        recycle = int(
            os.environ.get("ARKSHOP_DB_POOL_RECYCLE", str(DEFAULT_DB_POOL_RECYCLE))
            or DEFAULT_DB_POOL_RECYCLE
        )
    timeout = pool_timeout
    if timeout is None:
        timeout = int(
            os.environ.get("ARKSHOP_DB_POOL_TIMEOUT", str(DEFAULT_DB_POOL_TIMEOUT))
            or DEFAULT_DB_POOL_TIMEOUT
        )

    size = max(5, int(size))
    overflow = max(0, int(overflow))
    recycle = max(60, int(recycle))
    timeout = max(2, int(timeout))

    if not (POOL_SIZE_MIN <= size <= POOL_SIZE_MAX):
        log.warning(
            "ARKSHOP_DB_POOL_SIZE=%s fora da faixa recomendada %s–%s "
            "(alinhamento Waitress / MariaDB)",
            size,
            POOL_SIZE_MIN,
            POOL_SIZE_MAX,
        )
    if overflow and not (MAX_OVERFLOW_MIN <= overflow <= MAX_OVERFLOW_MAX):
        log.warning(
            "ARKSHOP_DB_MAX_OVERFLOW=%s fora da faixa recomendada %s–%s",
            overflow,
            MAX_OVERFLOW_MIN,
            MAX_OVERFLOW_MAX,
        )

    return {
        "pool_size": size,
        "max_overflow": overflow,
        "pool_recycle": recycle,
        "pool_timeout": timeout,
    }


def engine_pool_kwargs(**overrides: int | None) -> dict[str, int]:
    """Kwargs prontos para sqlalchemy.create_engine(..., **engine_pool_kwargs())."""
    return resolve_pool_settings(**overrides)


@contextmanager
def db_session(
    session_factory: Callable[[], Any],
    *,
    release: Callable[..., None] | None = None,
    commit: bool = False,
) -> Generator[Any, None, None]:
    """Abre sessão, executa bloco, devolve conexão ao pool imediatamente.

    Sempre faz rollback (se não commit) + close/remove no finally — mesmo path
    de request Flask. Usar para transações curtas antes de I/O externo.

    Exemplo::

        with db_session(_SessionLocal, release=_release_db_session, commit=True) as db:
            db.add(row)
        # aqui a conexão já voltou ao pool — seguro chamar RCON/Steam/MP
    """
    db = session_factory()
    try:
        yield db
        if commit:
            db.commit()
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass
        raise
    finally:
        if release is not None:
            try:
                release(db, force=True)
            except TypeError:
                release(db)
        else:
            try:
                db.close()
            except Exception:
                pass


def release_before_external_io(
    release: Callable[..., None],
    db: Any | None = None,
) -> None:
    """Liberta a sessão ANTES de RCON / Steam / Mercado Pago / HTTP externo.

    Problema que evita: worker Waitress + conexão QueuePool presos 4–30s em I/O
    → pool esgotado → QueuePool timeout nos outros requests.
    """
    try:
        release(db, force=True)
    except TypeError:
        release(db)
