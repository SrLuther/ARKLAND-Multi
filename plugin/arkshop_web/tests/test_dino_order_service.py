"""Testes — Encomenda de Dino (MVP)."""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timedelta, timezone

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
    list_admin_history,
    list_admin_queue,
    list_gallery_species,
    list_player_orders,
    quote,
    reject_order,
    requeue_failed_order,
    _level_from_stat_points,
    _normalize_player_spec,
)
from dino_order_showcase_service import configure_dino_order_showcase
from dino_order_vitrine_service import configure_dino_order_vitrine, set_permanent_species

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
    configure_dino_order_vitrine(vitrine_file=tmp_path / "vitrine.json")
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


def _seed_rex_on_vitrine():
    """Coloca rex nos permanentes da vitrine (catálogo encomendável)."""
    set_permanent_species(["rex"])


def _seed_rex(db):
    _seed_species(db, species_key="rex", display_name="Rex")
    _seed_rex_on_vitrine()
    db.execute(
        text("INSERT INTO players (steam_id, points, kits) VALUES (:sid, :pts, '{}')"),
        {"sid": USER, "pts": 1_000_000},
    )
    db.commit()


def _set_dino_order_settings(tmp_path, **extra):
    """Atualiza settings.json do fixture (auto_approve_max etc.)."""
    path = tmp_path / "settings.json"
    data = {"dino_order_enabled": True, "custom_dino_enabled": True}
    data.update(extra)
    path.write_text(json.dumps(data), encoding="utf-8")


def test_level_from_stat_points_auto():
    assert _level_from_stat_points({}) == 1
    assert _level_from_stat_points({"health": 10, "melee": 5}) == 16
    assert _level_from_stat_points({"health": 254, "melee": 254}) == 509
    spec = _normalize_player_spec({
        "species_key": "rex",
        "level": 999,
        "stat_points": {"health": 20, "stamina": 10, "melee": 5},
    })
    assert spec["level"] == 36
    assert spec["stat_points"]["health"] == 20


def test_list_gallery_species_dedup_by_display_name():
    db = _app_module._SessionLocal()
    try:
        _seed_species(db, species_key="astrodelphis_1", display_name="Astrodelphis", root_value=4000)
        _seed_species(db, species_key="astrodelphis_200", display_name="Astrodelphis", root_value=6000)
        set_permanent_species(["astrodelphis_1"])
        gallery = list_gallery_species(db)
        astro = [s for s in gallery if str(s.get("display_name")).lower() == "astrodelphis"]
        assert len(astro) == 1
        assert astro[0]["species_key"] == "astrodelphis_1"
    finally:
        db.close()


def test_list_gallery_species_uses_friendly_catalog_names():
    """Legacy keys / English class names → nome do catálogo (Shadowmane, Small Manticore)."""
    db = _app_module._SessionLocal()
    try:
        _seed_species(
            db,
            species_key="lionfishlion",
            display_name="Lionfish Lion",
            root_value=16000,
        )
        _seed_species(
            db,
            species_key="sb_manticore_200",
            display_name="sb_manticore_200",
            root_value=22400,
        )
        set_permanent_species(["lionfishlion", "sb_manticore_200"])
        gallery = list_gallery_species(db)
        by_key = {s["species_key"]: s for s in gallery}
        assert by_key["lionfishlion"]["display_name"] == "Shadowmane"
        assert by_key["sb_manticore_200"]["display_name"] == "Small Manticore"
        assert "Nível 200" not in by_key["sb_manticore_200"]["display_name"]
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


