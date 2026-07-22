"""Jobs de manutenção DeliverPending (Fase 2).

recover_stale ENTREGANDO corre a cada ~10s em background — NÃO no claim/GET
por acesso de jogador (evita trabalho extra em cada poll do plugin).
"""
from __future__ import annotations

import logging
from typing import Any, Callable

log = logging.getLogger("arkshop_web.pending_jobs")

DEFAULT_STALE_INTERVAL_SEC = 10.0
_STALE_WORKER_NAME = "arkshop-pending-stale"


def start_pending_stale_scheduler(
    *,
    interval_sec: float = DEFAULT_STALE_INTERVAL_SEC,
    recover_fn: Callable[[], int] | None = None,
) -> Any:
    """Arranca (idempotente) o tick de recuperação ENTREGANDO stale."""
    from background_tasks import start_interval_worker

    fn = recover_fn or recover_stale_entregando_global
    return start_interval_worker(
        fn,
        interval_sec=interval_sec,
        name=_STALE_WORKER_NAME,
        run_immediately=False,
    )


def is_pending_stale_scheduler_alive() -> bool:
    """True se o worker ~10s está realmente a correr (não só flag de boot)."""
    from background_tasks import is_interval_worker_alive

    return is_interval_worker_alive(_STALE_WORKER_NAME)


def recover_stale_entregando_global() -> int:
    """Reabre shop/kit ENTREGANDO expirados (todos os jogadores, lote).

    Sessão curta por jogador + commit explícito: ``_release_db_session(..., force=True)``
    faz rollback — sem commit o UPDATE era descartado. Uma sessão partilhada no lote
    também falhava no 2.º steam_id se algo fechasse o scoped_session a meio.
    """
    import app as app_mod

    if not app_mod._db_ready():
        return 0
    if getattr(app_mod, "_scheduler_pool_busy", lambda: False)():
        return 0

    minutes = app_mod.get_shop_stale_entregando_minutes()
    if minutes <= 0:
        return 0

    from datetime import timedelta
    from sqlalchemy import text

    cutoff = app_mod._now() - timedelta(minutes=minutes)
    if getattr(cutoff, "tzinfo", None) is not None:
        cutoff = cutoff.replace(tzinfo=None)

    db = app_mod._SessionLocal()
    try:
        rows = db.execute(
            text(
                "SELECT DISTINCT steam_id FROM orders "
                "WHERE status = 'ENTREGANDO' AND item_type != 'custom_dino' "
                "AND updated_at < :cutoff LIMIT 80"
            ),
            {"cutoff": cutoff},
        ).fetchall()
        steam_ids = [str(r[0] or "").strip() for r in rows if r and r[0]]
    except Exception:
        log.exception("pending stale recover global failed")
        return 0
    finally:
        app_mod._release_db_session(db, force=True)

    if not steam_ids:
        return 0

    total = 0
    for sid in steam_ids:
        if not sid:
            continue
        db = app_mod._SessionLocal()
        try:
            n = int(
                app_mod.recover_stale_entregando_shop_orders(
                    db, sid, minutes=minutes,
                )
                or 0
            )
            if n:
                db.commit()
                total += n
        except Exception as exc:
            try:
                db.rollback()
            except Exception:
                pass
            log.warning("pending stale recover steam=%s: %s", sid, exc)
        finally:
            app_mod._release_db_session(db, force=True)

    if total:
        log.info("pending stale recover recovered=%s players=%s", total, len(steam_ids))
    return total
