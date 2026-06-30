"""Testes do sistema de tickets (1.9.153)."""
from __future__ import annotations

import json
import uuid

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

import app as _app_module
from app import Order, app
from ticket_service import (
    TICKET_CATEGORIES,
    add_ticket_reply,
    attend_ticket,
    close_ticket,
    create_ticket,
    ensure_ticket_schema,
    get_ticket_detail,
    get_ticket_history,
    list_tickets_admin,
    list_tickets_for_player,
    request_player_close,
    save_discord_link,
    ticket_meta,
    ticket_permissions,
    update_ticket_priority,
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


def _seed_order(db, *, steam_id: str = USER_STEAM) -> str:
    bind = db.get_bind()
    Order.__table__.create(bind, checkfirst=True)
    oid = str(uuid.uuid4())
    db.add(
        Order(
            order_id=oid,
            steam_id=steam_id,
            server_id="default",
            item_type="shop",
            item_id="test_kit",
            amount=1,
            points_spent=100,
            status="PENDENTE",
        )
    )
    db.commit()
    return oid


def test_ticket_meta():
    meta = ticket_meta()
    assert "categories" in meta
    assert "priorities" in meta
    assert "statuses" in meta
    assert any(c["id"] == "suporte" for c in meta["categories"])


def test_create_and_list_ticket(ticket_db):
    created = create_ticket(
        ticket_db,
        steam_id=USER_STEAM,
        player_name="JogadorTeste",
        subject="Problema no resgate",
        body="Não recebi meu kit.",
        category="resgate",
        priority="urgente",
        links=["https://example.com/prova"],
    )
    assert created["ok"] is True
    assert created["ticket"]["subject"] == "Problema no resgate"
    assert created["ticket"]["player_name"] == "JogadorTeste"
    assert created["ticket"]["status"] == "AGUARDANDO_SUPORTE"
    assert created["ticket"]["priority"] == "urgente"
    assert created["ticket"]["category_label"] == "Resgate / entrega"

    items, total = list_tickets_for_player(ticket_db, USER_STEAM, status="abertos")
    assert total == 1
    assert items[0]["id"] == created["ticket"]["id"]

    items_open, _ = list_tickets_for_player(ticket_db, USER_STEAM, status="open")
    assert len(items_open) == 1

    detail = get_ticket_detail(ticket_db, items[0]["id"], viewer_steam_id=USER_STEAM)
    assert detail is not None
    assert len(detail["messages"]) == 1
    assert detail["messages"][0]["links"] == ["https://example.com/prova"]
    assert len(detail["history"]) >= 1
    assert detail["history"][0]["event_type"] == "created"
    assert detail["permissions"]["can_player_reply"] is True


def test_player_visibility_after_admin_attend(ticket_db):
    """Ticket permanece na aba Abertos do jogador após admin atender."""
    created = create_ticket(
        ticket_db,
        steam_id=USER_STEAM,
        player_name="Nick",
        subject="Ajuda",
        body="Preciso de suporte",
        category="suporte",
    )
    tid = created["ticket"]["id"]

    attended = attend_ticket(
        ticket_db, tid, admin_steam_id=ADMIN_STEAM, admin_name="Admin"
    )
    assert attended["ok"] is True
    assert attended["ticket"]["status"] == "AGUARDANDO_SUPORTE"

    open_items, open_total = list_tickets_for_player(ticket_db, USER_STEAM, status="abertos")
    assert open_total == 1
    assert open_items[0]["status"] == "AGUARDANDO_SUPORTE"

    closed_items, closed_total = list_tickets_for_player(ticket_db, USER_STEAM, status="encerrados")
    assert closed_total == 0

    detail = get_ticket_detail(ticket_db, tid, viewer_steam_id=USER_STEAM)
    assert detail["permissions"]["can_player_reply"] is True


def test_create_with_order_id(ticket_db):
    oid = _seed_order(ticket_db)
    created = create_ticket(
        ticket_db,
        steam_id=USER_STEAM,
        player_name="Nick",
        subject="Disputa pedido",
        body="Item não chegou",
        category="pagamento",
        order_id=oid,
    )
    assert created["ok"] is True
    assert created["ticket"]["order_id"] == oid

    detail = get_ticket_detail(
        ticket_db, created["ticket"]["id"], viewer_steam_id=USER_STEAM, include_order=True
    )
    assert detail["order"]["order_id"] == oid
    assert detail["order"]["item_id"] == "test_kit"

    bad = create_ticket(
        ticket_db,
        steam_id=USER_STEAM,
        player_name="Nick",
        subject="Pedido alheio",
        body="Teste",
        order_id=str(uuid.uuid4()),
    )
    assert bad["ok"] is False


def test_admin_reply_status_history_and_close(ticket_db):
    created = create_ticket(
        ticket_db,
        steam_id=USER_STEAM,
        player_name="Nick",
        subject="Ajuda",
        body="Preciso de suporte",
        category="suporte",
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

    detail = get_ticket_detail(ticket_db, tid, is_admin=True)
    assert detail["ticket"]["status"] == "AGUARDANDO_JOGADOR"

    waiting = update_ticket_status(
        ticket_db,
        tid,
        status="AGUARDANDO_JOGADOR",
        admin_steam_id=ADMIN_STEAM,
        admin_name="Admin",
    )
    assert waiting["ok"] is True
    assert waiting["ticket"]["status"] == "AGUARDANDO_JOGADOR"

    open_items, _ = list_tickets_for_player(ticket_db, USER_STEAM, status="abertos")
    assert any(t["id"] == tid for t in open_items)

    pri = update_ticket_priority(
        ticket_db,
        tid,
        priority="urgente",
        admin_steam_id=ADMIN_STEAM,
        admin_name="Admin",
    )
    assert pri["ok"] is True
    assert pri["ticket"]["priority"] == "urgente"

    closed = close_ticket(
        ticket_db, tid, admin_steam_id=ADMIN_STEAM, admin_name="Admin"
    )
    assert closed["ok"] is True
    assert closed["ticket"]["status"] == "ENCERRADO"

    open_after, open_n = list_tickets_for_player(ticket_db, USER_STEAM, status="abertos")
    assert open_n == 0
    closed_after, closed_n = list_tickets_for_player(ticket_db, USER_STEAM, status="encerrados")
    assert closed_n == 1
    assert closed_after[0]["id"] == tid

    hist = get_ticket_history(ticket_db, tid, is_admin=True)
    assert hist is not None
    events = [h["event_type"] for h in hist["history"]]
    assert "created" in events
    assert "status_changed" in events
    assert "priority_changed" in events
    assert "reply_admin" in events
    assert "closed" in events

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

    admin_items, admin_total = list_tickets_admin(ticket_db, status="ENCERRADO")
    assert admin_total >= 1


def test_player_request_close(ticket_db):
    created = create_ticket(
        ticket_db,
        steam_id=USER_STEAM,
        player_name="Nick",
        subject="Resolvido",
        body="Problema",
        category="suporte",
    )
    tid = created["ticket"]["id"]

    attend_ticket(ticket_db, tid, admin_steam_id=ADMIN_STEAM, admin_name="Admin")

    req = request_player_close(
        ticket_db, tid, steam_id=USER_STEAM, player_name="Nick"
    )
    assert req["ok"] is True
    assert req["ticket"]["status"] == "AGUARDANDO_SUPORTE"

    open_items, _ = list_tickets_for_player(ticket_db, USER_STEAM, status="abertos")
    assert any(t["id"] == tid for t in open_items)

    hist = get_ticket_history(ticket_db, tid, viewer_steam_id=USER_STEAM)
    assert any(h["event_type"] == "close_requested" for h in hist["history"])


def test_player_reply_from_aguardando(ticket_db):
    created = create_ticket(
        ticket_db,
        steam_id=USER_STEAM,
        player_name="Nick",
        subject="Dúvida",
        body="Ajuda",
        category="suporte",
    )
    tid = created["ticket"]["id"]
    update_ticket_status(
        ticket_db,
        tid,
        status="AGUARDANDO_JOGADOR",
        admin_steam_id=ADMIN_STEAM,
        admin_name="Admin",
    )

    reply = add_ticket_reply(
        ticket_db,
        tid,
        author_type="player",
        author_steam_id=USER_STEAM,
        author_name="Nick",
        body="Ainda tenho dúvida",
        viewer_steam_id=USER_STEAM,
    )
    assert reply["ok"] is True

    detail = get_ticket_detail(ticket_db, tid, viewer_steam_id=USER_STEAM)
    assert detail["ticket"]["status"] == "AGUARDANDO_SUPORTE"


def test_ticket_permissions():
    assert ticket_permissions("AGUARDANDO_SUPORTE")["can_player_reply"] is True
    assert ticket_permissions("ABERTO")["can_player_reply"] is True
    assert ticket_permissions("EM_ANALISE")["can_player_reply"] is True
    assert ticket_permissions("AGUARDANDO_JOGADOR")["can_player_reply"] is True
    assert ticket_permissions("ENCERRADO")["can_player_reply"] is False
    assert ticket_permissions("ENCERRADO")["is_closed"] is True


def test_admin_filters(ticket_db):
    create_ticket(
        ticket_db,
        steam_id=USER_STEAM,
        player_name="A",
        subject="Bug mapa",
        body="Erro",
        category="bug",
        priority="baixa",
    )
    create_ticket(
        ticket_db,
        steam_id=USER_STEAM,
        player_name="B",
        subject="Doação",
        body="Pix",
        category="doacao",
        priority="urgente",
    )
    bugs, n = list_tickets_admin(ticket_db, category="bug")
    assert n == 1
    assert bugs[0]["category"] == "bug"

    urgent, n2 = list_tickets_admin(ticket_db, priority="urgente")
    assert n2 == 1
    assert urgent[0]["priority"] == "urgente"


def test_legacy_status_migration(ticket_db):
    ticket_db.execute(
        text(
            "INSERT INTO support_tickets (steam_id, player_name, subject, category, status, priority) "
            "VALUES (:sid, 'Legado', 'Old', 'geral', 'OPEN', 'normal')"
        ),
        {"sid": USER_STEAM},
    )
    ticket_db.commit()
    engine = ticket_db.get_bind()
    ensure_ticket_schema(engine)
    row = ticket_db.execute(
        text("SELECT status FROM support_tickets WHERE subject = 'Old'")
    ).fetchone()
    assert row[0] == "AGUARDANDO_SUPORTE"


def test_discord_link_manual(ticket_db):
    link = save_discord_link(
        ticket_db,
        steam_id=USER_STEAM,
        discord_user_id="123456789012345678",
        discord_username="player#0001",
    )
    assert link["discord_username"] == "player#0001"


def test_invalid_category_normalized(ticket_db):
    created = create_ticket(
        ticket_db,
        steam_id=USER_STEAM,
        player_name="X",
        subject="Teste",
        body="Corpo",
        category="invalida_xyz",
    )
    assert created["ok"] is True
    assert created["ticket"]["category"] == "geral"
    assert "geral" in TICKET_CATEGORIES


def test_tickets_meta_endpoint(client):
    r = client.get("/api/tickets/meta")
    assert r.status_code == 200
    data = r.get_json()
    assert data["ok"] is True
    assert len(data["statuses"]) == 3


def test_admin_list_includes_closed_by_default(ticket_db):
    """Admin sem filtro de status vê tickets abertos e encerrados."""
    created = create_ticket(
        ticket_db,
        steam_id=USER_STEAM,
        player_name="Nick",
        subject="Aberto",
        body="Teste",
        category="suporte",
    )
    tid = created["ticket"]["id"]
    close_ticket(ticket_db, tid, admin_steam_id=ADMIN_STEAM, admin_name="Admin")

    create_ticket(
        ticket_db,
        steam_id=USER_STEAM,
        player_name="Nick",
        subject="Ainda aberto",
        body="Teste",
        category="suporte",
    )

    all_items, all_total = list_tickets_admin(ticket_db)
    assert all_total >= 2
    statuses = {t["status"] for t in all_items}
    assert "ENCERRADO" in statuses
    assert "AGUARDANDO_SUPORTE" in statuses

    open_items, open_total = list_tickets_admin(ticket_db, status="open")
    assert open_total == 1
    assert all(t["status"] != "ENCERRADO" for t in open_items)


def test_admin_tickets_list_requires_admin(client, monkeypatch):
    _login(client, USER_STEAM)
    monkeypatch.setattr(_app_module, "_db_ready", lambda: True)
    r = client.get("/api/admin/tickets")
    assert r.status_code in (401, 403)
