"""Testes do import admin de config.json (mestre + propagação + relatório)."""
from __future__ import annotations

import io
import json
from pathlib import Path

import pytest

import app as _app_module
from app import app

ADMIN_STEAM = "76561198000000001"


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


def test_catalog_import_requires_admin(client):
    data = {
        "Items": {"sword": {"Price": 1}},
        "Kits": {},
    }
    r = client.post(
        "/api/admin/catalog/import",
        data={"file": (io.BytesIO(json.dumps(data).encode("utf-8")), "config.json")},
        content_type="multipart/form-data",
    )
    assert r.status_code in (401, 403)


def test_catalog_import_writes_master_and_reports_stages(client, tmp_path, monkeypatch):
    _login(client, ADMIN_STEAM)
    master = tmp_path / "CustomShop" / "configs" / "config.json"
    map_cfg = tmp_path / "Ragnarok" / "ShooterGame" / "Binaries" / "Win64" / "ArkApi" / "Plugins" / "CustomShop" / "config.json"
    map_cfg.parent.mkdir(parents=True, exist_ok=True)
    map_cfg.write_text(
        json.dumps({
            "Settings": {"ServerId": "ragnarok"},
            "Database": {"Password": "keep-me"},
            "Items": {"old": {"Price": 1}},
            "Kits": {},
        }),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        _app_module,
        "canonical_master_catalog_path",
        lambda: master,
    )
    monkeypatch.setattr(
        "src.shop_integration.canonical_master_catalog_path",
        lambda: master,
    )
    monkeypatch.setattr(_app_module, "_load_settings", lambda: {
        "config_path": str(master),
        "rcon_host": "127.0.0.1",
        "rcon_port": 27020,
        "rcon_password": "",
    })
    monkeypatch.setattr(_app_module, "_plugin_sync_targets", lambda settings: [
        {"label": "Catálogo mestre", "path": str(master), "kind": "master"},
        {"label": "Ragnarok", "path": str(map_cfg), "kind": "server"},
    ])
    monkeypatch.setattr(_app_module, "_discover_local_rcon_servers", lambda: [])
    monkeypatch.setattr(_app_module, "_reload_all_plugins", lambda settings: [{
        "server_id": "ragnarok",
        "label": "Ragnarok",
        "ok": True,
        "status": "ok",
        "connectivity": "ok",
        "command_sent": True,
        "command": "Shop.Reload",
        "response": "Reloaded",
        "endpoint": "127.0.0.1:27020",
        "rcon_host": "127.0.0.1",
        "rcon_port": 27020,
        "plugin_config_path": str(map_cfg),
    }])
    monkeypatch.setattr(_app_module, "_invalidate_shop_config_cache", lambda: None)
    monkeypatch.setattr(
        _app_module,
        "write_and_propagate_master_catalog",
        lambda catalog, map_targets=None, skip_shrink_guard=False: {
            "ok": True,
            "master_path": str(master),
            "items": 1,
            "kits": 0,
            "stages": [
                {
                    "id": "master_written",
                    "label": "Mestre gravado",
                    "status": "ok",
                    "path": str(master),
                    "items": 1,
                    "kits": 0,
                    "detail": str(master),
                },
                {
                    "id": "webstore",
                    "label": "WEBSTORE atualizada",
                    "status": "ok",
                    "path": str(tmp_path / "webstore" / "config.json"),
                    "detail": "ok",
                },
                {
                    "id": "bin_mirror",
                    "label": "Espelho bin/config.json",
                    "status": "skipped",
                    "detail": "n/a",
                },
                {
                    "id": "maps_written",
                    "label": "Configs dos mapas gravados",
                    "status": "ok",
                    "detail": "1 ok",
                    "maps_ok": 1,
                    "maps_fail": 0,
                },
            ],
            "maps": [{
                "label": "Ragnarok",
                "path": str(map_cfg),
                "status": "ok",
                "items": 1,
                "kits": 0,
                "detail": "gravado",
            }],
            "notes": ["Mestre gravado", "Mapa substituído ← mestre: Ragnarok"],
            "errors": [],
            "maps_updated": 1,
            "kits_sanitized": 0,
        },
    )

    # Também grava o mestre de verdade para provar o path (serviço mockado acima)
    master.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "Items": {"sword": {"Price": 10, "Description": "x"}},
        "Kits": {},
    }
    r = client.post(
        "/api/admin/catalog/import",
        data={
            "file": (io.BytesIO(json.dumps(payload).encode("utf-8")), "config.json"),
            "reload": "1",
        },
        content_type="multipart/form-data",
    )
    assert r.status_code == 200, r.get_data(as_text=True)
    body = r.get_json()
    assert body["ok"] is True
    assert body["overall"] in ("success", "partial")
    assert body["master_path"] == str(master)
    stage_ids = [s["id"] for s in body["stages"]]
    assert "parse" in stage_ids
    assert "master_written" in stage_ids
    assert "rcon_reload" in stage_ids
    assert body["maps"][0]["label"] == "Ragnarok"
    assert body["rcon"][0]["status"] == "ok"
    assert body["rcon"][0]["connectivity"] == "ok"
    assert body["rcon"][0]["command_sent"] is True
    assert body["rcon"][0].get("file_written") is True


def test_write_and_propagate_master_catalog_unit(tmp_path, monkeypatch):
    from src.shop_integration import write_and_propagate_master_catalog

    master = tmp_path / "configs" / "config.json"
    map_a = tmp_path / "mapA" / "config.json"
    map_a.parent.mkdir(parents=True)
    map_a.write_text(
        json.dumps({
            "Settings": {"ServerId": "mapaA"},
            "Database": {"Password": "secret-db"},
            "Items": {},
            "Kits": {},
        }),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "src.shop_integration.canonical_master_catalog_path",
        lambda: master,
    )
    monkeypatch.setattr(
        "src.shop_integration.push_catalog_to_webstore",
        lambda src: None,
    )
    monkeypatch.setattr(
        "src.shop_integration.webstore_data_dir",
        lambda: tmp_path / "webstore",
    )
    monkeypatch.setattr(
        "src.shop_integration._mirror_master_to_bin",
        lambda m: None,
    )

    catalog = {
        "Items": {"pick": {"Price": 5}},
        "Kits": {"starter": {"Price": 0}},
    }
    report = write_and_propagate_master_catalog(
        catalog,
        map_targets=[("Mapa A", map_a)],
        skip_shrink_guard=True,
    )
    assert report["ok"] is True
    assert master.is_file()
    assert Path(report["master_path"]) == master
    assert any(s["id"] == "master_written" and s["status"] == "ok" for s in report["stages"])
    assert report["maps"][0]["status"] == "ok"
    saved_map = json.loads(map_a.read_text(encoding="utf-8"))
    assert saved_map["Settings"]["ServerId"] == "mapaA"
    assert saved_map["Database"]["Password"] == "secret-db"
    assert "pick" in saved_map["Items"]


def test_classify_rcon_error():
    assert _app_module._classify_rcon_error(TimeoutError("timed out")) == "timeout"
    assert _app_module._classify_rcon_error("Connection refused") == "refused"
    assert _app_module._classify_rcon_error("Authentication failed") == "auth_fail"
