"""Diagnóstico honesto da Web Store (local vs domínio vs internet)."""
from __future__ import annotations

from unittest.mock import patch

from src.config_manager import ShopGlobalConfig
from src.shop_integration import (
    ShopConnectivityReport,
    diagnose_shop_connectivity,
    diagnose_webstore_access,
    probe_local_caddy_https,
)


def test_status_label_players_ok():
    r = ShopConnectivityReport(local_ok=True, public_ok=True, www_ok=True, wan_ok=True)
    assert r.status_label() == "Online · jogadores"


def test_status_label_modem_blocks():
    r = ShopConnectivityReport(local_ok=True, public_ok=True, wan_ok=False)
    assert r.status_label() == "Online · modem bloqueia"


def test_status_label_caddy_local_only():
    r = ShopConnectivityReport(local_ok=True, public_ok=True, wan_ok=None)
    assert r.status_label() == "Online · Caddy local"


def test_host_players_ok_requires_wan():
    shop = ShopGlobalConfig(mode="host", host_ip="192.168.1.10", port=27199)
    report = ShopConnectivityReport(
        local_ok=True,
        lan_ok=True,
        public_ok=True,
        www_ok=True,
        wan_ok=False,
        lines=["Internet: FALHOU"],
    )
    with patch("src.shop_integration.diagnose_shop_connectivity", return_value=report):
        ok, msg, local_ok = diagnose_webstore_access(shop)
    assert ok is False
    assert local_ok is True


def test_host_full_ok():
    shop = ShopGlobalConfig(mode="host", host_ip="192.168.1.10", port=27199)
    report = ShopConnectivityReport(
        local_ok=True,
        public_ok=True,
        www_ok=True,
        wan_ok=True,
        lines=["Internet: OK"],
    )
    with patch("src.shop_integration.diagnose_shop_connectivity", return_value=report):
        ok, msg, local_ok = diagnose_webstore_access(shop)
    assert ok is True


def test_diagnose_flags_modem_when_wan_closed():
    shop = ShopGlobalConfig(
        mode="host",
        host_ip="192.168.15.51",
        public_url="https://arkland.com.br",
        public_ip="1.2.3.4",
        port=27199,
    )

    def _fake_test(url: str, api_key: str = ""):
        if url.startswith("http://127.0.0.1") and ":27199" in url:
            return True, "ok"
        if "192.168" in url:
            return True, "ok"
        return False, "timeout"

    with patch("src.shop_integration.test_shop_connection", side_effect=_fake_test), patch(
        "src.shop_integration.probe_local_caddy_https", return_value=(True, "ok")
    ), patch("src.shop_integration.fetch_public_ip", return_value=(True, "1.2.3.4")), patch(
        "src.shop_integration.resolve_dns_ipv4", return_value=(True, "1.2.3.4")
    ), patch("src.shop_integration.probe_wan_tcp_port", return_value=(False, "fechada")), patch(
        "src.caddy_proxy._port_open", return_value=True
    ):
        report = diagnose_shop_connectivity(shop)

    assert report.public_ok
    assert report.wan_ok is False
    assert not report.players_ok
    assert any("modem" in line.lower() for line in report.lines)


def test_local_caddy_uses_host_header():
    with patch("urllib.request.urlopen") as mock_open:
        mock_open.return_value.__enter__.return_value.status = 200
        ok, msg = probe_local_caddy_https("arkland.com.br")
    assert ok is True
    req = mock_open.call_args[0][0]
    assert req.get_header("Host") == "arkland.com.br"
