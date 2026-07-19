"""Testes — doação boleto manual (instruções + ticket) e flag MP."""
from __future__ import annotations

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("ARKSHOP_DATABASE_URL", "")
os.environ.setdefault("ARKSHOP_WEB_SECRET", "test-secret")
os.environ.setdefault("ARKSHOP_RETRY_INTERVAL", "9999")
os.environ.setdefault("ARKSHOP_SKIP_DB_BOOT", "1")

import app as _app_module
from app import app

ADMIN_STEAM = "76561198000000001"


@pytest.fixture(autouse=True)
def isolated_settings(tmp_path, monkeypatch):
    monkeypatch.setattr(_app_module, "_STATE_FILE", tmp_path / "settings.json")
    monkeypatch.setattr(_app_module, "_ADMIN_FILE", tmp_path / "admin_steamids.json")
    (tmp_path / "admin_steamids.json").write_text(json.dumps([ADMIN_STEAM]), encoding="utf-8")
    yield


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def _login(client, steam_id: str):
    with client.session_transaction() as sess:
        sess["steam_id"] = steam_id


def test_catalog_hides_boleto_by_default(client):
    d = client.get("/api/catalog").get_json()
    assert d.get("boleto_mp_enabled") is False
    assert d.get("boleto_manual_enabled") is False


def test_catalog_exposes_boleto_manual_when_enabled(client, tmp_path):
    (tmp_path / "settings.json").write_text(
        json.dumps({
            "boleto_manual_enabled": True,
            "boleto_manual_instructions": "Dados bancários de teste.",
        }),
        encoding="utf-8",
    )
    d = client.get("/api/catalog").get_json()
    assert d["boleto_manual_enabled"] is True
    assert "Dados bancários" in d["boleto_manual_instructions"]
    assert d.get("boleto_mp_enabled") is False


def test_admin_can_toggle_boleto_settings(client, tmp_path):
    _login(client, ADMIN_STEAM)
    custom = "Instruções customizadas boleto."
    r = client.post(
        "/api/settings",
        json={
            "boleto_mp_enabled": True,
            "boleto_manual_enabled": True,
            "boleto_manual_instructions": custom,
        },
    )
    assert r.status_code == 200
    assert r.get_json()["ok"] is True

    s = client.get("/api/settings").get_json()
    assert s["boleto_mp_enabled"] is True
    assert s["boleto_manual_enabled"] is True
    assert s["boleto_manual_instructions"] == custom

    cat = client.get("/api/catalog").get_json()
    assert cat["boleto_manual_enabled"] is True
    assert cat["boleto_manual_instructions"] == custom
    # MP boleto só fica efetivo com access token
    assert cat.get("boleto_mp_enabled") is False
