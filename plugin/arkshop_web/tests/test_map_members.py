"""Testes — membros por mapa (staff) + player_data_id."""
from __future__ import annotations

import json
from pathlib import Path
import sys

import pytest
from flask import jsonify, request
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app as _app_module
from app import app
from map_members_service import (
    build_map_members_payload,
    get_member_detail,
    list_members_for_server,
)
from tribe_service import ensure_tribe_schema, record_presence

ADMIN_STEAM = "76561198000000001"
USER_STEAM = "76561198000000002"
USER_A = "76561198000000011"
USER_B = "76561198000000012"
SERVER_BR = "brighamia"
SERVER_ALPS = "alps"


@pytest.fixture()
def engine(tmp_path):
    path = tmp_path / "map_members.db"
    eng = create_engine(f"sqlite:///{path}", future=True)
    with eng.connect() as conn:
        conn.execute(text(
            "CREATE TABLE IF NOT EXISTS players "
            "(steam_id TEXT PRIMARY KEY, points INTEGER DEFAULT 0, kits TEXT DEFAULT '{}')"
        ))
        conn.execute(text(
            "CREATE TABLE IF NOT EXISTS market_listings "
            "(id INTEGER PRIMARY KEY AUTOINCREMENT, status TEXT, seller_steam_id TEXT, "
            "effective_price INTEGER, tribe_split_id INTEGER, split_snapshot TEXT)"
        ))
        conn.commit()
    ensure_tribe_schema(eng)
    return eng


@pytest.fixture()
def db(engine):
    Session = sessionmaker(bind=engine)
    s = Session()
    yield s
    s.close()


@pytest.fixture(autouse=True)
def _admin_env(tmp_path, monkeypatch):
    monkeypatch.setenv("ARKSHOP_WEB_SECRET", "test-secret")
    monkeypatch.setattr(_app_module, "_ADMIN_FILE", tmp_path / "admin_steamids.json")
    monkeypatch.setattr(_app_module, "_STATE_FILE", tmp_path / "settings.json")
    monkeypatch.setattr(_app_module, "_SERVERS_FILE", tmp_path / "servers.json")
    (tmp_path / "admin_steamids.json").write_text(json.dumps([ADMIN_STEAM]), encoding="utf-8")
    (tmp_path / "servers.json").write_text(
        json.dumps([
            {"server_id": SERVER_BR, "label": "Brighamia", "show_on_home": True},
            {"server_id": SERVER_ALPS, "label": "Alps", "show_on_home": True},
        ]),
        encoding="utf-8",
    )
    yield


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def _login(client, steam_id: str) -> None:
    with client.session_transaction() as sess:
        sess["steam_id"] = steam_id


def _seed_two_maps(db):
    record_presence(
        db,
        steam_id=USER_A,
        server_id=SERVER_BR,
        map_name="Brighamia",
        tribe_id=1001,
        tribe_name="ArkLand",
        is_owner=True,
        member_rank="Owner",
        members=[{
            "steam_id": USER_A,
            "player_data_id": 543086853,
            "character_name": "oCiano",
            "is_owner": True,
            "rank_name": "Owner",
        }],
    )
    record_presence(
        db,
        steam_id=USER_A,
        server_id=SERVER_ALPS,
        map_name="Alps",
        tribe_id=2002,
        tribe_name="ArkLand FOB",
        is_owner=True,
        member_rank="Owner",
        members=[{
            "steam_id": USER_A,
            "player_data_id": 543086853,
            "character_name": "oCiano",
            "is_owner": True,
            "rank_name": "Owner",
        }],
    )
    record_presence(
        db,
        steam_id=USER_B,
        server_id=SERVER_BR,
        map_name="Brighamia",
        tribe_id=1001,
        tribe_name="ArkLand",
        is_owner=False,
        member_rank="Member",
        members=[{
            "steam_id": USER_B,
            "player_data_id": 111,
            "character_name": "Bob",
            "is_owner": False,
            "rank_name": "Member",
        }],
    )


def test_schema_has_player_data_id(engine):
    with engine.connect() as conn:
        cols = [r[1] for r in conn.execute(text("PRAGMA table_info(tribe_members)")).fetchall()]
    assert "player_data_id" in cols


def test_upsert_persists_player_data_id(db):
    _seed_two_maps(db)
    row = db.execute(
        text("""
            SELECT player_data_id, character_name FROM tribe_members
            WHERE steam_id = :sid AND server_id = :svid
        """),
        {"sid": USER_A, "svid": SERVER_BR},
    ).fetchone()
    assert row is not None
    assert int(row[0]) == 543086853
    assert row[1] == "oCiano"