def test_quote_rejects_species_without_vitrine():
    db = _app_module._SessionLocal()
    try:
        _seed_species(db, species_key="rex", display_name="Rex")
        _seed_species(db, species_key="dodo", display_name="Dodo")
        # Vitrine válida sem rex (não auto-roda enquanto o prazo for futuro)
        from dino_order_vitrine_service import load_store, save_store

        store = load_store()
        store["rotating_species_keys"] = ["dodo"]
        store["permanent_species_keys"] = []
        store["rotation_days"] = 7
        store["rotation_ends_at"] = (
            datetime.now(timezone.utc).replace(microsecond=0) + timedelta(days=7)
        ).isoformat()
        save_store(store)
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
        assert q["premium_budget"] > 0
        assert (q.get("q_index") or 0) > 0
        assert q["color_component"] == 400
        assert q["total"] > q["market_equivalent"]
    finally:
        db.close()


def test_quote_full_254_raises_above_floor():
    """Full 254 deve subir V acima do root — não pode colar no «a partir de»."""
    db = _app_module._SessionLocal()
    try:
        _seed_species(
            db,
            species_key="sb_drake_fire",
            display_name="Small Drake Fogo",
            root_value=5500,
        )
        set_permanent_species(["sb_drake_fire"])
        q0 = quote(
            {
                "species_key": "sb_drake_fire",
                "colors": [0, 0, 0, 0, 0, 0],
                "stat_points": {},
            },
            db=db,
            skip_vanilla_check=True,
        )
        q254 = quote(
            {
                "species_key": "sb_drake_fire",
                "colors": [0, 0, 0, 0, 0, 0],
                "stat_points": {
                    "health": 254,
                    "stamina": 254,
                    "oxygen": 254,
                    "food": 254,
                    "weight": 254,
                    "melee": 254,
                    "speed": 254,
                },
            },
            db=db,
            skip_vanilla_check=True,
        )
        assert q0["stats_component"] == 5500
        assert q0["total"] == 8800
        assert q254["premium_budget"] > 0
        assert q254["q_index"] == 1.0
        assert q254["stats_component"] > q0["stats_component"]
        assert q254["total"] > q0["total"]
    finally:
        db.close()


def test_quote_mismatched_key_recovers_budget_via_blueprint():
    """species_key fora do JSON mas blueprint certo → ainda aplica B."""
    from market_economy import SpeciesEconomy, apply_economy_meta, calculate_suggested_value

    eco = SpeciesEconomy(
        species_key="legacy_small_drake_fire_typo",
        display_name="Small Drake Fogo",
        root_value=5500,
        blueprint_path=(
            "/Game/Mods/SmallBosses/SmallDrake/"
            "SmallDrake_Character_BP_Fire.SmallDrake_Character_BP_Fire"
        ),
        pricing_mode="floor_quality",
    )
    apply_economy_meta(eco)
    assert eco.premium_budget > 0
    v0, _ = calculate_suggested_value(eco, {})
    v254, _ = calculate_suggested_value(
        eco,
        {
            "health": 254,
            "melee": 254,
            "weight": 254,
            "stamina": 254,
            "speed": 254,
        },
    )
    assert v0 == 5500
    assert v254 > v0


