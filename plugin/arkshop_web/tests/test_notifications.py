"""Testes de notificações in-app."""
from __future__ import annotations

import json

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app as _app_module
from app import UserNotification, app
from notification_service import (
    create_notification,
    ensure_notification_schema,
    list_notifications,
    mark_all_read,
    mark_read,
    unread_count,
)
from ticket_service import add_ticket_reply, attend_ticket, create_ticket, ensure_ticket_schema

ADMIN_STEAM = "76561198000000001"
USER_STEAM = "76561198000000002"


@pytest.fixture()
def notif_db(tmp_path):
    path = tmp_path / "notif.db"
    engine = create_engine(f"sqlite:///{path}", future=True)
    ensure_notification_schema(engine)
    ensure_ticket_schema(engine)
    UserNotification.__table__.create(engine, checkfirst=True)
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
    yield


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def _login(client, steam_id: str) -> None:
    with client.session_transaction() as sess:
        sess["steam_id"] = steam_id


def test_create_and_list_notifications(notif_db):
    create_notification(
        notif_db,
        steam_id=USER_STEAM,
        type="ticket_reply",
        title="Nova resposta",
        body="Suporte respondeu seu ticket.",
        link_type="ticket",
        link_id="42",
    )
    notif_db.commit()

    items, total = list_notifications(notif_db, USER_STEAM)
    assert total == 1
    assert items[0]["title"] == "Nova resposta"
    assert items[0]["read"] is False
    assert items[0]["link_type"] == "ticket"
    assert unread_count(notif_db, USER_STEAM) == 1


def test_mark_read_and_mark_all(notif_db):
    for i in range(3):
        create_notification(
            notif_db,
            steam_id=USER_STEAM,
            title=f"N{i}",
            body="x",
        )
    notif_db.commit()
    items, _ = list_notifications(notif_db, USER_STEAM)
    rid = items[0]["id"]

    result = mark_read(notif_db, rid, steam_id=USER_STEAM)
    assert result["ok"] is True
    assert result["notification"]["read"] is True
    assert unread_count(notif_db, USER_STEAM) == 2

    all_res = mark_all_read(notif_db, steam_id=USER_STEAM)
    assert all_res["ok"] is True
    assert all_res["updated"] == 2
    assert unread_count(notif_db, USER_STEAM) == 0


def test_admin_reply_creates_player_notification(notif_db, monkeypatch):
    monkeypatch.setattr("ticket_notify.notify_ticket_discord", lambda *a, **k: False)

    created = create_ticket(
        notif_db,
        steam_id=USER_STEAM,
        player_name="Jogador",
        subject="Ajuda",
        body="Preciso de suporte",
    )
    tid = created["ticket"]["id"]

    add_ticket_reply(
        notif_db,
        tid,
        author_type="admin",
        author_steam_id=ADMIN_STEAM,
        author_name="Suporte",
        body="Olá, estamos verificando.",
        is_admin=True,
    )

    items, total = list_notifications(notif_db, USER_STEAM, unread_only=True)
    assert total >= 1
    assert any(
        "resposta" in (n["title"] or "").lower() or "status" in (n["title"] or "").lower()
        for n in items
    )


def test_support_team_notified_on_status_change(notif_db, tmp_path, monkeypatch):
    monkeypatch.setattr("ticket_notify.notify_ticket_discord", lambda *a, **k: False)
    monkeypatch.setattr(_app_module, "_SUPPORT_FILE", tmp_path / "support_steamids.json")
    (tmp_path / "support_steamids.json").write_text(
        json.dumps(["76561198000000099"]), encoding="utf-8"
    )
    _app_module._invalidate_support_steamids_cache()

    created = create_ticket(
        notif_db,
        steam_id=USER_STEAM,
        player_name="Jogador",
        subject="Ajuda",
        body="Preciso de suporte",
    )
    tid = created["ticket"]["id"]

    support_items, support_total = list_notifications(
        notif_db, "76561198000000099", unread_only=True
    )
    assert support_total >= 1
    assert any("novo ticket" in (n["title"] or "").lower() for n in support_items)

    add_ticket_reply(
        notif_db,
        tid,
        author_type="admin",
        author_steam_id=ADMIN_STEAM,
        author_name="Suporte",
        body="Olá, estamos verificando.",
        is_admin=True,
    )

    player_items, player_total = list_notifications(notif_db, USER_STEAM, unread_only=True)
    assert player_total >= 1
    assert any("status" in (n["title"] or "").lower() for n in player_items)

    support_items2, _ = list_notifications(notif_db, "76561198000000099", unread_only=True)
    assert any("status" in (n["title"] or "").lower() for n in support_items2)


def test_notifications_api_requires_login(client):
    r = client.get("/api/notifications")
    assert r.status_code in (401, 403)

    r2 = client.get("/api/notifications/unread-count")
    assert r2.status_code in (401, 403)


def test_notifications_read_routes_have_generous_rate_limits():
    """GET de notificações não deve herdar o default global (50/h) do limiter."""
    from flask import Flask

    from notification_routes import register_notification_routes

    limits: list[str] = []

    class _FakeLimiter:
        def limit(self, rule: str, **kwargs):
            limits.append(rule)

            def deco(fn):
                return fn

            return deco

    mini = Flask(__name__)
    register_notification_routes(
        mini,
        db_ready=lambda: True,
        session_factory=lambda: None,
        login_required=lambda f: f,
        steam_id_from_session=lambda: USER_STEAM,
        limiter=_FakeLimiter(),
    )
    assert any("300 per hour" in x for x in limits)
    assert any("600 per hour" in x for x in limits)
