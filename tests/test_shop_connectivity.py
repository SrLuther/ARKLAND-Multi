"""Diagnóstico honesto da Web Store (local vs domínio vs internet)."""
from __future__ import annotations

from unittest.mock import patch

from src.config_manager import ShopGlobalConfig
from src.shop_integration import (
    ShopConnectivityReport,
    diagnose_shop_connectivity,
    diagnose_webstore_access,
    get_shop_subprocess_env,
    probe_public_https,
    resolve_web_secret,
)


def test_status_label_players_ok():
    r = ShopConnectivityReport(local_ok=True, public_ok=True, www_ok=True)
    assert r.status_label() == "Online · jogadores"


def test_status_label_lan_only():
    r = ShopConnectivityReport(local_ok=True, lan_ok=True, public_ok=False)
    assert r.status_label() == "Online · LAN"


def test_status_label_domain_partial():
    r = ShopConnectivityReport(local_ok=True, public_ok=True, www_ok=False)
    assert r.status_label() == "Online · domínio parcial"


def test_host_players_ok_when_https_works():
    shop = ShopGlobalConfig(mode="host", host_ip="192.168.1.10", port=27199)
    report = ShopConnectivityReport(
        local_ok=True,
        lan_ok=True,
        public_ok=True,
        www_ok=True,
        lines=["HTTPS: OK"],
    )
    with patch("src.shop_integration.diagnose_shop_connectivity", return_value=report):
        ok, msg, local_ok = diagnose_webstore_access(shop)
    assert ok is True
    assert local_ok is True


def test_host_not_ok_when_domain_fails():
    shop = ShopGlobalConfig(mode="host", host_ip="192.168.1.10", port=27199)
    report = ShopConnectivityReport(
        local_ok=True,
        lan_ok=True,
        public_ok=False,
        www_ok=False,
        lines=["HTTPS: FALHOU"],
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
        lines=["HTTPS: OK"],
    )
    with patch("src.shop_integration.diagnose_shop_connectivity", return_value=report):
        ok, msg, local_ok = diagnose_webstore_access(shop)
    assert ok is True


def test_diagnose_uses_public_https():
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
        if url.startswith("https://arkland.com.br"):
            return True, "loja online"
        if url.startswith("https://www.arkland.com.br"):
            return True, "www ok"
        return False, "timeout"

    with patch("src.shop_integration.test_shop_connection", side_effect=_fake_test), patch(
        "src.shop_integration.fetch_public_ip", return_value=(True, "1.2.3.4")
    ), patch("src.shop_integration.resolve_dns_ipv4", return_value=(True, "104.21.0.1")):
        report = diagnose_shop_connectivity(shop)

    assert report.public_ok
    assert report.www_ok
    assert report.players_ok
    assert any("HTTPS (arkland.com.br)" in line for line in report.lines)
    assert not any("Caddy" in line for line in report.lines)


def test_probe_public_https_delegates_to_shop_connection():
    with patch("src.shop_integration.test_shop_connection", return_value=(True, "ok")) as mock:
        ok, msg = probe_public_https("arkland.com.br")
    assert ok is True
    mock.assert_called_once_with("https://arkland.com.br")


def test_resolve_web_secret_persists_and_reuses(tmp_path, monkeypatch):
    monkeypatch.delenv("ARKSHOP_WEB_SECRET", raising=False)
    monkeypatch.setattr("src.shop_integration.webstore_data_dir", lambda: tmp_path)

    first = resolve_web_secret()
    second = resolve_web_secret()

    assert first
    assert first == second
    assert (tmp_path / "web_secret.txt").read_text(encoding="utf-8").strip() == first


def test_get_shop_subprocess_env_includes_web_secret(tmp_path, monkeypatch):
    monkeypatch.delenv("ARKSHOP_WEB_SECRET", raising=False)
    monkeypatch.setattr("src.shop_integration.webstore_data_dir", lambda: tmp_path)

    shop = ShopGlobalConfig(mode="host", api_key="test-key")
    env = get_shop_subprocess_env(shop)

    assert env["ARKSHOP_WEB_SECRET"]
    assert env["ARKSHOP_API_KEY"] == "test-key"


def test_get_shop_subprocess_env_loads_steam_api_key_from_dotenv(tmp_path, monkeypatch):
    monkeypatch.delenv("STEAM_API_KEY", raising=False)
    monkeypatch.setattr("src.shop_integration.webstore_data_dir", lambda: tmp_path)
    monkeypatch.setattr("src.shop_integration._PROJECT_ROOT", tmp_path)
    (tmp_path / ".env").write_text("STEAM_API_KEY=from-dotenv-key\n", encoding="utf-8")

    shop = ShopGlobalConfig(mode="host")
    env = get_shop_subprocess_env(shop)

    assert env["STEAM_API_KEY"] == "from-dotenv-key"
