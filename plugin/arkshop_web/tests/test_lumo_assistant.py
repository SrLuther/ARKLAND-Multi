from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import lumo_assistant as assistant


def test_recognizes_accent_insensitive_triggers_with_word_boundaries():
    assert assistant.recognize_trigger("Qual é o status dos servidores?").key == "STATUS"
    assert assistant.recognize_trigger("Tem alguma votação aberta?").key == "VOTACAO"
    assert assistant.recognize_trigger("Como funciona o Bet Land?").key == "BETLAND"
    assert assistant.recognize_trigger("Spirit Rex é bom?") is None


def test_disabled_trigger_and_custom_alias_are_applied():
    assert assistant.recognize_trigger("status", enabled={"STATUS": False}) is None
    match = assistant.recognize_trigger("Qual o estado do cluster?", aliases={"STATUS": ["estado do cluster"]})
    assert match and match.key == "STATUS"


def test_specific_license_requires_license_or_economic_context():
    licenses = [{"group": "Ascensão", "label": "Licença Ascensão", "item_id": "asc", "aliases": ["ascensao"]}]
    assert assistant.recognize_trigger("O que acha da Ascensão?", licenses) is None
    match = assistant.recognize_trigger("Qual o preço da Licença Ascensão?", licenses)
    assert match and match.key == "LICENCAS" and match.rule == "license_specific"


def test_status_uses_admin_configured_channel_key():
    title, body = assistant.build_response(
        assistant.TriggerMatch("STATUS", "keyword_or_phrase"),
        {"ok": True},
        {"lumo_status_channel_id": "12345678901234567"},
    )
    assert "Status" in title
    assert "<#12345678901234567>" in body


def test_betland_and_poll_responses_use_live_payload_without_fabricating_data():
    match = assistant.TriggerMatch("BETLAND", "keyword_or_phrase")
    title, body = assistant.build_response(match, {
        "ok": True,
        "enabled": True,
        "campaign": {"status": "ACTIVE", "prize_amber_total": 1250, "amber_random_price": 10,
                     "amber_reserve_price": 20, "draw_at_display": "25/11/2026 20:00",
                     "seconds_remaining": 3600, "title": "Sorteio atual"},
    }, {})
    assert title == "Sorteio atual" and "1.250" in body and "25/11/2026" in body
    try:
        assistant.build_response(match, {"ok": False}, {})
    except RuntimeError:
        pass
    else:
        raise AssertionError("falha de fonte não pode se passar por Bet Land sem dados")

    _, polls = assistant.build_response(assistant.TriggerMatch("VOTACAO", "keyword_or_phrase"), {
        "ok": True, "polls": [{"id": 42, "is_open": True, "title": "Mapa favorito", "reward_amber": 20,
                                "ends_at": "2026-11-25T23:00:00+00:00"}],
    }, {})
    assert "Mapa favorito" in polls and "#/polls/42" in polls


def test_greetings_are_varied_and_discord_embed_limits_are_enforced():
    assert len(assistant.GREETING_REPLIES) >= 30
    assert assistant.pick_greeting(assistant.GREETING_REPLIES[0]) != assistant.GREETING_REPLIES[0]
    payload = assistant.make_embed_payload("Teste", "Corpo", now=datetime(2026, 11, 25, tzinfo=UTC))
    assert payload["color"] == assistant.COLOR
    assert payload["timestamp"] == "2026-11-25T00:00:00Z"
