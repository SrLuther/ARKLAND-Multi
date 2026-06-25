"""WebApiUrl dos plugins — LAN no host, domínio no cliente."""
from __future__ import annotations

from src.config_manager import ShopGlobalConfig
from src.shop_integration import (
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
