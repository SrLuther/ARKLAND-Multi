"""Testes do markup/JS de conexão Steam na home pública."""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from server_connect import ARK_ASE_STEAM_APP_ID, build_steam_connect_url

INDEX_HTML = Path(__file__).resolve().parents[1] / "static" / "index.html"


@pytest.fixture(scope="module")
def index_html() -> str:
    return INDEX_HTML.read_text(encoding="utf-8")


def test_home_connect_buttons_use_delegation_attributes(index_html: str):
    assert 'data-ark-connect' in index_html
    assert 'data-ark-copy-ip' in index_html
    assert "function initArkConnectDelegation()" in index_html
    assert "initArkConnectDelegation();" in index_html


def test_home_connect_play_buttons_do_not_block_steam_navigation(index_html: str):
    """return false + window.location.href bloqueava steam:// em HTTPS."""
    assert 'onclick="connectToArkServer' not in index_html
    assert "window.location.href = url" not in index_html
    play_blocks = re.findall(
        r'data-ark-connect[^>]*onclick="[^"]*return false',
        index_html,
        flags=re.I,
    )
    assert play_blocks == []


def test_steam_url_js_helper_matches_python(index_html: str):
    assert "_ARK_ASE_STEAM_APP_ID" in index_html
    assert "//+connect%20${addr}" in index_html or "//+connect%20" in index_html
    sample = build_steam_connect_url("203.0.113.10", 7777)
    assert sample == f"steam://run/{ARK_ASE_STEAM_APP_ID}//+connect%20203.0.113.10:7777"


def test_copy_feedback_class_present(index_html: str):
    assert "btn--copied" in index_html
    assert "IP copiado:" in index_html
