"""Testes do sistema de Mídias (vídeos YouTube)."""
from __future__ import annotations

import json

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

import app as _app_module
from app import app
from media_service import (
    create_media_video,
    delete_media_video,
    ensure_media_schema,
    list_media_admin,
    list_media_public,
    media_meta,
    parse_youtube_id,
    update_media_video,
)

ADMIN_STEAM = "76561198000000001"
USER_STEAM = "76561198000000002"

SAMPLE_URL = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
SAMPLE_ID = "dQw4w9WgXcQ"


@pytest.fixture()
def media_db(tmp_path):
    path = tmp_path / "media.db"
    engine = create_engine(f"sqlite:///{path}", future=True)
    ensure_media_schema(engine)
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


def test_parse_youtube_id_variants():
    assert parse_youtube_id(SAMPLE_URL) == SAMPLE_ID
    assert parse_youtube_id("https://youtu.be/dQw4w9WgXcQ") == SAMPLE_ID
    assert parse_youtube_id("https://www.youtube.com/embed/dQw4w9WgXcQ") == SAMPLE_ID
    assert parse_youtube_id("https://www.youtube.com/shorts/dQw4w9WgXcQ") == SAMPLE_ID
    assert parse_youtube_id(SAMPLE_ID) == SAMPLE_ID
    assert parse_youtube_id("invalid") is None
    assert parse_youtube_id("") is None


def test_media_meta():
    meta = media_meta()
    assert len(meta["categories"]) == 3
    assert meta["categories"][0]["id"] == "tutorial"


def test_create_list_public_and_admin(media_db):
    created = create_media_video(
        media_db,
        youtube_url=SAMPLE_URL,
        title="Tutorial de conexão",
        description="Como entrar no servidor",
        category="tutorial",
        sort_order=10,
        published=True,
        created_by_steam_id=ADMIN_STEAM,
    )
    assert created["video_id"] == SAMPLE_ID
    assert created["published"] is True
    assert created["category"] == "tutorial"
    assert "embed_url" in created

    draft = create_media_video(
        media_db,
        video_id=SAMPLE_ID,
        title="Rascunho",
        published=False,
    )
    assert draft["published"] is False

    public = list_media_public(media_db)
    assert len(public) == 1
    assert public[0]["title"] == "Tutorial de conexão"

    public_tut = list_media_public(media_db, category="tutorial")
    assert len(public_tut) == 1

    admin = list_media_admin(media_db)
    assert len(admin) == 2


def test_update_and_delete(media_db):
    created = create_media_video(
        media_db,
        youtube_url=SAMPLE_URL,
        title="Original",
        category="geral",
        published=False,
    )
    pk = created["id"]

    updated = update_media_video(
        media_db,
        pk,
        title="Atualizado",
        category="informativo",
        published=True,
        sort_order=5,
    )
    assert updated["title"] == "Atualizado"
    assert updated["category"] == "informativo"
    assert updated["published"] is True
    assert updated["sort_order"] == 5

    update_media_video(
        media_db,
        pk,
        youtube_url="https://youtu.be/abcdefghijk",
    )
    row = media_db.execute(
        text("SELECT video_id FROM media_videos WHERE id = :id"),
        {"id": pk},
    ).fetchone()
    assert row.video_id == "abcdefghijk"

    delete_media_video(media_db, pk)
    assert list_media_admin(media_db) == []


def test_create_invalid_url(media_db):
    with pytest.raises(ValueError, match="inválido"):
        create_media_video(media_db, youtube_url="not-a-url", title="X")


def test_create_requires_title(media_db):
    with pytest.raises(ValueError, match="Título"):
        create_media_video(media_db, youtube_url=SAMPLE_URL, title="")


def test_admin_create_requires_admin(client):
    r = client.post(
        "/api/admin/media",
        json={"youtube_url": SAMPLE_URL, "title": "Teste"},
    )
    assert r.status_code in (401, 403)


def test_admin_list_requires_admin(client):
    with client.session_transaction() as sess:
        sess["steam_id"] = USER_STEAM
    r = client.get("/api/admin/media")
    assert r.status_code in (401, 403)
