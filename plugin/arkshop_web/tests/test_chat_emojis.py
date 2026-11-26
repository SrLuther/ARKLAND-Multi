from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).parents[1]))
from chat_arkland_emojis import EMOJIS, native_image, normalize_emojis, render_emojis
from chat_arkland_config import DEFAULTS, format_global, validate_config
from .test_chat_arkland import hub, player, exchange, event, A, B, C


@pytest.mark.parametrize("row", EMOJIS, ids=lambda row: row["asset"])
def test_basic_native_ascii_unicode_roundtrip(row):
    expected = row["unicode"]
    image = native_image(row["asset"])
    for value in [expected, image, *row["ascii"], *row["aliases"]]:
        assert normalize_emojis("Oi " + value) == "Oi " + expected
        assert render_emojis("Oi " + value) == "Oi " + image


def test_foreign_markup_and_paths_stay_escaped():
    for body in ('<img src="Chat.Image" path="/Other/Unsafe.Unsafe"/>',
                 '<img src="Chat.Image" path="/Game/PrimalEarth/Emo/Emo_Unknown.Emo_Unknown"/>',
                 '<img src="Chat.Image" path="/Game/PrimalEarth/Emo/Emo_Smile.Emo_Smile" onerror="bad"/>',
                 '<RichColor Color="1,0,0,1">fake</>', '<img src="https://attacker/image.png"/>'):
        assert normalize_emojis(body) == body
        assert "<img" not in render_emojis(body)
        assert "<RichColor" not in render_emojis(body)
    assert normalize_emojis('&lt;img src="Chat.Image" path="/Game/PrimalEarth/Emo/Emo_Smile.Emo_Smile"/&gt;').startswith('&lt;img')


def test_urls_identifiers_and_longer_tokens_are_not_rewritten():
    text = 'https://arkland.com.br/:) ftp://example/x=:P www.exemplo.com/:D abc:D :Download Olá:)'
    assert normalize_emojis(text) == text
    assert normalize_emojis('>:) :)! (;) :P') == '😈 🙂! (😉 😛'


def test_icon_runs_are_outside_color_spans():
    cfg = validate_config({})
    payload = format_global(cfg, {"name": "<img fake>", "tribe_name": ""}, "1", "Mapa", "Oi :) tudo")
    image = native_image('Emo_Smile')
    assert payload['body'] == 'Oi 🙂 tudo'
    assert payload['plain'].endswith('Oi 🙂 tudo')
    assert '</>' + image + '<RichColor' in payload['rich']
    assert '&lt;img' not in payload['rich']
    assert '‹img fake›' in payload['plain']


def test_normalization_precedes_length_and_censorship():
    cfg = validate_config({})
    cfg['MaxMessageLength'] = 10
    cfg['BadWords'].update(Enabled=True, Words=['PrimalEarth', 'ruim'])
    payload = format_global(cfg, {"name": "A"}, "1", "Mapa", 'ruim ' + native_image('Emo_Smile'))
    assert payload['body'] == '**** 🙂'
    assert native_image('Emo_Smile') in payload['rich']


def test_legacy_game_message_long_tags_is_accepted_and_relayed(hub):
    service, _, _ = hub
    a = player(A, 'aaaaaaaa')
    b = player(B, 'bbbbbbbb')
    exchange(service, 'tek:aaa', 'aaaaaaaa', [a])
    exchange(service, 'tek:bbb', 'bbbbbbbb', [b])
    body = ' '.join([native_image('Emo_Smile')] * 8)
    assert len(body) > DEFAULTS['MaxMessageLength']
    e = event(A, 'global', body)
    reply = exchange(service, 'tek:aaa', 'aaaaaaaa', [a], [e])
    assert e['event_id'] in reply['accepted']
    received = exchange(service, 'tek:bbb', 'bbbbbbbb', [b])
    rows = [row for row in received['deliveries'] if row['kind'] == 'global' and row['event_id'] == e['event_id']]
    assert len(rows) == 1
    assert rows[0]['body'] == ' '.join(['🙂'] * 8)
    assert rows[0]['rich'].count(native_image('Emo_Smile')) == 8
    assert '<img' not in rows[0]['discord_plain']


def test_private_emojis_remain_private(hub):
    service, _, _ = hub
    a, b, c = player(A, 'aaaaaaaa'), player(B, 'bbbbbbbb'), player(C, 'bbbbbbbb')
    exchange(service, 'tek:aaa', 'aaaaaaaa', [a])
    identities = exchange(service, 'tek:bbb', 'bbbbbbbb', [b, c])
    e = event(A, 'pm', str(identities['players'][B]['public_id']) + ' ' + native_image('Emo_Wink'))
    exchange(service, 'tek:aaa', 'aaaaaaaa', [a], [e])
    reply = exchange(service, 'tek:bbb', 'bbbbbbbb', [b, c])
    messages = [row for row in reply['deliveries'] if row['kind'] == 'pm']
    assert len(messages) == 1 and messages[0]['recipients'] == [B]
    assert messages[0]['text'].endswith('😉')
    assert service.claim_discord('emoji-test') is None


def test_discord_portable_faces_render_as_native_images(hub):
    service, _, _ = hub
    a = player(A, 'aaaaaaaa')
    exchange(service, 'tek:aaa', 'aaaaaaaa', [a])
    assert service.ingest_discord('998877', '112233', 'Pessoa', 'Oi :) 😉')
    reply = exchange(service, 'tek:aaa', 'aaaaaaaa', [a])
    row = next(row for row in reply['deliveries'] if row['kind'] == 'global' and row['body'] == 'Oi 🙂 😉')
    assert native_image('Emo_Smile') in row['rich'] and native_image('Emo_Wink') in row['rich']
