"""Testes Dino Lab — Fase 0."""
from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

import app as _app_module
from custom_dino_service import (
    ITEM_TYPE,
    claim_custom_dino_orders,
    create_custom_dino_order,
    ensure_custom_dino_schema,
    list_custom_dino_orders_admin,
    list_species_admin,
    mark_custom_dino_delivered,
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
