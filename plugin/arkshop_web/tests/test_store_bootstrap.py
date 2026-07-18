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
    assert "STORE_WARMUP_GATE_MS" in html
    assert "skipStoreWarmup" in html
    assert "FORCE_MS" in html or "__earlyForceReleaseWarmup" in html
    assert "Entrar mesmo assim" in html
    assert "indexedDB" in html or "IndexedDB" in html


def test_service_worker_does_not_cache_bootstrap(client):
    r = client.get("/service-worker.js")
    body = r.get_data(as_text=True)
    assert "/api/store/bootstrap" in body
    assert "isPublicCatalog" in body
    assert "store/bootstrap" in body.lower() or "bootstrap" in body
    assert "arkland-webstore-static-v4" in body
    assert "no-store" in body
    assert "skipWaiting" in body
    assert "isHeavyImageAsset" in body
    assert "/species/icons/" in body


def test_index_admin_config_load_does_not_false_empty():
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    assert "if (!_config) return;" in html
    assert "admin-config-loading" in html
    assert 'timeoutMs: 12000' in html
    assert "data._config_path_missing" in html or "_config_path_missing" in html


def test_index_kit_limits_respects_partial_empty():
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    assert "d.partial && !d.kits.length" in html
    assert "_ensureKitLimitsLoaded" in html


def test_index_load_catalog_passes_cached_kit_limits():
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    assert "kitLimits: cached.kit_limits" in html


def test_index_catalog_thumbs_are_lazy():
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    assert 'loading="lazy"' in html
    assert 'decoding="async"' in html
    assert "runStoreWarmup" in html
    assert "timeoutMs: 15000" in html


def test_index_nav_syncs_warmup_ready_flags():
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    assert "_syncStoreWarmupReady" in html
    assert "window.__warmupForceReleased" in html
    assert "if (!_syncStoreWarmupReady()) return;" in html


def test_index_catalog_distinguishes_load_error_from_empty():
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    assert "_catalogLoadError" in html
    assert "_catalogPanelIdleHtml" in html
    assert "Catálogo indisponível" in html
    assert "loadCatalog({force:true})" in html
    assert "_catalogLoading" in html


def test_index_admin_nav_shows_loading_without_config():
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    assert 'else if (_auth.is_admin) setAdminShopLoading("Carregando config.json…");' in html
    assert "_updateCatalogStatusBar" in html
