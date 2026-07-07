"""Testes — Encomenda de Dino (MVP)."""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone

import pytest
from sqlalchemy import text

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("ARKSHOP_DATABASE_URL", "")
os.environ.setdefault("ARKSHOP_WEB_SECRET", "test-secret")

import app as _app_module
from app import _add_player_points_tx, _configure_database, _get_player_points, _subtract_player_points_tx
from custom_dino_service import ensure_custom_dino_schema
from dino_order_service import (
    ORDER_SOURCE,
    approve_order,
    calc_color_component,
    checkout,
    configure_dino_order,
    get_pricing_config,
    list_gallery_species,
    quote,
    reject_order,
)
from dino_order_showcase_service import configure_dino_order_showcase, create_showcase

USER = "76561198000000001"
ADMIN = "76561198000000003"


@pytest.fixture(autouse=True)
def fresh_db(tmp_path, monkeypatch):
    db_url = f"sqlite:///{tmp_path / 'dino_order_test.db'}"
    monkeypatch.setattr(_app_module, "_ACTIVE_DATABASE_URL", "")
    _configure_database(db_url)
    settings_file = tmp_path / "settings.json"
    settings_file.write_text(
        json.dumps({
            "dino_order_enabled": True,
            "custom_dino_enabled": True,
        }),
        encoding="utf-8",
    )
    monkeypatch.setattr(_app_module, "_STATE_FILE", settings_file)
    from custom_dino_service import configure_custom_dino

    configure_custom_dino(settings_fn=_app_module._load_settings)
    configure_dino_order(
        settings_fn=_app_module._load_settings,
        debit_fn=_subtract_player_points_tx,
        credit_fn=_add_player_points_tx,
        get_player_points_fn=_get_player_points,
    )
    configure_dino_order_showcase(
        showcases_file=tmp_path / "showcases.json",
        uploads_dir=tmp_path / "showcase_uploads",
    )
    yield
    _configure_database("")


