"""Testes do mural de avisos / carrossel de cards da home."""
from __future__ import annotations

import io
import json

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

import app as _app_module
from app import app, _configure_database
from home_notice_service import (
    configure_home_cards,
    create_home_card,
    ensure_home_notice_schema,
    get_home_notice,
    list_home_cards,
    set_home_notice,
)

ADMIN_STEAM = "76561198000000001"
USER_STEAM = "76561198000000002"


@pytest.fixture()
def notice_db(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'notice.db'}", future=True)
    ensure_home_notice_schema(engine)
    configure_home_cards(uploads_dir=tmp_path / "card_uploads")
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
    uploads = tmp_path / "home_card_uploads"
    uploads.mkdir(parents=True, exist_ok=True)
    configure_home_cards(uploads_dir=uploads)
    monkeypatch.setattr(_app_module, "_HOME_CARD_UPLOADS_DIR", uploads)
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
        cards = conn.execute(text(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='home_cards'"
        )).fetchone()
    assert row is not None
    assert cards is not None


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

    cards = list_home_cards(notice_db, active_only=True)
    assert len(cards) == 1
    assert cards[0]["title"] == "Manutenção"
    assert cards[0]["has_image"] is False


def test_update_overwrites_singleton(notice_db):
    set_home_notice(notice_db, title="A", body="um")
    set_home_notice(notice_db, title="B", body="dois", updated_by_steam_id="1")
    n = get_home_notice(notice_db)
    assert n["title"] == "B"
    assert n["body"] == "dois"
    count = notice_db.execute(text("SELECT COUNT(*) FROM home_notice")).scalar()
    assert count == 1
    assert len(list_home_cards(notice_db)) == 1


def test_clear_notice(notice_db):
    set_home_notice(notice_db, title="X", body="Y")
    cleared = set_home_notice(notice_db, title="", body="")
    assert cleared["has_content"] is False
    assert list_home_cards(notice_db) == []


def test_migrate_legacy_notice_to_card(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'mig.db'}", future=True)
    with engine.begin() as conn:
        conn.execute(text(
            """
            CREATE TABLE home_notice (
              id INTEGER PRIMARY KEY NOT NULL,
              title VARCHAR(120) NOT NULL DEFAULT '',
              body TEXT NOT NULL DEFAULT '',
              updated_by_steam_id VARCHAR(32) NULL,
              updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        ))
        conn.execute(
            text(
                "INSERT INTO home_notice (id, title, body) VALUES (1, :t, :b)"
            ),
            {"t": "Legado", "b": "Só texto antigo"},
        )
    ensure_home_notice_schema(engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    try:
        cards = list_home_cards(db)
        assert len(cards) == 1
        assert cards[0]["title"] == "Legado"
        assert cards[0]["body"] == "Só texto antigo"
        assert cards[0]["image_url"] is None
    finally:
        db.close()


def test_card_crud(notice_db):
    card = create_home_card(
        notice_db,
        title="Evento",
        body="Fear Evolved",
        image_url="https://cdn.example/banner.jpg",
        link_url="https://arkland.gg",
        active=True,
        sort_order=2,
        updated_by_steam_id=ADMIN_STEAM,
    )
    assert card["id"]
    assert card["image_url"].endswith("banner.jpg")
    assert card["link_url"] == "https://arkland.gg"
    assert card["order"] == 2

    from home_notice_service import update_home_card, delete_home_card

    updated = update_home_card(notice_db, card["id"], title="Evento 2", active=False)
    assert updated["title"] == "Evento 2"
    assert updated["active"] is False
    assert list_home_cards(notice_db, active_only=True) == []
    delete_home_card(notice_db, card["id"])
    assert list_home_cards(notice_db) == []


def test_public_and_admin_routes(client):
    r = client.get("/api/public/home-notice")
    assert r.status_code == 200
    data = r.get_json()
    assert data["ok"] is True
    assert data["notice"]["has_content"] is False

    cards_pub = client.get("/api/public/home-cards")
    assert cards_pub.status_code == 200
    cards_data = cards_pub.get_json()
    assert cards_data["ok"] is True
    assert cards_data["cards"] == []
    assert cards_data["recommended_width"] == 1200
    assert cards_data["recommended_height"] == 675

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

    cards_after = client.get("/api/public/home-cards").get_json()["cards"]
    assert len(cards_after) == 1
    assert cards_after[0]["title"] == "Aviso"

    created = client.post(
        "/api/admin/home-cards",
        json={
            "title": "Banner",
            "body": "Nova season",
            "image_url": "https://cdn.example/s.jpg",
            "active": True,
            "order": 5,
        },
    )
    assert created.status_code == 201
    card_id = created.get_json()["card"]["id"]

    patched = client.patch(
        f"/api/admin/home-cards/{card_id}",
        json={"active": False},
    )
    assert patched.status_code == 200
    assert patched.get_json()["card"]["active"] is False

    active_only = client.get("/api/public/home-cards").get_json()["cards"]
    assert not any(c["id"] == card_id for c in active_only)

    home = client.get("/api/public/home")
    assert home.status_code == 200
    home_data = home.get_json()
    assert home_data.get("home_notice", {}).get("title") == "Aviso"
    assert isinstance(home_data.get("home_cards"), list)
    assert any(c.get("title") == "Aviso" for c in home_data["home_cards"])


def test_admin_upload_image(client):
    with client.session_transaction() as sess:
        sess["steam_id"] = ADMIN_STEAM

    png_bytes = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f"
        b"\x00\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    data = {
        "file": (io.BytesIO(png_bytes), "card.png", "image/png"),
    }
    up = client.post(
        "/api/admin/home-cards/upload",
        data=data,
        content_type="multipart/form-data",
    )
    assert up.status_code == 201
    payload = up.get_json()
    assert payload["ok"] is True
    assert payload["image_url"].startswith("/api/public/home-card-images/")
    filename = payload["filename"]
    img = client.get(f"/api/public/home-card-images/{filename}")
    assert img.status_code == 200


def test_admin_route_requires_auth(client):
    r = client.put("/api/admin/home-notice", json={"title": "x", "body": "y"})
    assert r.status_code in (401, 403)

    with client.session_transaction() as sess:
        sess["steam_id"] = USER_STEAM
    r2 = client.put("/api/admin/home-notice", json={"title": "x", "body": "y"})
    assert r2.status_code in (401, 403)

    r3 = client.post("/api/admin/home-cards", json={"title": "x"})
    assert r3.status_code in (401, 403)


def test_index_has_notice_ui():
    from pathlib import Path

    html = (Path(__file__).resolve().parents[1] / "static" / "index.html").read_text(
        encoding="utf-8"
    )
    assert "home-carousel" in html
    assert "_homeHeroCarouselHtml" in html
    assert "admin-home-notice" in html
    assert "1200" in html and "675" in html
    assert "1200 × 675" in html or "1200 × 675 px" in html
    assert "home-card-dims-banner" in html
    assert "home-card-dims-hint" in html
    assert "_checkHomeCardFileDims" in html
    assert "loadAdminHomeCards" in html
