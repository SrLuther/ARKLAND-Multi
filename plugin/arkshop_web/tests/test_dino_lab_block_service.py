"""Testes do bloqueio Dino Lab no mercado."""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("ARKSHOP_DATABASE_URL", "")
os.environ.setdefault("ARKSHOP_WEB_SECRET", "test-secret")

import app as _app_module
from custom_dino_service import (
    ITEM_TYPE,
    ensure_custom_dino_schema,
    mark_custom_dino_delivered,
)
from dino_lab_block_service import (
    DINO_LAB_BLOCK_MESSAGE,
    PLAYER_CHECK_DISCLAIMER,
    append_debug_fields,
    audit_dino_lab_block_event,
    canonical_id,
    check_blocked_from_metadata,
    check_blocked_reason,
    check_dino_id_from_body,
    check_single_id_blocked,
    ensure_dino_lab_block_schema,
    get_dino_lab_block_debug_snapshot,
    get_dino_lab_block_stats_api,
    is_any_id_blocked,
    is_dino_lab_block_debug,
    lookup_blocked_from_metadata,
    lookup_blocked_match,
    new_trace_id,
    parse_dino_id_input,
    register_blocked_dino_ids,
    search_blocked_ids,
)
from market_listings import preview_plugin_economy, process_plugin_upload

API_KEY = "test-api-key"
ADMIN = "76561198000000001"
USER = "76561198000000001"
SELLER = "76561198000000002"
ORDER = "cd_testblock001"
TRACE = "trace_dino_lab_block_000001"


@pytest.fixture()
def block_db(tmp_path):
    path = tmp_path / "dino_lab_block.db"
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
                "payload_json TEXT,"
                "created_at DATETIME,"
                "updated_at DATETIME"
                ")"
            )
        )
        conn.commit()
    ensure_custom_dino_schema(engine)
    ensure_dino_lab_block_schema(engine)
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


@pytest.fixture()
def market_client(tmp_path, monkeypatch):
    db_url = f"sqlite:///{tmp_path / 'market_block_http.db'}"
    monkeypatch.setenv("ARKSHOP_API_KEY", API_KEY)
    monkeypatch.setattr(_app_module, "_ARKSHOP_API_KEY", API_KEY)
    monkeypatch.setattr(_app_module, "_DB_INITIALIZED", True)
    monkeypatch.setattr(_app_module, "_ACTIVE_DATABASE_URL", "")
    _app_module._configure_database(db_url)
    from dino_lab_block_service import ensure_dino_lab_block_schema

    if _app_module._ENGINE is not None:
        ensure_dino_lab_block_schema(_app_module._ENGINE)
    return _app_module.app.test_client()


def _register_sample(block_db, *, id1: int = 0xAABBCCDD, id2: int = 0x11223344) -> None:
    register_blocked_dino_ids(
        block_db,
        ORDER,
        USER,
        {
            "dino_id1": id1,
            "dino_id2": id2,
            "ancestors": [
                {"dino_id1": 1, "dino_id2": 2, "side": "male", "generation": 1},
            ],
        },
    )
    block_db.commit()


def test_canonical_id_format():
    assert canonical_id(0xAABBCCDD, 0x11223344) == "AABBCCDD-11223344"


def test_register_and_lookup_self(block_db):
    _register_sample(block_db)
    assert is_any_id_blocked(block_db, [(0xAABBCCDD, 0x11223344)])
    assert check_blocked_reason(block_db, [(0xAABBCCDD, 0x11223344)]) == DINO_LAB_BLOCK_MESSAGE
    assert not is_any_id_blocked(block_db, [(999, 888)])


def test_register_ancestor_match(block_db):
    _register_sample(block_db)
    assert is_any_id_blocked(block_db, [(1, 2)])


def test_check_blocked_from_metadata(block_db):
    _register_sample(block_db)
    meta = {
        "dino_identity": {
            "dino_id1": 0xAABBCCDD,
            "dino_id2": 0x11223344,
            "ancestors": [],
        }
    }
    assert check_blocked_from_metadata(block_db, meta) == DINO_LAB_BLOCK_MESSAGE


