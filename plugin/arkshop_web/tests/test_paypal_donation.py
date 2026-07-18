"""Testes mínimos — doação PayPal QR + ticket manual."""
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
from app import (
    DEFAULT_PAYPAL_QR_PATH,
    app,
)

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


def test_paypal_static_asset_exists():
    static_dir = _app_module._BUNDLE_DIR / "static"
    assert (static_dir / "paypal-qr.jpeg").is_file()


def test_catalog_exposes_paypal_when_enabled(client, tmp_path):
    (tmp_path / "settings.json").write_text(
        json.dumps({"paypal_enabled": True, "paypal_qr_path": "/paypal-qr.jpeg"}),
        encoding="utf-8",
    )
    d = client.get("/api/catalog").get_json()
    assert d["paypal_enabled"] is True
    assert d["paypal_qr_url"] == "/paypal-qr.jpeg"
    assert "paypal_instructions" in d
    assert "PayPal" in d["paypal_instructions"] or "ticket" in d["paypal_instructions"].lower()


def test_catalog_hides_paypal_by_default(client):
    d = client.get("/api/catalog").get_json()
    assert d.get("paypal_enabled") is False


def test_admin_can_toggle_paypal_settings(client, tmp_path):
    _login(client, ADMIN_STEAM)
    custom_instr = "Instruções customizadas PayPal."
    r = client.post(
        "/api/settings",
        json={
            "paypal_enabled": True,
            "paypal_qr_path": "/custom-qr.jpeg",
            "paypal_instructions": custom_instr,
        },
    )
    assert r.status_code == 200
    assert r.get_json()["ok"] is True

    s = client.get("/api/settings").get_json()
    assert s["paypal_enabled"] is True
    assert s["paypal_qr_url"] == "/custom-qr.jpeg"
    assert s["paypal_instructions"] == custom_instr

    cat = client.get("/api/catalog").get_json()
    assert cat["paypal_enabled"] is True
    assert cat["paypal_qr_url"] == "/custom-qr.jpeg"


def test_paypal_qr_served_as_static(client):
    r = client.get(DEFAULT_PAYPAL_QR_PATH)
    assert r.status_code == 200
    assert r.mimetype in ("image/jpeg", "image/jpg")
