"""Testes do sistema de sugestões da comunidade."""
from __future__ import annotations

import json

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

import app as _app_module
from app import app
from suggestion_service import (
    SUGGESTION_CATEGORIES,
    create_suggestion,
    ensure_suggestion_schema,
    list_suggestions_admin,
    list_suggestions_for_player,
    public_suggestion_stats,
    suggestion_meta,
    update_suggestion_admin,
)

ADMIN_STEAM = "76561198000000001"
USER_STEAM = "76561198000000002"


@pytest.fixture()
def sugg_db(tmp_path):
    path = tmp_path / "suggestions.db"
    engine = create_engine(f"sqlite:///{path}", future=True)
    ensure_suggestion_schema(engine)
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


def test_suggestion_meta():
    meta = suggestion_meta()
    assert meta["daily_limit"] == 3
    assert any(c["id"] == "dino" for c in meta["categories"])
    assert any(s["id"] == "pending" for s in meta["statuses"])


def test_create_and_list_suggestion(sugg_db):
    created = create_suggestion(
        sugg_db,
        steam_id=USER_STEAM,
        category="dino",
        title="Buff no Rex",
        description="Aumentar vida base do Rex em 10%.",
        details={"species_name": "Rex", "reason": "PvE balance"},
    )
    assert created["ok"] is True
    assert created["suggestion"]["category"] == "dino"
    assert created["suggestion"]["status"] == "pending"
    assert created["suggestion"]["details"]["species_name"] == "Rex"

    items, total = list_suggestions_for_player(sugg_db, USER_STEAM)
    assert total == 1
    assert items[0]["title"] == "Buff no Rex"


def test_daily_limit(sugg_db):
    for i in range(3):
        r = create_suggestion(
            sugg_db,
            steam_id=USER_STEAM,
            category="item",
            title=f"Sugestão {i}",
            description="Detalhes",
        )
        assert r["ok"] is True

    blocked = create_suggestion(
        sugg_db,
        steam_id=USER_STEAM,
        category="item",
        title="Quarta",
        description="Não deve passar",
    )
    assert blocked["ok"] is False
    assert "Limite" in blocked["error"]


def test_admin_list_and_update(sugg_db):
    created = create_suggestion(
        sugg_db,
        steam_id=USER_STEAM,
        category="recurso",
        title="Mais metal",
        description="Spawn de metal no mapa",
    )
    sid = created["suggestion"]["id"]

    items, total = list_suggestions_admin(sugg_db, status="pending")
    assert total == 1

    updated = update_suggestion_admin(
        sugg_db,
        sid,
        status="em_analise",
        admin_note="Vamos avaliar no próximo wipe",
        admin_steam_id=ADMIN_STEAM,
    )
    assert updated["ok"] is True
    assert updated["suggestion"]["status"] == "em_analise"
    assert updated["suggestion"]["admin_note"] == "Vamos avaliar no próximo wipe"

    approved = update_suggestion_admin(
        sugg_db, sid, status="aprovada", admin_steam_id=ADMIN_STEAM,
    )
    assert approved["suggestion"]["status"] == "aprovada"


def test_admin_list_em_analise_after_update(sugg_db):
    created = create_suggestion(
        sugg_db,
        steam_id=USER_STEAM,
        category="dino",
        title="Novo dino",
        description="Adicionar Yuty",
    )
    sid = created["suggestion"]["id"]

    updated = update_suggestion_admin(
        sugg_db,
        sid,
        status="em_analise",
        admin_note="Em avaliação",
        admin_steam_id=ADMIN_STEAM,
    )
    assert updated["suggestion"]["status"] == "em_analise"

    all_items, all_total = list_suggestions_admin(sugg_db)
    assert all_total == 1
    assert all_items[0]["status"] == "em_analise"

    filtered, filtered_total = list_suggestions_admin(sugg_db, status="em_analise")
    assert filtered_total == 1
    assert filtered[0]["id"] == sid

    pending_items, pending_total = list_suggestions_admin(sugg_db, status="pending")
    assert pending_total == 0

    stats = public_suggestion_stats(sugg_db)
    assert stats["by_status"]["em_analise"] == 1


def test_public_stats(sugg_db):
    create_suggestion(
        sugg_db,
        steam_id=USER_STEAM,
        category="dino",
        title="A",
        description="x",
    )
    create_suggestion(
        sugg_db,
        steam_id=USER_STEAM,
        category="item",
        title="B",
        description="y",
    )
    stats = public_suggestion_stats(sugg_db)
    assert stats["total"] == 2
    assert stats["by_status"]["pending"] == 2
    assert stats["by_category"]["dino"] == 1


def test_invalid_category_normalized(sugg_db):
    created = create_suggestion(
        sugg_db,
        steam_id=USER_STEAM,
        category="invalida",
        title="Teste",
        description="Corpo",
    )
    assert created["ok"] is True
    assert created["suggestion"]["category"] == "outro"
    assert "outro" in SUGGESTION_CATEGORIES


def test_suggestions_meta_endpoint(client):
    r = client.get("/api/suggestions/meta")
    assert r.status_code == 200
    data = r.get_json()
    assert data["ok"] is True
    assert data["daily_limit"] == 3


def test_create_requires_login(client):
    r = client.post(
        "/api/suggestions",
        json={"title": "X", "description": "Y", "category": "dino"},
    )
    assert r.status_code in (401, 403)


def test_admin_list_requires_admin(client, monkeypatch):
    _login(client, USER_STEAM)
    monkeypatch.setattr(_app_module, "_db_ready", lambda: True)
    r = client.get("/api/admin/suggestions")
    assert r.status_code in (401, 403)
