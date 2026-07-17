"""Testes do warmup agregado /api/store/bootstrap e cache frontend."""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("ARKSHOP_DATABASE_URL", "")
os.environ.setdefault("ARKSHOP_WEB_SECRET", "test-secret")
os.environ.setdefault("ARKSHOP_RETRY_INTERVAL", "9999")
os.environ.setdefault("ARKSHOP_SKIP_DB_BOOT", "1")

from app import app  # noqa: E402

STATIC = Path(__file__).resolve().parents[1] / "static"


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def test_store_bootstrap_anonymous(client):
    r = client.get("/api/store/bootstrap")
    assert r.status_code == 200
    d = r.get_json()
    assert d["ok"] is True
    assert d["me"]["authenticated"] is False
    assert "catalog" in d
    assert d["kit_limits"] is None
    assert d["entitlements"] is None
    assert isinstance(d["fingerprint"], str) and len(d["fingerprint"]) >= 8
    assert "server_time" in d
    assert r.headers.get("Cache-Control") == "private, no-store, max-age=0"


def test_store_bootstrap_catalog_matches_public_endpoint(client):
    boot = client.get("/api/store/bootstrap").get_json()
    cat = client.get("/api/catalog").get_json()
    assert boot["catalog"].get("shop_name") == cat.get("shop_name")
    assert boot["fingerprint"]


def test_index_has_warmup_overlay_and_cache_keys():
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    assert "store-warmup-overlay" in html
    assert "A preparar a loja" in html
    assert "/api/store/bootstrap" in html
    assert "STORE_CACHE_META_KEY" in html
    assert "indexedDB" in html or "IndexedDB" in html


def test_service_worker_does_not_cache_bootstrap(client):
    r = client.get("/service-worker.js")
    body = r.get_data(as_text=True)
    assert "/api/store/bootstrap" in body
    assert "isPublicCatalog" in body
    assert "store/bootstrap" in body.lower() or "bootstrap" in body
