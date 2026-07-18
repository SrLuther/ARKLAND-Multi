"""Testes mínimos PWA (manifest, service worker, ícones)."""
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


def test_manifest_route_and_content_type(client):
    r = client.get("/manifest.webmanifest")
    assert r.status_code == 200
    assert "manifest" in (r.content_type or "")
    data = r.get_json(force=True, silent=True) or __import__("json").loads(r.get_data(as_text=True))
    assert data["name"]
    assert data["display"] == "standalone"
    assert data["start_url"] == "/"
    icons = {i["src"] for i in data["icons"]}
    assert "/icons/icon-192.png" in icons
    assert "/icons/icon-512.png" in icons


def test_service_worker_exists_and_no_api_cache(client):
    r = client.get("/service-worker.js")
    assert r.status_code == 200
    body = r.get_data(as_text=True)
    assert "isApiRequest" in body or "/api/" in body
    assert "caches.put" in body or "cache.put" in body
    # API path must not be cached (network-only branch)
    assert "nunca cachear" in body.lower() or "isApiRequest" in body
    assert "Cache-Control" in r.headers
    assert "no-cache" in r.headers.get("Cache-Control", "")


def test_pwa_icon_files_exist():
    for name in ("icon-192.png", "icon-512.png", "apple-touch-icon.png"):
        path = STATIC / "icons" / name
        assert path.is_file(), path
        assert path.stat().st_size > 1000


def test_index_links_manifest_and_pwa_script():
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    assert 'href="/manifest.webmanifest' in html
    assert "pwa-install.js" in html
    assert "data-pwa-install" in html


def test_pwa_service_worker_skips_species_icons(client):
    """Imagens de espécie não entram no Cache Storage (agravante, não causa SQL)."""
    body = client.get("/service-worker.js").get_data(as_text=True)
    assert "arkland-webstore-static-v4" in body
    assert "isHeavyImageAsset" in body
    assert "/species/icons/" in body
    assert "PRECACHE_URLS" in body or "/icons/icon-192.png" in body
    # HTML e APIs continuam network-only
    assert "no-store" in body
    assert "isApiRequest" in body
