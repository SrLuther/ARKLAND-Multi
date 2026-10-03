"""Unificação Mídias -> Tutoriais na Web Store (index.html estático).

Cobre, sem GUI/navegador:
- item «Mídias» ausente da sidebar do jogador;
- página #page-midias removida (vídeos vivem dentro de #page-tutoriais);
- vídeos acima do conteúdo escrito dos tutoriais;
- roteamento legado 'midias' -> 'tutoriais' (nav, goToPage e hash #/midias).
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


def test_sidebar_sem_item_midias_publico(html):
    items = _nav_items(html)
    pages = [p for p, _ in items]
    assert "midias" not in pages
    assert "tutoriais" in pages
    # Nenhum item do jogador com rótulo exato «Mídias».
    assert not [t for _, t in items if t.endswith("Mídias")]


def test_sidebar_ordem_utilidades_tutoriais_votacoes(html):
    pages = [p for p, _ in _nav_items(html)]
    i = pages.index("downloads")
    assert pages[i : i + 3] == ["downloads", "tutoriais", "polls"]


def test_pagina_midias_removida_e_admin_preservado(html):
    assert 'id="page-midias"' not in html
    # CRUD admin dos vídeos continua disponível.
    assert 'id="page-midias-admin"' in html
    assert 'data-page="midias-admin"' in html
    assert "function loadMidiasAdmin" in html


def test_videos_acima_do_conteudo_de_tutoriais(html):
    start = html.index('id="page-tutoriais"')
    page = html[start:]
    i_videos = page.index('id="tutoriais-videos"')
    i_grid = page.index('id="midias-grid"')
    i_filters = page.index('id="midias-filter-tabs"')
    i_hero = page.index('class="tutorial-hero"')
    i_acc = page.index('id="tutorial-accordion"')
    assert i_videos < i_filters < i_grid < i_hero < i_acc


def test_tutoriais_carrega_videos_ao_abrir(html):
    assert re.search(r'if \(page === "tutoriais"\) \{\s*loadMidias\(\);', html)
    # Sem carga/roteamento próprio da antiga página.
    assert 'if (page === "midias") loadMidias();' not in html


def test_roteamento_legado_midias_para_tutoriais(html):
    assert re.search(r'LEGACY_PAGE_ALIASES\s*=\s*\{\s*midias:\s*"tutoriais"\s*(,[^}]*)?\}', html)
    assert "let page = resolveLegacyPage(el.dataset.page);" in html
    assert "page = resolveLegacyPage(page);" in html  # goToPage
    # Hash legado #/midias abre Tutoriais no boot.
    assert 'hashRoute === "midias"' in html
    assert 'data-page="tutoriais"' in html
    assert '.nav-item[data-page="midias"]' not in html
