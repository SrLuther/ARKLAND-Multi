"""Guia da Web Store: menu do jogador, índice e artigo Primal Fear."""
from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

_STATIC = Path(__file__).resolve().parents[1] / "static"
_SECTIONS = (
    "kb-sec-creatures",
    "kb-sec-armor",
    "kb-sec-resources",
    "kb-sec-weapons",
    "kb-sec-consumables",
    "kb-sec-structures",
    "kb-sec-saddles",
    "kb-sec-summoners",
    "kb-sec-ammo",
    "kb-sec-costumes",
    "kb-sec-bosses",
    "kb-sec-eggs",
    "kb-sec-patch",
    "kb-sec-gus",
    "kb-sec-guides",
)
_FIELDS = ("tier", "ataque", "doma", "habilidade", "sela", "breed")
_BANNED = (
    r"\baba\b",
    r"\bcoluna\b",
    r"\bc[eé]lula\b",
    r"\bplanilha\b",
    r"fonte\s*:",
    r"\bCLK\b",
    r"\brodap[eé]\b",
    r"documenta[cç][aã]o consultada",
    r"não informa uma sela",
    r"não existe",
    r"Saddle Codes",
)
_UNSOURCED = (
    "ponto fraco na cabeça",
    "em geral no ARK",
    "todo jogador sabe",
    "como todo mundo",
)


@pytest.fixture(scope="module")
def html() -> str:
    return (_STATIC / "index.html").read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def js() -> str:
    return (_STATIC / "guia.js").read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def css() -> str:
    return (_STATIC / "guia.css").read_text(encoding="utf-8")


def test_menu_guia_jogador(html: str):
    m = re.search(r'<div class="nav-item([^"]*)"\s+data-page="guia"', html)
    assert m, "menu sem Guia"
    assert "admin-only" not in m.group(1)
    assert "Guia" in html[m.start(): m.start() + 220]
    jogador = html.find(">Jogador<")
    assert jogador != -1 and m.start() > jogador


def test_page_shell_and_assets(html: str):
    assert 'id="page-guia"' in html
    assert 'id="kb-root"' in html
    assert re.search(r'<script src="guia\.js\?v=__WEB_BUILD__" defer></script>', html)
    assert re.search(r'<link rel="stylesheet" href="guia\.css\?v=__WEB_BUILD__"\s*/?>', html)


def test_index_for_future_topics(js: str):
    assert "KB_TOPICS" in js
    assert "primal-fear" in js
    assert 'id="kb-index"' in js or "kb-index" in js
    assert "data-kb-open" in js


def _js_string_after(js: str, key: str) -> str:
    i = js.find(key)
    assert i != -1, key
    i += len(key)
    out = []
    esc = False
    while i < len(js):
        c = js[i]
        if esc:
            out.append(c)
            esc = False
        elif c == "\\":
            esc = True
        elif c == '"':
            break
        else:
            out.append(c)
        i += 1
    return "".join(out)


def test_dois_topicos_primal_fear(js: str):
    assert 'id: "primal-fear"' in js
    assert 'id: "primal-fear-jogador"' in js
    assert "Primal Fear — jogador" in js
    player = _js_string_after(js, '"primal-fear-jogador": "')
    assert "kb-article-primal-fear-jogador" in player
    for sec in (
        "kb-pfj-agora",
        "kb-pfj-tiers",
        "kb-pfj-tame",
        "kb-pfj-criaturas",
        "kb-pfj-recursos",
        "kb-pfj-bosses",
        "kb-pfj-sistemas",
    ):
        assert sec in player
    for pat in (r"\baba\b", r"\bcoluna\b"):
        assert re.search(pat, player, re.I) is None, pat
    old = _js_string_after(js, '"primal-fear": "')
    assert "kb-article-primal-fear" in old
    assert "kb-sec-gus" in old
    assert "Usa a sela de Allosaurus (Alossauro)." in old
    assert "primal-fear-jogador" not in old


def test_primal_fear_player_voice(js: str):
    assert "Primal Fear" in js
    for sec in _SECTIONS:
        assert sec in js
    for field in _FIELDS:
        assert f'data-kb-field=\\"{field}\\"' in js
    assert 'data-kb-field=\\"fraqueza\\"' not in js
    assert "https://ark.fandom.com/wiki/Mod:Primal_Fear" in js
    assert "https://primalfear.wiki.gg/wiki/Primal_Fear" in js
    for phrase in _UNSOURCED:
        assert phrase not in js
    for pat in _BANNED:
        assert re.search(pat, js, re.I) is None, pat


def test_allo_sela_casa_com_allosaurus(js: str):
    cards = re.findall(
        r'data-kb-dino=\\"Allo\\" data-kb-tier=\\"ALPHA\\".*?</article>',
        js,
    )
    assert cards, "ficha do Allo Alpha ausente"
    card = cards[0]
    assert "Usa a sela de Allosaurus (Alossauro)." in card
    assert "não informa" not in card
    assert "não existe" not in card
    for name in (
        "Ankylosaurus",
        "Carnotaurus",
        "Tiranossauro",
        "Triceratops",
        "Stegosaurus",
        "Pteranodon",
        "Espinossauro",
    ):
        assert name in js


def test_css_prefixed(css: str):
    selectors = re.findall(r"(?m)^\s*([.#][^{@/]+?)\s*\{", css)
    assert selectors
    assert all(".kb-" in s for s in selectors), [s for s in selectors if ".kb-" not in s]
    assert "@media (max-width: 640px)" in css


@pytest.mark.skipif(shutil.which("node") is None, reason="node não instalado")
def test_node_check_syntax():
    proc = subprocess.run(
        ["node", "--check", str(_STATIC / "guia.js")],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert proc.returncode == 0, proc.stderr
