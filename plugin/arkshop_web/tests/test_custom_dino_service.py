"""Testes Dino Lab — Fase 0."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

import app as _app_module
from custom_dino_service import (
    ITEM_TYPE,
    STAT_COUNT,
    STAT_MAX,
    calc_spawn_exact_level,
    claim_custom_dino_orders,
    create_custom_dino_order,
    ensure_custom_dino_schema,
    list_custom_dino_orders_admin,
    list_species_admin,
    mark_custom_dino_delivered,
    recover_stale_entregando_custom_dino_orders,
    release_custom_dino_orders,
    validate_payload,
)

USER = "76561198000000001"
ADMIN = "76561198000000003"


@pytest.fixture()
def custom_dino_db(tmp_path):
    path = tmp_path / "dino_lab.db"
    engine = create_engine(f"sqlite:///{path}", future=True)
    with engine.connect() as conn:
        conn.execute(
            text(
                "CREATE TABLE orders ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT,"
                "order_id VARCHAR(64) UNIQUE,"
                "steam_id VARCHAR(32),"
                "server_id VARCHAR(64) DEFAULT 'default',"
                "item_type VARCHAR(32) DEFAULT 'shop',"
                "item_id VARCHAR(128),"
                "amount INTEGER DEFAULT 1,"
                "points_spent INTEGER DEFAULT 0,"
                "status VARCHAR(32) DEFAULT 'PENDENTE',"
                "original_order_id VARCHAR(64),"
                "retry_count INTEGER DEFAULT 0,"
                "last_error TEXT,"
                "contested INTEGER DEFAULT 0,"
                "created_at DATETIME,"
                "updated_at DATETIME"
                ")"
            )
        )
        conn.commit()
    ensure_custom_dino_schema(engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(autouse=True)
def _custom_dino_enabled(tmp_path, monkeypatch):
    settings_file = tmp_path / "settings.json"
    settings_file.write_text(json.dumps({"custom_dino_enabled": True}), encoding="utf-8")
    monkeypatch.setattr(_app_module, "_STATE_FILE", settings_file)
    from custom_dino_service import configure_custom_dino

    configure_custom_dino(settings_fn=_app_module._load_settings)


def _valid_body(**overrides):
    body = {
        "species_key": "rex",
        "level": 150,
        "gender": "female",
        "neutered": False,
        "colors": [14, 14, 14, 0, 0, 0],
        "deliver_as": "cryopod",
        "note": "Compensação suporte ticket teste",
    }
    body.update(overrides)
    if "species_key" in overrides and overrides["species_key"] is None:
        body.pop("species_key", None)
    return body


def test_ensure_custom_dino_schema_adds_payload_json(tmp_path):
    path = tmp_path / "schema.db"
    engine = create_engine(f"sqlite:///{path}", future=True)
    with engine.connect() as conn:
        conn.execute(
            text(
                "CREATE TABLE orders ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT,"
                "order_id VARCHAR(64) UNIQUE,"
                "steam_id VARCHAR(32)"
                ")"
            )
        )
        conn.commit()
    ensure_custom_dino_schema(engine)
    with engine.connect() as conn:
        cols = {str(r[1]) for r in conn.execute(text("PRAGMA table_info(orders)")).fetchall()}
    assert "payload_json" in cols
    ensure_custom_dino_schema(engine)


def test_validate_catalog_only_species_via_catalog_lookup(monkeypatch):
    """Espécies só no catálogo (ex. SmallBosses) devem validar como na lista admin."""
    sb_bp = (
        "/Game/Mods/SmallBosses/SmallDrake/SmallDrake_Character_BP_Fire"
        ".SmallDrake_Character_BP_Fire"
    )
    monkeypatch.setattr("custom_dino_service._species_catalog", lambda: {})
    monkeypatch.setattr(
        "custom_dino_service._blueprint_from_catalog_item",
        lambda item_id: sb_bp if item_id == "sb_drake_fire" else "",
    )
    payload, err = validate_payload(_valid_body(
        species_key="sb_drake_fire",
        level=1779,
        note="Compensação teste sb drake fire",
    ))
    assert err is None
    assert payload is not None
    assert payload["species_key"] == "sb_drake_fire"
    assert "SmallDrake_Character_BP_Fire" in payload["species_blueprint"]
    assert payload["mod_source"] == "smallbosses"


def test_list_species_admin_catalog_only_mod(monkeypatch):
    sb_bp = (
        "/Game/Mods/SmallBosses/SmallDrake/SmallDrake_Character_BP_Fire"
        ".SmallDrake_Character_BP_Fire"
    )
    monkeypatch.setattr(
        "custom_dino_service._species_catalog",
        lambda: {"sb_drake_fire": {}},
    )
    monkeypatch.setattr(
        "custom_dino_service._blueprint_from_catalog_item",
        lambda item_id: sb_bp if item_id == "sb_drake_fire" else "",
    )
    all_items = list_species_admin(vanilla_only=False)
    sb = next(s for s in all_items if s["species_key"] == "sb_drake_fire")
    assert sb["mod_source"] == "smallbosses"
    vanilla = list_species_admin(vanilla_only=True)
    assert not any(s["species_key"] == "sb_drake_fire" for s in vanilla)


def test_validate_payload_rex():
    payload, err = validate_payload(_valid_body())
    assert err is None
    assert payload is not None
    assert payload["species_key"] == "rex"
    assert payload["colors"] == [14, 14, 14, 0, 0, 0]
    assert "Blueprint'" in payload["species_blueprint"]


def test_list_species_admin_catalog_fallback(monkeypatch):
    monkeypatch.setattr(
        "custom_dino_service._species_catalog",
        lambda: {
            "rex": {
                "display_name": "Rex",
                "mod_source": "vanilla",
                "reference_catalog_item_id": "rex_femea",
            },
            "indominus": {
                "display_name": "Indominus Rex",
                "mod_source": "indominus_rex",
                "blueprint_path": "/Game/Mods/IndominusRex/Models/IndominusRex_Character_BP.IndominusRex_Character_BP",
            },
        },
    )
    monkeypatch.setattr(
        "custom_dino_service._blueprint_from_catalog",
        lambda defn: "/Game/PrimalEarth/Dinos/Rex/Rex_Character_BP.Rex_Character_BP"
        if defn.get("reference_catalog_item_id") == "rex_femea"
        else "",
    )
    vanilla = list_species_admin(vanilla_only=True)
    assert [s["species_key"] for s in vanilla] == ["rex"]
    all_items = list_species_admin(vanilla_only=False)
    assert {s["species_key"] for s in all_items} == {"rex", "indominus"}


def test_validate_rejects_short_note():
    _, err = validate_payload(_valid_body(note="curto"))
    assert err is not None


def test_validate_payload_manual_blueprint():
    bp = "/Game/PrimalEarth/Dinos/Rex/Rex_Character_BP.Rex_Character_BP"
    payload, err = validate_payload(_valid_body(
        species_key=None,
        species_blueprint=bp,
        species_display_name="Rex manual teste",
    ))
    assert err is None
    assert payload is not None
    assert payload["species_key"] == "custom"
    assert payload["species_display_name"] == "Rex manual teste"
    assert payload["mod_source"] == "manual"
    assert payload["species_blueprint"] == f"Blueprint'{bp}'"

    payload2, err2 = validate_payload(_valid_body(
        species_key=None,
        species_blueprint=f"Blueprint'{bp}'",
    ))
    assert err2 is None
    assert payload2["species_display_name"] == "custom"

    _, err3 = validate_payload(_valid_body(species_key=None, species_blueprint="invalid/path"))
    assert err3 is not None


def test_validate_rejects_saddle_as_species():
    saddle = "/Game/PrimalEarth/CoreBlueprints/Items/Armor/Saddles/PrimalItemArmor_RexSaddle.PrimalItemArmor_RexSaddle"
    _, err = validate_payload(_valid_body(species_key=None, species_blueprint=saddle))
    assert err is not None
    assert "não parece ser de criatura" in err


def test_validate_accepts_mod_dino_blueprint():
    bp = "/Game/Mods/Custom/Dino_BP.Dino_BP"
    payload, err = validate_payload(_valid_body(
        species_key=None,
        species_blueprint=bp,
        species_display_name="Dino mod teste",
    ))
    assert err is None
    assert payload is not None


def test_create_and_claim_manual_blueprint(custom_dino_db):
    bp = "/Game/Mods/Custom/Dino_BP.Dino_BP"
    payload, _ = validate_payload(_valid_body(
        species_key=None,
        species_blueprint=bp,
        species_display_name="Dino mod teste",
    ))
    result = create_custom_dino_order(
        custom_dino_db,
        steam_id=USER,
        payload=payload,
        admin_steam_id=ADMIN,
    )
    custom_dino_db.commit()
    claimed = claim_custom_dino_orders(custom_dino_db, USER)
    custom_dino_db.commit()
    assert len(claimed) == 1
    assert claimed[0]["payload"]["species_blueprint"] == f"Blueprint'{bp}'"
    assert claimed[0]["payload"]["mod_source"] == "manual"


def test_create_and_claim_custom_dino(custom_dino_db):
    payload, _ = validate_payload(_valid_body())
    result = create_custom_dino_order(
        custom_dino_db,
        steam_id=USER,
        payload=payload,
        admin_steam_id=ADMIN,
    )
    custom_dino_db.commit()
    assert result["status"] == "PENDENTE"
    assert result["order_id"].startswith("cd_")

    claimed = claim_custom_dino_orders(custom_dino_db, USER)
    custom_dino_db.commit()
    assert len(claimed) == 1
    assert claimed[0]["item_type"] == ITEM_TYPE
    assert claimed[0]["payload"]["species_key"] == "rex"

    delivered = mark_custom_dino_delivered(custom_dino_db, USER, [result["order_id"]])
    custom_dino_db.commit()
    assert delivered == [result["order_id"]]

    listed = list_custom_dino_orders_admin(custom_dino_db)
    assert listed["total"] == 1
    assert listed["orders"][0]["status"] == "ENTREGUE"
    assert listed["orders"][0]["species_image_url"].endswith("/generated/rex.webp")


def test_calc_spawn_exact_level():
    assert calc_spawn_exact_level([0] * STAT_COUNT, [0] * STAT_COUNT) == 1
    assert calc_spawn_exact_level([10, 5, 0, 0, 0, 0, 0], [20, 0, 0, 0, 0, 0, 0]) == 36


def test_validate_spawn_exact_payload(tmp_path, monkeypatch):
    settings_file = tmp_path / "spawn_exact_settings.json"
    settings_file.write_text(
        json.dumps({"custom_dino_enabled": True, "custom_dino_spawn_exact": True}),
        encoding="utf-8",
    )
    monkeypatch.setattr(_app_module, "_STATE_FILE", settings_file)
    from custom_dino_service import configure_custom_dino

    configure_custom_dino(settings_fn=_app_module._load_settings)

    wild = [30, 30, 30, 30, 30, 30, 30]
    tamed = [30, 30, 30, 30, 30, 30, 30]
    payload, err = validate_payload(_valid_body(
        spawn_exact={
            "enabled": True,
            "wild_stats": wild,
            "tamed_stats": tamed,
            "imprint_pct": 100,
            "imprinter_name": "Admin",
            "imprinter_id_hex": "7B5A3C2D",
        },
    ))
    assert err is None
    assert payload is not None
    assert payload["level"] == calc_spawn_exact_level(wild, tamed)
    assert payload["spawn_exact"]["enabled"] is True
    assert payload["spawn_exact"]["wild_stats"] == wild
    assert payload["spawn_exact"]["imprint_pct"] == 1.0


def test_validate_spawn_exact_rejects_when_flag_off(tmp_path, monkeypatch):
    settings_file = tmp_path / "spawn_exact_off.json"
    settings_file.write_text(
        json.dumps({"custom_dino_enabled": True, "custom_dino_spawn_exact": False}),
        encoding="utf-8",
    )
    monkeypatch.setattr(_app_module, "_STATE_FILE", settings_file)
    from custom_dino_service import configure_custom_dino

    configure_custom_dino(settings_fn=_app_module._load_settings)

    _, err = validate_payload(_valid_body(spawn_exact={"enabled": True, "wild_stats": [1] * 7, "tamed_stats": [0] * 7}))
    assert err is not None
    assert "custom_dino_spawn_exact" in err


def test_validate_spawn_exact_unlimited_allows_high_level(tmp_path, monkeypatch):
    settings_file = tmp_path / "spawn_exact_unlimited.json"
    settings_file.write_text(
        json.dumps({
            "custom_dino_enabled": True,
            "custom_dino_spawn_exact": True,
            "custom_dino_level_max": 0,
        }),
        encoding="utf-8",
    )
    monkeypatch.setattr(_app_module, "_STATE_FILE", settings_file)
    from custom_dino_service import configure_custom_dino

    configure_custom_dino(settings_fn=_app_module._load_settings)

    wild = [STAT_MAX] * STAT_COUNT
    tamed = [STAT_MAX] * STAT_COUNT
    payload, err = validate_payload(_valid_body(spawn_exact={"enabled": True, "wild_stats": wild, "tamed_stats": tamed}))
    assert err is None
    assert payload is not None
    assert payload["level"] == 1 + STAT_MAX * STAT_COUNT * 2


def test_validate_spawn_exact_254_preset_level_3557(tmp_path, monkeypatch):
    """Preset 254 wild + 254 tamed → nível 3557 (1 + 7×254 + 7×254); stats no payload, não em colors."""
    settings_file = tmp_path / "spawn_exact_254.json"
    settings_file.write_text(
        json.dumps({"custom_dino_enabled": True, "custom_dino_spawn_exact": True}),
        encoding="utf-8",
    )
    monkeypatch.setattr(_app_module, "_STATE_FILE", settings_file)
    from custom_dino_service import configure_custom_dino

    configure_custom_dino(settings_fn=_app_module._load_settings)

    wild = [STAT_MAX] * STAT_COUNT
    tamed = [STAT_MAX] * STAT_COUNT
    colors = [79] * 6
    payload, err = validate_payload(_valid_body(
        spawn_exact={"enabled": True, "wild_stats": wild, "tamed_stats": tamed},
        colors=colors,
    ))
    assert err is None
    assert payload is not None
    assert payload["level"] == 3557
    assert payload["spawn_exact"]["wild_stats"] == wild
    assert payload["spawn_exact"]["tamed_stats"] == tamed
    assert payload["colors"] == colors


def test_validate_spawn_exact_level_cap(tmp_path, monkeypatch):
    settings_file = tmp_path / "spawn_exact_cap.json"
    settings_file.write_text(
        json.dumps({
            "custom_dino_enabled": True,
            "custom_dino_spawn_exact": True,
            "custom_dino_level_max": 450,
        }),
        encoding="utf-8",
    )
    monkeypatch.setattr(_app_module, "_STATE_FILE", settings_file)
    from custom_dino_service import configure_custom_dino

    configure_custom_dino(settings_fn=_app_module._load_settings)

    wild = [STAT_MAX] * STAT_COUNT
    tamed = [STAT_MAX] * STAT_COUNT
    _, err = validate_payload(_valid_body(spawn_exact={"enabled": True, "wild_stats": wild, "tamed_stats": tamed}))
    assert err is not None
    assert "450" in err
    assert "custom_dino_level_max" in err


def test_validate_simple_level_cap(tmp_path, monkeypatch):
    settings_file = tmp_path / "simple_level_cap.json"
    settings_file.write_text(
        json.dumps({
            "custom_dino_enabled": True,
            "custom_dino_level_max": 200,
        }),
        encoding="utf-8",
    )
    monkeypatch.setattr(_app_module, "_STATE_FILE", settings_file)
    from custom_dino_service import configure_custom_dino

    configure_custom_dino(settings_fn=_app_module._load_settings)

    _, err = validate_payload(_valid_body(level=500))
    assert err is not None
    assert "200" in err

    payload, err2 = validate_payload(_valid_body(level=150))
    assert err2 is None
    assert payload is not None


def test_validate_spawn_exact_stat_bounds(tmp_path, monkeypatch):
    settings_file = tmp_path / "spawn_exact_bounds.json"
    settings_file.write_text(
        json.dumps({"custom_dino_enabled": True, "custom_dino_spawn_exact": True}),
        encoding="utf-8",
    )
    monkeypatch.setattr(_app_module, "_STATE_FILE", settings_file)
    from custom_dino_service import configure_custom_dino

    configure_custom_dino(settings_fn=_app_module._load_settings)

    _, err = validate_payload(_valid_body(spawn_exact={
        "enabled": True,
        "wild_stats": [STAT_MAX + 1] + [0] * (STAT_COUNT - 1),
        "tamed_stats": [0] * STAT_COUNT,
    }))
    assert err is not None
    assert "wild_stats" in err

    _, err2 = validate_payload(_valid_body(spawn_exact={
        "enabled": True,
        "wild_stats": [0] * STAT_COUNT,
        "tamed_stats": [0] * 6,
    }))
    assert err2 is not None
    assert "tamed_stats" in err2


def test_recover_stale_entregando_and_reclaim(custom_dino_db):
    payload, _ = validate_payload(_valid_body())
    result = create_custom_dino_order(
        custom_dino_db,
        steam_id=USER,
        payload=payload,
        admin_steam_id=ADMIN,
    )
    custom_dino_db.commit()
    claimed = claim_custom_dino_orders(custom_dino_db, USER)
    custom_dino_db.commit()
    assert len(claimed) == 1
    assert claimed[0]["order_id"] == result["order_id"]

    stale_time = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=10)
    custom_dino_db.execute(
        text("UPDATE orders SET updated_at = :t WHERE order_id = :oid"),
        {"t": stale_time, "oid": result["order_id"]},
    )
    custom_dino_db.commit()

    recovered = recover_stale_entregando_custom_dino_orders(custom_dino_db, USER, minutes=5)
    custom_dino_db.commit()
    assert recovered == 1

    row = custom_dino_db.execute(
        text("SELECT status FROM orders WHERE order_id = :oid"),
        {"oid": result["order_id"]},
    ).fetchone()
    assert row[0] == "PENDENTE"

    reclaimed = claim_custom_dino_orders(custom_dino_db, USER)
    custom_dino_db.commit()
    assert len(reclaimed) == 1
    assert reclaimed[0]["order_id"] == result["order_id"]


def test_validate_payload_null_optional_fields_serialized_as_empty_strings():
    """Campos opcionais null no body não devem virar JSON null no payload (evita crash no plugin)."""
    payload, err = validate_payload(_valid_body(
        saddle_blueprint=None,
        custom_name=None,
    ))
    assert err is None
    assert payload is not None
    assert payload["saddle_blueprint"] == ""
    assert payload["custom_name"] == ""
    serialized = json.loads(json.dumps(payload))
    assert serialized["saddle_blueprint"] == ""
    assert serialized["custom_name"] == ""


def test_mark_custom_dino_failed(custom_dino_db):
    payload, _ = validate_payload(_valid_body())
    result = create_custom_dino_order(
        custom_dino_db,
        steam_id=USER,
        payload=payload,
        admin_steam_id=ADMIN,
    )
    custom_dino_db.commit()
    claim_custom_dino_orders(custom_dino_db, USER)
    custom_dino_db.commit()

    from custom_dino_service import mark_custom_dino_failed

    released = release_custom_dino_orders(custom_dino_db, USER, [result["order_id"]])
    custom_dino_db.commit()
    assert released == [result["order_id"]]

    ok = mark_custom_dino_failed(
        custom_dino_db, USER, result["order_id"], error="dino_delivery_failed"
    )
    custom_dino_db.commit()
    assert ok is True

    row = custom_dino_db.execute(
        text("SELECT status, last_error FROM orders WHERE order_id = :oid"),
        {"oid": result["order_id"]},
    ).fetchone()
    assert row[0] == "FALHA"
    assert "dino_delivery_failed" in str(row[1])


    payload, _ = validate_payload(_valid_body())
    result = create_custom_dino_order(
        custom_dino_db,
        steam_id=USER,
        payload=payload,
        admin_steam_id=ADMIN,
    )
    custom_dino_db.commit()
    claim_custom_dino_orders(custom_dino_db, USER)
    custom_dino_db.commit()

    released = release_custom_dino_orders(custom_dino_db, USER, [result["order_id"]])
    custom_dino_db.commit()
    assert released == [result["order_id"]]

    row = custom_dino_db.execute(
        text("SELECT status FROM orders WHERE order_id = :oid"),
        {"oid": result["order_id"]},
    ).fetchone()
    assert row[0] == "PENDENTE"