def _seed_species(db, *, species_key, display_name, root_value=5000):
    from app import MarketSpecies, MarketSpeciesStatMultiplier

    ensure_custom_dino_schema(_app_module._ENGINE)
    species = MarketSpecies(
        species_key=species_key,
        catalog_item_id=f"{species_key}_femea",
        display_name=display_name,
        blueprint_path="/Game/PrimalEarth/Dinos/Rex/Rex_Character_BP.Rex_Character_BP",
        reference_level=1,
        root_value=root_value,
        tier="A",
        status="ACTIVE",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(species)
    db.flush()
    for sk, mult in (("health", 95), ("melee", 700)):
        db.add(
            MarketSpeciesStatMultiplier(
                species_id=species.id,
                stat_key=sk,
                multiplier=mult,
                enabled=True,
            )
        )
    db.commit()


def _seed_rex_showcase():
    create_showcase({
        "species_key": "rex",
        "color_name": "Padrão",
        "colors": [0, 0, 0, 0, 0, 0],
        "description": "Teste",
        "active": True,
    })


def _seed_rex(db):
    _seed_species(db, species_key="rex", display_name="Rex")
    _seed_rex_showcase()
    db.execute(
        text("INSERT INTO players (steam_id, points, kits) VALUES (:sid, :pts, '{}')"),
        {"sid": USER, "pts": 1_000_000},
    )
    db.commit()


def test_list_gallery_species_dedup_by_display_name():
    db = _app_module._SessionLocal()
    try:
        _seed_species(db, species_key="astrodelphis_1", display_name="Astrodelphis", root_value=4000)
        _seed_species(db, species_key="astrodelphis_200", display_name="Astrodelphis", root_value=6000)
        create_showcase({
            "species_key": "astrodelphis_1",
            "color_name": "Azul",
            "colors": [2, 2, 2, 0, 0, 0],
            "active": True,
        })
        gallery = list_gallery_species(db)
        astro = [s for s in gallery if str(s.get("display_name")).lower() == "astrodelphis"]
        assert len(astro) == 1
        assert astro[0]["species_key"] == "astrodelphis_1"
    finally:
        db.close()


def _base_spec(**overrides):
    spec = {
        "species_key": "rex",
        "level": 150,
        "gender": "female",
        "colors": [0, 0, 0, 0, 0, 0],
        "stat_points": {},
    }
    spec.update(overrides)
    return spec


def test_quote_rejects_species_without_showcase():
    db = _app_module._SessionLocal()
    try:
        _seed_species(db, species_key="rex", display_name="Rex")
        with pytest.raises(ValueError, match="species_not_in_gallery"):
            quote(_base_spec(), db=db)
    finally:
        db.close()


def test_quote_rex_default_price():
    db = _app_module._SessionLocal()
    try:
        _seed_rex(db)
        q = quote(_base_spec(), db=db)
        assert q["root_value"] == 5000
        assert q["stats_component"] == 5000
        assert q["color_component"] == 0
        assert q["base_surcharge"] == 1250
        assert q["service_premium"] == 1750
        assert q["total"] == 8000
        assert q["auto_approve"] is True
    finally:
        db.close()


def test_quote_color_uniform_vs_varied():
    cfg = get_pricing_config()
    assert calc_color_component(5000, [0, 0, 0, 0, 0, 0], cfg) == 0
    assert calc_color_component(5000, [14, 14, 14, 14, 14, 14], cfg) == 400
    varied = calc_color_component(5000, [14, 14, 14, 0, 0, 0], cfg)
    assert varied == round(5000 * 0.05) + 3 * round(5000 * 0.02)


def test_quote_moderate_stats():
    db = _app_module._SessionLocal()
    try:
        _seed_rex(db)
        q = quote(
            _base_spec(
                colors=[14, 14, 14, 14, 14, 14],
                stat_points={"health": 78, "melee": 105},
            ),
            db=db,
        )
        assert q["stats_component"] > 5000
        assert q["color_component"] == 400
        assert q["total"] > q["market_equivalent"]
    finally:
        db.close()


def test_checkout_debits_and_creates_order():
    db = _app_module._SessionLocal()
    try:
        _seed_rex(db)
        before = _get_player_points(USER)
        result = checkout(db, USER, _base_spec())
        db.commit()
        after = _get_player_points(USER)
        assert result["status"] == "PENDENTE"
        assert result["points_spent"] == 8000
        assert before - after == 8000
        row = db.execute(
            text("SELECT status, points_spent, payload_json FROM orders WHERE order_id = :oid"),
            {"oid": result["order_id"]},
        ).fetchone()
        assert row[0] == "PENDENTE"
        assert int(row[1]) == 8000
        payload = json.loads(row[2])
        assert payload["order_source"] == ORDER_SOURCE
    finally:
        db.close()


def test_checkout_auto_approve_high_value():
    db = _app_module._SessionLocal()
    try:
        _seed_rex(db)
        result = checkout(
            db,
            USER,
            _base_spec(
                colors=[1, 2, 3, 4, 5, 6],
                stat_points={"health": 254, "melee": 254},
            ),
        )
        db.commit()
        assert result["status"] == "AGUARDANDO_APROVACAO"
        assert result["points_spent"] > 200_000
    finally:
        db.close()


def test_approve_moves_to_pendente():
    db = _app_module._SessionLocal()
    try:
        _seed_rex(db)
        result = checkout(
            db,
            USER,
            _base_spec(stat_points={"health": 254, "melee": 254}),
        )
        db.commit()
        assert result["status"] == "AGUARDANDO_APROVACAO"
        approved = approve_order(db, result["order_id"], admin_steam_id=ADMIN)
        db.commit()
        assert approved["status"] == "PENDENTE"
    finally:
        db.close()


def test_reject_refunds_points():
    db = _app_module._SessionLocal()
    try:
        _seed_rex(db)
        before = _get_player_points(USER)
        result = checkout(
            db,
            USER,
            _base_spec(stat_points={"health": 254, "melee": 254}),
        )
        db.commit()
        mid = _get_player_points(USER)
        assert mid < before
        rejected = reject_order(db, result["order_id"], admin_steam_id=ADMIN, reason="Teste")
        db.commit()
        after = _get_player_points(USER)
        assert rejected["status"] == "REJEITADO"
        assert rejected["refunded"] == result["points_spent"]
        assert after == before
    finally:
        db.close()


def test_rate_limit_blocks_fourth_order():
    db = _app_module._SessionLocal()
    try:
        _seed_rex(db)
        for _ in range(3):
            checkout(db, USER, _base_spec())
            db.commit()
        with pytest.raises(ValueError, match="rate_limit"):
            checkout(db, USER, _base_spec())
    finally:
        db.close()
