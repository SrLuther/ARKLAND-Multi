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
    assert meta["version"] == "1.0"
    assert len(meta["sections"]) >= 10
