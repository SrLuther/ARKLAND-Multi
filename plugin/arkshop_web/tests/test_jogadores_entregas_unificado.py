"""Unificação Jogadores & Entregas -> Gerenciar Jogadores (index.html estático).

Cobre, sem GUI/navegador:
- item «Jogadores & Entregas» ausente da sidebar (fica só Gerenciar Jogadores);
- página #page-rcon removida; cadastro, entrega de resgate e pontos vivem em #page-players-admin;
- roteamento legado rcon / jogadores / entregas → players-admin (goToPage, nav e hash).
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

_INDEX = Path(__file__).resolve().parents[1] / "static" / "index.html"


@pytest.fixture(scope="module")
def html() -> str:
    return _INDEX.read_text(encoding="utf-8")


def _nav_items(html: str) -> list[tuple[str, str]]:
    """(data-page, texto) de cada .nav-item da sidebar."""
    out = []
    for m in re.finditer(
        r'<div class="nav-item([^"]*)"\s+data-page="([^"]+)"[^>]*>(.*?)</div>', html, re.S
    ):
        text = re.sub(r"<[^>]+>", "", m.group(3))
        out.append((m.group(2), " ".join(text.split())))
    return out


def _players_admin_page(html: str) -> str:
    start = html.index('id="page-players-admin"')
    end = html.index('id="page-map-members-admin"', start)
    return html[start:end]


def test_menu_so_tem_gerenciar_jogadores(html):
    items = _nav_items(html)
    pages = [p for p, _ in items]
    labels = [t for _, t in items]
    assert pages.count("players-admin") == 1
    assert sum(1 for t in labels if t.endswith("Gerenciar Jogadores")) == 1
    assert "rcon" not in pages
    assert not any("Jogadores & Entregas" in t for t in labels)
    assert "Jogadores & Entregas" not in html
    # Continua na secção Suporte, antes de Membros por mapa. Ferramentas abre no console.
    assert pages.index("players-admin") < pages.index("map-members-admin")
    ferramentas = html.index(">Ferramentas</div>")
    depois = html[ferramentas : ferramentas + 400]
    assert 'data-page="server-console"' in depois
    assert 'data-page="rcon"' not in depois


def test_pagina_solta_removida_e_blocos_na_unificada(html):
    assert 'id="page-rcon"' not in html
    page = _players_admin_page(html)
    for needle in (
        "Cadastro de Jogador",
        'id="player-steam-id"',
        "savePlayer()",
        "clearPlayerForm()",
        "Entrega de Resgate",
        'id="deliver-steam-id"',
        "deliverPurchase()",
        "Cria pedido PENDENTE",
        "Pontos de Jogador",
        'id="admin-points-steam"',
        "adminPoints('get')",
        "adminPoints('add')",
        "adminPoints('set')",
        "Saldo no banco central MySQL",
    ):
        assert needle in page, needle
    # Um formulário só — os ids não ficaram na página antiga.
    for needle in ('id="player-steam-id"', 'id="deliver-steam-id"', 'id="admin-points-steam"'):
        assert html.count(needle) == 1


def test_ficha_nao_duplica_ajuste_nem_catalogo(html):
    """Ajustar Âmbar e Entregar do catálogo já existiam na ficha; não foram copiados de novo."""
    assert html.count("Ajustar Âmbar") == 1
    assert html.count("Entregar do catálogo") == 1
    assert "playerAdminPoints('add')" in html
    assert "playerAdminCatalogDeliver()" in html


def test_roteamento_legado_abre_gerenciar_jogadores(html):
    m = re.search(r"const LEGACY_PAGE_ALIASES = (\{[^}]*\});", html)
    assert m, "LEGACY_PAGE_ALIASES ausente"
    aliases = m.group(1)
    assert 'midias: "tutoriais"' in aliases
    assert 'sell: "market"' in aliases
    for key in ("rcon", "jogadores", "entregas"):
        assert f'{key}: "players-admin"' in aliases
    assert "let page = resolveLegacyPage(el.dataset.page);" in html
    assert "page = resolveLegacyPage(page);" in html  # goToPage
    assert 'hashRouteBoot === "rcon"' in html
    assert 'hashRouteBoot === "jogadores"' in html
    assert 'hashRouteBoot === "entregas"' in html
    assert 'data-page="players-admin"' in html
    assert '.nav-item[data-page="rcon"]' not in html
    assert 'if (page === "rcon"' not in html
    assert "loadPlayers();" in html
    assert 'if (page === "players-admin") { loadPlayersAdminLicenseCatalog(); loadPlayersAdmin(true); loadPlayers(); }' in html
