"""Testes do mapeamento do painel Discord de status."""
from __future__ import annotations

import re

from src.discord_status_board import (
    STATUS_ATUALIZANDO,
    STATUS_INICIANDO,
    STATUS_ONLINE,
    STATUS_PARADO,
    build_embed,
    connected_label,
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
        ("Ragnarok", STATUS_ONLINE, 12),
        ("TheIsland", STATUS_INICIANDO, None),
        ("Aberration", STATUS_PARADO, 99),
    ])
    assert emb["title"]
    desc = emb["description"]
    assert "Ragnarok" in desc and "ONLINE" in desc and "12 jogadores" in desc
    assert "TheIsland" in desc and "INICIANDO" in desc
    assert "Aberration" in desc and "PARADO" in desc
    # parado / query ausente: traço, sem reaproveitar contagem antiga
    assert "99" not in desc
    island_line = next(line for line in desc.splitlines() if "TheIsland" in line)
    aberr_line = next(line for line in desc.splitlines() if "Aberration" in line)
    assert "—" in island_line
    assert "—" in aberr_line
    assert "1/3 online" in emb["footer"]["text"]
    assert "Atualizado" in emb["footer"]["text"]
    assert "Brasília" in emb["footer"]["text"]
    # dd/mm/yyyy hh:mm:ss
    assert re.search(r"\d{2}/\d{2}/\d{4} \d{2}:\d{2}:\d{2}", emb["footer"]["text"])
    # continua um único embed
    assert isinstance(emb, dict)
    assert "fields" not in emb or not emb.get("fields")


def test_build_embed_bad_row_does_not_drop_card():
    emb = build_embed([
        ("Ragnarok", STATUS_ONLINE, 4),
        None,
        ("TheIsland", STATUS_ONLINE, 0),
    ])
    desc = emb["description"]
    assert "Ragnarok" in desc and "4 jogadores" in desc
    assert "TheIsland" in desc and "0 jogadores" in desc
    assert emb["title"]


def test_connected_label_does_not_invent_count():
    assert connected_label(STATUS_ONLINE, None) == "—"
    assert connected_label(STATUS_ONLINE, 7) == "7 jogadores"
    assert connected_label(STATUS_PARADO, 7) == "—"
    assert connected_label(STATUS_ATUALIZANDO, 3) == "—"


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

    from src.discord_status_board import _rows_for_embed
    emb = build_embed(_rows_for_embed(rows))
    assert "12 jogadores" in emb["description"]
    assert "Brighamia" in emb["description"]


def test_collect_status_payload_query_miss_is_dash_and_sibling_survives():
    """Query A2S ausente vira traço; um servidor quebrado não derruba o card."""
    from types import SimpleNamespace
    from src.discord_status_board import _rows_for_embed, collect_status_payload
    from src.server_visibility import STEAM_AVAILABLE

    class Boom:
        id = "bad"
        name = "Quebrado"

        def __getattribute__(self, item):
            if item in ("id", "name"):
                return object.__getattribute__(self, item)
            raise RuntimeError("boom")

    good = SimpleNamespace(
        id="ok",
        shop_server_id="ilha",
        session_name="Ilha",
        name="Ilha",
        max_players=70,
    )
    quiet = SimpleNamespace(
        id="quiet",
        shop_server_id="",
        session_name="SemQuery",
        name="SemQuery",
        max_players=20,
    )
    inst_ok = SimpleNamespace(status="running", steam_status=STEAM_AVAILABLE, a2s_players=3, a2s_max_players=70)
    inst_quiet = SimpleNamespace(status="running", steam_status=STEAM_AVAILABLE, a2s_players=None, a2s_max_players=None)

    def get_instance(sid):
        if sid == "ok":
            return inst_ok
        if sid == "quiet":
            return inst_quiet
        raise RuntimeError("nope")

    app = SimpleNamespace(
        asm_config_manager=SimpleNamespace(servers=[good, quiet, Boom()]),
        asm_server_manager=SimpleNamespace(get_instance=get_instance),
    )
    rows = collect_status_payload(app)
    by_name = {}
    for row in rows:
        by_name.setdefault(row["display_name"], row)
    assert by_name["Ilha"]["players"] == 3
    assert by_name["SemQuery"]["players"] is None
    assert "Quebrado" in by_name

    desc = build_embed(_rows_for_embed(rows))["description"]
    assert "3 jogadores" in desc
    quiet_line = next(line for line in desc.splitlines() if "SemQuery" in line)
    assert "—" in quiet_line
    assert "Ilha" in desc and "Quebrado" in desc


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
