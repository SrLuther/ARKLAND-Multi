"""Botão de tradução da Ficha Primal Fear: texto troca, blueprint e chave não."""
from __future__ import annotations

import json
import re
from pathlib import Path

_STATIC = Path(__file__).resolve().parents[1] / "static"
_HTML = _STATIC / "index.html"
_JS = _STATIC / "primal_fear_ficha.js"
_JSON = _STATIC / "primal_fear_ficha.json"
_ALLO_SPAWN = (
    'admincheat SpawnDino "Blueprint\''
    "/Game/Mods/Primal_Fear/Dinos/Alpha/Alpha_Allo/"
    "AlphaAllo_Character_BP.AlphaAllo_Character_BP'\" 500 0 0 35"
)
_TOKEN = re.compile(
    r"Blueprint'[^']+'|/Game/\S+|EngramEntry_[A-Za-z0-9_]+_C|"
    r"PrimalItem[A-Za-z0-9_]*_C|[A-Za-z0-9_]+_Character_BP\w*"
)


def test_botao_traduz_texto_e_preserva_blueprint_e_chave():
    html = _HTML.read_text(encoding="utf-8")
    page = html.split('id="page-primal-fear-ficha"', 1)[1].split('id="page-blueprint-index"', 1)[0]
    assert 'id="pf-ficha-lang"' in page
    assert "Traduzir para português" in page
    assert "togglePrimalFearLang()" in page

    js = _JS.read_text(encoding="utf-8")
    assert "Ver original" in js
    assert "function togglePrimalFearLang()" in js
    assert "function _pfWholeLocked(" in js
    assert "if (!_pfLangPt || _pfWholeLocked(text)) return text;" in js

    data = json.loads(_JSON.read_text(encoding="utf-8"))
    pt = data["pt"]
    assert isinstance(pt, dict) and pt
    assert pt["SPAWN RATES"] == "TAXAS DE SPAWN"
    assert pt["Yes"] == "Sim"
    assert pt["No"] == "Não"
    assert "Control + C" in pt["Key Binding: Control + C\nAffect:\nWhen using the celestial power up ability, Stamina drains rapidly. This stops when you turn off the power up or dismount\nCelestial gains 150% melee damage, receives 25% less damage, and is immune to all status effects\nAll Demonics can now power up. The demonic power up does 15% less damage taken, and 120% more damage to enemies. While this is less than celestials, it also slowly heals your creature, and sets anything around it on fire.\nAll Demonics can power up in the wild, or when allied or tamed and attacking an enemy. Can also be powered up through the radial menu."]

    spawn = _ALLO_SPAWN
    tag = "PFAlphaAllo"
    found_spawn = False
    found_tag = False
    for sheet in data["sheets"]:
        if sheet.get("id") != "dino-tags":
            continue
        for group in sheet.get("groups") or []:
            for dino in group.get("dinos") or []:
                if dino.get("name") != "Allo":
                    continue
                for field in dino.get("fields") or []:
                    if field.get("label") == "Spawn" and field.get("value") == spawn:
                        found_spawn = True
                    if field.get("label") == "Tag" and field.get("value") == tag:
                        found_tag = True
    assert found_spawn and found_tag
    assert pt.get(spawn, spawn) == spawn
    assert pt.get(tag, tag) == tag
    assert pt.get("L CLK", "L CLK") == "L CLK"
    assert pt.get("LFT CTRL", "LFT CTRL") == "LFT CTRL"
    assert "Blueprint'/Game/Mods/Primal_Fear/Dinos/Alpha/Alpha_Allo/AlphaAllo_Character_BP.AlphaAllo_Character_BP'" in spawn

    for src, dst in pt.items():
        for token in _TOKEN.findall(src):
            assert token in dst
        assert "EngramEntryAutoUnlocks=" not in src
