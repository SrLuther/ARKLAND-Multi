"""Ações em lote — Itens da Loja (admin): aba Dinossauros (market_include/market_exclude/delete)."""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

import app as _app_module
from app import app

ADMIN_STEAM = "76561198000000001"
USER_STEAM = "76561198000000099"
URL = "/api/admin/shop-items/bulk"
INDEX_HTML = Path(__file__).resolve().parents[1] / "static" / "index.html"


def _catalog() -> dict:
    return {
        "Settings": {"ServerId": "master"},
        "Items": {
            "ab_achatina_aberrante": {"Type": "dino", "Name": "[AB] Achatina Aberrante", "Price": 100,
                                       "Dinos": [{"Blueprint": "/Game/Achatina.Achatina_C", "Level": 1}]},
            "rex_f": {"Type": "dino", "Name": "Rex F", "Price": 500, "MarketInclude": True,
                      "Dinos": [{"Blueprint": "/Game/Rex.Rex_C", "Level": 1}]},
            "giga": {"Type": "dino", "Name": "Giga", "Price": 900,
                     "Dinos": [{"Blueprint": "/Game/Giga.Giga_C", "Level": 1}]},
            "metal_100": {"Type": "item", "Name": "Metal x100", "Price": 10, "Blueprint": "/Game/Metal.Metal_C"},
        },
        "Kits": {"k1": {"Description": "kit", "Price": 1, "Items": []}},
    }


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("ARKSHOP_WEB_SECRET", "test-secret")
    monkeypatch.setattr(_app_module, "_ADMIN_FILE", tmp_path / "admin_steamids.json")
    monkeypatch.setattr(_app_module, "_STATE_FILE", tmp_path / "settings.json")
    (tmp_path / "admin_steamids.json").write_text(json.dumps([ADMIN_STEAM]), encoding="utf-8")
    master = tmp_path / "master" / "config.json"
    master.parent.mkdir(parents=True)
    master.write_text(json.dumps(_catalog()), encoding="utf-8")
    settings = {"config_path": str(master)}
    monkeypatch.setattr(_app_module, "_load_settings", lambda: dict(settings))
    monkeypatch.setattr(_app_module, "_plugin_sync_targets", lambda s: [
        {"label": "Catálogo mestre", "path": str(master), "kind": "master"},
    ])
    reloads: list[int] = []
    monkeypatch.setattr(_app_module, "_enqueue_shop_reload", lambda s=None: reloads.append(1) or [])
    monkeypatch.setattr("src.shop_integration.push_catalog_to_webstore", lambda *a, **k: None)
    monkeypatch.setattr("catalog_feed_service.maybe_feed_on_catalog_save", lambda *a, **k: None)
    audits: list[tuple] = []
    monkeypatch.setattr(_app_module, "_audit_event", lambda ev, **kw: audits.append((ev, kw)))
    monkeypatch.setattr(_app_module, "_db_ready", lambda: False)
    _app_module._invalidate_shop_config_cache()
    app.config["TESTING"] = True
    yield {"master": master, "reloads": reloads, "audits": audits}
    _app_module._invalidate_shop_config_cache()


@pytest.fixture
def client(env):
    with app.test_client() as c:
        yield c


def _login(client, steam_id: str) -> None:
    with client.session_transaction() as sess:
        sess["steam_id"] = steam_id


def _saved_items(master: Path) -> dict:
    data = json.loads(master.read_text(encoding="utf-8"))
    return data.get("Items") or data.get("ShopItems") or {}


# ── Permissão ────────────────────────────────────────────────────────────────
def test_bulk_requires_admin_anonymous(client, env):
    r = client.post(URL, json={"action": "delete", "ids": ["giga"], "confirm": True})
    assert r.status_code in (401, 403)
    assert "giga" in _saved_items(env["master"])


def test_bulk_denied_for_non_admin(client, env):
    _login(client, USER_STEAM)
    r = client.post(URL, json={"action": "delete", "ids": ["giga"], "confirm": True})
    assert r.status_code in (401, 403)
    assert "giga" in _saved_items(env["master"])


