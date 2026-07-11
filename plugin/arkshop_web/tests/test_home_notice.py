"""Testes do mural de avisos da home."""
from __future__ import annotations

import json

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

import app as _app_module
from app import app, _configure_database
from home_notice_service import ensure_home_notice_schema, get_home_notice, set_home_notice

ADMIN_STEAM = "76561198000000001"
USER_STEAM = "76561198000000002"


@pytest.fixture()
def notice_db(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'notice.db'}", future=True)
    ensure_home_notice_schema(engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(autouse=True)
def _admin_env(tmp_path, monkeypatch):
    monkeypatch.setenv("ARKSHOP_WEB_SECRET", "test-secret")
    monkeypatch.setattr(_app_module, "_ADMIN_FILE", tmp_path / "admin_steamids.json")
    monkeypatch.setattr(_app_module, "_STATE_FILE", tmp_path / "settings.json")
    (tmp_path / "admin_steamids.json").write_text(json.dumps([ADMIN_STEAM]), encoding="utf-8")
    (tmp_path / "settings.json").write_text("{}", encoding="utf-8")
    yield


@pytest.fixture
def client(tmp_path, monkeypatch):
    catalog = tmp_path / "config.json"
    catalog.write_text(json.dumps({"Settings": {}}), encoding="utf-8")
    (tmp_path / "settings.json").write_text(
        json.dumps({"config_path": str(catalog)}),
        encoding="utf-8",
    )
    servers_file = tmp_path / "servers.json"
    servers_file.write_text("[]", encoding="utf-8")
    monkeypatch.setattr(_app_module, "_SERVERS_FILE", servers_file)
    monkeypatch.setattr(_app_module, "_ACTIVE_DATABASE_URL", "")
    db_url = f"sqlite:///{tmp_path / 'route_notice.db'}"
    _configure_database(db_url)
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c
    _configure_database("")


def test_ensure_schema_idempotent(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'n2.db'}", future=True)
    ensure_home_notice_schema(engine)
    ensure_home_notice_schema(engine)
    with engine.connect() as conn:
        row = conn.execute(text(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='home_notice'"
        )).fetchone()
    assert row is not None


def test_get_empty_notice(notice_db):
    n = get_home_notice(notice_db)
    assert n["has_content"] is False
    assert n["title"] == ""
    assert n["body"] == ""


def test_set_and_get_notice(notice_db):
    saved = set_home_notice(
        notice_db,
        title="Manutenção",
        body="Cluster offline às 22h.\n**Obrigado**",
        updated_by_steam_id=ADMIN_STEAM,
    )
    assert saved["has_content"] is True
    assert saved["title"] == "Manutenção"
    assert "22h" in saved["body"]
    assert saved["updated_by_steam_id"] == ADMIN_STEAM
    assert saved["updated_at"]

    again = get_home_notice(notice_db)
    assert again["title"] == "Manutenção"
    assert again["body"] == saved["body"]


def test_update_overwrites_singleton(notice_db):
    set_home_notice(notice_db, title="A", body="um")
    set_home_notice(notice_db, title="B", body="dois", updated_by_steam_id="1")
    n = get_home_notice(notice_db)
    assert n["title"] == "B"
    assert n["body"] == "dois"
    count = notice_db.execute(text("SELECT COUNT(*) FROM home_notice")).scalar()
    assert count == 1


def test_clear_notice(notice_db):
    set_home_notice(notice_db, title="X", body="Y")
    cleared = set_home_notice(notice_db, title="", body="")
    assert cleared["has_content"] is False


def test_public_and_admin_routes(client):
    r = client.get("/api/public/home-notice")
    assert r.status_code == 200
    data = r.get_json()
    assert data["ok"] is True
    assert data["notice"]["has_content"] is False

    with client.session_transaction() as sess:
        sess["steam_id"] = ADMIN_STEAM

    put = client.put(
        "/api/admin/home-notice",
        json={"title": "Aviso", "body": "Linha 1\nLinha 2"},
    )
    assert put.status_code == 200
    put_data = put.get_json()
    assert put_data["ok"] is True
    assert put_data["notice"]["title"] == "Aviso"

    r2 = client.get("/api/public/home-notice")
    assert r2.get_json()["notice"]["body"] == "Linha 1\nLinha 2"

    get_admin = client.get("/api/admin/home-notice")
    assert get_admin.status_code == 200
    assert get_admin.get_json()["notice"]["title"] == "Aviso"

    home = client.get("/api/public/home")
    assert home.status_code == 200
    home_data = home.get_json()
    assert home_data.get("home_notice", {}).get("title") == "Aviso"


def test_admin_route_requires_auth(client):
    r = client.put("/api/admin/home-notice", json={"title": "x", "body": "y"})
    assert r.status_code in (401, 403)

    with client.session_transaction() as sess:
        sess["steam_id"] = USER_STEAM
    r2 = client.put("/api/admin/home-notice", json={"title": "x", "body": "y"})
    assert r2.status_code in (401, 403)


def test_index_has_notice_ui():
    from pathlib import Path

    html = (Path(__file__).resolve().parents[1] / "static" / "index.html").read_text(
        encoding="utf-8"
    )
    assert "home-hero__notice" in html
    assert "_homeHeroNoticeHtml" in html
    assert "admin-home-notice" in html
    assert "Quadro de avisos" in html
