"""Instrumentação global da camada DB — pool, connect, queries lentas.

Coleta evidência para distinguir:
  - connect_ms alto → latência de rede/TLS ao MySQL remoto
  - pool_wait_ms alto → conexões presas / pool esgotado
  - query_ms alto com DB vazio → DDL, locks ou N+1 por request
"""
from __future__ import annotations

import hashlib
import logging
import os
import re
import threading
import time
import uuid
from collections import Counter, deque
from typing import Any, Callable

from sqlalchemy import event, text
from sqlalchemy.engine import Engine
from sqlalchemy.pool import Pool

log = logging.getLogger("arkshop_web.db_diagnostics")

SLOW_WARN_MS = 500
SLOW_CRITICAL_MS = 1000
_MAX_SLOW = 50
_MAX_ERRORS = 40
_MAX_POOL_SAMPLES = 200
_MAX_CONNECT_SAMPLES = 50

_lock = threading.Lock()
_attached_engines: set[int] = set()

# Ring buffers
_slow_queries: deque[dict[str, Any]] = deque(maxlen=_MAX_SLOW)
_recent_errors: deque[dict[str, Any]] = deque(maxlen=_MAX_ERRORS)
_pool_wait_samples: deque[float] = deque(maxlen=_MAX_POOL_SAMPLES)
_connect_samples: deque[float] = deque(maxlen=_MAX_CONNECT_SAMPLES)
_txn_samples: deque[float] = deque(maxlen=_MAX_POOL_SAMPLES)

# Aggregates (since process start)
_query_count = 0
_query_total_ms = 0.0
_pool_wait_total_ms = 0.0
_pool_wait_count = 0
_connect_total_ms = 0.0
_connect_count = 0
_txn_total_ms = 0.0
_txn_count = 0
_txn_long_count = 0  # transactions > 1s

# Per-request context (thread-local — Waitress = 1 thread/request)
_ctx = threading.local()

# Circuit breaker (fail-fast quando DB degrada)
_circuit_failures = 0
_circuit_open_until = 0.0
_CIRCUIT_THRESHOLD = max(3, int(os.environ.get("ARKSHOP_DB_CIRCUIT_THRESHOLD", "8") or 8))
_CIRCUIT_COOLDOWN_S = max(5.0, float(os.environ.get("ARKSHOP_DB_CIRCUIT_COOLDOWN_S", "30") or 30))

# Fingerprints agregados (top slow)
_fingerprint_ms: Counter[str] = Counter()
_fingerprint_count: Counter[str] = Counter()

_RE_WHITESPACE = re.compile(r"\s+")
_RE_STRINGS = re.compile(r"'(?:[^'\\]|\\.)*'")
_RE_NUMBERS = re.compile(r"\b\d+(?:\.\d+)?\b")


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def set_request_context(*, endpoint: str | None = None, request_id: str | None = None) -> str:
    rid = request_id or str(uuid.uuid4())[:12]
    _ctx.endpoint = endpoint or ""
    _ctx.request_id = rid
    _ctx.pool_wait_recorded = False
    return rid


def clear_request_context() -> None:
    for attr in (
        "endpoint",
        "request_id",
        "pool_wait_recorded",
        "checkout_started",
        "db_wait_total_ms",
    ):
        try:
            delattr(_ctx, attr)
        except AttributeError:
            pass


def get_request_id() -> str:
    return str(getattr(_ctx, "request_id", "") or "")


def get_endpoint() -> str:
    return str(getattr(_ctx, "endpoint", "") or "")


def get_request_db_wait_ms() -> float:
    return float(getattr(_ctx, "db_wait_total_ms", 0.0) or 0.0)


def _accumulate_request_pool_wait(ms: float) -> None:
    if ms <= 0:
        return
    _ctx.db_wait_total_ms = float(getattr(_ctx, "db_wait_total_ms", 0.0) or 0.0) + ms
    try:
        from request_diagnostics import add_db_wait_ms

        add_db_wait_ms(ms)
    except Exception:
        pass


def _emit_request_event(event_type: str, *, level: str = "info", **fields: Any) -> None:
    try:
        from request_diagnostics import record_event

        record_event(event_type, level=level, **fields)
    except Exception:
        pass


