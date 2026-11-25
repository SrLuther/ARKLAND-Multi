from __future__ import annotations

import functools
from io import BytesIO
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest
from flask import Flask, jsonify
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import lumo_routes


class Limiter:
    def limit(self, *_args, **_kwargs):
        return lambda fn: fn


class Idempotency:
    def __init__(self):
        self.keys = set()

    def claim(self, key):
        if key in self.keys:
            return False
        self.keys.add(key)
        return True


def make_app(*, initial_settings=None, encrypted=True, uploads_dir=None):
    app = Flask(__name__)
    app.secret_key = "test"
    state = {"settings": {"lumo_webhook_url": "", "lumo_webhook_status": "not_configured", **(initial_settings or {})}}
    audit = []
    access = {"admin": True}
    idem = Idempotency()

    def admin_required(fn):
        @functools.wraps(fn)
        def wrapped(*args, **kwargs):
            if not access["admin"]:
                return jsonify({"ok": False, "error": "Acesso negado"}), 403
            return fn(*args, **kwargs)
        return wrapped

    class UnusedSession:
        def query(self, *_args):
            raise AssertionError("history was not expected in these tests")

        def close(self):
            pass

    lumo_routes.register_lumo_routes(
        app,
        admin_required=admin_required,
        limiter=Limiter(),
        load_settings=lambda: dict(state["settings"]),
        save_settings=lambda settings: state.update(settings=dict(settings)),
        get_fernet=lambda: object() if encrypted else None,
        encrypt_value=lambda value: "ENC:encrypted" if encrypted else value,
        audit_event=lambda *args, **kwargs: audit.append((args, kwargs)),
        session_factory=UnusedSession,
        audit_model=object,
        idempotency_store=idem,
        now=lambda: datetime(2026, 11, 25, 12, 0, tzinfo=UTC),
        get_admin_id=lambda: "76561198000000000",
        index_view=lambda: "admin page",
        db_ready=lambda: True,
        uploads_dir=uploads_dir,
    )
    return app, state, audit, access, idem


def test_webhook_url_accepts_only_official_https_endpoint():
    valid = "https://discord.com/api/webhooks/12345678901234567/abcdefghijklmnopqrstuvwxyz"
    assert lumo_routes.validate_webhook_url(valid) == valid
    for bad in (
        "http://discord.com/api/webhooks/12345678901234567/abcdefghijklmnopqrstuvwxyz",
        "https://discord.com.evil.test/api/webhooks/12345678901234567/abcdefghijklmnopqrstuvwxyz",
        "https://discord.com:8443/api/webhooks/12345678901234567/abcdefghijklmnopqrstuvwxyz",
        "https://user@discord.com/api/webhooks/12345678901234567/abcdefghijklmnopqrstuvwxyz",
        "https://discord.com/api/webhooks/12345678901234567/abcdefghijklmnopqrstuvwxyz?next=https://evil.test",
    ):
        with pytest.raises(ValueError):
            lumo_routes.validate_webhook_url(bad)


def test_embed_enforces_discord_limits_and_fixed_identity():
    embed = lumo_routes.validate_embed("Aviso", "**Olá**")
    assert embed["color"] == 65535
    assert embed["footer"]["text"] == "Lumo • Assistente oficial da ARKLAND"
    assert embed["timestamp"].endswith("Z")
    with pytest.raises(ValueError, match="4.096"):
        lumo_routes.validate_embed("", "x" * 4097)
    with pytest.raises(ValueError, match="256"):
        lumo_routes.validate_embed("x" * 257, "corpo")


def test_config_never_returns_full_webhook_and_refuses_plaintext_fallback():
    url = "https://discord.com/api/webhooks/12345678901234567/abcdefghijklmnopqrstuvwxyz"
    app, state, _audit, _access, _idem = make_app()
    client = app.test_client()
    saved = client.post("/api/admin/lumo/config", json={"webhook_url": url})
    assert saved.status_code == 200
    assert state["settings"]["lumo_webhook_url"] == url
    assert url not in saved.get_data(as_text=True)
    assert "wxyz" in saved.get_data(as_text=True)
    assert "masked_url" in saved.get_data(as_text=True) or "discord.com/api/webhooks/" in saved.get_data(as_text=True)

    insecure_app, _state, _audit, _access, _idem = make_app(encrypted=False)
    response = insecure_app.test_client().post("/api/admin/lumo/config", json={"webhook_url": url})
    assert response.status_code == 503


