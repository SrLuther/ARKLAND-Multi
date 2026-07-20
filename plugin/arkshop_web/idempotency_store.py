"""Chaves de idempotência persistentes (SQLite local) — sobrevive restart do processo."""
from __future__ import annotations

import logging
import sqlite3
import threading
import time
from pathlib import Path

log = logging.getLogger("arkshop_web.idempotency")

_DEFAULT_TTL_SEC = 3600
_lock = threading.Lock()
_db_path: Path | None = None


def configure(db_path: Path, *, ttl_sec: int = _DEFAULT_TTL_SEC) -> None:
    global _db_path
    _db_path = db_path
    _DEFAULT_TTL_SEC  # noqa: referenced for callers via get_ttl


def _conn() -> sqlite3.Connection:
    if _db_path is None:
        raise RuntimeError("idempotency_store not configured")
    _db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(_db_path), timeout=5.0, check_same_thread=False)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS idempotency_keys "
        "(key TEXT PRIMARY KEY, created_at REAL NOT NULL)"
    )
    return conn


def claim(key: str, *, ttl_sec: int = _DEFAULT_TTL_SEC) -> bool:
    """True na primeira vez que a chave é vista; False se duplicata dentro do TTL."""
    if not key:
        return True
    now = time.time()
    cutoff = now - ttl_sec
    with _lock:
        try:
            conn = _conn()
            try:
                conn.execute("DELETE FROM idempotency_keys WHERE created_at < ?", (cutoff,))
                cur = conn.execute(
                    "INSERT OR IGNORE INTO idempotency_keys (key, created_at) VALUES (?, ?)",
                    (key, now),
                )
                conn.commit()
                return int(cur.rowcount or 0) > 0
            finally:
                conn.close()
        except Exception as exc:
            log.warning("idempotency_store claim failed: %s", exc)
            raise


def release(key: str) -> None:
    if not key:
        return
    with _lock:
        try:
            conn = _conn()
            try:
                conn.execute("DELETE FROM idempotency_keys WHERE key = ?", (key,))
                conn.commit()
            finally:
                conn.close()
        except Exception as exc:
            log.warning("idempotency_store release failed: %s", exc)
