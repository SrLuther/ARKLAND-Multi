"""Testes do regulamento — conteúdo estático para produção (PyInstaller)."""
from __future__ import annotations

from pathlib import Path

import regulamento_service as rs


def test_static_html_bundled():
    assert rs._STATIC_HTML_PATH.is_file(), (
        f"Arquivo estático ausente: {rs._STATIC_HTML_PATH}. "
        "Rode scripts/build_regulamento_html.py antes do build."
    )


def test_content_from_static_when_md_missing(monkeypatch):
    monkeypatch.setattr(rs, "_REGULAMENTO_MD_PATH", Path("/nonexistent/REGULAMENTO_SERVIDOR.md"))
    html = rs.regulamento_content_html()
    assert "indisponível" not in html.lower()
    assert "<h2" in html
    assert len(html) > 1000


def test_meta_sections_from_static_when_md_missing(monkeypatch):
    monkeypatch.setattr(rs, "_REGULAMENTO_MD_PATH", Path("/nonexistent/REGULAMENTO_SERVIDOR.md"))
    meta = rs.regulamento_meta()
    assert meta["version"] == "1.4"
    assert len(meta["sections"]) >= 10


def test_markdown_table_cells_render_inline_formatting():
    md = (
        "| Canal | Uso |\n"
        "|-------|-----|\n"
        "| **Web Store** | [https://arkland.com.br](https://arkland.com.br) |\n"
        "| **Âmbar / Âmbares** | Moeda simbólica |\n"
    )
    html = rs._markdown_to_html(md)
    assert "<strong>Web Store</strong>" in html
    assert '<a href="https://arkland.com.br" target="_blank" rel="noopener">https://arkland.com.br</a>' in html
    assert "<strong>Âmbar / Âmbares</strong>" in html
    assert "**Web Store**" not in html
    assert "[https://arkland.com.br]" not in html