def test_webhook_verification_reads_metadata_without_publishing(monkeypatch):
    url = "https://discord.com/api/webhooks/12345678901234567/abcdefghijklmnopqrstuvwxyz"
    app, state, audit, _access, _idem = make_app(initial_settings={"lumo_webhook_url": url, "lumo_webhook_status": "unverified"})
    calls = []

    def fake_request(target, **kwargs):
        calls.append((target, kwargs))
        return 200, {"id": "12345678901234567", "channel_id": "98765432109876543", "guild_id": "76543210987654321"}, {}

    monkeypatch.setattr(lumo_routes, "_discord_request", fake_request)
    response = app.test_client().post("/api/admin/lumo/verify", json={})
    payload = response.get_json()
    assert response.status_code == 200 and payload["ok"] is True
    assert state["settings"]["lumo_webhook_status"] == "verified"
    assert payload["integration"]["channel_id"] == "98765432109876543"
    assert len(calls) == 1 and calls[0][1] == {}
    assert not any(event[0][0] == "lumo_publish" for event in audit)


def test_publish_sends_embed_once_with_mentions_disabled(monkeypatch):
    url = "https://discord.com/api/webhooks/12345678901234567/abcdefghijklmnopqrstuvwxyz"
    app, _state, audit, _access, idem = make_app(initial_settings={"lumo_webhook_url": url, "lumo_webhook_status": "verified", "lumo_webhook_channel_id": "98765432109876543"})
    calls = []

    def fake_request(target, **kwargs):
        calls.append((target, kwargs))
        return 200, {"id": "11223344556677889", "channel_id": "98765432109876543", "guild_id": "76543210987654321"}, {}

    monkeypatch.setattr(lumo_routes, "_discord_request", fake_request)
    body = {"title": "Aviso", "content": "Olá, sobreviventes!", "request_id": "a" * 32}
    client = app.test_client()
    response = client.post("/api/admin/lumo/publish", json=body)
    assert response.status_code == 200
    assert len(calls) == 1
    target, options = calls[0]
    payload = options["payload"]
    assert target.endswith("?wait=true")
    assert options["method"] == "POST"
    assert payload["username"] == "Lumo"
    assert payload["embeds"][0]["color"] == 65535
    assert payload["allowed_mentions"] == {"parse": []}
    assert "content" not in payload
    assert len([entry for entry in audit if entry[0][0] == "lumo_publish"]) == 1
    assert client.post("/api/admin/lumo/publish", json=body).status_code == 409
    assert len(calls) == 1


def test_admin_page_and_apis_are_denied_without_admin():
    app, _state, _audit, access, _idem = make_app()
    access["admin"] = False
    client = app.test_client()
    assert client.get("/admin/lumo").status_code == 403
    assert client.get("/api/admin/lumo/config").status_code == 403
    assert client.post("/api/admin/lumo/publish", json={}).status_code == 403


def test_game_chat_requires_a_separate_numeric_channel():
    app, _state, _audit, _access, _idem = make_app()
    client = app.test_client()
    bad_id = client.post("/api/admin/lumo/assistant/config", json={
        "enabled": False, "guild_id": "76543210987654321", "game_chat_enabled": True,
        "game_chat_channel_id": "not-a-channel",
    })
    assert bad_id.status_code == 400
    same = client.post("/api/admin/lumo/assistant/config", json={
        "enabled": True, "guild_id": "76543210987654321", "interaction_channel_id": "98765432109876543",
        "game_chat_enabled": True, "game_chat_channel_id": "98765432109876543",
    })
    assert same.status_code == 400 and "canais diferentes" in same.get_json()["error"]


def test_uploaded_image_is_stored_and_sent_as_discord_attachment(tmp_path, monkeypatch):
    url = "https://discord.com/api/webhooks/12345678901234567/abcdefghijklmnopqrstuvwxyz"
    app, state, _audit, _access, _idem = make_app(
        initial_settings={"lumo_webhook_url": url, "lumo_webhook_status": "verified"}, uploads_dir=tmp_path,
    )
    output = BytesIO()
    Image.new("RGB", (20, 12), "green").save(output, format="PNG")
    upload = app.test_client().post("/api/admin/lumo/assets", data={"file": (BytesIO(output.getvalue()), "poster.png")}, content_type="multipart/form-data")
    assert upload.status_code == 201
    asset = upload.get_json()["asset"]
    assert asset["mime_type"] == "image/png" and asset["width"] == 20
    assert (tmp_path / asset["filename"]).is_file()

    calls = []
    def fake_request(target, **kwargs):
        calls.append((target, kwargs))
        return 200, {"id": "11223344556677889", "channel_id": "98765432109876543", "guild_id": "76543210987654321"}, {}
    monkeypatch.setattr(lumo_routes, "_discord_request", fake_request)
    response = app.test_client().post("/api/admin/lumo/publish", json={
        "title": "Imagem", "content": "Comunicado", "image_asset_id": asset["id"], "request_id": "b" * 32,
    })
    assert response.status_code == 200
    options = calls[0][1]
    assert options["payload"]["embeds"][0]["image"]["url"] == f"attachment://{asset['filename']}"
    assert options["files"][0][1:3] == (asset["filename"], "image/png")
    assert state["settings"]["lumo_media_assets"][0]["last_used_at"]
