"""Testes do cache TTL curto (Fase 4)."""
from __future__ import annotations

import time

import ttl_cache as tc


def test_clamp_ttl_range():
    assert tc.clamp_ttl(3) == 5.0
    assert tc.clamp_ttl(10) == 10.0
    assert tc.clamp_ttl(20) == 15.0
    assert tc.clamp_ttl(0) == 0.0
    assert tc.clamp_ttl(-1) == 0.0


def test_get_or_set_hit_and_miss():
    cache = tc.TtlCache("t", default_ttl=10)
    calls = {"n": 0}

    def factory():
        calls["n"] += 1
        return {"v": calls["n"]}

    v1, hit1 = cache.get_or_set("k", factory)
    v2, hit2 = cache.get_or_set("k", factory)
    assert hit1 is False
    assert hit2 is True
    assert v1 == v2 == {"v": 1}
    assert calls["n"] == 1
    assert cache.hits >= 1
    assert cache.misses >= 1


def test_expire_and_invalidate():
    cache = tc.TtlCache("t2", default_ttl=5)
    # TTL mínimo é 5 — usa set com ttl interno via monkeypatch do store
    cache.set("a", 1, ttl=5)
    assert cache.get("a") == 1
    # Força expiração
    with cache._lock:
        key = "a"
        _exp, val = cache._store[key]
        cache._store[key] = (time.monotonic() - 1, val)
    assert cache.get("a") is None
    cache.set("b", 2)
    cache.invalidate("b")
    assert cache.get("b") is None
    cache.set("c", 3)
    cache.invalidate()
    assert cache.get("c") is None


def test_named_caches_exist():
    assert tc.products.name == "products"
    assert tc.system_config.name == "system_config"
    assert tc.servers_status.name == "servers_status"
    assert tc.sync_recent.name == "sync_recent"
    stats = tc.short_cache_stats()
    assert "caches" in stats
    assert 5 <= stats["ttl_sec"] <= 15
