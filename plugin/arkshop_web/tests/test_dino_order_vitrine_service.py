"""Testes — vitrine rotativa de encomenda."""
from __future__ import annotations

import json
import os
import random
import sys
from datetime import datetime, timedelta, timezone

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dino_order_vitrine_service import (
    MAX_PERMANENT,
    ROTATING_SLOTS,
    configure_dino_order_vitrine,
    draw_rotating_species,
    ensure_vitrine,
    force_rotate,
    is_species_on_vitrine,
    load_store,
    normalize_size_class,
    page_candidates,
    save_store,
    set_permanent_species,
    set_rotation_days,
)


@pytest.fixture(autouse=True)
def vitrine_store(tmp_path):
    configure_dino_order_vitrine(vitrine_file=tmp_path / "vitrine.json")
    yield


def _cand(key: str, size: str) -> dict:
    return {
        "species_key": key,
        "display_name": key.title(),
        "size_class": size,
        "tier": "A",
        "root_value": 1000,
        "image_url": "",
    }


def _pool_full() -> list[dict]:
    out = []
    for i in range(10):
        out.append(_cand(f"large_{i}", "large"))
    for i in range(8):
        out.append(_cand(f"medium_{i}", "medium"))
    for i in range(6):
        out.append(_cand(f"small_{i}", "small"))
    return out


def test_normalize_size_class_aliases():
    assert normalize_size_class("grande") == "large"
    assert normalize_size_class("médio") == "medium"
    assert normalize_size_class("medio") == "medium"
    assert normalize_size_class("pequeno") == "small"
    assert normalize_size_class("LARGE") == "large"
    assert normalize_size_class(None) == "medium"


def test_draw_mix_6_2_2():
    keys, meta = draw_rotating_species(_pool_full(), rng=random.Random(42))
    assert len(keys) == ROTATING_SLOTS
    assert len(set(keys)) == ROTATING_SLOTS
    assert meta["actual_mix"]["large"] == 6
    assert meta["actual_mix"]["medium"] == 2
    assert meta["actual_mix"]["small"] == 2
    assert meta["fallback_used"] is False


def test_draw_excludes_permanents():
    permanents = {"large_0", "medium_0", "small_0"}
    keys, _meta = draw_rotating_species(
        _pool_full(), exclude=permanents, rng=random.Random(7)
    )
    assert len(keys) == ROTATING_SLOTS
    assert not set(keys) & permanents


def test_draw_fallback_when_size_pool_short():
    pool = [_cand(f"medium_{i}", "medium") for i in range(12)]
    keys, meta = draw_rotating_species(pool, rng=random.Random(1))
    assert len(keys) == ROTATING_SLOTS
    assert meta["fallback_used"] is True
    assert meta["actual_mix"]["medium"] == ROTATING_SLOTS
    assert meta["filled_by_target"]["large"] == 0
    assert meta["filled_by_target"]["small"] == 0


def test_no_duplicates_across_sizes():
    pool = _pool_full()
    keys, _ = draw_rotating_species(pool, rng=random.Random(99))
    assert len(keys) == len(set(keys))


def test_permanent_cap_5():
    with pytest.raises(ValueError, match="permanent_limit_exceeded"):
        set_permanent_species([f"p{i}" for i in range(MAX_PERMANENT + 1)])
    result = set_permanent_species([f"p{i}" for i in range(MAX_PERMANENT)])
    assert len(result["permanent_species_keys"]) == MAX_PERMANENT


def test_permanents_removed_from_rotating():
    store = load_store()
    store["rotating_species_keys"] = [f"r{i}" for i in range(10)]
    store["permanent_species_keys"] = []
    save_store(store)
    result = set_permanent_species(["r0", "r1"])
    assert result["permanent_species_keys"] == ["r0", "r1"]
    assert "r0" not in result["rotating_species_keys"]
    assert "r1" not in result["rotating_species_keys"]
    assert result["removed_from_rotating"] == 2


def test_force_rotate_resets_timer(monkeypatch):
    class _FakeDb:
        pass

    now = datetime(2026, 7, 12, 12, 0, tzinfo=timezone.utc)
    candidates = _pool_full()

    monkeypatch.setattr(
        "dino_order_vitrine_service.list_candidate_species",
        lambda db, force_refresh=False: candidates,
    )

    set_rotation_days(15)
    snap1 = force_rotate(_FakeDb(), rng=random.Random(1), now=now)
    ends1 = snap1["rotation_ends_at"]
    assert ends1.startswith("2026-07-27")

    later = now + timedelta(days=2)
    snap2 = force_rotate(_FakeDb(), rng=random.Random(2), now=later)
    assert snap2["rotation_ends_at"].startswith("2026-07-29")
    assert snap2["rotation"]["reason"] == "force"
    assert len(snap2["rotating_species_keys"]) == ROTATING_SLOTS


