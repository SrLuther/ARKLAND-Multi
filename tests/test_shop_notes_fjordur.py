"""Contrato das runas Fjordur desbloqueadas pelo /notas (CustomShop ShopNotes.cpp)."""
from __future__ import annotations

from src.player_level_ascension import EXTRA_BONUSES

# Indices GiveExplorerNote usados pelo plugin (comunidade ARK / arkforum.de).
FJORDUR_RUNE_NOTE_FIRST = 1000
FJORDUR_RUNE_COUNT = 200
FJORDUR_RUNE_NOTE_LAST = FJORDUR_RUNE_NOTE_FIRST + FJORDUR_RUNE_COUNT - 1


def test_fjordur_rune_note_range():
    assert FJORDUR_RUNE_NOTE_FIRST == 1000
    assert FJORDUR_RUNE_NOTE_LAST == 1199
    assert FJORDUR_RUNE_COUNT == 200


def test_fjordur_runes_match_level_panel_bonus():
    bonuses = dict((bid, levels) for bid, _label, levels in EXTRA_BONUSES)
    assert bonuses["explorer_notes"] == 10
    assert bonuses["fjordur_runes"] == 10