def test_quote_indominus_full_254_with_colors(monkeypatch):
    """Indominus 254 pts + cores: Lab > mercado V; breakdown stats/serviço/cores."""
    from market_economy import SpeciesEconomy, calculate_encomenda_value

    db = _app_module._SessionLocal()
    try:
        _seed_species(
            db,
            species_key="indominus",
            display_name="Indominus Rex",
            root_value=28_000,
        )
        set_permanent_species(["indominus"])

        # Garante meta floor_quality mesmo sem defaults JSON da espécie
        orig_resolve = __import__(
            "dino_order_service", fromlist=["_resolve_species_economy"]
        )._resolve_species_economy

        def _fake_resolve(db_sess, species_key):
            eco = orig_resolve(db_sess, species_key)
            if eco is None:
                return None
            eco.premium_budget = 122_000
            eco.dino_role = "boss"
            eco.pricing_mode = "floor_quality"
            return eco

        monkeypatch.setattr("dino_order_service._resolve_species_economy", _fake_resolve)

        colors = [14, 22, 33, 44, 55, 66]
        q = quote(
            {
                "species_key": "indominus",
                "level": 150,
                "gender": "female",
                "colors": colors,
                "stat_points": {
                    "health": 254,
                    "melee": 254,
                    "weight": 254,
                    "stamina": 254,
                    "speed": 254,
                },
            },
            db=db,
            skip_vanilla_check=True,
        )
        assert q["stats_component"] >= 28_000
        assert q["color_component"] > 0
        assert q["service_premium"] > 0
        assert q["base_surcharge"] == round(28_000 * 0.25)
        assert q["service_component"] == q["base_surcharge"] + q["service_premium"]
        assert q["total"] > q["market_equivalent"]
        expected = calculate_encomenda_value(
            SpeciesEconomy(
                species_key="indominus",
                display_name="Indominus Rex",
                root_value=28_000,
                tier="S+",
                dino_role="boss",
                premium_budget=122_000,
            ),
            q["stats_component"],
            color_component=q["color_component"],
        )
        assert q["total"] == expected
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
        # Sem pontos de stats → SpawnExact off (nível simples)
        assert payload.get("spawn_exact", {}).get("enabled") is False
    finally:
        db.close()


def test_checkout_with_stat_points_enables_spawn_exact(tmp_path, monkeypatch):
    """Problema A: HP/melee da encomenda devem ir para wild_stats (SpawnExact)."""
    settings_file = tmp_path / "settings_spawn_exact.json"
    settings_file.write_text(
        json.dumps({
            "dino_order_enabled": True,
            "custom_dino_enabled": True,
            "custom_dino_spawn_exact": True,
        }),
        encoding="utf-8",
    )
    monkeypatch.setattr(_app_module, "_STATE_FILE", settings_file)
    from custom_dino_service import configure_custom_dino

    configure_custom_dino(settings_fn=_app_module._load_settings)

    db = _app_module._SessionLocal()
    try:
        _seed_rex(db)
        result = checkout(
            db,
            USER,
            _base_spec(stat_points={"health": 78, "melee": 105}),
        )
        db.commit()
        payload = result["payload"]
        se = payload["spawn_exact"]
        assert se["enabled"] is True
        assert se["wild_stats"][0] == 78  # Health
        assert se["wild_stats"][5] == 105  # Melee
        assert payload["level"] == 1 + 78 + 105
        assert payload["stat_points_requested"] == {"health": 78, "melee": 105}
    finally:
        db.close()


def test_list_player_orders_includes_species_image_url():
    db = _app_module._SessionLocal()
    try:
        _seed_rex(db)
        result = checkout(db, USER, _base_spec())
        db.commit()
        data = list_player_orders(db, USER)
        assert data["total"] == 1
        assert data["orders"][0]["order_id"] == result["order_id"]
        assert data["orders"][0]["species_image_url"].endswith("/generated/rex.webp")
    finally:
        db.close()


def test_admin_queue_includes_auto_approved_pendente():
    """Bug: checkout auto-approve → PENDENTE sumia da fila admin (só AGUARDANDO/FALHA)."""
    db = _app_module._SessionLocal()
    try:
        _seed_rex(db)
        result = checkout(db, USER, _base_spec())
        db.commit()
        assert result["status"] == "PENDENTE"
        queue = list_admin_queue(db)
        ids = [o["order_id"] for o in queue["orders"]]
        assert result["order_id"] in ids
        row = next(o for o in queue["orders"] if o["order_id"] == result["order_id"])
        assert row["status"] == "PENDENTE"
        assert row["status_label"] == "Paga — na fila de entrega"
        assert row["steam_id"] == USER
    finally:
        db.close()


