"""Testes do sistema de tickets (MVP 1.9.149)."""
from __future__ import annotations

import json

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app as _app_module
from app import app
from ticket_service import (
    add_ticket_reply,
    create_ticket,
    ensure_ticket_schema,
    get_ticket_detail,
    list_tickets_admin,
    list_tickets_for_player,
    save_discord_link,
    update_ticket_status,
)

ADMIN_STEAM = "76561198000000001"
USER_STEAM = "76561198000000002"


@pytest.fixture()
def ticket_db(tmp_path):
    path = tmp_path / "tickets.db"
    engine = create_engine(f"sqlite:///{path}", future=True)
    ensure_ticket_schema(engine)
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


def test_create_and_list_ticket(ticket_db):
    created = create_ticket(
        ticket_db,
        steam_id=USER_STEAM,
        player_name="JogadorTeste",
        subject="Problema no resgate",
        body="Não recebi meu kit.",
        category="resgate",
        links=["https://example.com/prova"],
    )
    assert created["ok"] is True
    assert created["ticket"]["subject"] == "Problema no resgate"
    assert created["ticket"]["player_name"] == "JogadorTeste"

    items, total = list_tickets_for_player(ticket_db, USER_STEAM, status="open")
    assert total == 1
    assert items[0]["id"] == created["ticket"]["id"]

    detail = get_ticket_detail(ticket_db, items[0]["id"], viewer_steam_id=USER_STEAM)
    assert detail is not None
    assert len(detail["messages"]) == 1
    assert detail["messages"][0]["links"] == ["https://example.com/prova"]


def test_admin_reply_and_close(ticket_db):
    created = create_ticket(
        ticket_db,
        steam_id=USER_STEAM,
        player_name="Nick",
        subject="Ajuda",
        body="Preciso de suporte",
    )
    tid = created["ticket"]["id"]

    reply = add_ticket_reply(
        ticket_db,
        tid,
        author_type="admin",
        author_steam_id=ADMIN_STEAM,
        author_name="Suporte",
        body="Olá, estamos verificando.",
        is_admin=True,
    )
    assert reply["ok"] is True

    closed = update_ticket_status(ticket_db, tid, status="CLOSED", admin_steam_id=ADMIN_STEAM)
    assert closed["ok"] is True
    assert closed["ticket"]["status"] == "CLOSED"

    blocked = add_ticket_reply(
        ticket_db,
        tid,
        author_type="player",
        author_steam_id=USER_STEAM,
        author_name="Nick",
        body="Mais uma dúvida",
        viewer_steam_id=USER_STEAM,
    )
    assert blocked["ok"] is False

    admin_items, admin_total = list_tickets_admin(ticket_db, status="CLOSED")
    assert admin_total >= 1


def test_discord_link_manual(ticket_db):
    link = save_discord_link(
        ticket_db,
        steam_id=USER_STEAM,
        discord_user_id="123456789012345678",
        discord_username="player#0001",
    )
    assert link["discord_username"] == "player#0001"


def test_admin_tickets_list_requires_admin(client, monkeypatch):
    _login(client, USER_STEAM)
    monkeypatch.setattr(_app_module, "_db_ready", lambda: True)
    r = client.get("/api/admin/tickets")
    assert r.status_code in (401, 403)