def sql_fingerprint(statement: str) -> str:
    """Normaliza SQL para agrupamento — sem valores literais."""
    s = str(statement or "").strip()
    if not s:
        return ""
    s = _RE_STRINGS.sub("?", s)
    s = _RE_NUMBERS.sub("?", s)
    s = _RE_WHITESPACE.sub(" ", s)
    if len(s) > 240:
        s = s[:240] + "…"
    return s


def _fingerprint_hash(fp: str) -> str:
    return hashlib.sha256(fp.encode("utf-8", errors="replace")).hexdigest()[:16]


def record_pool_wait_ms(ms: float) -> None:
    global _pool_wait_total_ms, _pool_wait_count
    if ms < 0:
        return
    with _lock:
        _pool_wait_samples.append(ms)
        _pool_wait_total_ms += ms
        _pool_wait_count += 1


def record_connect_ms(ms: float) -> None:
    global _connect_total_ms, _connect_count
    if ms < 0:
        return
    with _lock:
        _connect_samples.append(ms)
        _connect_total_ms += ms
        _connect_count += 1


def record_transaction_ms(ms: float, *, outcome: str = "commit") -> None:
    global _txn_total_ms, _txn_count, _txn_long_count
    if ms < 0:
        return
    with _lock:
        _txn_samples.append(ms)
        _txn_total_ms += ms
        _txn_count += 1
        if ms >= SLOW_CRITICAL_MS:
            _txn_long_count += 1
            ep = get_endpoint() or "?"
            log.warning("long_transaction %.0fms outcome=%s ep=%s", ms, outcome, ep)
            _emit_request_event(
                "long_transaction",
                level="warning",
                duration_ms=round(ms, 2),
                outcome=outcome,
                endpoint=ep,
                request_id=get_request_id(),
            )


def record_query(
    *,
    statement: str,
    duration_ms: float,
    endpoint: str = "",
    request_id: str = "",
    error: str | None = None,
) -> None:
    global _query_count, _query_total_ms
    fp = sql_fingerprint(statement)
    fp_hash = _fingerprint_hash(fp)
    ep = endpoint or get_endpoint()
    rid = request_id or get_request_id()
    entry: dict[str, Any] = {
        "at": _now_iso(),
        "duration_ms": round(duration_ms, 2),
        "fingerprint": fp,
        "fingerprint_hash": fp_hash,
        "endpoint": ep,
        "request_id": rid,
    }
    if error:
        entry["error"] = error[:200]
    with _lock:
        _query_count += 1
        _query_total_ms += duration_ms
        _fingerprint_ms[fp_hash] += duration_ms
        _fingerprint_count[fp_hash] += 1
        if duration_ms >= SLOW_WARN_MS or error:
            _slow_queries.appendleft(entry)
        if error:
            _recent_errors.appendleft({
                "at": entry["at"],
                "error": error[:300],
                "endpoint": ep,
                "request_id": rid,
                "fingerprint": fp[:120],
            })
            _register_circuit_failure()


def _register_circuit_failure() -> None:
    global _circuit_failures, _circuit_open_until
    _circuit_failures += 1
    if _circuit_failures >= _CIRCUIT_THRESHOLD:
        _circuit_open_until = time.monotonic() + _CIRCUIT_COOLDOWN_S
        log.warning(
            "DB circuit breaker OPEN por %.0fs após %d falhas consecutivas",
            _CIRCUIT_COOLDOWN_S,
            _circuit_failures,
        )


def record_circuit_success() -> None:
    global _circuit_failures, _circuit_open_until
    _circuit_failures = 0
    _circuit_open_until = 0.0


def circuit_is_open() -> bool:
    if time.monotonic() < _circuit_open_until:
        return True
    return False


def circuit_status() -> dict[str, Any]:
    open_until = _circuit_open_until
    remaining = max(0.0, open_until - time.monotonic()) if open_until else 0.0
    return {
        "open": circuit_is_open(),
        "failures": _circuit_failures,
        "cooldown_remaining_s": round(remaining, 1) if circuit_is_open() else 0,
        "threshold": _CIRCUIT_THRESHOLD,
    }


