"""Testes do mapeamento do painel Discord de status."""
from __future__ import annotations

import re

from src.discord_status_board import (
    STATUS_ATUALIZANDO,
    STATUS_INICIANDO,
    STATUS_ONLINE,
    STATUS_PARADO,
    build_embed,
    map_public_status,
)
from src.server_visibility import (
    STEAM_AVAILABLE,
    STEAM_LAN,
    STEAM_UNAVAILABLE,
    STEAM_WAITING,
)


def test_map_parado():
    assert map_public_status("stopped", STEAM_AVAILABLE) == STATUS_PARADO
    assert map_public_status("stopping", STEAM_AVAILABLE) == STATUS_PARADO
    assert map_public_status("crashed", "") == STATUS_PARADO
    assert map_public_status("", "") == STATUS_PARADO


def test_map_iniciando():
    assert map_public_status("starting", STEAM_WAITING) == STATUS_INICIANDO
    assert map_public_status("running", STEAM_WAITING) == STATUS_INICIANDO
    assert map_public_status("running", STEAM_UNAVAILABLE) == STATUS_INICIANDO
    assert map_public_status("running", STEAM_LAN) == STATUS_INICIANDO
    assert map_public_status("running", "") == STATUS_INICIANDO


def test_map_online_only_steam_listed():
    assert map_public_status("running", STEAM_AVAILABLE) == STATUS_ONLINE
    assert map_public_status("starting", STEAM_AVAILABLE) == STATUS_INICIANDO


def test_map_atualizando():
    assert map_public_status("updating", STEAM_AVAILABLE) == STATUS_ATUALIZANDO
    assert map_public_status("updating", STEAM_WAITING) == STATUS_ATUALIZANDO


def test_build_embed_lines():
    emb = build_embed([
        ("Ragnarok", STATUS_ONLINE),
        ("TheIsland", STATUS_INICIANDO),
        ("Aberration", STATUS_PARADO),
    ])
    assert emb["title"]
    desc = emb["description"]
    assert "Ragnarok" in desc and "ONLINE" in desc
    assert "TheIsland" in desc and "INICIANDO" in desc
    assert "Aberration" in desc and "PARADO" in desc
    assert "1/3 online" in emb["footer"]["text"]
    assert "Atualizado" in emb["footer"]["text"]
    assert "Brasília" in emb["footer"]["text"]
    # dd/mm/yyyy hh:mm:ss
    assert re.search(r"\d{2}/\d{2}/\d{4} \d{2}:\d{2}:\d{2}", emb["footer"]["text"])


def test_collect_status_payload_includes_players():
    from types import SimpleNamespace
    from src.discord_status_board import collect_status_payload
    from src.server_visibility import STEAM_AVAILABLE

    srv = SimpleNamespace(
        id="map1",
        shop_server_id="brighamia",
        session_name="Brighamia",
        name="Brighamia",
        max_players=70,
    )
    inst = SimpleNamespace(
        status="running",
        steam_status=STEAM_AVAILABLE,
        a2s_players=12,
        a2s_max_players=70,
    )
    mgr = SimpleNamespace(get_instance=lambda _id: inst)
    cfg_mgr = SimpleNamespace(servers=[srv])
    app = SimpleNamespace(asm_config_manager=cfg_mgr, asm_server_manager=mgr)

    rows = collect_status_payload(app)
    by_id = {r["server_id"]: r for r in rows}
    assert by_id["brighamia"]["status"] == STATUS_ONLINE
    assert by_id["brighamia"]["players"] == 12
    assert by_id["brighamia"]["max_players"] == 70
    assert by_id["map1"]["players"] == 12


def test_boot_status_board_pushes_webstore_when_discord_disabled(monkeypatch):
    """Home não depende do painel Discord — boot deve empurrar runtime-status."""
    from types import SimpleNamespace
    import src.discord_status_board as board

    calls: list = []
    monkeypatch.setattr(board, "boot_webstore_status_push", lambda app: calls.append(app))
    monkeypatch.setattr(board, "_status_cfg", lambda _app: SimpleNamespace(status_board_enabled=False))

    app = SimpleNamespace()
    board.boot_status_board(app)
    assert calls == [app]


def test_schedule_suppress_still_pushes_webstore(monkeypatch):
    from types import SimpleNamespace
    import src.discord_status_board as board

    pushed: list = []
    monkeypatch.setattr(board, "push_status_to_webstore", lambda app, items=None: pushed.append(app))
    board._suppress_updates = True
    try:
        board.schedule_status_board_update(SimpleNamespace())
        assert len(pushed) == 1
    finally:
        board._suppress_updates = False
