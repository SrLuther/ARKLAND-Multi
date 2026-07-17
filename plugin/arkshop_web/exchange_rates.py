"""Cotações BRL → USD/EUR para estimativas na loja (cache 1h, fallback estático)."""
from __future__ import annotations

import json
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Any

# Aproximação quando a API pública falha (1 BRL → moeda estrangeira).
FALLBACK_RATES: dict[str, float] = {
    "USD": 0.18,
    "EUR": 0.17,
}

_CACHE_TTL_SEC = 3600
# Após falha, não re-tenta a cada request — segura fallback por este intervalo.
_FAILURE_RETRY_SEC = 300
_cache_lock = threading.Lock()
_cache: dict[str, Any] = {
    "rates": dict(FALLBACK_RATES),
    "source": "fallback",
    "fetched_at": None,
    "expires_at": 0.0,
    "refresh_inflight": False,
}


def _fetch_frankfurter() -> dict[str, float]:
    url = "https://api.frankfurter.app/latest?from=BRL&to=USD,EUR"
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        body = resp.read().decode("utf-8", errors="replace")
    data = json.loads(body)
    rates = data.get("rates") or {}
    out: dict[str, float] = {}
    for code in ("USD", "EUR"):
        val = rates.get(code)
        if val is not None:
            out[code] = float(val)
    if len(out) != 2:
        raise ValueError("Resposta incompleta da API de câmbio")
    return out


def _refresh_cache_blocking() -> None:
    """Consulta a API e atualiza o cache (fallback + retry curto em falha)."""
    now = time.time()
    rates = dict(FALLBACK_RATES)
    source = "fallback"
    ttl = float(_FAILURE_RETRY_SEC)
    try:
        rates = _fetch_frankfurter()
        source = "frankfurter"
        ttl = float(_CACHE_TTL_SEC)
    except (urllib.error.URLError, urllib.error.HTTPError, ValueError, json.JSONDecodeError, OSError):
        pass

    fetched_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    with _cache_lock:
        _cache["rates"] = dict(rates)
        _cache["source"] = source
        _cache["fetched_at"] = fetched_at
        _cache["expires_at"] = now + ttl


def get_exchange_rates(*, force_refresh: bool = False) -> dict[str, Any]:
    """Cotações com cache em memória (1h) — stale-while-revalidate.

    Cache expirado NÃO bloqueia o request (frankfurter tem timeout de 10s e é
    chamado no hot path /api/catalog): devolve o valor atual e dispara refresh
    em background com single-flight. force_refresh mantém o fetch síncrono.
    """
    if force_refresh:
        _refresh_cache_blocking()
        with _cache_lock:
            return _public_payload_from_cache()

    now = time.time()
    with _cache_lock:
        if _cache["expires_at"] > now:
            return _public_payload_from_cache()
        if _cache.get("refresh_inflight"):
            return _public_payload_from_cache()
        _cache["refresh_inflight"] = True
        stale_payload = _public_payload_from_cache()

    def _worker() -> None:
        try:
            _refresh_cache_blocking()
        finally:
            with _cache_lock:
                _cache["refresh_inflight"] = False

    threading.Thread(target=_worker, daemon=True, name="exchange-rates-refresh").start()
    return stale_payload


def _public_payload_from_cache() -> dict[str, Any]:
    return {
        "base": "BRL",
        "rates": dict(_cache["rates"]),
        "source": _cache["source"],
        "fetched_at": _cache["fetched_at"],
    }


def estimate_foreign(amount_brl: float, rates: dict[str, float] | None = None) -> dict[str, float]:
    """Converte valor BRL para estimativas USD/EUR."""
    r = rates if rates is not None else dict(_cache.get("rates") or FALLBACK_RATES)
    amount = max(0.0, float(amount_brl or 0))
    return {
        "USD": round(amount * float(r.get("USD", FALLBACK_RATES["USD"])), 2),
        "EUR": round(amount * float(r.get("EUR", FALLBACK_RATES["EUR"])), 2),
    }