def test_admin_queue_includes_aguardando_and_falha(tmp_path):
    db = _app_module._SessionLocal()
    try:
        _seed_rex(db)
        _set_dino_order_settings(tmp_path, dino_order_auto_approve_max=1)
        high = checkout(db, USER, _base_spec())
        db.commit()
        assert high["status"] == "AGUARDANDO_APROVACAO"

        fail_id = "de_failtest01"
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        payload = {
            "order_source": ORDER_SOURCE,
            "species_key": "rex",
            "species_display_name": "Rex",
        }
        db.execute(
            text(
                "INSERT INTO orders "
                "(order_id, steam_id, server_id, item_type, item_id, amount, points_spent, status, "
                "retry_count, contested, payload_json, last_error, created_at, updated_at) "
                "VALUES (:oid, :sid, 'default', 'custom_dino', :oid, 1, 1000, 'FALHA', "
                "0, 0, :pj, 'spawn failed', :now, :now)"
            ),
            {
                "oid": fail_id,
                "sid": USER,
                "pj": json.dumps(payload, ensure_ascii=False),
                "now": now,
            },
        )
        db.commit()

        queue = list_admin_queue(db)
        by_id = {o["order_id"]: o for o in queue["orders"]}
        assert high["order_id"] in by_id
        assert by_id[high["order_id"]]["status_label"] == "Paga — aguardando aprovação"
        assert fail_id in by_id
        assert by_id[fail_id]["status_label"] == "Falha de entrega"

        filtered = list_admin_queue(db, status="FALHA")
        assert filtered["total"] >= 1
        assert all(o["status"] == "FALHA" for o in filtered["orders"])
    finally:
        db.close()


def test_admin_queue_excludes_entregue_and_rejeitado():
    db = _app_module._SessionLocal()
    try:
        _seed_rex(db)
        created = checkout(db, USER, _base_spec())
        db.commit()
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        db.execute(
            text("UPDATE orders SET status = 'ENTREGUE', updated_at = :now WHERE order_id = :oid"),
            {"now": now, "oid": created["order_id"]},
        )
        db.commit()
        queue = list_admin_queue(db)
        ids = [o["order_id"] for o in queue["orders"]]
        assert created["order_id"] not in ids

        hist = list_admin_history(db)
        hist_ids = [o["order_id"] for o in hist["orders"]]
        assert created["order_id"] in hist_ids
        row = next(o for o in hist["orders"] if o["order_id"] == created["order_id"])
        assert row["status_label"] == "Entregue"
        assert row["payment_status"] == "paid"

        filt = list_admin_history(db, status="ENTREGUE")
        assert all(o["status"] == "ENTREGUE" for o in filt["orders"])
    finally:
        db.close()


def test_admin_queue_status_filter_pendente(tmp_path):
    db = _app_module._SessionLocal()
    try:
        _seed_rex(db)
        created = checkout(db, USER, _base_spec())
        db.commit()
        assert created["status"] == "PENDENTE"
        _set_dino_order_settings(tmp_path, dino_order_auto_approve_max=1)
        waiting = checkout(db, USER, _base_spec(stat_points={"health": 10, "melee": 10}))
        db.commit()
        assert waiting["status"] == "AGUARDANDO_APROVACAO"
        filt = list_admin_queue(db, status="PENDENTE")
        assert filt["total"] >= 1
        assert all(o["status"] == "PENDENTE" for o in filt["orders"])
        ids = {o["order_id"] for o in filt["orders"]}
        assert created["order_id"] in ids
        assert waiting["order_id"] not in ids
    finally:
        db.close()


def test_requeue_failed_order_returns_to_pendente():
    db = _app_module._SessionLocal()
    try:
        _seed_rex(db)
        created = checkout(db, USER, _base_spec())
        db.commit()
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        db.execute(
            text(
                "UPDATE orders SET status = 'FALHA', last_error = 'spawn failed', "
                "updated_at = :now WHERE order_id = :oid"
            ),
            {"now": now, "oid": created["order_id"]},
        )
        db.commit()
        result = requeue_failed_order(db, created["order_id"], admin_steam_id=ADMIN)
        db.commit()
        assert result["status"] == "PENDENTE"
        assert result["status_label"] == "Paga — na fila de entrega"
        row = db.execute(
            text("SELECT status, last_error FROM orders WHERE order_id = :oid"),
            {"oid": created["order_id"]},
        ).fetchone()
        assert row[0] == "PENDENTE"
        assert row[1] is None
    finally:
        db.close()