# ── Validação de entrada ─────────────────────────────────────────────────────
@pytest.mark.parametrize("payload", [
    {},
    {"action": "explode", "ids": ["giga"]},
    {"action": "market_include"},
    {"action": "market_include", "ids": []},
    {"action": "market_include", "ids": "giga"},
    {"action": "market_include", "ids": [123]},
    {"action": "market_include", "ids": ["   "]},
    {"action": "market_include", "ids": ["x" * 201]},
])
def test_bulk_rejects_invalid_input(client, env, payload):
    _login(client, ADMIN_STEAM)
    r = client.post(URL, json=payload)
    assert r.status_code == 400
    assert r.get_json()["ok"] is False


def test_bulk_rejects_non_object_body(client, env):
    _login(client, ADMIN_STEAM)
    r = client.post(URL, json=["giga"])
    assert r.status_code == 400


def test_bulk_rejects_too_many_ids(client, env):
    _login(client, ADMIN_STEAM)
    ids = [f"id_{i}" for i in range(_app_module.SHOP_BULK_MAX_IDS + 1)]
    r = client.post(URL, json={"action": "market_include", "ids": ids})
    assert r.status_code == 400
    assert str(_app_module.SHOP_BULK_MAX_IDS) in r.get_json()["error"]


def test_bulk_delete_requires_confirm(client, env):
    _login(client, ADMIN_STEAM)
    r = client.post(URL, json={"action": "delete", "ids": ["giga"]})
    assert r.status_code == 400
    assert "giga" in _saved_items(env["master"])
    r = client.post(URL, json={"action": "delete", "ids": ["giga"], "confirm": "true"})
    assert r.status_code == 400
    assert "giga" in _saved_items(env["master"])


# ── IDs inexistentes / não-dino ──────────────────────────────────────────────
def test_bulk_unknown_ids_reported_and_nothing_written(client, env):
    _login(client, ADMIN_STEAM)
    before = env["master"].read_text(encoding="utf-8")
    r = client.post(URL, json={"action": "market_include", "ids": ["nao_existe"]})
    assert r.status_code == 422
    body = r.get_json()
    assert body["ok"] is False and body["succeeded"] == 0 and body["failed"] == 1
    assert body["results"][0] == {"id": "nao_existe", "ok": False, "error": "Item não encontrado no catálogo."}
    assert env["master"].read_text(encoding="utf-8") == before
    assert env["reloads"] == []


def test_bulk_non_dino_item_rejected_per_item(client, env):
    _login(client, ADMIN_STEAM)
    r = client.post(URL, json={"action": "delete", "ids": ["metal_100", "giga"], "confirm": True})
    assert r.status_code == 200
    body = r.get_json()
    by_id = {x["id"]: x for x in body["results"]}
    assert by_id["metal_100"]["ok"] is False
    assert by_id["giga"]["ok"] is True
    assert body["ok"] is False and body["succeeded"] == 1 and body["failed"] == 1
    items = _saved_items(env["master"])
    assert "metal_100" in items and "giga" not in items


# ── Incluir / remover do Comércio ────────────────────────────────────────────
def test_bulk_market_include_sets_flag_and_preregisters(client, env, monkeypatch):
    _login(client, ADMIN_STEAM)
    monkeypatch.setattr(_app_module, "_db_ready", lambda: True)

    class _DB:
        def close(self): pass
        def rollback(self): pass

    monkeypatch.setattr(_app_module, "_db_session_factory", lambda: _DB())
    called: list[str] = []

    def _pre(db, catalog, item_id):
        called.append(item_id)
        assert item_id in (catalog.get("Items") or catalog.get("ShopItems"))
        return {"species_key": item_id, "status": "PRE_REGISTERED"}

    monkeypatch.setattr("market_service.pre_register_catalog_item", _pre)
    r = client.post(URL, json={"action": "market_include", "ids": ["ab_achatina_aberrante", "giga", "giga"]})
    assert r.status_code == 200
    body = r.get_json()
    assert body["ok"] is True and body["requested"] == 2 and body["succeeded"] == 2
    assert all(x["status"] == "market_included" for x in body["results"])
    assert sorted(called) == ["ab_achatina_aberrante", "giga"]
    items = _saved_items(env["master"])
    assert items["ab_achatina_aberrante"]["MarketInclude"] is True
    assert items["giga"]["MarketInclude"] is True
    assert "MarketInclude" not in items["metal_100"]
    assert items["ab_achatina_aberrante"]["Name"] == "[AB] Achatina Aberrante"
    assert env["reloads"] == [1]  # Shop.Reload uma vez, como o salvar individual
    assert env["audits"] and env["audits"][0][0] == "SHOP_ITEMS_BULK_MARKET_INCLUDE"