def attach_engine_listeners(engine: Engine) -> None:
    """Regista eventos SQLAlchemy uma vez por engine."""
    eid = id(engine)
    with _lock:
        if eid in _attached_engines:
            return
        _attached_engines.add(eid)

    @event.listens_for(engine, "before_cursor_execute")
    def _before_cursor_execute(
        conn: Any,
        cursor: Any,
        statement: str,
        parameters: Any,
        context: Any,
        executemany: bool,
    ) -> None:
        conn.info["query_start"] = time.perf_counter()

    @event.listens_for(engine, "after_cursor_execute")
    def _after_cursor_execute(
        conn: Any,
        cursor: Any,
        statement: str,
        parameters: Any,
        context: Any,
        executemany: bool,
    ) -> None:
        start = conn.info.pop("query_start", None)
        if start is None:
            return
        ms = (time.perf_counter() - start) * 1000.0
        if ms >= SLOW_WARN_MS:
            log.warning(
                "slow_query %.0fms ep=%s fp=%s",
                ms,
                get_endpoint() or "?",
                sql_fingerprint(statement)[:80],
            )
        record_query(statement=statement, duration_ms=ms)

    @event.listens_for(engine, "handle_error")
    def _handle_error(exception_context: Any) -> None:
        stmt = ""
        try:
            stmt = str(exception_context.statement or "")
        except Exception:
            pass
        record_query(statement=stmt, duration_ms=0.0, error=str(exception_context.original_exception))

    pool = engine.pool

    @event.listens_for(pool, "checkout")
    def _pool_checkout(dbapi_conn: Any, connection_record: Any, connection_proxy: Any) -> None:
        started = connection_record.info.pop("connect_started", None)
        if started is not None:
            connect_ms = (time.perf_counter() - started) * 1000.0
            record_connect_ms(connect_ms)
            connection_record.info["was_new_connect"] = True
        # Tempo de espera no checkout (desde que a thread pediu conexão)
        wait_started = getattr(_ctx, "checkout_started", None)
        if wait_started is not None:
            wait_ms = (time.perf_counter() - wait_started) * 1000.0
            record_pool_wait_ms(wait_ms)
            _accumulate_request_pool_wait(wait_ms)
            _ctx.checkout_started = None
            pool_timeout_ms = max(
                2000.0,
                float(os.environ.get("ARKSHOP_DB_POOL_TIMEOUT", "5") or 5) * 1000.0 * 0.85,
            )
            if wait_ms >= pool_timeout_ms:
                _emit_request_event(
                    "pool_wait_high",
                    level="warning",
                    pool_wait_ms=round(wait_ms, 2),
                    endpoint=get_endpoint() or "?",
                    request_id=get_request_id(),
                )

    @event.listens_for(pool, "checkin")
    def _pool_checkin(dbapi_conn: Any, connection_record: Any) -> None:
        connection_record.info.pop("connect_started", None)
        connection_record.info.pop("was_new_connect", None)

    @event.listens_for(engine, "do_connect")
    def _do_connect(dialect: Any, conn_rec: Any, cargs: Any, cparams: Any) -> None:
        conn_rec.info["connect_started"] = time.perf_counter()

    @event.listens_for(pool, "connect")
    def _pool_connect(dbapi_conn: Any, connection_record: Any) -> None:
        started = connection_record.info.pop("connect_started", None)
        if started is not None:
            connect_ms = (time.perf_counter() - started) * 1000.0
            record_connect_ms(connect_ms)

    @event.listens_for(engine, "begin")
    def _on_begin(conn: Any) -> None:
        conn.info["txn_start"] = time.perf_counter()

    @event.listens_for(engine, "commit")
    def _on_commit(conn: Any) -> None:
        try:
            start = conn.info.pop("txn_start", None)
        except Exception:
            return
        if start is not None:
            record_transaction_ms((time.perf_counter() - start) * 1000.0, outcome="commit")

    @event.listens_for(engine, "rollback")
    def _on_rollback(conn: Any) -> None:
        try:
            start = conn.info.pop("txn_start", None)
        except Exception:
            return
        if start is not None:
            record_transaction_ms((time.perf_counter() - start) * 1000.0, outcome="rollback")


