"""Testes Waitress alinhado ao pool (Fase 5)."""
from __future__ import annotations

import waitress_config as wc


def test_workers_formula():
    assert wc.workers_formula(1) == 3
    assert wc.workers_formula(2) == 5
    assert wc.workers_formula(4) == 9
    assert wc.workers_formula(8) == 17


def test_default_threads_clamped_4_to_8():
    assert wc.default_http_threads(1) == 4  # formula 3 → floor 4
    assert wc.default_http_threads(2) == 5
    assert wc.default_http_threads(4) == 8  # formula 9 → cap 8
    assert wc.default_http_threads(16) == 8


def test_resolve_caps_to_pool(monkeypatch):
    monkeypatch.delenv("ARKSHOP_HTTP_THREADS", raising=False)
    monkeypatch.delenv("ARKSHOP_HTTP_THREADS_FORCE", raising=False)
    monkeypatch.delenv("ARKSHOP_HTTP_THREADS_CAP_TO_POOL", raising=False)
    cfg = wc.resolve_http_threads(pool_size=20, cpus=4)
    assert 4 <= cfg["threads"] <= 8
    assert cfg["threads"] <= 20
    assert cfg["source"] == "cpu_formula"
    assert cfg["workers_formula"] == 9


def test_resolve_env_override_capped(monkeypatch):
    monkeypatch.setenv("ARKSHOP_HTTP_THREADS", "32")
    monkeypatch.delenv("ARKSHOP_HTTP_THREADS_FORCE", raising=False)
    monkeypatch.delenv("ARKSHOP_HTTP_THREADS_CAP_TO_POOL", raising=False)
    monkeypatch.delenv("ARKSHOP_HTTP_POOL_HEADROOM", raising=False)
    cfg = wc.resolve_http_threads(pool_size=20, cpus=8)
    # Cap = pool − headroom(6) → 14 (não esgota pool com bg workers)
    assert cfg["threads"] == 14
    assert cfg["threads"] <= 20
    assert cfg["capped_to_pool"] is True
    assert cfg["source"] == "env"
    assert cfg["pool_headroom"] == 6


def test_resolve_force_no_cap(monkeypatch):
    monkeypatch.setenv("ARKSHOP_HTTP_THREADS", "32")
    monkeypatch.setenv("ARKSHOP_HTTP_THREADS_FORCE", "1")
    cfg = wc.resolve_http_threads(pool_size=20, cpus=8)
    assert cfg["threads"] == 32
    assert cfg["capped_to_pool"] is False


def test_threads_do_not_crush_phase1_pool():
    """threads ≤ pool−headroom e ≪ pool+overflow (30); pool_timeout=5."""
    cfg = wc.resolve_http_threads(pool_size=20, cpus=8)
    assert cfg["threads"] <= 20
    assert cfg["threads"] <= 8  # default auto nunca > 8
    assert cfg["threads"] + cfg["pool_headroom"] <= 20


def test_pool_floor_does_not_exceed_cap(monkeypatch):
    """THREADS_MIN não pode desfazer o cap quando pool é pequeno."""
    monkeypatch.setenv("ARKSHOP_HTTP_THREADS", "32")
    monkeypatch.delenv("ARKSHOP_HTTP_THREADS_FORCE", raising=False)
    monkeypatch.setenv("ARKSHOP_HTTP_POOL_HEADROOM", "0")
    cfg = wc.resolve_http_threads(pool_size=3, cpus=8)
    assert cfg["threads"] <= 3
    assert cfg["threads"] >= 1