"""Testes Season Pass config + admin API + claim queue stub."""
from __future__ import annotations

import json

import pytest

import app as _app_module
from app import app
import season_pass_config as spcfg

ADMIN_STEAM = "76561198000000001"
USER_STEAM = "76561198000000002"


@pytest.fixture(autouse=True)
def _sp_env(tmp_path, monkeypatch):
    monkeypatch.setenv("ARKSHOP_WEB_SECRET", "test-secret")
    monkeypatch.setattr(_app_module, "_ADMIN_FILE", tmp_path / "admin_steamids.json")
    monkeypatch.setattr(_app_module, "_STATE_FILE", tmp_path / "settings.json")
    (tmp_path / "admin_steamids.json").write_text(json.dumps([ADMIN_STEAM]), encoding="utf-8")
    (tmp_path / "settings.json").write_text("{}", encoding="utf-8")
    cfg_path = tmp_path / "season_pass_config.json"
    claims_path = tmp_path / "season_pass_claims.json"
    monkeypatch.setattr(_app_module, "_SEASON_PASS_CONFIG_FILE", cfg_path)
    monkeypatch.setattr(_app_module, "_SEASON_PASS_CLAIMS_FILE", claims_path)
    spcfg.configure_season_pass(config_file=cfg_path, claims_file=claims_path)
    yield


@pytest.fixture
def client(tmp_path, monkeypatch):
    catalog = tmp_path / "config.json"
    catalog.write_text(json.dumps({"Settings": {}}), encoding="utf-8")
    servers_file = tmp_path / "servers.json"
    servers_file.write_text("[]", encoding="utf-8")
    monkeypatch.setattr(_app_module, "_SERVERS_FILE", servers_file)
    monkeypatch.setattr(_app_module, "_ACTIVE_DATABASE_URL", "")
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def _login(client, steam_id: str):
    with client.session_transaction() as sess:
        sess["steam_id"] = steam_id


def test_default_seed_has_typed_amber_and_pending_skus():
    cfg = spcfg.load_config()
    assert cfg["current_tier"] == "Delta"
    assert cfg["premium_price_by_tier"]["Delta"] == 15_000
    free4 = cfg["free_rewards"]["4"]
    assert free4[0]["type"] == "amber"
    assert free4[0]["qty"] == 500
    assert free4[0]["grant_ready"] is True
    free8 = cfg["free_rewards"]["8"]
    assert free8[0]["type"] == "kit"
    assert free8[0]["grant_ready"] is False
    assert free8[0]["delivery"] == "sku_pending"
    prem30 = cfg["premium_rewards"]["30"]
    assert prem30[0]["qty"] == 20_000
    prem29 = cfg["premium_rewards"]["29"]
    assert prem29[0]["type"] == "license"
    assert prem29[0]["days"] == 30
    assert prem29[0]["grant_ready"] is True


def test_save_and_reload_config(tmp_path):
    cfg = spcfg.load_config()
    cfg["premium_price_by_tier"]["Delta"] = 16_500
    cfg["free_rewards"]["4"] = [{"type": "amber", "qty": 777, "label": "777 Â"}]
    cfg["free_rewards"]["8"] = [{
        "type": "kit", "id": "KitConsumiveis", "qty": 1, "label": "Kit teste"
    }]
    saved = spcfg.save_config(cfg, updated_by_steam_id=ADMIN_STEAM)
    assert saved["premium_price_by_tier"]["Delta"] == 16_500
    assert saved["free_rewards"]["8"][0]["grant_ready"] is True
    reloaded = spcfg.load_config()
    assert reloaded["free_rewards"]["4"][0]["qty"] == 777
    assert reloaded["updated_by_steam_id"] == ADMIN_STEAM


def test_preview_reads_config_grants(client):
    r = client.get("/api/season-pass/preview")
    assert r.status_code == 200
    data = r.get_json()
    assert data["ok"] is True
    assert data["grant_engine_live"] is False
    assert data["xp_live"] is False
    free = data["tracks"]["free"]
    n4 = next(x for x in free if x["level"] == 4)
    assert n4["grants"][0]["type"] == "amber"
    assert n4["claimable"] is False  # xp=0
    assert n4["delivery"]["in_game_delivery"] is False


def test_admin_config_requires_admin(client):
    r = client.get("/api/admin/season-pass/config")
    assert r.status_code == 401
    _login(client, USER_STEAM)
    r2 = client.get("/api/admin/season-pass/config")
    assert r2.status_code == 403


def test_admin_get_put_config(client):
    _login(client, ADMIN_STEAM)
    g = client.get("/api/admin/season-pass/config")
    assert g.status_code == 200
    assert g.get_json()["config"]["premium_price_by_tier"]["Delta"] == 15_000
    payload = {
        "current_tier": "Delta",
        "duration_days": 30,
        "premium_price_by_tier": {
            "Delta": 15_500,
            "Gamma": 18_000,
            "Beta": 22_000,
            "Alfa": 28_000,
            "Omega": 35_000,
            "Transcendente": 45_000,
        },
        "free_rewards": {
            "4": [{"type": "amber", "qty": 600, "label": "600 Â"}],
            "8": [{"type": "kit", "id": "KitX", "qty": 1, "label": "Kit X"}],
        },
        "premium_rewards": {
            "1": [{"type": "amber", "qty": 300}],
        },
    }
    put = client.put("/api/admin/season-pass/config", json=payload)
    assert put.status_code == 200, put.get_json()
    cfg = put.get_json()["config"]
    assert cfg["premium_price_by_tier"]["Delta"] == 15_500
    assert cfg["free_rewards"]["4"][0]["qty"] == 600
    assert cfg["free_rewards"]["8"][0]["grant_ready"] is True
    meta = client.get("/api/season-pass/meta").get_json()
    assert meta["premium_price_amber"] == 15_500


def test_claim_blocked_without_xp(client):
    _login(client, USER_STEAM)
    r = client.post("/api/season-pass/claim", json={"track": "free", "level": 4})
    assert r.status_code == 400
    body = r.get_json()
    assert body["ok"] is False
    assert body["xp_live"] is False


def test_enqueue_claim_records_intended_grants_not_delivered(tmp_path):
    cfg = spcfg.load_config()
    grants = spcfg.rewards_for(cfg, "free", 4)
    result = spcfg.enqueue_claim(
        steam_id=USER_STEAM,
        season_id="season-delta",
        tier="Delta",
        track="free",
        level=4,
        grants=grants,
    )
    assert result["already_queued"] is False
    claim = result["claim"]
    assert claim["in_game_delivered"] is False
    assert claim["status"] == "queued_not_delivered"
    assert claim["grants"][0]["type"] == "amber"
    again = spcfg.enqueue_claim(
        steam_id=USER_STEAM,
        season_id="season-delta",
        tier="Delta",
        track="free",
        level=4,
        grants=grants,
    )
    assert again["already_queued"] is True
    claimed = spcfg.player_claimed_set(USER_STEAM, "season-delta")
    assert ("free", 4) in claimed
