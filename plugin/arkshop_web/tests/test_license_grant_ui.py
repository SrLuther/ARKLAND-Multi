"""Editor de item da loja: painel LicenseGrant sem atalhos (presets) de licença."""

from pathlib import Path

_INDEX = Path(__file__).resolve().parents[1] / "static" / "index.html"


def _html() -> str:
    return _INDEX.read_text(encoding="utf-8")


def _license_editor_block(html: str) -> str:
    start = html.index("function licenseGrantEditorHtml(")
    end = html.index("function toggleLicenseGrantFields(", start)
    return html[start:end]


def test_license_presets_shortcuts_removed():
    html = _html()
    assert "applyLicensePreset" not in html
    assert "LICENSE_GRANT_PRESETS" not in html
    block = _license_editor_block(html)
    # Nenhum botão no painel (placeholders de texto podem citar nomes de grupos).
    assert "<button" not in block
    assert "onclick=\"applyLicense" not in block
    for label in ("☁️ Nuvem", "Δ Delta", "Γ Gamma", "β Beta", "α Alfa", "Ω Omega", "✦ Exótico"):
        assert label not in block, label


def test_license_panel_and_checkbox_kept():
    block = _license_editor_block(_html())
    assert "Concessão de licença (LicenseGrant)" in block
    assert "Registrar licença no resgate (MySQL + plugin)" in block
    assert 'id="${prefix}-lic-enabled"' in block
    assert 'id="${prefix}-lic-group"' in block
    assert 'id="${prefix}-lic-days"' in block
    assert 'id="${prefix}-lic-timed-bonus"' in block
    assert 'id="${prefix}-lic-redeemable"' in block
    assert "toggleLicenseGrantFields('${prefix}')" in block


def test_license_read_helpers_still_present():
    html = _html()
    assert "function readLicenseGrantFromDOM(prefix)" in html
    assert "function readTimedPointsBonusFromDOM(prefix)" in html
    assert 'const licGrant = readLicenseGrantFromDOM("mi");' in html
    assert "it.LicenseGrant = licGrant;" in html
