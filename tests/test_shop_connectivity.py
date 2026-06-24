"""Diagnóstico honesto da Web Store (local vs domínio)."""
from __future__ import annotations

from unittest.mock import patch

from src.config_manager import ShopGlobalConfig
from src.shop_integration import (
    ShopConnectivityReport,
    diagnose_shop_connectivity,
    diagnose_webstore_access,
)


def test_status_label_players_ok():
    r = ShopConnectivityReport(local_ok=True, public_ok=True)
    assert r.status_label() == "Online · jogadores"


def test_status_label_local_only():
    r = ShopConnectivityReport(local_ok=True, public_ok=False, lan_ok=False)
    assert r.status_label() == "Online · só local"


def test_host_ok_public_means_players_reachable():
    shop = ShopGlobalConfig(mode="host", host_ip="192.168.1.10", port=27199)
    report = ShopConnectivityReport(
        local_ok=True,
        lan_ok=True,
        public_ok=True,
        lines=["Domínio: OK"],
    )
    with patch("src.shop_integration.diagnose_shop_connectivity", return_value=report):
        ok, msg, local_ok = diagnose_webstore_access(shop)
    assert ok is True
    assert local_ok is True


def test_host_local_ok_public_fail_not_green():
    shop = ShopGlobalConfig(mode="host", host_ip="192.168.1.10", port=27199)
    report = ShopConnectivityReport(
        local_ok=True,
        lan_ok=True,
        public_ok=False,
        lines=["Local: OK", "Domínio: FALHOU"],
    )
    with patch("src.shop_integration.diagnose_shop_connectivity", return_value=report):
        ok, msg, local_ok = diagnose_webstore_access(shop)
    assert ok is False
    assert local_ok is True
    assert "Domínio" in msg


def test_diagnose_flags_caddy_down():
    shop = ShopGlobalConfig(
        mode="host",
        host_ip="192.168.15.51",
        public_url="https://arkland.com.br",
        public_ip="1.2.3.4",
        port=27199,
    )

    def _fake_test(url: str, api_key: str = ""):
        if url.startswith("http://127.0.0.1"):
            return True, "ok"
        if "192.168" in url:
            return True, "ok"
        return False, "timeout"

    with patch("src.shop_integration.test_shop_connection", side_effect=_fake_test), patch(
        "src.shop_integration.fetch_public_ip", return_value=(True, "1.2.3.4")
    ), patch("src.shop_integration.resolve_dns_ipv4", return_value=(True, "1.2.3.4")), patch(
        "src.caddy_proxy._port_open", return_value=False
    ):
        report = diagnose_shop_connectivity(shop)

    assert report.local_ok
    assert not report.public_ok
    assert any("Caddy" in line for line in report.lines)