def test_bulk_market_include_without_db_still_saves_flag_with_warning(client, env):
    _login(client, ADMIN_STEAM)
    r = client.post(URL, json={"action": "market_include", "ids": ["giga"]})
    assert r.status_code == 200
    res = r.get_json()["results"][0]
    assert res["ok"] is True and "warning" in res
    assert _saved_items(env["master"])["giga"]["MarketInclude"] is True


def test_bulk_market_exclude_removes_flag(client, env):
    _login(client, ADMIN_STEAM)
    assert _saved_items(env["master"])["rex_f"]["MarketInclude"] is True
    r = client.post(URL, json={"action": "market_exclude", "ids": ["rex_f"], "reload": False})
    assert r.status_code == 200 and r.get_json()["ok"] is True
    assert "MarketInclude" not in _saved_items(env["master"])["rex_f"]
    assert env["reloads"] == []  # reload=false respeitado


# ── Deletar ──────────────────────────────────────────────────────────────────
def test_bulk_delete_removes_items_keeps_rest(client, env):
    _login(client, ADMIN_STEAM)
    r = client.post(URL, json={"action": "delete", "ids": ["giga", "rex_f"], "confirm": True})
    assert r.status_code == 200
    body = r.get_json()
    assert body["ok"] is True and body["succeeded"] == 2
    assert [x["status"] for x in body["results"]] == ["deleted", "deleted"]
    saved = json.loads(env["master"].read_text(encoding="utf-8"))
    items = saved.get("Items") or saved.get("ShopItems")
    assert set(items) == {"ab_achatina_aberrante", "metal_100"}
    assert "k1" in saved["Kits"]  # kits intactos
    assert env["audits"][0][0] == "SHOP_ITEMS_BULK_DELETE"
    assert env["audits"][0][1]["item_ids"] == ["giga", "rex_f"]


def test_bulk_delete_refuses_when_catalog_empty(client, env):
    _login(client, ADMIN_STEAM)
    env["master"].write_text(json.dumps({"Items": {}, "Kits": {}}), encoding="utf-8")
    _app_module._invalidate_shop_config_cache()
    r = client.post(URL, json={"action": "delete", "ids": ["giga"], "confirm": True})
    assert r.status_code in (409, 500)
    assert r.get_json()["ok"] is False


# ── Markup / JS (aba Dinossauros + lote) ─────────────────────────────────────
def _html() -> str:
    return INDEX_HTML.read_text(encoding="utf-8")


def test_markup_has_shop_admin_tabs_and_bulk_bar():
    html = _html()
    page = html[html.index('id="page-shop"'):]
    page = page[: page.index('id="page-kits"')]
    assert 'data-shop-admin-tab="dino"' in page and 'data-shop-admin-tab="item"' in page
    assert 'id="shop-admin-search"' in page and 'id="shop-bulk-bar"' in page
    assert "Buscar nome, ID, categoria" in page


def test_js_bulk_ui_wiring():
    html = _html()
    for token in (
        "function setShopAdminTab",
        "function shopBulkToggleAll",
        "function shopBulkToggleRow",
        "async function shopBulkRun",
        "/api/admin/shop-items/bulk",
        'shop-bulk-select-all',
        "SHOP_BULK_ACTIONS",
    ):
        assert token in html, token
    actions = re.findall(r'\{ action: "(\w+)"', html)
    assert {"market_include", "market_exclude", "delete"} <= set(actions)
    # delete exige confirmação explícita com quantidade
    assert "DELETAR ${n}" in html and "confirm(spec.confirm(" in html
    # critério de dino reutilizado (_isDinoType) na aba
    render = html[html.index("function renderShop()"):]
    render = render[: render.index("function renderKits()")]
    assert "_isDinoType(items[k]?.Type)" in render
