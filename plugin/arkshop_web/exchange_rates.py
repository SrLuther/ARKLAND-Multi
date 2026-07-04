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
_cache_lock = threading.Lock()
_cache: dict[str, Any] = {
    "rates": dict(FALLBACK_RATES),
    "source": "fallback",
    "fetched_at": None,
    "expires_at": 0.0,
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


def get_exchange_rates(*, force_refresh: bool = False) -> dict[str, Any]:
    """Retorna cotações com cache em memória (1h)."""
    now = time.time()
    with _cache_lock:
        if not force_refresh and _cache["expires_at"] > now:
            return _public_payload_from_cache()

    rates = dict(FALLBACK_RATES)
    source = "fallback"
    try:
        rates = _fetch_frankfurter()
        source = "frankfurter"
    except (urllib.error.URLError, urllib.error.HTTPError, ValueError, json.JSONDecodeError, OSError):
        rates = dict(FALLBACK_RATES)
        source = "fallback"

    fetched_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    with _cache_lock:
        _cache["rates"] = dict(rates)
        _cache["source"] = source
        _cache["fetched_at"] = fetched_at
        _cache["expires_at"] = now + _CACHE_TTL_SEC
        return _public_payload_from_cache()


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
