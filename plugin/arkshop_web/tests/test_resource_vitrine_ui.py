"""Vitrine de Recursos — front-end (HTML/JS/CSS estáticos), sem navegador.

Cobre: aba separada da vitrine de dinos, admin presente, legado «Venda in-game» removido (com redirecionamento
de 'sell'), rotas/payloads do JS iguais às do backend, includes de CSS/JS, `node --check`, tutorial e que
as mudanças recentes de outros agentes no index.html continuam presentes.
"""
from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

_STATIC = Path(__file__).resolve().parents[1] / "static"
_ROUTES = Path(__file__).resolve().parents[1] / "resource_vitrine_routes.py"


@pytest.fixture(scope="module")
def html() -> str:
    return (_STATIC / "index.html").read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def js() -> str:
    return (_STATIC / "resource_vitrine.js").read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def css() -> str:
    return (_STATIC / "resource_vitrine.css").read_text(encoding="utf-8")


def _nav_pages(html: str) -> list[str]:
    return re.findall(r'<div class="nav-item[^"]*"\s+data-page="([^"]+)"', html)


# ── Markup / menu ────────────────────────────────────────────────────────────

def test_tab_resources_present_and_separate_from_dino_tabs(html):
    assert 'data-market-tab="resources"' in html
    assert 'id="market-panel-resources"' in html
    # vitrine de dinos intacta e com ids próprios
    assert 'id="market-panel-browse"' in html
    assert 'id="market-browse-grid"' in html
    # o painel de recursos não reaproveita ids do painel de dinos
    panel = html.split('id="market-panel-resources"', 1)[1].split("<!-- PAGE: Itens da Loja", 1)[0]
    assert "market-browse" not in panel
    assert 'id="rv-grid"' in panel and 'id="rv-mine-root"' in panel
    assert "Explorar" in panel and "Minha vitrine" in panel


def test_resource_subtabs_have_aria(html):
    assert 'role="tablist"' in html and 'data-rv-tab="explore"' in html and 'data-rv-tab="mine"' in html
    assert 'aria-controls="rv-sub-explore"' in html and 'aria-controls="rv-sub-mine"' in html
    assert 'for="rv-filter-resource"' in html and 'for="rv-filter-seller"' in html


def test_set_market_tab_and_reload_hook_resources(html):
    assert re.search(r'tab === "resources"[^\n]*rvOnTabShown\(\)', html)
    assert '_marketTab === "resources"' in html and "rvReload" in html


def test_admin_page_and_menu_present(html):
    pages = _nav_pages(html)
    assert "market-resources-admin" in pages
    assert 'id="page-market-resources-admin"' in html
    assert 'id="rv-admin-root"' in html
    assert "Recursos (vitrine)" in html
    assert re.search(r'page === "market-resources-admin"[^\n]*rvAdminLoad\(\)', html)
    # no bloco MERCADO do menu admin
    assert pages.index("market-admin") < pages.index("market-resources-admin") < pages.index("admin-downloads")


def test_legacy_sell_removed_but_config_flags_kept(html):
    pages = _nav_pages(html)
    assert "sell" not in pages
    for needle in (
        'data-page="sell"', 'id="page-sell"', 'id="modal-sell"', "renderSell", "openSellModal",
        "confirmSell", "deleteSell", "Venda in-game (legado)", "sell-list",
    ):
        assert needle not in html, needle
    # config continua legível/gravável (sem quebrar quem lê)
    assert "DisableSellButton" in html and 'id="g-disable-sell"' in html


def test_legacy_sell_redirects_to_market(html):
    m = re.search(r"const LEGACY_PAGE_ALIASES = (\{[^}]*\});", html)
    assert m, "LEGACY_PAGE_ALIASES ausente"
    assert 'sell: "market"' in m.group(1)
    assert 'midias: "tutoriais"' in m.group(1)  # alias anterior preservado
    assert "function resolveLegacyPage" in html
    nav_body = html.split("function nav(el) {", 1)[1][:600]
    assert "resolveLegacyPage(el.dataset.page)" in nav_body
    assert "function goToPage(page) {\n  page = resolveLegacyPage(page);" in html


def test_assets_included_with_cache_bust(html):
    assert re.search(r'<script src="resource_vitrine\.js\?v=__WEB_BUILD__" defer></script>', html)
    assert re.search(r'<link rel="stylesheet" href="resource_vitrine\.css\?v=__WEB_BUILD__"\s*/?>', html)
    assert (_STATIC / "resource_vitrine.js").is_file() and (_STATIC / "resource_vitrine.css").is_file()


def test_tutorial_mentions_vitrine(html):
    sec = html.split('id="tut-comercio"', 1)[1].split('id="tut-comandos"', 1)[0]
    assert "Vitrine de Recursos" in sec
    for cmd in ("/vitrine", "/confirmar", "/mercado"):
        assert cmd in sec
    assert "tamanho do lote" in sec and "preço do lote" in sec


# ── JS: rotas/payloads do contrato ───────────────────────────────────────────

