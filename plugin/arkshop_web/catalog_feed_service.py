"""Feed automático catálogo → Mercado + DinoLab (job periódico e gatilhos admin)."""
from __future__ import annotations

import logging
import os
import threading
from datetime import datetime, timezone
from typing import Any, Callable

log = logging.getLogger("arkshop_web.catalog_feed")

_feed_lock = threading.Lock()
_feed_run_lock = threading.Lock()
_last_feed_at: datetime | None = None
_last_feed_result: dict[str, Any] | None = None
_last_feed_source: str | None = None
_scheduler_thread: threading.Thread | None = None
_scheduler_stop = threading.Event()


def _env_flag(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name, "").strip().lower()
    if not raw:
        return default
    return raw in ("1", "true", "yes", "on")


def _feed_interval_minutes() -> int:
    raw = os.environ.get("MARKET_CATALOG_FEED_INTERVAL_MINUTES", "0").strip()
    try:
        return max(0, int(raw))
    except ValueError:
        return 0


def get_catalog_feed_status() -> dict[str, Any]:
    with _feed_lock:
        return {
            "last_run_at": _last_feed_at.isoformat() if _last_feed_at else None,
            "last_source": _last_feed_source,
            "last_result": dict(_last_feed_result) if _last_feed_result else None,
            "interval_minutes": _feed_interval_minutes(),
            "feed_on_catalog_save": _env_flag("MARKET_FEED_ON_CATALOG_SAVE", default=True),
            "auto_activate": _env_flag("MARKET_AUTO_ACTIVATE_SPECIES"),
        }


def _record_feed_result(source: str, result: dict[str, Any]) -> None:
    global _last_feed_at, _last_feed_result, _last_feed_source
    with _feed_lock:
        _last_feed_at = datetime.now(timezone.utc)
        _last_feed_result = result
        _last_feed_source = source


def run_catalog_feed(
    *,
    source: str = "manual",
    activate: bool | None = None,
    catalog: dict[str, Any] | None = None,
    only_missing: bool = False,
    session_factory: Callable[[], Any] | None = None,
    read_catalog: Callable[[], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Executa feed catálogo → market_species com deduplicação."""
    if session_factory is None or read_catalog is None:
        try:
            import app as app_module

            session_factory = app_module._SessionLocal
            read_catalog = app_module._read_shop_config
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    if session_factory is None:
        return {"ok": False, "error": "Banco não configurado"}

    if activate is None:
        activate = _env_flag("MARKET_AUTO_ACTIVATE_SPECIES")

    # Evita feeds concorrentes (boot + save + scheduler) a saturar o pool.
    if not _feed_run_lock.acquire(blocking=False):
        return {
            "ok": False,
            "error": "catalog_feed já em execução",
            "source": source,
            "skipped": True,
        }
    try:
        return _run_catalog_feed_locked(
            source=source,
            activate=activate,
            catalog=catalog,
            only_missing=only_missing,
            session_factory=session_factory,
            read_catalog=read_catalog,
        )
    finally:
        _feed_run_lock.release()


def _run_catalog_feed_locked(
    *,
    source: str,
    activate: bool,
    catalog: dict[str, Any] | None,
    only_missing: bool,
    session_factory: Callable[[], Any],
    read_catalog: Callable[[], dict[str, Any]] | None,
) -> dict[str, Any]:
    db = session_factory()
    try:
        from market_service import feed_catalog_to_market

        cat = catalog if catalog is not None else (read_catalog() if read_catalog else {})
        result = feed_catalog_to_market(
            db,
            cat,
            activate=activate,
            level1_only=True,
            only_missing=only_missing,
            include_reference_and_registry=True,
        )
        result["ok"] = True
        result["source"] = source
        _record_feed_result(source, result)
        log.info(
            "catalog_feed [%s]: created=%s updated=%s merged=%s skipped_duplicate=%s",
            source,
            result.get("created"),
            result.get("updated"),
            result.get("merged"),
            result.get("skipped_duplicate"),
        )
        return result
    except Exception as exc:
        log.warning("catalog_feed [%s] falhou: %s", source, exc)
        err = {"ok": False, "error": str(exc), "source": source}
        _record_feed_result(source, err)
        return err
    finally:
        try:
            db.close()
        except Exception:
            pass
        try:
            if hasattr(session_factory, "remove"):
                session_factory.remove()
            else:
                import app as app_module

                if getattr(app_module, "_SessionLocal", None) is not None:
                    app_module._SessionLocal.remove()
        except Exception:
            pass


def _scheduler_worker(interval_minutes: int) -> None:
    log.info("catalog_feed scheduler started (interval=%s min)", interval_minutes)
    while not _scheduler_stop.wait(interval_minutes * 60):
        try:
            run_catalog_feed(source="scheduler", only_missing=False)
        except Exception as exc:
            log.warning("catalog_feed scheduler tick failed: %s", exc)


def start_catalog_feed_scheduler_if_needed() -> None:
    """Inicia job periódico se MARKET_CATALOG_FEED_INTERVAL_MINUTES > 0."""
    global _scheduler_thread
    interval = _feed_interval_minutes()
    if interval <= 0:
        return
    if _scheduler_thread is not None and _scheduler_thread.is_alive():
        return
    _scheduler_stop.clear()
    _scheduler_thread = threading.Thread(
        target=_scheduler_worker,
        args=(interval,),
        name="catalog-feed",
        daemon=True,
    )
    _scheduler_thread.start()
    if _env_flag("MARKET_CATALOG_FEED_ON_BOOT", default=True):
        threading.Thread(
            target=lambda: run_catalog_feed(source="boot", only_missing=False),
            name="catalog-feed-boot",
            daemon=True,
        ).start()


def maybe_feed_on_catalog_save(catalog: dict[str, Any] | None = None) -> dict[str, Any] | None:
    """Gatilho após salvar config.json (se MARKET_FEED_ON_CATALOG_SAVE=1)."""
    if not _env_flag("MARKET_FEED_ON_CATALOG_SAVE", default=True):
        return None
    return run_catalog_feed(source="catalog_save", catalog=catalog, only_missing=False)
