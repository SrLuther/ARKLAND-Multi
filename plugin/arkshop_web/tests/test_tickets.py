"""Testes do sistema de tickets (1.9.153)."""
from __future__ import annotations

import json
import uuid
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

import app as _app_module
from app import Order, StoreUser, SupportTicketDiscordLink, app
from ticket_service import (
    TICKET_CATEGORIES,
    add_ticket_reply,
    admin_unlink_discord,
    admin_credit_discord_link_bonus,
    attend_ticket,
    close_ticket,
    confirm_discord_link_code_for_discord_user,
    create_ticket,
    ensure_ticket_schema,
    generate_discord_link_code,
    get_discord_link,
    get_ticket_detail,
    get_ticket_history,
    list_discord_link_admin_audit,
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
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE players (steam_id TEXT PRIMARY KEY, points INTEGER NOT NULL DEFAULT 0, kits TEXT NOT NULL DEFAULT '{}')"))
    StoreUser.__table__.create(engine, checkfirst=True)
    from amber_ledger import ensure_amber_schema
    ensure_amber_schema(engine, run_backfill=False)
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


def test_translation_route_validates_without_touching_ticket_creation(client):
    _login(client, USER_STEAM)
    assert client.post("/api/translate", json={"text": "", "target": "pt"}).status_code == 400
    assert client.post("/api/translate", json={"text": "Hello", "target": "fr"}).status_code == 400
    assert client.post("/api/translate", json={"text": "x" * 5001, "target": "pt"}).status_code == 413


def test_translation_admin_status_and_test_are_admin_only_and_never_return_key(client, ticket_db, monkeypatch):
    import translation_service
    from sqlalchemy.orm import sessionmaker

    monkeypatch.setattr(_app_module, "_SessionLocal", sessionmaker(bind=ticket_db.get_bind()))
    monkeypatch.setenv("AZURE_TRANSLATOR_KEY", "do-not-return-this-key")
    calls = []

    def fake_translate(text, target, source=None, **kwargs):
        calls.append((text, target, source, kwargs.get("config_override")))
        kwargs["before_attempt"](len(text))
        kwargs["after_attempt"]({
            "reserved_characters": len(text), "metered_characters": len(text),
            "success": True, "duration_ms": 12, "source_language": "en",
            "target_language": target, "request_id": "azure-test-id",
        })
        return SimpleNamespace(
            translated_text="Ol?, preciso de ajuda com meu servidor.",
            source_language="en", target_language=target, provider="azure",
            confidence=0.99, duration_ms=12, http_status=200, request_id="azure-test-id",
        )

    monkeypatch.setattr(translation_service, "translate", fake_translate)
    assert client.get("/api/admin/translation/status").status_code == 401
    _login(client, USER_STEAM)
    assert client.get("/api/admin/translation/status").status_code == 403
    _login(client, ADMIN_STEAM)
    status = client.get("/api/admin/translation/status")
    assert status.status_code == 200
    assert status.get_json()["config"]["key_configured"] is True
    assert "do-not-return-this-key" not in status.get_data(as_text=True)
    response = client.post("/api/admin/translation/test", json={})
    assert response.status_code == 200
    assert response.get_json()["translated"]
    assert len(calls) == 1
    assert client.get("/api/admin/translation/status").get_json()["usage"]["successful"] == 1
    saved = client.post("/api/admin/translation/settings", json={
        "monthly_character_limit": 5000, "alert_thresholds": [50, 90],
        "translator_key": "site-admin-azure-key", "region": "brazilsouth",
        "endpoint": "https://api.cognitive.microsofttranslator.com",
    })
    assert saved.status_code == 200
    assert saved.get_json()["config"]["monthly_character_limit"] == 5000
    assert saved.get_json()["config"]["alert_thresholds"] == [50, 90]
    assert saved.get_json()["config"]["region"] == "brazilsouth"
    assert "site-admin-azure-key" not in saved.get_data(as_text=True)
    translated = client.post("/api/translate", json={
        "text": "I need help with my server.", "target": "pt", "source": "en"
    })
    assert translated.status_code == 200
    assert calls[-1][3] == {
        "key": "site-admin-azure-key", "region": "brazilsouth",
        "endpoint": "https://api.cognitive.microsofttranslator.com",
    }
    assert client.post("/api/admin/translation/settings", json={
        "monthly_character_limit": -1, "alert_thresholds": [101]
    }).status_code == 400


def test_translation_provider_failure_does_not_block_ticket_creation(client, ticket_db, monkeypatch):
    import translation_service
    import regulamento_service
    from sqlalchemy.orm import sessionmaker

    monkeypatch.setattr(_app_module, "_SessionLocal", sessionmaker(bind=ticket_db.get_bind()))
    monkeypatch.setattr(regulamento_service, "guard_regulamento_accepted", lambda *_args, **_kwargs: None)

    def fail_translation(*_args, **_kwargs):
        raise translation_service.TranslationServiceError(
            "AZURE_TRANSLATOR_UNAVAILABLE", "translate", "safe error", http_status=503
        )

    monkeypatch.setattr(translation_service, "translate", fail_translation)
    _login(client, USER_STEAM)
    translated = client.post("/api/translate", json={"text": "I need help with my server.", "target": "pt"})
    assert translated.status_code == 503
    assert translated.get_json()["error_code"] == "AZURE_TRANSLATOR_UNAVAILABLE"

    created = client.post("/api/tickets", json={
        "subject": "Server support", "body": "I need help with my server.", "category": "suporte"
    })
    assert created.status_code == 201
    assert created.get_json()["ok"] is True


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


def test_generate_and_confirm_discord_link_code(ticket_db):
    out = generate_discord_link_code(
        ticket_db,
        steam_id=USER_STEAM,
    )
    assert out["ok"] is True
    assert len(out["code"]) >= 6

    duplicate = generate_discord_link_code(
        ticket_db,
        steam_id=USER_STEAM,
    )
    assert duplicate["ok"] is True
    assert duplicate["pending"] is True

    confirm = confirm_discord_link_code_for_discord_user(
        ticket_db,
        out["code"],
        discord_user_id="987654321",
        discord_username="nick_teste",
    )
    assert confirm["ok"] is True
    assert confirm["first_link_bonus"] == 10_000
    balance = ticket_db.execute(text("SELECT points FROM players WHERE steam_id=:sid"), {"sid": USER_STEAM}).scalar_one()
    assert balance == 10_000
    replay = confirm_discord_link_code_for_discord_user(
        ticket_db,
        out["code"],
        discord_user_id="987654321",
        discord_username="nick_teste",
    )
    assert replay["ok"] is False
    balance = ticket_db.execute(text("SELECT points FROM players WHERE steam_id=:sid"), {"sid": USER_STEAM}).scalar_one()
    assert balance == 10_000
    audit = list_discord_link_admin_audit(ticket_db)
    assert audit[0]["event_type"] == "bonus_credited"
    assert audit[0]["amber_delta"] == 10_000
    assert audit[1]["event_type"] == "link_confirmed"
    assert audit[1]["amber_delta"] == 0
    assert audit[0]["is_active"] == 1
    saved = get_discord_link(ticket_db, USER_STEAM)
    assert saved is not None
    assert saved["discord_user_id"] == "987654321"
    assert saved["link_method"] == "ingame_code"

    removed = admin_unlink_discord(
        ticket_db,
        steam_id=USER_STEAM,
        actor_steam_id=ADMIN_STEAM,
        actor_name="Admin",
    )
    assert removed["ok"] is True
    second_code = generate_discord_link_code(ticket_db, steam_id=USER_STEAM)
    relink = confirm_discord_link_code_for_discord_user(
        ticket_db,
        second_code["code"],
        discord_user_id="987654321",
        discord_username="nick_teste",
    )
    assert relink["first_link_bonus"] == 10_000
    balance = ticket_db.execute(
        text("SELECT points FROM players WHERE steam_id=:sid"), {"sid": USER_STEAM}
    ).scalar_one()
    assert balance == 20_000
    audit = list_discord_link_admin_audit(ticket_db)
    assert [event["event_type"] for event in audit[:4]] == [
        "bonus_credited", "link_confirmed", "unlink_admin", "bonus_credited"
    ]


def test_admin_can_force_uncredited_active_discord_link_bonus_once(ticket_db):
    from app import SupportTicketDiscordLink

    ticket_db.add(SupportTicketDiscordLink(
        steam_id=USER_STEAM, discord_user_id="555123456",
        discord_username="Ciano", link_method="legacy",
    ))
    ticket_db.commit()

    first = admin_credit_discord_link_bonus(
        ticket_db, steam_id=USER_STEAM, actor_steam_id=ADMIN_STEAM,
        actor_name="Admin",
    )
    assert first["ok"] is True
    assert first["amber_delta"] == 10_000
    assert ticket_db.execute(
        text("SELECT points FROM players WHERE steam_id=:sid"), {"sid": USER_STEAM}
    ).scalar_one() == 10_000
    audit = list_discord_link_admin_audit(ticket_db)
    assert audit[0]["event_type"] == "bonus_credited"
    assert audit[0]["actor_steam_id"] == ADMIN_STEAM
    assert audit[0]["bonus_eligible"] is False

    duplicate = admin_credit_discord_link_bonus(
        ticket_db, steam_id=USER_STEAM, actor_steam_id=ADMIN_STEAM,
    )
    assert duplicate["ok"] is False
    assert duplicate["status"] == 409
    assert ticket_db.execute(
        text("SELECT points FROM players WHERE steam_id=:sid"), {"sid": USER_STEAM}
    ).scalar_one() == 10_000


def test_discord_link_rolls_back_when_bonus_ledger_write_fails(ticket_db, monkeypatch):
    import amber_ledger
    from app import SupportTicketDiscordLink, SupportTicketDiscordLinkCode

    generated = generate_discord_link_code(ticket_db, steam_id=USER_STEAM)
    monkeypatch.setattr(amber_ledger, "record_admin_adjust", lambda *args, **kwargs: False)

    with pytest.raises(RuntimeError, match="discord_link_bonus_ledger_write_failed"):
        confirm_discord_link_code_for_discord_user(
            ticket_db, generated["code"], discord_user_id="987654321"
        )

    ticket_db.rollback()
    assert ticket_db.execute(
        text("SELECT points FROM players WHERE steam_id=:sid"), {"sid": USER_STEAM}
    ).scalar_one_or_none() is None
    assert ticket_db.get(SupportTicketDiscordLink, USER_STEAM) is None
    code = ticket_db.query(SupportTicketDiscordLinkCode).filter_by(code=generated["code"]).one()
    assert code.used_at is None


def test_legacy_active_discord_link_without_bonus_audit_gets_bonus(ticket_db):
    # Reproduce legacy state: link row exists, but no prior audit/credit event.
    saved = save_discord_link(
        ticket_db,
        steam_id=USER_STEAM,
        discord_user_id="987654321",
        discord_username="nick_teste",
        link_method="ingame_code",
    )
    assert saved["steam_id"] == USER_STEAM
    assert list_discord_link_admin_audit(ticket_db) == []

    generated = generate_discord_link_code(ticket_db, steam_id=USER_STEAM)
    confirmed = confirm_discord_link_code_for_discord_user(
        ticket_db,
        generated["code"],
        discord_user_id="987654321",
        discord_username="nick_teste",
    )

    assert confirmed["ok"] is True
    assert confirmed["first_link_bonus"] == 10_000
    balance = ticket_db.execute(
        text("SELECT points FROM players WHERE steam_id=:sid"), {"sid": USER_STEAM}
    ).scalar_one()
    assert balance == 10_000


def test_save_discord_link_without_commit_flushes_and_returns_pending_link(ticket_db):
    from app import SupportTicketDiscordLink

    ticket_db.autoflush = False
    result = save_discord_link(
        ticket_db,
        steam_id=USER_STEAM,
        discord_user_id="987654321",
        discord_username="nick_teste",
        link_method="ingame_code",
        commit=False,
    )

    assert result["steam_id"] == USER_STEAM
    assert result["discord_user_id"] == "987654321"
    assert ticket_db.query(SupportTicketDiscordLink).filter_by(steam_id=USER_STEAM).one()
    assert ticket_db.in_transaction()


def test_confirm_discord_link_survives_empty_readback_after_save(ticket_db, monkeypatch):
    import ticket_service

    # Match the production session factory in app.py, which disables autoflush.
    ticket_db.autoflush = False
    generated = generate_discord_link_code(ticket_db, steam_id=USER_STEAM)
    assert generated["ok"] is True
    monkeypatch.setattr(ticket_service, "get_discord_link", lambda *_args: None)

    confirmed = confirm_discord_link_code_for_discord_user(
        ticket_db,
        generated["code"],
        discord_user_id="987654321",
        discord_username="nick_teste",
    )

    assert confirmed["ok"] is True
    assert confirmed["first_link_bonus"] == 10_000
    balance = ticket_db.execute(
        text("SELECT points FROM players WHERE steam_id=:sid"), {"sid": USER_STEAM}
    ).scalar_one()
    assert balance == 10_000


def test_confirm_discord_link_code_accepts_legacy_double_hyphen(ticket_db):
    from app import SupportTicketDiscordLinkCode

    generated = generate_discord_link_code(ticket_db, steam_id=USER_STEAM)
    assert generated["ok"] is True
    legacy_code = generated["code"].replace("ARKLAND-", "ARKLAND--", 1)
    row = ticket_db.query(SupportTicketDiscordLinkCode).filter_by(code=generated["code"]).one()
    row.code = legacy_code
    ticket_db.commit()

    confirmed = confirm_discord_link_code_for_discord_user(
        ticket_db,
        legacy_code,
        discord_user_id="987654321",
        discord_username="nick_teste",
    )

    assert confirmed["ok"] is True
    assert confirmed["first_link_bonus"] == 10_000


def test_discord_link_admin_audit_converts_mixed_mysql_charsets_before_collation():
    class Result:
        def mappings(self):
            return self

        def all(self):
            return []

    class FakeMySQLSession:
        bind = SimpleNamespace(dialect=SimpleNamespace(name="mysql"))
        statement = ""

        def execute(self, statement, _params):
            self.statement = str(statement)
            return Result()

    db = FakeMySQLSession()
    assert list_discord_link_admin_audit(db) == []
    assert "CONVERT(l.steam_id USING utf8mb4) COLLATE utf8mb4_unicode_ci = CONVERT(a.steam_id USING utf8mb4) COLLATE utf8mb4_unicode_ci" in db.statement
    assert "CONVERT(l.discord_user_id USING utf8mb4) COLLATE utf8mb4_unicode_ci = CONVERT(a.discord_user_id USING utf8mb4) COLLATE utf8mb4_unicode_ci" in db.statement


def test_discord_link_admin_audit_route_returns_link_bonus_and_unlink_events(ticket_db, tmp_path):
    from flask import Flask, session
    from ticket_routes import register_ticket_routes

    Session = sessionmaker(bind=ticket_db.get_bind())
    code = generate_discord_link_code(ticket_db, steam_id=USER_STEAM)
    confirm = confirm_discord_link_code_for_discord_user(
        ticket_db, code["code"], discord_user_id="555123456", discord_username="Ciano"
    )
    assert confirm["ok"] is True
    assert admin_unlink_discord(
        ticket_db, steam_id=USER_STEAM, actor_steam_id=ADMIN_STEAM, actor_name="Admin"
    )["ok"] is True
    ticket_db.execute(text("UPDATE support_ticket_discord_link_audit SET steam_name='CianoSteam' WHERE steam_id=:sid"), {"sid": USER_STEAM})
    ticket_db.commit()

    route_app = Flask("discord-audit-test")
    route_app.secret_key = "test-secret"

    def admin_required(fn):
        return fn

    register_ticket_routes(
        route_app,
        db_ready=lambda: True,
        session_factory=Session,
        login_required=lambda fn: fn,
        admin_required=admin_required,
        ticket_staff_required=lambda fn: fn,
        steam_id_from_session=lambda: session.get("steam_id"),
        is_admin_steamid=lambda sid: sid == ADMIN_STEAM,
        can_manage_tickets=lambda sid: sid == ADMIN_STEAM,
        uploads_dir=tmp_path,
    )
    with route_app.test_client() as route_client:
        with route_client.session_transaction() as sess:
            sess["steam_id"] = ADMIN_STEAM
        response = route_client.get("/api/admin/discord-link/audit")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["ok"] is True
    assert payload["total"] == 3
    assert payload["page"] == 1
    assert payload["pages"] == 1
    assert [event["event_type"] for event in payload["events"][:3]] == [
        "unlink_admin", "bonus_credited", "link_confirmed"
    ]
    assert payload["events"][1]["discord_username"] == "Ciano"
    assert payload["events"][1]["discord_user_id"] == "555123456"
    assert payload["events"][1]["amber_delta"] == 10_000

    ticket_db.execute(
        text("UPDATE support_ticket_discord_link_audit SET steam_name='Player Alpha' WHERE steam_id=:sid"),
        {"sid": USER_STEAM},
    )
    ticket_db.commit()
    for term in ("Player Alpha", "ciano", USER_STEAM, "555123456"):
        filtered = route_client.get(
            "/api/admin/discord-link/audit", query_string={"q": term, "page_size": 1}
        ).get_json()
        assert filtered["ok"] is True
        assert filtered["total"] >= 1, term
        assert len(filtered["events"]) == 1
        assert filtered["pages"] == filtered["total"]

    second_page = route_client.get("/api/admin/discord-link/audit?page=2&page_size=2").get_json()
    assert second_page["total"] == 3
    assert second_page["pages"] == 2
    assert [event["event_type"] for event in second_page["events"]] == ["link_confirmed"]
    clamped_page = route_client.get("/api/admin/discord-link/audit?page=999&page_size=2").get_json()
    assert clamped_page["page"] == 2
    assert len(clamped_page["events"]) == 1
    invalid_page = route_client.get("/api/admin/discord-link/audit?page=invalid")
    assert invalid_page.status_code == 400


def test_internal_discord_nickname_snapshot_uses_latest_linked_game_identity(ticket_db, tmp_path):
    from flask import Flask, session
    from ticket_routes import register_ticket_routes

    Session = sessionmaker(bind=ticket_db.get_bind())
    code = generate_discord_link_code(ticket_db, steam_id=USER_STEAM)
    confirmed = confirm_discord_link_code_for_discord_user(
        ticket_db, code["code"], discord_user_id="555123456", discord_username="CianoDiscord"
    )
    assert confirmed["ok"] is True
    ticket_db.execute(text("""
        CREATE TABLE tribe_members (
            steam_id TEXT NOT NULL, character_name TEXT, tribe_name TEXT,
            last_seen_at TEXT, server_id TEXT
        )
    """))
    ticket_db.execute(text("""
        INSERT INTO tribe_members (steam_id,character_name,tribe_name,last_seen_at,server_id)
        VALUES (:sid,'OldCharacter','OldTribe','2026-11-01 10:00:00','map_a'),
               (:sid,'Ciano','BøT','2026-11-05 10:00:00','map_b')
    """), {"sid": USER_STEAM})
    ticket_db.commit()

    route_app = Flask("discord-nickname-sync-test")
    route_app.secret_key = "test-secret"
    register_ticket_routes(
        route_app,
        db_ready=lambda: True,
        session_factory=Session,
        login_required=lambda fn: fn,
        admin_required=lambda fn: fn,
        ticket_staff_required=lambda fn: fn,
        steam_id_from_session=lambda: session.get("steam_id"),
        is_admin_steamid=lambda _sid: False,
        can_manage_tickets=lambda _sid: False,
        uploads_dir=tmp_path,
        api_key_required=lambda _allow_admin: (lambda fn: fn),
    )
    payload = route_app.test_client().get("/api/internal/discord/nickname-sync").get_json()
    assert payload == {
        "ok": True,
        "users": [{
            "discord_user_id": "555123456",
            "character_name": "Ciano",
            "tribe_name": "BøT",
        }],
    }


def test_confirm_discord_link_code_rejects_reused_discord_account(ticket_db):
    first_code = generate_discord_link_code(
        ticket_db,
        steam_id=USER_STEAM,
    )
    first = confirm_discord_link_code_for_discord_user(ticket_db, first_code["code"],
        discord_user_id="111222333", discord_username="alice")
    assert first["steam_id"] == USER_STEAM

    generated = generate_discord_link_code(
        ticket_db,
        steam_id=ADMIN_STEAM,
    )
    assert generated["ok"] is True
    conflict = confirm_discord_link_code_for_discord_user(
        ticket_db,
        generated["code"],
        discord_user_id="111222333",
        discord_username="alice",
    )
    assert conflict["ok"] is False


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


def test_admin_ticket_identity_uses_current_names_without_rewriting_history(ticket_db):
    created = create_ticket(
        ticket_db,
        steam_id=USER_STEAM,
        player_name=USER_STEAM,
        subject="Ticket legado sem nick",
        body="Mensagem inicial",
        discord_user_id=None,
        discord_username=None,
    )
    ticket_id = created["ticket"]["id"]
    ticket_db.add(StoreUser(
        steam_id=USER_STEAM,
        display_name="Nome de conta",
        steam_persona="Nick Steam Atual",
    ))
    ticket_db.add(SupportTicketDiscordLink(
        steam_id=USER_STEAM,
        discord_user_id="555123456",
        discord_username="NickDiscordAtual",
    ))
    ticket_db.commit()

    detail = get_ticket_detail(ticket_db, ticket_id, is_admin=True)
    assert detail is not None
    assert detail["ticket"]["player_display_name"] == "Nick Steam Atual"
    assert detail["ticket"]["discord_display_name"] == "NickDiscordAtual"
    assert detail["ticket"]["player_name"] == USER_STEAM
    assert detail["messages"][0]["author_display_name"] == "Nick Steam Atual"
    assert detail["messages"][0]["author_discord_name"] == "NickDiscordAtual"
    assert detail["messages"][0]["author_name"] == USER_STEAM

    rows, total = list_tickets_admin(ticket_db)
    assert total == 1
    assert rows[0]["player_display_name"] == "Nick Steam Atual"
    assert rows[0]["discord_display_name"] == "NickDiscordAtual"
    # A consulta enriquece a resposta, mas preserva snapshots e histórico no banco.
    stored = ticket_db.get(_app_module.SupportTicket, ticket_id)
    assert stored.player_name == USER_STEAM
    assert stored.discord_username is None


def test_ticket_admin_ui_prefers_resolved_identity_fields():
    from pathlib import Path

    html = (Path(__file__).resolve().parents[1] / "static" / "index.html").read_text(encoding="utf-8")
    assert "t.player_display_name || t.player_name || t.steam_id" in html
    assert "t.discord_display_name || t.discord_username || t.discord_user_id" in html
    assert "m.author_display_name || m.author_name || m.author_type" in html


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


def test_discord_link_manual_is_disabled(ticket_db):
    link = save_discord_link(
        ticket_db,
        steam_id=USER_STEAM,
        discord_user_id="123456789012345678",
        discord_username="player#0001",
    )
    assert link["ok"] is False
    assert "código" in link["error"].lower()


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
