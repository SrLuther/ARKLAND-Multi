"""Contratos estáticos e de acessibilidade do mascote do atendimento."""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / "static" / "index.html").read_text(encoding="utf-8")


def test_help_button_preserves_existing_widget_and_serves_mascot_art():
    assert 'id="support-fab"' in HTML
    assert 'onclick="supportWidgetOpenHelp()"' in HTML
    assert 'aria-controls="support-window"' in HTML
    assert 'src="arkland-help-cat-v1.png?v=__WEB_BUILD__"' in HTML
    assert 'class="support-fab__tail-layer"' not in HTML
    assert 'class="support-fab__plaque">Precisa de ajuda?' in HTML
    image = ROOT / "static" / "arkland-help-cat-v1.png"
    data = image.read_bytes()
    assert data.startswith(b"\x89PNG\r\n\x1a\n")
    assert data[25] == 6  # PNG color type RGBA, alpha channel retained.


def test_faq_keeps_ticket_creation_and_covers_requested_topics():
    for topic in ("Catálogo e criaturas", "Resgates e entregas", "Kits", "Licenças e Ambares", "Doações", "Vincular Discord"):
        assert topic in HTML
    assert 'supportWidgetFaqNeedHelp()' in HTML
    assert 'supportWidgetTab("new")' in HTML
    assert 'fetchJson("/api/tickets"' in HTML
    assert 'supportWidgetTab("list")' in HTML


def test_mascot_gaze_is_bounded_and_respects_reduced_motion():
    assert 'prefers-reduced-motion: reduce' in HTML
    assert 'requestAnimationFrame(paintGaze)' in HTML
    assert 'Math.max(-24,Math.min(24' in HTML
    assert 'Math.max(-17,Math.min(17' in HTML
    assert 'pointerleave",centerGaze' in HTML
    assert 'supportWidgetFaqResolved' in HTML


def test_mascot_uses_single_static_art_and_keeps_only_eye_animations():
    assert HTML.count('class="support-fab__art"') == 1
    assert 'class="support-fab__tail-layer"' not in HTML
    assert HTML.count('data-support-pupil=') == 2
    assert HTML.count('class="support-fab__lid"') == 2
    assert 'window.addEventListener("pointermove",onPointerMove' in HTML
    assert '.support-fab.is-blinking .support-fab__lid { animation:supportMascotBlink' in HTML
    assert 'initSupportMascotTail' not in HTML


def test_character_art_stays_grounded_until_articulated_layers_are_ready():
    assert 'class="support-fab__character"' in HTML
    assert '@keyframes supportMascotIdle' not in HTML
    assert 'support-fab__eyes' in HTML
    assert '.support-fab:hover { filter:drop-shadow(0 9px 15px rgba(0,0,0,.64)) drop-shadow(0 0 8px rgba(70,174,197,.28)); }' in HTML


def test_personalized_greeting_uses_authenticated_display_name_safely():
    assert 'id="support-head-title"' in HTML
    assert '_auth?.steam_persona||_auth?.display_name' in HTML
    assert 'title.textContent=name?' in HTML
