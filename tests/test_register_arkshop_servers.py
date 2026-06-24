"""Testes de sync ARKLAND → servers.json da loja web."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import pytest

from src.config_manager import ShopGlobalConfig
from src.shop_integration import register_arkshop_servers


@dataclass
class _FakeSrv:
    id: str
    name: str
    shop_server_id: str = ""
    shop_show_on_home: bool = True
    shop_exclude: bool = False
    install_dir: str = r"C:\ARK\test"
    server_ip: str = "192.168.1.10"
    rcon_port: int = 27020
    rcon_password: str = "secret"
    admin_password: str = ""
    customshop_config_path: str = ""


class _FakeCM:
    def __init__(self, servers=None):
        self.servers = servers or []


class _FakeAsmCM:
    def __init__(self, servers=None):
        self.servers = servers or []


@pytest.fixture
def shop_dir(tmp_path, monkeypatch):
    import src.shop_integration as si

    target = tmp_path / "arkshop_web"
    target.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(si, "webstore_data_dir", lambda: target)
    return target


def _host_shop(**kwargs) -> ShopGlobalConfig:
    return ShopGlobalConfig(mode="host", **kwargs)


def _load_servers(path: Path) -> list:
    return json.loads(path.read_text(encoding="utf-8"))


def test_register_upsert_and_arkland_ref(shop_dir):
    srv = _FakeSrv(id="tek-1", name="Fjordur", shop_server_id="fjordur")
    register_arkshop_servers(_FakeCM(), _host_shop(), asm_cm=_FakeAsmCM([srv]))
    data = _load_servers(shop_dir / "servers.json")
    assert len(data) == 1
    assert data[0]["server_id"] == "fjordur"
    assert data[0]["arkland_ref"] == "tek:tek-1"
    assert data[0]["show_on_home"] is True


def test_prune_removed_tek_server(shop_dir):
    servers_file = shop_dir / "servers.json"
    servers_file.write_text(
        json.dumps([
            {
                "server_id": "old_map",
                "label": "Old",
                "arkland_ref": "tek:deleted-id",
            },
            {
                "server_id": "fjordur",
                "label": "Fjordur",
                "arkland_ref": "tek:tek-1",
            },
        ]),
        encoding="utf-8",
    )
    srv = _FakeSrv(id="tek-1", name="Fjordur", shop_server_id="fjordur")
    register_arkshop_servers(_FakeCM(), _host_shop(), asm_cm=_FakeAsmCM([srv]))
    ids = {e["server_id"] for e in _load_servers(servers_file)}
    assert ids == {"fjordur"}


def test_rename_shop_server_id_removes_stale_entry(shop_dir):
    servers_file = shop_dir / "servers.json"
    servers_file.write_text(
        json.dumps([{
            "server_id": "crystal_isles",
            "label": "Crystal",
            "arkland_ref": "tek:tek-c",
        }]),
        encoding="utf-8",
    )
    srv = _FakeSrv(id="tek-c", name="Crystal", shop_server_id="crystal")
    register_arkshop_servers(_FakeCM(), _host_shop(), asm_cm=_FakeAsmCM([srv]))
    data = _load_servers(servers_file)
    assert len(data) == 1
    assert data[0]["server_id"] == "crystal"


def test_shop_exclude_removes_entry(shop_dir):
    servers_file = shop_dir / "servers.json"
    servers_file.write_text(
        json.dumps([{
            "server_id": "hidden",
            "label": "Hidden",
            "arkland_ref": "tek:tek-h",
        }]),
        encoding="utf-8",
    )
    srv = _FakeSrv(id="tek-h", name="Hidden", shop_server_id="hidden", shop_exclude=True)
    register_arkshop_servers(_FakeCM(), _host_shop(), asm_cm=_FakeAsmCM([srv]))
    assert _load_servers(servers_file) == []


def test_prune_scoped_by_machine_label(shop_dir):
    servers_file = shop_dir / "servers.json"
    servers_file.write_text(
        json.dumps([
            {
                "server_id": "other_map",
                "label": "Other",
                "arkland_ref": "tek:other-id",
                "machine_label": "Maquina-B",
            },
        ]),
        encoding="utf-8",
    )
    srv = _FakeSrv(id="tek-1", name="Fjordur", shop_server_id="fjordur")
    register_arkshop_servers(
        _FakeCM(), _host_shop(machine_label="Maquina-A"), asm_cm=_FakeAsmCM([srv]),
    )
    data = _load_servers(servers_file)
    ids = {e["server_id"] for e in data}
    assert "fjordur" in ids
    assert "other_map" in ids


def test_preserve_manual_server_without_arkland_ref(shop_dir):
    servers_file = shop_dir / "servers.json"
    servers_file.write_text(
        json.dumps([{
            "server_id": "manual1",
            "label": "Manual Server",
            "rcon_host": "10.0.0.5",
        }]),
        encoding="utf-8",
    )
    srv = _FakeSrv(id="tek-1", name="Fjordur", shop_server_id="fjordur")
    register_arkshop_servers(_FakeCM(), _host_shop(), asm_cm=_FakeAsmCM([srv]))
    data = _load_servers(servers_file)
    assert len(data) == 2
    manual = next(e for e in data if e["server_id"] == "manual1")
    assert manual["label"] == "Manual Server"
    assert not manual.get("arkland_ref")


def test_remote_register_calls_central_api(shop_dir, monkeypatch):
    import src.shop_integration as si

    captured: dict = {}

    class _Resp:
        def read(self):
            return json.dumps({"ok": True, "registered": 1}).encode()

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

    def _fake_urlopen(req, timeout=0):
        captured["url"] = req.full_url
        captured["body"] = json.loads(req.data.decode())
        captured["api_key"] = req.headers.get("X-api-key") or req.headers.get("X-API-Key")
        return _Resp()

    monkeypatch.setattr(si.urllib.request, "urlopen", _fake_urlopen)

    srv = _FakeSrv(id="tek-1", name="Volcano", shop_server_id="volcano")
    shop = ShopGlobalConfig(mode="client", central_url="https://cross.test", api_key="secret-key")
    shop.machine_label = "Maquina-B"
    n = register_arkshop_servers(_FakeCM(), shop, asm_cm=_FakeAsmCM([srv]))
    assert n == 1
    assert captured["url"].endswith("/api/servers/sync")
    assert captured["api_key"] == "secret-key"
    assert captured["body"]["machine_label"] == "Maquina-B"
    assert any(s["server_id"] == "volcano" for s in captured["body"]["servers"])
    assert not (shop_dir / "servers.json").exists()