def mark_checkout_started() -> None:
    """Chamar imediatamente antes de obter sessão/conexão do pool."""
    _ctx.checkout_started = time.perf_counter()


def record_pool_timeout(*, endpoint: str = "", error: str = "") -> None:
    _emit_request_event(
        "pool_timeout",
        level="error",
        endpoint=endpoint or get_endpoint() or "?",
        request_id=get_request_id(),
        error=(error or "pool checkout timeout")[:200],
    )


def _pool_stats(engine: Engine) -> dict[str, Any]:
    pool = engine.pool
    try:
        return {
            "pool_size": pool.size(),
            "checked_in": pool.checkedin(),
            "checked_out": pool.checkedout(),
            "overflow": pool.overflow(),
            "max_overflow": getattr(pool, "_max_overflow", None),
        }
    except Exception as exc:
        return {"error": str(exc)}


def _percentile(samples: deque[float], pct: float) -> float | None:
    if not samples:
        return None
    ordered = sorted(samples)
    idx = min(len(ordered) - 1, max(0, int(len(ordered) * pct / 100.0)))
    return round(ordered[idx], 2)


def _avg(samples: deque[float]) -> float | None:
    if not samples:
        return None
    return round(sum(samples) / len(samples), 2)


def top_slow_fingerprints(limit: int = 10) -> list[dict[str, Any]]:
    with _lock:
        slow_copy = list(_slow_queries)
        fp_map: dict[str, dict[str, Any]] = {}
        for entry in slow_copy:
            h = entry.get("fingerprint_hash") or _fingerprint_hash(str(entry.get("fingerprint") or ""))
            if h not in fp_map:
                fp_map[h] = {
                    "fingerprint_hash": h,
                    "fingerprint": entry.get("fingerprint", ""),
                    "count": 0,
                    "max_ms": 0.0,
                    "total_ms": 0.0,
                    "last_endpoint": entry.get("endpoint", ""),
                }
            fp_map[h]["count"] += 1
            ms = float(entry.get("duration_ms") or 0)
            fp_map[h]["total_ms"] += ms
            fp_map[h]["max_ms"] = max(fp_map[h]["max_ms"], ms)
            fp_map[h]["last_endpoint"] = entry.get("endpoint") or fp_map[h]["last_endpoint"]
        ranked = sorted(fp_map.values(), key=lambda x: (-x["max_ms"], -x["count"]))
        out = []
        for row in ranked[:limit]:
            cnt = max(1, row["count"])
            out.append({
                "fingerprint_hash": row["fingerprint_hash"],
                "fingerprint": row["fingerprint"],
                "count": row["count"],
                "max_ms": round(row["max_ms"], 2),
                "avg_ms": round(row["total_ms"] / cnt, 2),
                "last_endpoint": row["last_endpoint"],
            })
        return out


def recent_slow_queries(limit: int = 20) -> list[dict[str, Any]]:
    with _lock:
        return list(_slow_queries)[:limit]


def recent_errors(limit: int = 15) -> list[dict[str, Any]]:
    with _lock:
        return list(_recent_errors)[:limit]


def aggregate_stats() -> dict[str, Any]:
    with _lock:
        q_count = _query_count
        q_total = _query_total_ms
        pw_count = _pool_wait_count
        pw_total = _pool_wait_total_ms
        c_count = _connect_count
        c_total = _connect_total_ms
        t_count = _txn_count
        t_total = _txn_total_ms
        t_long = _txn_long_count
        pw_samples = list(_pool_wait_samples)
        c_samples = list(_connect_samples)
        t_samples = list(_txn_samples)
    return {
        "queries_total": q_count,
        "queries_avg_ms": round(q_total / q_count, 2) if q_count else None,
        "pool_wait_samples": len(pw_samples),
        "pool_wait_avg_ms": round(pw_total / pw_count, 2) if pw_count else None,
        "pool_wait_p95_ms": _percentile(deque(pw_samples), 95),
        "pool_wait_max_ms": round(max(pw_samples), 2) if pw_samples else None,
        "connect_samples": len(c_samples),
        "connect_avg_ms": round(c_total / c_count, 2) if c_count else None,
        "connect_p95_ms": _percentile(deque(c_samples), 95),
        "connect_max_ms": round(max(c_samples), 2) if c_samples else None,
        "transaction_samples": len(t_samples),
        "transaction_avg_ms": round(t_total / t_count, 2) if t_count else None,
        "transaction_p95_ms": _percentile(deque(t_samples), 95),
        "transaction_max_ms": round(max(t_samples), 2) if t_samples else None,
        "transaction_long_count": t_long,
    }


