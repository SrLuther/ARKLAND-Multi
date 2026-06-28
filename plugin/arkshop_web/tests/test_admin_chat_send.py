"""Envio de mensagens do painel admin para o chat cluster."""
from __future__ import annotations

import json

import pytest

import app as _app_module
from app import app
from cross_chat_service import SITE_CHAT_SOURCE, poll_messages, publish_message

ADMIN_STEAM = "76561198000000001"
USER_STEAM = "76561198000000002"


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


def test_publish_site_message(db_session):
    r = publish_message(
        db_session,
        source_server=SITE_CHAT_SOURCE,
        steam_id="",
        player_name="Admin Site",
        message="aviso do site",
        skip_mute=True,
    )
    assert r["ok"] is True
    msgs = poll_messages(db_session, server_id="Island", since_id=0)
    assert len(msgs) == 1
    assert msgs[0]["source_server"] == SITE_CHAT_SOURCE
    assert msgs[0]["message"] == "aviso do site"


def test_admin_chat_send_endpoint(client, monkeypatch):
    _login(client, ADMIN_STEAM)
    monkeypatch.setattr(_app_module, "_db_ready", lambda: True)

    captured: dict = {}

    def _fake_publish(db, **kwargs):
        captured.update(kwargs)
        return {"ok": True, "id": 42}

    monkeypatch.setattr("cross_chat_routes.publish_message", _fake_publish)

    r = client.post(
        "/api/admin/chat/send",
        json={"message": "ola cluster"},
    )
    assert r.status_code == 200
    assert r.get_json()["ok"] is True
    assert captured["source_server"] == SITE_CHAT_SOURCE
    assert captured["message"] == "ola cluster"
    assert captured.get("skip_mute") is True


def test_admin_chat_send_requires_admin(client, monkeypatch):
    _login(client, USER_STEAM)
    monkeypatch.setattr(_app_module, "_db_ready", lambda: True)
    r = client.post("/api/admin/chat/send", json={"message": "x"})
    assert r.status_code in (401, 403)
