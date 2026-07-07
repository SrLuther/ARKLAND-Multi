"""Testes de snapshot de config de servidor para cards da home."""
from __future__ import annotations

import json
from dataclasses import dataclass

import pytest

from src.buff_manager import BuffEvent, BuffRates, BUFF_STATUS_ACTIVE
from src.server_config_snapshot import (
    build_snapshot_indexes,
    collect_server_snapshot,
    compute_max_player_level,
    compute_max_wild_dino_level,
    match_snapshot_for_map,
    snapshot_public_view,
)


@pytest.fixture
def shop_dir(tmp_path, monkeypatch):
    import src.shop_integration as si

    target = tmp_path / "arkshop_web"
    target.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(si, "webstore_data_dir", lambda: target)
    return target


@dataclass
class _TekSrv:
    id: str = "tek-1"
    name: str = "Brighamia"
    install_dir: str = ""
    enable_difficulty_override: bool = True
    override_official_difficulty: float = 5.0
    difficulty_offset: float = 0.2
    override_max_xp_player: int = 0
    xp_multiplier: float = 44.0
    taming_speed_multiplier: float = 20.0
    harvest_amount_multiplier: float = 15.0
    mating_interval_multiplier: float = 1.0
    baby_mature_speed_multiplier: float = 8.0


def test_compute_levels_with_override():
    srv = _TekSrv()
    assert compute_max_wild_dino_level(srv) == 150
    assert compute_max_player_level(srv) == 180


def test_snapshot_public_view_formats_rates():
    view = snapshot_public_view({
        "xp_multiplier": 44,
        "taming_speed_multiplier": 20,
        "harvest_amount_multiplier": 15,
        "baby_mature_speed_multiplier": 8,
        "max_player_level": 180,
        "max_dino_level": 150,
    })
    assert view is not None
    assert view["xp"] == "44x"
    assert view["taming"] == "20x"
    assert view["harvest"] == "15x"
    assert view["max_player_level"] == 180
    assert view["max_dino_level"] == 150


def test_collect_snapshot_applies_active_buff():
    srv = _TekSrv(xp_multiplier=10.0, harvest_amount_multiplier=5.0)
    buff = BuffEvent(
        id="b1",
        name="XP Weekend",
        server_id="tek-1",
        types=["XP"],
        rates=BuffRates(xp_multiplier=10.0, harvest_amount_multiplier=2.0),
        start_dt="2026-01-01T00:00:00",
        end_dt="2026-01-02T00:00:00",
        status=BUFF_STATUS_ACTIVE,
    )
    snap = collect_server_snapshot(srv, buff_event=buff, reload_ini=False)
    assert snap["xp_multiplier"] == 100.0
    assert snap["harvest_amount_multiplier"] == 10.0
    assert snap["buff_active"] is True
    assert snap["seasonal_event_active"] is True
    assert snap["seasonal_event_name"] == buff.name


def test_match_snapshot_by_name_slug():
    servers = [{
        "server_id": "brighamia",
        "label": "Brighamia",
        "config_snapshot": {
            "xp_multiplier": 44,
            "taming_speed_multiplier": 20,
            "harvest_amount_multiplier": 15,
            "baby_mature_speed_multiplier": 1,
            "max_player_level": 180,
            "max_dino_level": 150,
        },
    }]
    by_id, by_slug = build_snapshot_indexes(servers)
    stats = match_snapshot_for_map({"name": "Brighamia"}, by_id, by_slug)
    assert stats is not None
    assert stats["xp"] == "44x"


def test_register_servers_includes_snapshot(shop_dir, monkeypatch):
    import src.shop_integration as si
    from src.config_manager import ShopGlobalConfig
    from src.shop_integration import register_arkshop_servers

    @dataclass
    class _Srv:
        id: str
        name: str
        shop_server_id: str = "brighamia"
        shop_show_on_home: bool = True
        shop_exclude: bool = False
        install_dir: str = ""
        server_ip: str = "127.0.0.1"
        rcon_port: int = 27020
        rcon_password: str = "x"
        admin_password: str = ""
        customshop_config_path: str = ""
        enable_difficulty_override: bool = True
        override_official_difficulty: float = 5.0
        difficulty_offset: float = 0.2
        override_max_xp_player: int = 0
        xp_multiplier: float = 10.0
        taming_speed_multiplier: float = 5.0
        harvest_amount_multiplier: float = 3.0
        mating_interval_multiplier: float = 1.0
        baby_mature_speed_multiplier: float = 1.0

    class _CM:
        servers = []

    class _Asm:
        servers = [_Srv(id="t1", name="Brighamia")]

    target = shop_dir
    register_arkshop_servers(_CM(), ShopGlobalConfig(mode="host"), asm_cm=_Asm())
    data = json.loads((target / "servers.json").read_text(encoding="utf-8"))
    assert data[0]["config_snapshot"]["xp_multiplier"] == 10.0