def test_js_routes_match_backend(js):
    assert 'RV_API = "/api/market/resources"' in js
    backend = _ROUTES.read_text(encoding="utf-8")
    assert 'PREFIX = "/api/market/resources"' in backend
    expected = [
        ('"/catalog"', 'f"{PREFIX}/catalog"'),
        ('"/listings?"', 'f"{PREFIX}/listings"'),
        ('"/my"', 'f"{PREFIX}/my"'),
        ("/my/stock/${rid}/listing", 'f"{PREFIX}/my/stock/<int:resource_id>/listing"'),
        ('"/my/withdraw"', 'f"{PREFIX}/my/withdraw"'),
        ("/listings/${Number(l.stock_id)}/purchase", 'f"{PREFIX}/listings/<int:stock_id>/purchase"'),
        ('"/admin/catalog"', 'f"{PREFIX}/admin/catalog"'),
        ("/admin/catalog/${Number(id)}", 'f"{PREFIX}/admin/catalog/<int:resource_id>"'),
        ('"/admin/settings"', 'f"{PREFIX}/admin/settings"'),
        ('"/admin/claims/expire-stale"', 'f"{PREFIX}/admin/claims/expire-stale"'),
    ]
    for js_frag, backend_frag in expected:
        assert js_frag in js, js_frag
        assert backend_frag in backend, backend_frag
    # nenhuma chamada às rotas do plugin (X-API-Key) a partir do navegador
    assert 'rvApi("/plugin' not in js and "/plugin/" not in js


def test_js_payloads_and_methods(js):
    # compra: lotes inteiros + idempotência + preço esperado
    assert re.search(r"body:\s*\{\s*lots:\s*lots\.lots,\s*request_id:\s*RV\.buy\.reqId,\s*expected_price:\s*price\s*\}", js)
    # anúncio
    assert '{ lot_size: lot.size, lot_price: lot.price, active }' in js
    assert 'method: "PUT", body: payload' in js
    # retirada
    assert "payload.resource_id = w.rid" in js and "payload.quantity = q" in js and "request_id: w.reqId" in js
    # admin
    for frag in ("max_types_per_player", "stack_size", "min_lot_price", "max_lot_price", "enabled", 'method: "DELETE"'):
        assert frag in js, frag
    # erros da API tratados
    for code in ("insufficient_balance", "insufficient_stock", "price_changed", "self_purchase", "not_found"):
        assert f'"{code}"' in js, code
    # mensagens ao jogador
    assert "/mercado" in js and "24" in js and "reembols" in js
    # saldo atualizado após compra
    assert "updateBalanceDisplays" in js and "refreshPlayerBalance({ force: true })" in js


def test_js_isolated_namespace(js):
    # funções e estado globais têm prefixo próprio (não colidem com a vitrine de dinos)
    top_level = re.findall(r"^(?:async\s+)?function\s+(\w+)", js, re.M)
    assert top_level
    assert all(name.startswith("rv") for name in top_level), [n for n in top_level if not n.startswith("rv")]
    assert not re.search(r"\bmarket[A-Z]\w*\(", js)  # não chama o código de dinos
    assert "_marketBrowse" not in js and "market-browse" not in js


def test_js_blueprint_preview_strips_cdo_and_suffix(js):
    """O preview do admin usa a mesma canonização que o serviço (Default__ e _c)."""
    body = js.split("function rvNormalizeBlueprint", 1)[1].split("function rvAdminOpenForm", 1)[0]
    assert "Default__" in body
    assert "_c" in body or 'endsWith("c")' in body


def test_js_escapes_html_and_has_no_unsafe_sinks(js):
    assert "eval(" not in js and "document.write" not in js
    assert "rvEsc(" in js


def test_js_accessibility_basics(js, html):
    assert 'role="dialog"' in js or 'setAttribute("role", "dialog")' in js
    assert "aria-modal" in js and "aria-labelledby" in js and "aria-live" in js
    assert 'ev.key !== "Escape"' in js  # Esc fecha modal


def test_css_prefixed_and_responsive(css):
    selectors = re.findall(r"(?m)^\s*([.#][^{@/]+?)\s*\{", css)
    assert selectors
    assert all(".rv-" in s for s in selectors), [s for s in selectors if ".rv-" not in s]
    assert "@media (max-width: 640px)" in css


@pytest.mark.skipif(shutil.which("node") is None, reason="node não instalado")
def test_node_check_syntax():
    proc = subprocess.run(
        ["node", "--check", str(_STATIC / "resource_vitrine.js")], capture_output=True, text=True, timeout=60
    )
    assert proc.returncode == 0, proc.stderr


@pytest.mark.skipif(shutil.which("node") is None, reason="node não instalado")
def test_node_check_index_inline_scripts(html, tmp_path):
    """O JS inline do index.html continua sintaticamente válido após remover o código legado."""
    scripts = re.findall(r"<script>(.*?)</script>", html, re.S)
    assert scripts
    big = max(scripts, key=len)
    f = tmp_path / "inline.js"
    f.write_text(big, encoding="utf-8")
    proc = subprocess.run(["node", "--check", str(f)], capture_output=True, text=True, timeout=120)
    assert proc.returncode == 0, proc.stderr[:2000]


# ── Regressão: mudanças recentes de outros agentes seguem presentes ───────────

def test_other_agents_changes_not_reverted(html):
    assert 'data-shop-admin-tab="dino"' in html and 'data-shop-admin-tab="item"' in html
    assert "/api/admin/shop-items/bulk" in html and 'id="shop-bulk-bar"' in html
    assert 'id="tutoriais-videos"' in html
    assert html.index('id="tutoriais-videos"') < html.index('class="tutorial-hero"')
    assert "Reconsultar no MP" in html
    assert "presetLicense" not in html and "applyLicensePreset" not in html
    assert "_catalogDinoLevelFilter" in html and "_dinoLevelMax" in html  # filtro de níveis dinâmico
    assert "Gênero" in html and "Nv. " in html  # badges de Gênero/Nível nos cards de dinos
    assert 'data-page="midias"' not in html