def test_player_orders_include_payment_and_status_labels():
    db = _app_module._SessionLocal()
    try:
        _seed_rex(db)
        created = checkout(db, USER, _base_spec())
        db.commit()
        data = list_player_orders(db, USER)
        assert data["total"] == 1
        o = data["orders"][0]
        assert o["order_id"] == created["order_id"]
        assert o["payment_status"] == "paid"
        assert o["payment_status_label"] == "Paga"
        assert o["status_label"] == "Paga — na fila de entrega"
    finally:
        db.close()


def test_checkout_requires_manual_approve_when_above_auto_max(tmp_path):
    db = _app_module._SessionLocal()
    try:
        _seed_rex(db)
        _set_dino_order_settings(tmp_path, dino_order_auto_approve_max=1)
        result = checkout(db, USER, _base_spec())
        db.commit()
        assert result["status"] == "AGUARDANDO_APROVACAO"
        assert result["points_spent"] > 1
    finally:
        db.close()


def test_approve_moves_to_pendente(tmp_path):
    db = _app_module._SessionLocal()
    try:
        _seed_rex(db)
        _set_dino_order_settings(tmp_path, dino_order_auto_approve_max=1)
        result = checkout(db, USER, _base_spec())
        db.commit()
        assert result["status"] == "AGUARDANDO_APROVACAO"
        approved = approve_order(db, result["order_id"], admin_steam_id=ADMIN)
        db.commit()
        assert approved["status"] == "PENDENTE"
    finally:
        db.close()


def test_reject_refunds_points(tmp_path):
    db = _app_module._SessionLocal()
    try:
        _seed_rex(db)
        _set_dino_order_settings(tmp_path, dino_order_auto_approve_max=1)
        before = _get_player_points(USER)
        result = checkout(db, USER, _base_spec())
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


def test_reject_pendente_cancels_with_refund():
    """Auto-aprovada (PENDENTE) deve poder ser estornada pela fila Encomendas."""
    db = _app_module._SessionLocal()
    try:
        _seed_rex(db)
        before = _get_player_points(USER)
        result = checkout(db, USER, _base_spec())
        db.commit()
        assert result["status"] == "PENDENTE"
        mid = _get_player_points(USER)
        assert mid == before - result["points_spent"]
        cancelled = reject_order(db, result["order_id"], admin_steam_id=ADMIN, reason="Pedido duplicado")
        db.commit()
        assert cancelled["status"] == "CANCELADO"
        assert cancelled["status_label"] == "Cancelado"
        assert cancelled["refunded"] == result["points_spent"]
        assert cancelled["steam_id"] == USER
        assert _get_player_points(USER) == before
        queue = list_admin_queue(db)
        assert result["order_id"] not in [o["order_id"] for o in queue["orders"]]
        hist = list_admin_history(db)
        assert result["order_id"] in [o["order_id"] for o in hist["orders"]]
    finally:
        db.close()


def test_reject_falha_cancels_with_refund():
    db = _app_module._SessionLocal()
    try:
        _seed_rex(db)
        before = _get_player_points(USER)
        result = checkout(db, USER, _base_spec())
        db.commit()
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        db.execute(
            text(
                "UPDATE orders SET status = 'FALHA', last_error = 'spawn failed', "
                "updated_at = :now WHERE order_id = :oid"
            ),
            {"now": now, "oid": result["order_id"]},
        )
        db.commit()
        cancelled = reject_order(db, result["order_id"], admin_steam_id=ADMIN, reason="Abortar")
        db.commit()
        assert cancelled["status"] == "CANCELADO"
        assert cancelled["refunded"] == result["points_spent"]
        assert _get_player_points(USER) == before
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
