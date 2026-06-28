"""Dropdown de licenças no painel Gerenciar Jogadores."""
from __future__ import annotations

import json

import pytest

import app as _app_module
from app import app

ADMIN_STEAM = "76561198000000001"
USER_STEAM = "76561198000000002"


@pytest.fixture(autouse=True)
def _admin_env(tmp_path, monkeypatch):
    monkeypatch.setenv("ARKSHOP_WEB_SECRET", "test-secret")
    monkeypatch.setattr(_app_module, "_ADMIN_FILE", tmp_path / "admin_steamids.json")
    monkeypatch.setattr(_app_module, "_STATE_FILE", tmp_path / "settings.json")
    (tmp_path / "admin_steamids.json").write_text(json.dumps([ADMIN_STEAM]), encoding="utf-8")
    yield


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def _login(client, steam_id: str) -> None:
    with client.session_transaction() as sess:
        sess["steam_id"] = steam_id


def _write_catalog(path, items: dict) -> None:
    path.write_text(
        json.dumps({"Items": items, "Kits": {}}, ensure_ascii=False),
        encoding="utf-8",
    )


def test_catalog_license_options_lists_all_license_types(tmp_path, monkeypatch):
    full = tmp_path / "full.json"
    stub = tmp_path / "stub.json"
    _write_catalog(
        full,
        {
            "licenca_gamma": {
                "Type": "license",
                "Description": "Licença Gamma (30 dias)",
                "LicenseGrant": {"Group": "Gamma", "Days": 30},
            },
            "licenca_nuvem": {
                "Type": "command",
                "Category": "Licenças",
                "Description": "Licença de Nuvem (30 dias)",
                "LicenseGrant": {"Group": "keyvault", "Days": 30},
            },
            "licenca_vip_bronze": {
                "Type": "license",
                "Description": "Licença VIP Bronze (30 dias)",
                "LicenseGrant": {"Group": "VIPBronze", "Days": 30},
            },
        },
    )
    _write_catalog(
        stub,
        {
            "licenca_vip_bronze": {
                "Type": "license",
                "Description": "Licença VIP Bronze (30 dias)",
                "LicenseGrant": {"Group": "VIPBronze", "Days": 30},
            },
            "licenca_vip_prata": {
                "Type": "license",
                "Description": "Licença VIP Prata (30 dias)",
                "LicenseGrant": {"Group": "VIPPrata", "Days": 30},
            },
        },
    )
    monkeypatch.setattr(
        _app_module,
        "_read_shop_config",
        lambda: json.loads(stub.read_text(encoding="utf-8")),
    )
    monkeypatch.setattr(
        _app_module,
        "_collect_catalog_search_paths",
        lambda: [stub, full],
    )
    _app_module._invalidate_shop_config_cache()

    opts = _app_module._catalog_license_options()
    groups = {o["group"] for o in opts}
    assert groups == {"Gamma", "keyvault", "VIPBronze"}
    gamma = next(o for o in opts if o["group"] == "Gamma")
    assert gamma["label"].startswith("Licença Gamma")
    assert gamma["item_id"] == "licenca_gamma"
    assert gamma["days"] == 30


def test_catalog_license_group_from_type_without_grant():
    entry = {
        "Type": "license",
        "Description": "Licença Beta legada",
        "Permissions": "Admins,Beta",
    }
    assert _app_module._catalog_license_group(entry, "licenca_beta") == "Beta"


def test_get_license_grant_nuvem_from_item_id_without_block():
    entry = {
        "Type": "command",
        "Category": "Licenças",
        "Description": "Licença de Nuvem (30 dias)",
        "Commands": ["Permissions.AddTimed {SteamID} keyvault 720"],
    }
    lic = _app_module._get_license_grant(entry, "licenca_nuvem")
    assert lic is not None
    assert lic["Group"] == "keyvault"
    assert lic["Days"] == 30


def test_get_license_grant_from_commands_only():
    entry = {
        "Type": "command",
        "Description": "Licença legada",
        "Commands": ["Permissions.AddTimed {SteamID} keyvault 168"],
    }
    lic = _app_module._get_license_grant(entry, "item_x")
    assert lic == {"Group": "keyvault", "Days": 7, "Redeemable": True}


def test_admin_license_catalog_endpoint(client, tmp_path, monkeypatch):
    catalog = tmp_path / "catalog.json"
    _write_catalog(
        catalog,
        {
            "licenca_alfa": {
                "Type": "license",
                "Description": "Licença Alfa (30 dias)",
                "LicenseGrant": {"Group": "Alfa", "Days": 30},
            },
        },
    )
    monkeypatch.setattr(
        _app_module,
        "_read_shop_config",
        lambda: json.loads(catalog.read_text(encoding="utf-8")),
    )
    monkeypatch.setattr(_app_module, "_collect_catalog_search_paths", lambda: [catalog])
    _app_module._invalidate_shop_config_cache()

    _login(client, ADMIN_STEAM)
    r = client.get("/api/admin/license-catalog")
    d = r.get_json()
    assert d["ok"] is True
    assert len(d["items"]) == 1
    assert d["items"][0]["group"] == "Alfa"
    assert "Alfa" in d["items"][0]["label"]


def test_admin_license_catalog_forbidden_for_player(client):
    _login(client, USER_STEAM)
    r = client.get("/api/admin/license-catalog")
    assert r.status_code == 403
