"""Testes do serviço de auditoria pública de dinos do catálogo."""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from catalog_dino_audit_service import (
    canonical_id,
    ensure_catalog_dino_generations_schema,
    list_public_catalog_dinos,
    lookup_catalog_dino_by_identity,
    mask_display_name,
    register_catalog_dino_records,
    species_key_from_item_id,
)
from catalog_dino_public_code import (
    GENDER_FEMALE,
    GENDER_MALE,
    GENDER_NONE,
    VARIANT_ABYSS,
    VARIANT_VANILLA,
    build_public_code,
    family_letter,
    parse_species_key,
    reset_letter_state_for_tests,
    resolve_gender_digit,
    seed_families_from_catalog,
)


@pytest.fixture(autouse=True)
def _reset_public_codes():
    reset_letter_state_for_tests()
    yield
    reset_letter_state_for_tests()


@pytest.fixture()
def audit_db(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'cdg.db'}")
    ensure_catalog_dino_generations_schema(engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    db.execute(
        text(
            "CREATE TABLE store_users ("
            "steam_id TEXT PRIMARY KEY,"
            "display_name TEXT,"
            "steam_persona TEXT)"
        )
    )
    db.execute(
        text(
            "INSERT INTO store_users (steam_id, display_name, steam_persona) "
            "VALUES ('76561198000000001', 'AlphaTester', 'AlphaTester')"
        )
    )
    db.commit()
    yield db
    db.close()


def test_canonical_and_species_helpers():
    assert canonical_id(1, 2) == "00000001-00000002"
    assert species_key_from_item_id("rex_pack10") == "rex"
    assert species_key_from_item_id("rex_l200") == "rex"
    assert mask_display_name("AlphaTester") == "Alp***ter"
    assert mask_display_name("76561198000000001") == "Jogador"


def test_public_code_mapping():
    seed_families_from_catalog(
        {
            "Items": {
                "rex_femea": {"Type": "dino", "Gender": "female"},
                "abyss_rex_abyssal": {"Type": "dino", "Gender": "female"},
                "giga_femea": {"Type": "dino", "Gender": "female"},
                "bionicrex_femea": {"Type": "dino", "Gender": "female"},
            }
        }
    )
    fam, var = parse_species_key("rex_femea")
    assert fam == "rex"
    assert var == VARIANT_VANILLA
    fam2, var2 = parse_species_key("abyss_rex_abyssal")
    assert fam2 == "rex"
    assert var2 == VARIANT_ABYSS
    assert family_letter("rex") == "R"
    assert family_letter("giga") == "G"
    assert resolve_gender_digit(payload_gender="female") == GENDER_FEMALE
    assert resolve_gender_digit(payload_gender="male") == GENDER_MALE
    assert resolve_gender_digit(item_id="tekstrider_femea") == GENDER_FEMALE
    assert resolve_gender_digit() == GENDER_NONE
    code = build_public_code(
        species_key="rex_femea", gender_digit=GENDER_FEMALE, sequence=347
    )
    # R + vanilla(1) + female(2) + 347
    assert code == "R12347"
    code_abyss = build_public_code(
        species_key="abyss_rex_abyssal", gender_digit=GENDER_FEMALE, sequence=1
    )
    assert code_abyss == "R22001"


def test_register_filters_level_and_lists_public(audit_db):
    catalog = {
        "Items": {
            "rex": {"Type": "dino", "Gender": "female"},
            "rex_l200": {"Type": "dino"},
            "giga": {"Type": "dino", "Gender": "male"},
        }
    }
    seed_families_from_catalog(catalog)
    n = register_catalog_dino_records(
        audit_db,
        steam_id="76561198000000001",
        catalog=catalog,
        dino_records=[
            {
                "order_id": "ord1",
                "item_id": "rex",
                "dino_id1": 10,
                "dino_id2": 20,
                "level": 1,
                "gender": "female",
            },
            {
                "order_id": "ord1",
                "item_id": "rex_l200",
                "dino_id1": 11,
                "dino_id2": 21,
                "level": 200,
            },
            {
                "order_id": "ord2",
                "item_id": "giga",
                "dino_id1": 12,
                "dino_id2": 22,
                "level": 150,
            },
            {
                "order_id": "ord3",
                "item_id": "bad",
                "dino_id1": 0,
                "dino_id2": 0,
                "level": 1,
            },
        ],
    )
    audit_db.commit()
    assert n == 2

    all_rows = list_public_catalog_dinos(audit_db, page=1, page_size=10)
    assert all_rows["total"] == 2
    assert all_rows["items"][0]["display_name"] == "Alp***ter"
    assert "steam_id" not in all_rows["items"][0]
    assert all_rows["items"][0]["public_code"]
    assert all_rows["items"][0]["public_code"].startswith("R")

    only1 = list_public_catalog_dinos(audit_db, level=1)
    assert only1["total"] == 1
    assert only1["items"][0]["level"] == 1
    assert only1["items"][0]["canonical_id"] == "0000000A-00000014"
    assert only1["items"][0]["public_code"] == "R12001"
    assert only1["items"][0]["gender_digit"] == GENDER_FEMALE

    by_sp = list_public_catalog_dinos(audit_db, species="rex")
    assert by_sp["total"] == 2

    # segundo rex L1 → sequência 002 no mesmo prefixo
    n2 = register_catalog_dino_records(
        audit_db,
        steam_id="76561198000000001",
        catalog=catalog,
        dino_records=[
            {
                "order_id": "ord4",
                "item_id": "rex",
                "dino_id1": 30,
                "dino_id2": 40,
                "level": 1,
                "gender": "female",
            }
        ],
    )
    audit_db.commit()
    assert n2 == 1
    only1b = list_public_catalog_dinos(audit_db, level=1)
    codes = {r["public_code"] for r in only1b["items"]}
    assert "R12001" in codes
    assert "R12002" in codes


def test_lookup_by_dino_ids_and_canonical(audit_db):
    catalog = {"Items": {"rex": {"Type": "dino", "Gender": "female"}}}
    seed_families_from_catalog(catalog)
    register_catalog_dino_records(
        audit_db,
        steam_id="76561198000000001",
        catalog=catalog,
        dino_records=[
            {
                "order_id": "ord_lookup",
                "item_id": "rex",
                "dino_id1": 0xAABBCCDD,
                "dino_id2": 0x11223344,
                "level": 1,
                "gender": "female",
            }
        ],
    )
    audit_db.commit()

    hit = lookup_catalog_dino_by_identity(
        audit_db, dino_id1=0xAABBCCDD, dino_id2=0x11223344
    )
    assert hit["ok"] is True
    assert hit["found"] is True
    assert hit["public_code"] == "R12001"
    assert hit["canonical_id"] == "AABBCCDD-11223344"
    assert hit["level"] == 1
    assert hit["species_key"] == "rex"
    assert "steam_id" not in hit

    by_canon = lookup_catalog_dino_by_identity(
        audit_db, canonical="AABBCCDD-11223344"
    )
    assert by_canon["found"] is True
    assert by_canon["public_code"] == hit["public_code"]

    miss = lookup_catalog_dino_by_identity(audit_db, dino_id1=1, dino_id2=2)
    assert miss["ok"] is True
    assert miss["found"] is False

    bad = lookup_catalog_dino_by_identity(audit_db, dino_id1=0, dino_id2=0)
    assert bad["ok"] is False
    assert bad["error"] == "invalid_id"


def test_plugin_catalog_dino_lookup_endpoint(tmp_path, monkeypatch):
    import json

    import app as _app_module
    from catalog_dino_audit_service import ensure_catalog_dino_generations_schema

    api_key = "test-checar-key"
    monkeypatch.setenv("ARKSHOP_API_KEY", api_key)
    monkeypatch.setattr(_app_module, "_ARKSHOP_API_KEY", api_key)
    monkeypatch.setattr(_app_module, "_DB_INITIALIZED", True)
    monkeypatch.setattr(_app_module, "_ACTIVE_DATABASE_URL", "")
    db_url = f"sqlite:///{tmp_path / 'checar_lookup.db'}"
    _app_module._configure_database(db_url)
    assert _app_module._ENGINE is not None
    ensure_catalog_dino_generations_schema(_app_module._ENGINE)

    # store_users para display_name no register
    with _app_module._ENGINE.begin() as conn:
        conn.execute(
            text(
                "CREATE TABLE IF NOT EXISTS store_users ("
                "steam_id TEXT PRIMARY KEY,"
                "display_name TEXT,"
                "steam_persona TEXT)"
            )
        )
        conn.execute(
            text(
                "INSERT OR IGNORE INTO store_users (steam_id, display_name, steam_persona) "
                "VALUES ('76561198000000001', 'AlphaTester', 'AlphaTester')"
            )
        )

    catalog = {"Items": {"rex": {"Type": "dino", "Gender": "female"}}}
    seed_families_from_catalog(catalog)
    db = _app_module._SessionLocal()
    try:
        register_catalog_dino_records(
            db,
            steam_id="76561198000000001",
            catalog=catalog,
            dino_records=[
                {
                    "order_id": "ord_http",
                    "item_id": "rex",
                    "dino_id1": 10,
                    "dino_id2": 20,
                    "level": 1,
                    "gender": "female",
                }
            ],
        )
        db.commit()
    finally:
        db.close()

    client = _app_module.app.test_client()
    headers = {"X-API-Key": api_key, "Content-Type": "application/json"}

    denied = client.post(
        "/api/plugin/catalog-dino/lookup",
        json={"dino_id1": 10, "dino_id2": 20},
    )
    assert denied.status_code == 401

    hit = client.post(
        "/api/plugin/catalog-dino/lookup",
        headers=headers,
        json={"dino_id1": 10, "dino_id2": 20},
    )
    assert hit.status_code == 200
    data = hit.get_json()
    assert data["ok"] is True
    assert data["found"] is True
    assert data["public_code"] == "R12001"
    assert data["canonical_id"] == "0000000A-00000014"

    by_canon = client.post(
        "/api/plugin/catalog-dino/lookup",
        headers=headers,
        json={"canonical_id": "0000000A-00000014"},
    )
    assert by_canon.get_json()["public_code"] == "R12001"

    miss = client.post(
        "/api/plugin/catalog-dino/lookup",
        headers=headers,
        json={"dino_id1": 99, "dino_id2": 88},
    )
    assert miss.status_code == 200
    assert miss.get_json()["found"] is False

    bad = client.post(
        "/api/plugin/catalog-dino/lookup",
        headers=headers,
        json={},
    )
    assert bad.status_code == 400
    assert bad.get_json()["error"] == "invalid_id"