def test_auto_rotate_when_expired(monkeypatch):
    class _FakeDb:
        pass

    candidates = _pool_full()
    monkeypatch.setattr(
        "dino_order_vitrine_service.list_candidate_species",
        lambda db, force_refresh=False: candidates,
    )

    now = datetime(2026, 7, 1, 0, 0, tzinfo=timezone.utc)
    force_rotate(_FakeDb(), rng=random.Random(3), now=now)
    store = load_store()
    store["rotation_ends_at"] = (now + timedelta(days=7)).isoformat()
    store["rotating_species_keys"] = [f"old_{i}" for i in range(10)]
    save_store(store)

    after = now + timedelta(days=8)
    snap = ensure_vitrine(_FakeDb(), rng=random.Random(4), now=after)
    assert snap["rotation"]["rotated"] is True
    assert all(not k.startswith("old_") for k in snap["rotating_species_keys"])
    assert len(snap["rotating_species_keys"]) == ROTATING_SLOTS


def test_is_species_on_vitrine_union(monkeypatch):
    class _FakeDb:
        pass

    candidates = _pool_full()
    monkeypatch.setattr(
        "dino_order_vitrine_service.list_candidate_species",
        lambda db, force_refresh=False: candidates,
    )
    set_permanent_species(["large_9"])
    snap = force_rotate(_FakeDb(), rng=random.Random(5), now=datetime.now(timezone.utc))
    rotating = snap["rotating_species_keys"]
    assert is_species_on_vitrine(rotating[0], _FakeDb()) is True
    assert is_species_on_vitrine("large_9", _FakeDb()) is True
    assert is_species_on_vitrine("missing_species", _FakeDb()) is False
    assert "large_9" not in rotating


def test_orderable_keys_hot_path_skips_full_catalog(monkeypatch):
    """Cotação não pode re-listar todo o catálogo a cada slider."""
    from dino_order_vitrine_service import orderable_species_keys

    class _FakeDb:
        pass

    calls = {"n": 0}

    def _boom(db, force_refresh=False):
        calls["n"] += 1
        raise AssertionError("list_candidate_species não deve ser chamado no hot path")

    monkeypatch.setattr("dino_order_vitrine_service.list_candidate_species", _boom)

    now = datetime(2026, 7, 1, 12, 0, tzinfo=timezone.utc)
    store = load_store()
    store["rotating_species_keys"] = [f"r{i}" for i in range(10)]
    store["permanent_species_keys"] = ["p0"]
    # Longe no futuro em relação a _utcnow() — evita auto-rotação no hot path
    store["rotation_ends_at"] = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
    save_store(store)

    keys = orderable_species_keys(_FakeDb())
    assert calls["n"] == 0
    assert "r0" in keys and "p0" in keys
    assert is_species_on_vitrine("r0", _FakeDb()) is True
    assert calls["n"] == 0


def test_page_candidates_filter_and_limit():
    pool = [_cand(f"large_{i}", "large") for i in range(30)]
    page, total, more = page_candidates(pool, q="large_1", limit=5, offset=0)
    assert total == 11  # large_1, large_10..large_19
    assert len(page) == 5
    assert more is True
    page2, total2, more2 = page_candidates(pool, q="large_1", limit=5, offset=5)
    assert total2 == 11
    assert len(page2) == 5
    assert more2 is True
    page3, _, more3 = page_candidates(pool, q="large_1", limit=5, offset=10)
    assert len(page3) == 1
    assert more3 is False


def test_snapshot_paginates_candidates(monkeypatch):
    class _FakeDb:
        pass

    pool = _pool_full()
    monkeypatch.setattr(
        "dino_order_vitrine_service.list_candidate_species",
        lambda db, force_refresh=False: list(pool),
    )
    now = datetime(2026, 7, 1, 12, 0, tzinfo=timezone.utc)
    store = load_store()
    store["rotating_species_keys"] = [c["species_key"] for c in pool[:10]]
    store["permanent_species_keys"] = []
    store["rotation_ends_at"] = (now + timedelta(days=7)).isoformat()
    save_store(store)

    from dino_order_vitrine_service import get_vitrine_snapshot

    snap = get_vitrine_snapshot(
        _FakeDb(),
        store=store,
        now=now,
        candidates_limit=5,
        candidates_offset=0,
        use_cache=False,
    )
    assert snap["candidates_total"] == len(pool)
    assert len(snap["candidates"]) == 5
    assert snap["candidates_has_more"] is True
    assert len(snap["rotating"]) == 10
    # Imagens só nos slots, não no pool paginado
    assert all("image_url" in c for c in snap["rotating"])


def test_list_candidate_uses_lightweight_loader(monkeypatch):
    """Pool de candidatos vem do loader leve — não de list_species_public."""
    from dino_order_vitrine_service import invalidate_vitrine_caches, list_candidate_species

    calls = {"n": 0}

    def _fake_light(db):
        calls["n"] += 1
        return [_cand("rex", "large")]

    def _boom(*a, **k):
        raise AssertionError("list_species_public não deve ser usado na vitrine")

    monkeypatch.setattr(
        "dino_order_vitrine_service._load_candidates_lightweight",
        _fake_light,
    )
    monkeypatch.setattr("market_service.list_species_public", _boom, raising=False)
    invalidate_vitrine_caches()
    out = list_candidate_species(object(), force_refresh=True)
    assert calls["n"] == 1
    assert out[0]["species_key"] == "rex"
    # 2º call no TTL usa cache
    out2 = list_candidate_species(object(), force_refresh=False)
    assert calls["n"] == 1
    assert out2[0]["species_key"] == "rex"