def test_list_members_by_map(db):
    _seed_two_maps(db)
    block = list_members_for_server(db, server_id=SERVER_BR)
    assert block["total"] >= 2
    steam_ids = {i["steam_id"] for i in block["items"]}
    assert USER_A in steam_ids
    assert USER_B in steam_ids
    a = next(i for i in block["items"] if i["steam_id"] == USER_A)
    assert a["player_data_id"] == 543086853
    assert a["tribe_id"] == 1001


def test_detail_associated_maps(db):
    _seed_two_maps(db)
    labels = {SERVER_BR: "Brighamia", SERVER_ALPS: "Alps"}
    detail = get_member_detail(
        db, server_id=SERVER_BR, steam_id=USER_A, map_labels=labels,
    )
    assert detail is not None
    assert detail["player_data_id"] == 543086853
    assert detail["tribe_id"] == 1001
    assert detail["tribe_name"] == "ArkLand"
    assert detail["map_label"] == "Brighamia"
    assoc_ids = {m["server_id"] for m in detail["associated_maps"]}
    assert SERVER_ALPS in assoc_ids
    assert SERVER_BR not in assoc_ids
    alps = next(m for m in detail["associated_maps"] if m["server_id"] == SERVER_ALPS)
    assert alps["label"] == "Alps"
    assert alps["tribe_id"] == 2002


def test_detail_null_player_data_id_ok(db):
    db.execute(text("""
        INSERT INTO tribe_members
          (server_id, tribe_id, tribe_name, steam_id, character_name, is_owner,
           rank_name, player_data_id, joined_at, last_seen_at, updated_at)
        VALUES (:svid, 9, 'X', :sid, 'NoId', 0, 'M', NULL,
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
    """), {"svid": SERVER_BR, "sid": USER_B})
    db.commit()
    detail = get_member_detail(db, server_id=SERVER_BR, steam_id=USER_B, map_labels={})
    assert detail is not None
    assert detail["player_data_id"] is None


def test_build_payload_all_servers(db):
    _seed_two_maps(db)
    servers = [
        {"server_id": SERVER_BR, "label": "Brighamia"},
        {"server_id": SERVER_ALPS, "label": "Alps"},
    ]
    payload = build_map_members_payload(db, servers=servers)
    assert payload["ok"] is True
    assert len(payload["maps"]) == 2
    by_id = {m["server_id"]: m for m in payload["maps"]}
    assert by_id[SERVER_BR]["label"] == "Brighamia"
    assert by_id[SERVER_BR]["total"] >= 2
    assert by_id[SERVER_ALPS]["total"] >= 1


def test_api_requires_admin(client):
    r = client.get("/api/admin/map-members")
    assert r.status_code in (401, 403)
    _login(client, USER_STEAM)
    r2 = client.get("/api/admin/map-members")
    assert r2.status_code == 403


def test_api_admin_list_and_detail(client, db, monkeypatch, engine):
    _seed_two_maps(db)
    Session = sessionmaker(bind=engine)

    def admin_list():
        sid = _app_module._steam_id_from_session() or ""
        if not _app_module._is_admin_steamid(sid):
            return jsonify({"ok": False, "error": "Admin only"}), 403
        s = Session()
        try:
            payload = build_map_members_payload(
                s,
                servers=_app_module._load_servers(),
                server_id=str(request.args.get("server_id") or "").strip() or None,
                limit=int(request.args.get("limit") or 200),
                offset=int(request.args.get("offset") or 0),
            )
            return jsonify(payload)
        finally:
            s.close()

    def admin_detail(server_id, steam_id):
        sid = _app_module._steam_id_from_session() or ""
        if not _app_module._is_admin_steamid(sid):
            return jsonify({"ok": False, "error": "Admin only"}), 403
        s = Session()
        try:
            labels = {
                str(x.get("server_id")): str(x.get("label") or x.get("server_id"))
                for x in _app_module._load_servers()
            }
            detail = get_member_detail(
                s, server_id=server_id, steam_id=steam_id, map_labels=labels,
            )
            if not detail:
                return jsonify({"ok": False, "error": "not found"}), 404
            return jsonify({"ok": True, **detail})
        finally:
            s.close()

    monkeypatch.setitem(app.view_functions, "admin_map_members_list", admin_list)
    monkeypatch.setitem(app.view_functions, "admin_map_member_detail", admin_detail)

    _login(client, ADMIN_STEAM)
    r = client.get("/api/admin/map-members")
    assert r.status_code == 200
    data = r.get_json()
    assert data["ok"] is True
    assert len(data["maps"]) == 2

    r2 = client.get(f"/api/admin/map-members/{SERVER_BR}/{USER_A}")
    assert r2.status_code == 200
    d2 = r2.get_json()
    assert d2["ok"] is True
    assert d2["player_data_id"] == 543086853
    assert any(m["server_id"] == SERVER_ALPS for m in d2["associated_maps"])
