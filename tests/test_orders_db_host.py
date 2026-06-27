"""Testes para normalização de host MySQL nos plugins CustomShop."""
from __future__ import annotations

from unittest.mock import patch

from src.config_manager import ShopGlobalConfig
from src.shop_integration import (
    build_permissions_config_settings,
    build_plugin_database_settings,
    normalize_orders_db_host,
)


def test_normalize_orders_db_host_empty_defaults_localhost():
    shop = ShopGlobalConfig(orders_db_host="")
    with patch("src.pages.db_local_server.DbLocalServer.get_bind_lan", return_value=False):
        assert normalize_orders_db_host(shop) == "127.0.0.1"


def test_normalize_orders_db_host_lan_ip_to_localhost_when_bind_localhost_only():
    shop = ShopGlobalConfig(orders_db_host="192.168.1.50")
    with patch("src.pages.db_local_server.DbLocalServer.get_bind_lan", return_value=False), patch(
        "src.shop_integration.get_local_ip", return_value="192.168.1.50"
    ):
        assert normalize_orders_db_host(shop) == "127.0.0.1"


def test_normalize_orders_db_host_keeps_remote_lan_when_bind_localhost_only():
    shop = ShopGlobalConfig(orders_db_host="192.168.15.51")
    with patch("src.pages.db_local_server.DbLocalServer.get_bind_lan", return_value=False), patch(
        "src.shop_integration.get_local_ip", return_value="192.168.1.50"
    ):
        assert normalize_orders_db_host(shop) == "192.168.15.51"


def test_normalize_orders_db_host_keeps_lan_ip_when_bind_lan_enabled():
    shop = ShopGlobalConfig(orders_db_host="192.168.1.50")
    with patch("src.pages.db_local_server.DbLocalServer.get_bind_lan", return_value=True), patch(
        "src.shop_integration.get_local_ip", return_value="192.168.1.50"
    ):
        assert normalize_orders_db_host(shop) == "192.168.1.50"


def test_build_plugin_database_settings_uses_localhost_for_same_pc():
    shop = ShopGlobalConfig(
        orders_db_host="192.168.1.50",
        orders_db_user="arkland",
        orders_db_password="secret",
    )
    with patch("src.pages.db_local_server.DbLocalServer.get_bind_lan", return_value=False), patch(
        "src.shop_integration.get_local_ip", return_value="192.168.1.50"
    ), patch(
        "src.db_setup_resources.probe_mysql_host",
        return_value=("127.0.0.1", "Conectado"),
    ):
        db = build_plugin_database_settings(shop)
    assert db["Host"] == "127.0.0.1"
    assert db["Password"] == "secret"


def test_build_permissions_config_settings_normalizes_host():
    shop = ShopGlobalConfig(orders_db_host="192.168.1.50", orders_db_user="arkland")
    with patch("src.pages.db_local_server.DbLocalServer.get_bind_lan", return_value=False), patch(
        "src.shop_integration.get_local_ip", return_value="192.168.1.50"
    ), patch("src.shop_integration.resolve_shop_db_password", return_value="pwd"):
        cfg = build_permissions_config_settings(shop)
    assert cfg["MysqlHost"] == "127.0.0.1"
    assert cfg["MysqlPass"] == "pwd"
