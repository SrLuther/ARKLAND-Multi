"""WebApiUrl dos plugins — LAN no host, domínio no cliente."""
from __future__ import annotations

import json
from pathlib import Path

from src.config_manager import ShopGlobalConfig
from src.shop_integration import (
    fix_website_url_in_config_file,
    is_stale_ip_website_url,
    migrate_stale_plugin_website_urls,
    needs_website_url_fix,
    resolve_plugin_api_url,
    resolve_plugin_website_url,
    resolve_website_url,
)


def test_host_plugin_api_uses_lan_not_domain():
    shop = ShopGlobalConfig(
        mode="host",
        host_ip="192.168.15.51",
        port=27199,
        public_url="https://arkland.com.br",
    )
    assert resolve_plugin_api_url(shop) == "http://192.168.15.51:27199"
    assert resolve_website_url(shop) == "https://arkland.com.br"


def test_host_plugin_api_fallback_localhost():
    shop = ShopGlobalConfig(
        mode="host",
        host_ip="",
        port=27199,
        public_url="https://arkland.com.br",
    )
    assert resolve_plugin_api_url(shop) == "http://127.0.0.1:27199"


def test_client_plugin_api_uses_domain():
    shop = ShopGlobalConfig(
        mode="client",
        central_url="https://arkland.com.br",
        public_url="https://arkland.com.br",
    )
    assert resolve_plugin_api_url(shop) == "https://arkland.com.br"


def test_host_plugin_website_uses_public_domain_not_ip():
    shop = ShopGlobalConfig(
        mode="host",
        host_ip="",
        public_ip="179.185.19.88",
        port=27199,
        public_url="https://arkland.com.br",
    )
    assert resolve_plugin_website_url(shop) == "https://arkland.com.br"
    assert resolve_website_url(shop) == "https://arkland.com.br"
    assert resolve_plugin_api_url(shop) == "http://127.0.0.1:27199"


def test_host_plugin_website_defaults_to_arkland_when_public_url_empty():
    shop = ShopGlobalConfig(
        mode="host",
        public_ip="179.185.19.88",
        port=27199,
        public_url="",
    )
    assert resolve_plugin_website_url(shop) == "https://arkland.com.br"


def test_is_stale_ip_website_url_detects_legacy():
    assert is_stale_ip_website_url("http://179.185.19.88:27199")
    assert is_stale_ip_website_url("https://arkland.com.br") is False


def test_needs_website_url_fix_only_for_ip_or_empty():
    desired = "https://arkland.com.br"
    assert needs_website_url_fix("http://179.185.19.88:27199", desired)
    assert needs_website_url_fix("", desired)
    assert not needs_website_url_fix("https://arkland.com.br", desired)


def test_fix_website_url_in_config_file(tmp_path: Path):
    cfg = tmp_path / "config.json"
    cfg.write_text(
        json.dumps({"Settings": {"WebsiteUrl": "http://179.185.19.88:27199"}}),
        encoding="utf-8",
    )
    changed, msg = fix_website_url_in_config_file(
        cfg, "https://arkland.com.br", server_name="TestMap",
    )
    assert changed
    assert "179.185.19.88" in msg
    data = json.loads(cfg.read_text(encoding="utf-8"))
    assert data["Settings"]["WebsiteUrl"] == "https://arkland.com.br"


def test_migrate_stale_plugin_website_urls_no_servers():
    shop = ShopGlobalConfig(public_url="https://arkland.com.br")

    class _CM:
        servers = []

    fixed, errs = migrate_stale_plugin_website_urls(_CM(), shop, asm_cm=None)
    assert fixed == []
    assert errs == []
