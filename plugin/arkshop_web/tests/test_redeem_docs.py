"""Regressions for the redemption documentation module's public API."""
from pathlib import Path


_SCRIPT = Path(__file__).resolve().parents[1] / "static" / "redeem_docs.js"


def test_license_tier_renderer_name_matches_calls_and_export():
    source = _SCRIPT.read_text(encoding="utf-8")

    assert "function renderLicenseTiersGrid(" in source
    assert "${renderLicenseTiersGrid()}" in source
    assert "    renderLicenseTiersGrid," in source
    assert "function renderLicenseTierGrid(" not in source