def test_delivered_registers_before_entregue(block_db):
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    block_db.execute(
        text(
            "INSERT INTO orders "
            "(order_id, steam_id, item_type, item_id, status, created_at, updated_at) "
            "VALUES (:oid, :sid, :it, :iid, 'ENTREGANDO', :now, :now)"
        ),
        {"oid": ORDER, "sid": USER, "it": ITEM_TYPE, "iid": ORDER, "now": now},
    )
    block_db.commit()

    register_blocked_dino_ids(
        block_db,
        ORDER,
        USER,
        {"dino_id1": 555, "dino_id2": 666, "ancestors": []},
    )
    mark_custom_dino_delivered(block_db, USER, [ORDER])
    block_db.commit()

    row = block_db.execute(
        text("SELECT status FROM orders WHERE order_id = :oid"),
        {"oid": ORDER},
    ).fetchone()
    assert row[0] == "ENTREGUE"
    assert is_any_id_blocked(block_db, [(555, 666)])


def test_preview_rejects_blocked_dino(block_db):
    _register_sample(block_db)
    result = preview_plugin_economy(
        block_db,
        {
            "species_blueprint": "/Game/PrimalEarth/Dinos/Rex/Rex_Character_BP.Rex_Character_BP",
            "imprint_pct": 1.0,
            "dino_identity": {
                "dino_id1": 0xAABBCCDD,
                "dino_id2": 0x11223344,
                "ancestors": [],
            },
        },
    )
    assert result["ok"] is False
    assert result["blocked"] is True
    assert result["reason"] == "dino_lab_blocked"


