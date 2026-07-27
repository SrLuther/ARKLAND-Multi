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