def probe_database(
    engine: Engine,
    session_factory: Callable[[], Any],
    *,
    safe_db_fields: Callable[[str], dict[str, Any]] | None = None,
    active_url: str = "",
    connect_args: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Probe não-destrutivo: ping pooled, connect novo, versão MySQL, pool stats."""
    try:
        from request_diagnostics import diagnostics_snapshot as _req_diag

        request_diag = _req_diag()
    except Exception:
        request_diag = {}

    result: dict[str, Any] = {
        "ok": True,
        "probed_at": _now_iso(),
        "circuit": circuit_status(),
        "aggregates": aggregate_stats(),
        "slow_fingerprints": top_slow_fingerprints(10),
        "recent_slow_queries": recent_slow_queries(15),
        "recent_errors": recent_errors(10),
        "requests": request_diag,
    }

    # NÃO mentir com default 32 (legado) — usar a mesma resolução do Waitress.
    try:
        from db_pool import resolve_pool_settings
        from waitress_config import resolve_http_threads

        _pool = resolve_pool_settings()
        _http = resolve_http_threads(pool_size=_pool["pool_size"])
        result["waitress_threads_configured"] = int(_http["threads"])
        result["waitress_threads_source"] = _http.get("source")
        result["waitress_capped_to_pool"] = bool(_http.get("capped_to_pool"))
        result["db_pool_peak"] = int(_pool["pool_size"]) + int(_pool["max_overflow"])
    except Exception:
        result["waitress_threads_configured"] = max(
            4, int(os.environ.get("ARKSHOP_HTTP_THREADS", "8") or 8)
        )

    if safe_db_fields and active_url:
        result["database"] = safe_db_fields(active_url)
        host = str((result["database"] or {}).get("host") or "")
        result["database"]["likely_remote"] = host not in (
            "",
            "127.0.0.1",
            "localhost",
            "::1",
        )

    if engine is None or session_factory is None:
        result["ok"] = False
        result["error"] = "db_not_configured"
        return result

    result["pool"] = _pool_stats(engine)

    # --- Ping via pool (query_ms + pool_wait_ms) ---
    mark_checkout_started()
    t0 = time.perf_counter()
    db = session_factory()
    try:
        db.execute(text("SELECT 1")).fetchone()
        result["ping_pooled_ms"] = round((time.perf_counter() - t0) * 1000.0, 2)
        record_circuit_success()
    except Exception as exc:
        result["ping_pooled_ms"] = round((time.perf_counter() - t0) * 1000.0, 2)
        result["ping_pooled_error"] = str(exc)[:200]
        result["ok"] = False
        record_query(statement="SELECT 1", duration_ms=result["ping_pooled_ms"], error=str(exc))
    finally:
        try:
            db.close()
        except Exception:
            pass
        try:
            session_factory.remove()
        except Exception:
            pass

    result["pool_after_ping"] = _pool_stats(engine)

    # --- Connect NOVO (NullPool) — mede latência de rede/TLS pura ---
    fresh_ms: float | None = None
    fresh_err: str | None = None
    t_fresh = time.perf_counter()
    try:
        from sqlalchemy import create_engine as _ce
        from sqlalchemy.pool import NullPool

        url = str(engine.url)
        ca = dict(connect_args or {})
        fresh = _ce(
            url,
            future=True,
            poolclass=NullPool,
            pool_pre_ping=False,
            connect_args=ca,
        )
        try:
            cr = fresh.connect()
            try:
                cr.execute(text("SELECT 1")).fetchone()
                fresh_ms = round((time.perf_counter() - t_fresh) * 1000.0, 2)
            finally:
                cr.close()
        finally:
            fresh.dispose()
    except Exception as exc:
        fresh_err = str(exc)[:200]
        fresh_ms = round((time.perf_counter() - t_fresh) * 1000.0, 2)

    result["fresh_connect_ms"] = fresh_ms
    if fresh_err:
        result["fresh_connect_error"] = fresh_err

    # --- Versão do servidor (via pool existente) ---
    try:
        mark_checkout_started()
        db2 = session_factory()
        try:
            if "mysql" in str(engine.url.drivername or "").lower():
                ver_row = db2.execute(text("SELECT VERSION()")).fetchone()
                result["server_version"] = str(ver_row[0]) if ver_row else None
                status_row = db2.execute(text("SHOW STATUS LIKE 'Threads_connected'")).fetchone()
                if status_row:
                    result["threads_connected"] = status_row[1]
            elif "sqlite" in str(engine.url.drivername or "").lower():
                ver_row = db2.execute(text("SELECT sqlite_version()")).fetchone()
                result["server_version"] = f"sqlite {ver_row[0]}" if ver_row else "sqlite"
            else:
                result["server_version"] = str(engine.url.drivername)
        finally:
            try:
                db2.close()
            except Exception:
                pass
            try:
                session_factory.remove()
            except Exception:
                pass
    except Exception as exc:
        result["server_version_error"] = str(exc)[:200]

    # --- Diagnóstico heurístico (DB vazio → connect/pool_wait dominam) ---
    hints: list[str] = []
    ping = float(result.get("ping_pooled_ms") or 0)
    fresh = float(fresh_ms or 0)
    pw_p95 = (result.get("aggregates") or {}).get("pool_wait_p95_ms") or 0
    pw_max = (result.get("aggregates") or {}).get("pool_wait_max_ms") or 0

    if fresh >= 1000:
        hints.append(
            f"fresh_connect_ms={fresh:.0f} — latência de rede/TLS ao MySQL "
            "(host remoto ou DNS lento); cada conexão nova custa segundos."
        )
    elif fresh >= 200:
        hints.append(
            f"fresh_connect_ms={fresh:.0f} — conexão nova perceptível; "
            "verifique host remoto e pool_recycle/pre_ping."
        )

    if pw_p95 and float(pw_p95) >= 500:
        hints.append(
            f"pool_wait_p95_ms={pw_p95} — requests esperam conexão no pool "
            "(sessões presas durante I/O externo ou pool pequeno)."
        )
    elif pw_max and float(pw_max) >= 1000:
        hints.append(
            f"pool_wait_max_ms={pw_max} — pico de espera no checkout do pool."
        )

    if ping >= 5000 and fresh < 500:
        hints.append(
            "ping_pooled_ms alto mas fresh_connect_ms baixo — provável pool starvation "
            "ou lock wait, não latência de rede."
        )

    if ping < 100 and fresh < 100:
        hints.append(
            "ping e fresh_connect normais neste probe — se timeouts persistem, "
            "verifique endpoints que seguram sessão durante RCON/HTTP ou DDL no request."
        )

    result["diagnosis_hints"] = hints
    return result


def reset_stats_for_tests() -> None:
    """Limpa buffers — só testes."""
    global _query_count, _query_total_ms, _pool_wait_total_ms, _pool_wait_count
    global _connect_total_ms, _connect_count, _circuit_failures, _circuit_open_until
    global _txn_total_ms, _txn_count, _txn_long_count
    with _lock:
        _slow_queries.clear()
        _recent_errors.clear()
        _pool_wait_samples.clear()
        _connect_samples.clear()
        _txn_samples.clear()
        _fingerprint_ms.clear()
        _fingerprint_count.clear()
        _query_count = 0
        _query_total_ms = 0.0
        _pool_wait_total_ms = 0.0
        _pool_wait_count = 0
        _connect_total_ms = 0.0
        _connect_count = 0
        _txn_total_ms = 0.0
        _txn_count = 0
        _txn_long_count = 0
        _circuit_failures = 0
        _circuit_open_until = 0.0
        _attached_engines.clear()
