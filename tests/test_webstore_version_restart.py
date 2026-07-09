"""Testes de detecção de Web Store desatualizada após update."""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from src.shop_integration import (
    fetch_webstore_version,
    is_shop_port_open,
    webstore_needs_restart,
)


def test_webstore_needs_restart_when_version_differs():
    with patch("src.shop_integration.is_shop_port_open", return_value=True), patch(
        "src.shop_integration.fetch_webstore_version", return_value="1.10.15"
    ):
        assert webstore_needs_restart(27199, "1.10.16") is True


def test_webstore_needs_restart_false_when_version_matches():
    with patch("src.shop_integration.is_shop_port_open", return_value=True), patch(
        "src.shop_integration.fetch_webstore_version", return_value="1.10.16"
    ):
        assert webstore_needs_restart(27199, "1.10.16") is False


def test_webstore_needs_restart_false_when_port_closed():
    with patch("src.shop_integration.is_shop_port_open", return_value=False):
        assert webstore_needs_restart(27199, "1.10.16") is False


def test_webstore_needs_restart_when_version_unreadable():
    with patch("src.shop_integration.is_shop_port_open", return_value=True), patch(
        "src.shop_integration.fetch_webstore_version", return_value=None
    ):
        assert webstore_needs_restart(27199, "1.10.16") is True


def test_fetch_webstore_version_parses_json():
    payload = json.dumps({"version": "1.10.16", "date": "2026-07-09"}).encode("utf-8")
    mock_resp = MagicMock()
    mock_resp.read.return_value = payload
    mock_resp.__enter__.return_value = mock_resp
    mock_resp.__exit__.return_value = False
    with patch("src.shop_integration.is_shop_port_open", return_value=True), patch(
        "urllib.request.urlopen", return_value=mock_resp
    ):
        assert fetch_webstore_version(27199) == "1.10.16"


def test_is_shop_port_open_false_for_invalid_port():
    assert is_shop_port_open(0) is False
