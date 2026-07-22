"""Cache curto in-memory com TTL (Fase 4).

Redis NÃO é dependência deste projeto — se no futuro existir cliente Redis
configurado, pode-se plugar um backend sem mudar as rotas. Por agora: dict
thread-safe + time.monotonic().

TTL recomendado: 5–15 s (default 10). NÃO usar para status de pagamento
tempo-real (PIX/MP poll).
"""
from __future__ import annotations

import os
import threading
import time
from typing import Any, Callable, TypeVar

T = TypeVar("T")

# Faixa do plano (Fase 4)
TTL_MIN_SEC = 5.0
TTL_MAX_SEC = 15.0
DEFAULT_TTL_SEC = float(os.environ.get("ARKSHOP_SHORT_CACHE_TTL_SEC", "10") or 10)


def clamp_ttl(seconds: float | None = None) -> float:
    """Garante TTL na faixa 5–15 s (ou 0 = desligado)."""
    if seconds is None:
        seconds = DEFAULT_TTL_SEC
    try:
        val = float(seconds)
    except (TypeError, ValueError):
        val = DEFAULT_TTL_SEC
    if val <= 0:
        return 0.0
    return max(TTL_MIN_SEC, min(TTL_MAX_SEC, val))


class TtlCache:
    """Cache simples key→value com expiração por entrada."""

    def __init__(self, name: str, *, default_ttl: float | None = None) -> None:
        self.name = name
        self.default_ttl = clamp_ttl(default_ttl)
        self._lock = threading.RLock()
        self._store: dict[str, tuple[float, Any]] = {}
        self.hits = 0
        self.misses = 0

    def get(self, key: str) -> Any | None:
        if self.default_ttl <= 0:
            return None
        now = time.monotonic()
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                self.misses += 1
                return None
            expires, value = entry
            if expires <= now:
                self._store.pop(key, None)
                self.misses += 1
                return None
            self.hits += 1
            return value

    def set(self, key: str, value: Any, *, ttl: float | None = None) -> None:
        ttl_sec = clamp_ttl(self.default_ttl if ttl is None else ttl)
        if ttl_sec <= 0:
            return
        with self._lock:
            self._store[key] = (time.monotonic() + ttl_sec, value)

    def get_or_set(
        self,
        key: str,
        factory: Callable[[], T],
        *,
        ttl: float | None = None,
    ) -> tuple[T, bool]:
        """Devolve (valor, hit). Só chama factory em miss."""
        cached = self.get(key)
        if cached is not None:
            return cached, True  # type: ignore[return-value]
        value = factory()
        self.set(key, value, ttl=ttl)
        return value, False

    def invalidate(self, key: str | None = None) -> None:
        with self._lock:
            if key is None:
                self._store.clear()
            else:
                self._store.pop(key, None)

    def stats(self) -> dict[str, Any]:
        with self._lock:
            return {
                "name": self.name,
                "entries": len(self._store),
                "hits": self.hits,
                "misses": self.misses,
                "default_ttl_sec": self.default_ttl,
            }


# Caches nomeados (namespaces) — um por domínio do plano Fase 4.
products = TtlCache("products", default_ttl=DEFAULT_TTL_SEC)
system_config = TtlCache("system_config", default_ttl=DEFAULT_TTL_SEC)
servers_status = TtlCache("servers_status", default_ttl=DEFAULT_TTL_SEC)
sync_recent = TtlCache("sync_recent", default_ttl=DEFAULT_TTL_SEC)


def invalidate_all_short_caches() -> None:
    products.invalidate()
    system_config.invalidate()
    servers_status.invalidate()
    sync_recent.invalidate()


def short_cache_stats() -> dict[str, Any]:
    return {
        "ttl_sec": clamp_ttl(),
        "caches": [
            products.stats(),
            system_config.stats(),
            servers_status.stats(),
            sync_recent.stats(),
        ],
    }