def test_process_plugin_upload_rejects_blocked(block_db, tmp_path, monkeypatch):
    db_url = f"sqlite:///{tmp_path / 'market_upload_block.db'}"
    monkeypatch.setattr(_app_module, "_ACTIVE_DATABASE_URL", "")
    _app_module._configure_database(db_url)
    db = _app_module._SessionLocal()
    try:
        from app import MarketPlayerProfile, MarketSpecies, MarketSpeciesStatMultiplier

        ensure_dino_lab_block_schema(db.bind)
        species = MarketSpecies(
            species_key="rex_block",
            catalog_item_id="rex_block",
            display_name="Rex",
            blueprint_path="/Game/PrimalEarth/Dinos/Rex/Rex_Character_BP.Rex_Character_BP",
            reference_level=1,
            root_value=5000,
            tier="A",
            status="ACTIVE",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        db.add(species)
        db.flush()
        db.add(
            MarketSpeciesStatMultiplier(
                species_id=species.id, stat_key="melee", multiplier=700, enabled=True
            )
        )
        db.add(
            MarketPlayerProfile(
                steam_id=SELLER,
                market_display_name="Seller",
                commerce_enabled=True,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
        )
        register_blocked_dino_ids(
            db,
            ORDER,
            USER,
            {"dino_id1": 0xDEADBEEF, "dino_id2": 0xCAFEBABE, "ancestors": []},
        )
        db.commit()

        with pytest.raises(ValueError, match="Dino Lab"):
            process_plugin_upload(
                db,
                {
                    "steam_id": SELLER,
                    "inventory_removed": True,
                    "inventory_verified_empty": True,
                    "item_blob_hex": "0102ab",
                    "upload_id": TRACE,
                    "market_trace_id": TRACE,
                    "metadata": {
                        "species_blueprint": species.blueprint_path,
                        "imprint_pct": 1.0,
                        "name_map": "Blocked Rex",
                        "dino_identity": {
                            "dino_id1": 0xDEADBEEF,
                            "dino_id2": 0xCAFEBABE,
                            "ancestors": [],
                        },
                    },
                },
            )
    finally:
        db.close()


def test_lookup_blocked_match_includes_pair(block_db):
    _register_sample(block_db)
    match = lookup_blocked_match(block_db, [(0xAABBCCDD, 0x11223344)])
    assert match is not None
    assert match["blocked"] is True
    assert match["reason"] == "dino_lab_blocked"
    assert match["canonical_id"] == "AABBCCDD-11223344"
    assert match["matched_pair"] == [0xAABBCCDD, 0x11223344]
    assert match["order_id"] == ORDER


def test_lookup_blocked_from_metadata(block_db):
    _register_sample(block_db)
    match = lookup_blocked_from_metadata(
        block_db,
        {
            "dino_identity": {
                "dino_id1": 0xAABBCCDD,
                "dino_id2": 0x11223344,
                "ancestors": [],
            }
        },
    )
    assert match is not None
    assert match["matched_pair"] == [0xAABBCCDD, 0x11223344]


def test_audit_dino_lab_block_event_calls_fn():
    events: list[tuple[str, dict]] = []

    def _audit(event_type: str, **kwargs):
        events.append((event_type, kwargs))

    audit_dino_lab_block_event(
        _audit,
        "dino_lab_block_hit",
        order_id=ORDER,
        matched_pair=[1, 2],
        trace_id=TRACE,
    )
    assert events[0][0] == "dino_lab_block_hit"
    assert events[0][1]["order_id"] == ORDER
    assert events[0][1]["matched_pair"] == [1, 2]


def test_append_debug_fields_only_when_debug():
    base = {"blocked": True}
    out = append_debug_fields(base, debug=False, trace_id=TRACE, match={"matched_pair": [1, 2]})
    assert "trace_id" not in out
    out2 = append_debug_fields(base, debug=True, trace_id=TRACE, match={"matched_pair": [1, 2]})
    assert out2["trace_id"] == TRACE
    assert out2["matched_pair"] == [1, 2]


def test_debug_snapshot(block_db):
    _register_sample(block_db)
    block_db.commit()
    snap = get_dino_lab_block_debug_snapshot(block_db, limit=10)
    assert snap["stats"]["total_rows"] >= 2
    assert len(snap["recent"]) >= 2
    assert snap["recent"][0]["canonical_id"]


def test_is_dino_lab_block_debug_flag():
    assert not is_dino_lab_block_debug({})
    assert is_dino_lab_block_debug({"dino_lab_block_debug": True})


def test_new_trace_id_format():
    tid = new_trace_id()
    assert tid.startswith("dlb_")
    assert len(tid) > 8


def _login_admin(client, steam_id: str = ADMIN):
    with client.session_transaction() as sess:
        sess["steam_id"] = steam_id


def _setup_admin_file(tmp_path, monkeypatch, steam_id: str = ADMIN):
    admin_file = tmp_path / "admin_steamids.json"
    admin_file.write_text(json.dumps([steam_id]), encoding="utf-8")
    monkeypatch.setattr(_app_module, "_ADMIN_FILE", admin_file)


def test_search_blocked_ids_by_canonical_pair(block_db):
    _register_sample(block_db)
    result = search_blocked_ids(block_db, q="AABBCCDD-11223344")
    assert result["total"] == 1
    assert result["rows"][0]["canonical_id"] == "AABBCCDD-11223344"
    assert result["rows"][0]["role"] == "self"


def test_search_blocked_ids_by_decimal_id(block_db):
    _register_sample(block_db)
    result = search_blocked_ids(block_db, q="1")
    assert result["total"] >= 1
    assert any(r["role"] == "ancestor" for r in result["rows"])


def test_search_blocked_ids_filters_and_pagination(block_db):
    register_blocked_dino_ids(
        block_db,
        "order_a",
        USER,
        {"dino_id1": 10, "dino_id2": 20, "ancestors": []},
    )
    register_blocked_dino_ids(
        block_db,
        "order_b",
        SELLER,
        {"dino_id1": 30, "dino_id2": 40, "ancestors": []},
    )
    block_db.commit()

    by_steam = search_blocked_ids(block_db, steam_id=SELLER)
    assert by_steam["total"] == 1
    assert by_steam["rows"][0]["order_id"] == "order_b"

    by_order = search_blocked_ids(block_db, order_id="order_a")
    assert by_order["total"] == 1

    page1 = search_blocked_ids(block_db, page=1, per_page=1)
    assert page1["total"] >= 2
    assert page1["count"] == 1
    assert page1["pages"] >= 2

    page2 = search_blocked_ids(block_db, page=2, per_page=1)
    assert page2["count"] == 1
    assert page1["rows"][0]["canonical_id"] != page2["rows"][0]["canonical_id"]


def test_get_dino_lab_block_stats_api(block_db):
    _register_sample(block_db)
    stats = get_dino_lab_block_stats_api(block_db)
    assert stats["total_rows"] >= 2
    assert "dino_lab" in stats["by_source"]
    assert stats["last_24h"] >= 2


def test_admin_dino_lab_block_list_requires_admin(market_client):
    r = market_client.get("/api/admin/dino-lab-block/list")
    assert r.status_code in (401, 403)


def test_admin_dino_lab_block_list_and_stats(market_client, tmp_path, monkeypatch):
    _setup_admin_file(tmp_path, monkeypatch)
    db = _app_module._SessionLocal()
    try:
        register_blocked_dino_ids(
            db,
            "cd_adminlist01",
            USER,
            {"dino_id1": 0xABCDEF01, "dino_id2": 0x23456789, "ancestors": []},
        )
        db.commit()
    finally:
        db.close()

    _login_admin(market_client)
    stats = market_client.get("/api/admin/dino-lab-block/stats")
    assert stats.status_code == 200
    st = stats.get_json()
    assert st["ok"] is True
    assert st["stats"]["total_rows"] >= 1

    listed = market_client.get(
        "/api/admin/dino-lab-block/list?q=ABCDEF01-23456789&order_id=cd_adminlist01"
    )
    assert listed.status_code == 200
    data = listed.get_json()
    assert data["ok"] is True
    assert data["total"] == 1
    assert data["rows"][0]["order_id"] == "cd_adminlist01"
    assert data["rows"][0]["canonical_id"] == "ABCDEF01-23456789"


def test_check_dino_blocked_endpoint(market_client):
    db = _app_module._SessionLocal()
    try:
        register_blocked_dino_ids(
            db,
            ORDER,
            USER,
            {"dino_id1": 12345, "dino_id2": 67890, "ancestors": []},
        )
        db.commit()
    finally:
        db.close()

    headers = {"X-API-Key": API_KEY, "Content-Type": "application/json"}
    blocked = market_client.post(
        "/api/market/plugin/check-dino-blocked",
        headers=headers,
        json={"dino_id_pairs": [[12345, 67890]]},
    )
    assert blocked.status_code == 200
    data = blocked.get_json()
    assert data["ok"] is True
    assert data["blocked"] is True
    assert data["order_id"] == ORDER
    assert data["canonical_id"] == canonical_id(12345, 67890)
    assert data["matched_pair"] == [12345, 67890]

    allowed = market_client.post(
        "/api/market/plugin/check-dino-blocked",
        headers=headers,
        json={"dino_id_pairs": [[1, 2]]},
    )
    assert allowed.get_json()["blocked"] is False


def test_check_single_id_ancestor_not_matched_when_only_child_searched(block_db):
    """Verificação jogador: busca só o par informado — não infere bloqueio pela linhagem."""
    register_blocked_dino_ids(
        block_db,
        ORDER,
        USER,
        {
            "ancestors": [
                {"dino_id1": 1, "dino_id2": 2, "side": "male", "generation": 1},
            ],
        },
    )
    block_db.commit()

    # Ancestral cadastrado — match exato.
    assert check_single_id_blocked(block_db, 1, 2)["blocked"] is True

    # Filho com outro par — NÃO bloqueado (ancestralidade não é consultada).
    child_result = check_single_id_blocked(block_db, 0xCCCCDDDD, 0xEEEEFFFF)
    assert child_result["ok"] is True
    assert child_result["blocked"] is False
    assert child_result["disclaimer"] == PLAYER_CHECK_DISCLAIMER

    # Mercado (com metadata + ancestrais) bloquearia o filho se o ancestral estivesse na cryo.
    meta_child = {
        "dino_identity": {
            "dino_id1": 0xCCCCDDDD,
            "dino_id2": 0xEEEEFFFF,
            "ancestors": [{"dino_id1": 1, "dino_id2": 2}],
        }
    }
    assert check_blocked_from_metadata(block_db, meta_child) == DINO_LAB_BLOCK_MESSAGE


def test_parse_dino_id_input_formats():
    assert parse_dino_id_input({"dino_id1": 0xAABBCCDD, "dino_id2": 0x11223344}) == (
        0xAABBCCDD,
        0x11223344,
    )
    assert parse_dino_id_input({"canonical_id": "AABBCCDD-11223344"}) == (
        0xAABBCCDD,
        0x11223344,
    )
    assert parse_dino_id_input({"input": "AABBCCDD11223344"}) == (0xAABBCCDD, 0x11223344)
    assert parse_dino_id_input({"input": "12345"}) is None


def test_player_dino_lab_block_check_endpoint(market_client):
    db = _app_module._SessionLocal()
    try:
        register_blocked_dino_ids(
            db,
            ORDER,
            USER,
            {
                "dino_id1": 0xAABBCCDD,
                "dino_id2": 0x11223344,
                "ancestors": [{"dino_id1": 1, "dino_id2": 2, "generation": 1}],
            },
        )
        db.commit()
    finally:
        db.close()

    with market_client.session_transaction() as sess:
        sess["steam_id"] = SELLER

    blocked = market_client.post(
        "/api/dino-lab-block/check",
        json={"canonical_id": "AABBCCDD-11223344"},
    )
    assert blocked.status_code == 200
    data = blocked.get_json()
    assert data["ok"] is True
    assert data["blocked"] is True
    assert data["order_id"] == ORDER
    assert data["disclaimer"] == PLAYER_CHECK_DISCLAIMER

    ancestor_only = market_client.post(
        "/api/dino-lab-block/check",
        json={"dino_id1": 1, "dino_id2": 2},
    )
    assert ancestor_only.status_code == 200
    assert ancestor_only.get_json()["blocked"] is True

    unrelated = market_client.post(
        "/api/dino-lab-block/check",
        json={"canonical_id": "DEADBEEF-CAFEBABE"},
    )
    assert unrelated.status_code == 200
    assert unrelated.get_json()["blocked"] is False
    assert unrelated.get_json()["disclaimer"] == PLAYER_CHECK_DISCLAIMER

    no_auth = _app_module.app.test_client()
    denied = no_auth.post("/api/dino-lab-block/check", json={"canonical_id": "AABBCCDD-11223344"})
    assert denied.status_code == 401


def test_admin_debug_endpoint(market_client, tmp_path, monkeypatch):
    settings_file = tmp_path / "settings_debug.json"
    settings_file.write_text(
        json.dumps({"custom_dino_enabled": True, "dino_lab_block_debug": True}),
        encoding="utf-8",
    )
    monkeypatch.setattr(_app_module, "_STATE_FILE", settings_file)
    monkeypatch.setattr(_app_module, "_ADMIN_FILE", tmp_path / "admin_steamids.json")
    (tmp_path / "admin_steamids.json").write_text(json.dumps([USER]), encoding="utf-8")

    db = _app_module._SessionLocal()
    try:
        register_blocked_dino_ids(
            db,
            ORDER,
            USER,
            {"dino_id1": 999, "dino_id2": 888, "ancestors": []},
        )
        db.commit()
    finally:
        db.close()

    with market_client.session_transaction() as sess:
        sess["steam_id"] = USER
    resp = market_client.get("/api/admin/dino-lab-block/debug?limit=5")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["ok"] is True
    assert data["debug_enabled"] is True
    assert data["stats"]["total_rows"] >= 1
    assert len(data["recent"]) >= 1


def test_delivered_route_registers_blocked_ids(market_client):
    """Integração HTTP: delivered com dino_records persiste bloqueio."""
    db = _app_module._SessionLocal()
    order_id = "cd_httpblock01"
    try:
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        db.execute(
            text(
                "INSERT INTO orders "
                "(order_id, steam_id, server_id, item_type, item_id, amount, points_spent, "
                "status, retry_count, contested, payload_json, created_at, updated_at) "
                "VALUES (:oid, :sid, 'default', :it, :iid, 1, 0, 'ENTREGANDO', 0, 0, '{}', :now, :now)"
            ),
            {
                "oid": order_id,
                "sid": USER,
                "it": ITEM_TYPE,
                "iid": order_id,
                "now": now,
            },
        )
        db.commit()
    finally:
        db.close()

    headers = {"X-API-Key": API_KEY, "Content-Type": "application/json"}
    resp = market_client.post(
        "/api/pending/custom-dino/delivered",
        headers=headers,
        json={
            "steam_id": USER,
            "order_ids": [order_id],
            "dino_records": [
                {
                    "order_id": order_id,
                    "dino_id1": 0x11112222,
                    "dino_id2": 0x33334444,
                    "ancestors": [],
                }
            ],
        },
    )
    assert resp.status_code == 200
    assert resp.get_json().get("ok") is True

    db = _app_module._SessionLocal()
    try:
        match = lookup_blocked_match(db, [(0x11112222, 0x33334444)])
        assert match is not None
        assert match["blocked"] is True
        assert match["order_id"] == order_id
    finally:
        db.close()
