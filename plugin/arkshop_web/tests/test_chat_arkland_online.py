from datetime import datetime, timedelta
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from chat_arkland_online import online_table, width
from chat_arkland_online_metrics import ADVANCES, KERNING

NOW = datetime(2026, 11, 26, 21)
POLICY = {'ShowTribes': True, 'ShowOnlineTime': True}


def entry(name, id=1, tribe='BOT', map='Valguero OmG', minutes=50):
    return {'name': name, 'public_id': id, 'tribe_name': tribe, 'map': map,
            'connected_at': NOW - timedelta(minutes=minutes)}


def test_absolute_column_stops_and_centered_row_widths():
    rows = online_table([entry('Ciano'), entry('FLP', 2, 'The Hunter'),
                         entry('Santh', 3, 'Tribo de Santh'),
                         entry('Curalzinho', 4, 'Tribo de Curalzinho', 'Alps P.F.')], POLICY, True, NOW)
    rows = [row for row in rows if '|' in row]
    for index in range(5):
        positions = [width('|'.join(row.split('|')[:index + 1])) for row in rows]
        assert max(positions) - min(positions) <= ADVANCES[32] + .001
    assert rows[1].split('|')[4].strip() == '0h50m'
    assert len({len(row.split('|')) for row in rows}) == 1


@pytest.mark.parametrize('tribes,time,map', [(False, False, False), (True, False, False), (False, True, True)])
def test_disabled_and_private_columns_omitted(tribes, time, map):
    rows = online_table([entry('João')], {'ShowTribes': tribes, 'ShowOnlineTime': time}, map, NOW)
    assert ('TRIBO' in rows[0]) == tribes
    assert ('TEMPO' in rows[0]) == time
    assert ('MAPA' in rows[0]) == map
    assert ('Valguero' in rows[2]) == map


def test_long_wide_names_clip_without_truncating_id_or_hours():
    rows = online_table([entry('W' * 100, 123456789012, 'M' * 100, minutes=600000)], POLICY, True, NOW)
    assert rows[2].split('|')[0].strip().endswith('...')
    assert rows[2].split('|')[1].strip() == '123456789012'
    assert rows[2].split('|')[2].strip().endswith('...')
    assert rows[2].split('|')[4].strip() == '10000h00m'
    assert '|' == rows[2][-1]


def test_unicode_separators_and_absent_tribe_or_connection():
    player = entry('João | Águia', tribe='')
    player['connected_at'] = None
    rows = online_table([player], POLICY, True, NOW)
    assert rows[2].split('|')[0].strip() == 'João / Águia'
    assert rows[2].split('|')[2].strip() == '--'
    assert rows[2].split('|')[4].strip() == '0h00m'
    assert width('WWWW') > width('iiii')
    assert width('é') > 0 and width('a\u0301') == width('á')


def test_empty_page_is_still_a_valid_header():
    assert len(online_table([], POLICY, True, NOW)) == 2


def test_baked_font_and_whitespace_kerning_regression():
    assert len(ADVANCES) == 256
    assert KERNING == -9
    assert ADVANCES[32] == 19 and ADVANCES[ord('W')] == 40
    assert width('AA') == 2 * ADVANCES[ord('A')] - 9
    assert width('A A') == 2 * ADVANCES[ord('A')] + 19 - 9
    assert width('A  A') == width('A A') + 19
    assert width('🙂') == 2 * ADVANCES[127] - 9  # FString surrogate pair.


def test_model_reproduces_the_reported_bad_capture():
    # Literal 1.12.37 output, with measured bar centers from the administrator's
    # screenshot. These are independent of the new layout's padding algorithm.
    old_rows = [
        'NOME          | ID  | TRIBO                          | TEMPO  |',
        'Ciano           | 1    | Tribo de Santh          | 1h21m   |',
        'Santh           | 3   | Tribo de Santh           | 0h55m   |',
        'Curalzinho  | 4    | Tribo de Curalzinho  | 0h48m  |',
    ]
    measured = [[307.5,377,797,921.5], [356.5,436.5,757,880],
                [349,420,753.5,888.5], [347.5,432.5,706,830.5]]
    for row, expected in zip(old_rows, measured):
        predicted = [0.6719 * (width(row[:i]) - width(row) / 2) + 516.65
                     for i, char in enumerate(row) if char == '|']
        assert max(abs(a - b) for a, b in zip(predicted, expected)) < .5


def test_reported_players_align_after_client_centering():
    players = [entry('Ciano', 1, 'Tribo de Santh', minutes=81),
               entry('Santh', 3, 'Tribo de Santh', minutes=55),
               entry('Curalzinho', 4, 'Tribo de Curalzinho', minutes=48)]
    rows = online_table(players, POLICY, False, NOW)
    rows = [row for row in rows if '|' in row]
    positions = []
    for row in rows:
        starts = [0] + [i + 2 for i, char in enumerate(row) if char == '|' and i + 2 < len(row)]
        positions.append([width(row[:i + 1]) - ADVANCES[ord(row[i])] - width(row) / 2 for i in starts])
    # Spaces are indivisible. Bound the residual with the *captured* HUD scale,
    # rather than assuming equal character counts or validating a desktop font.
    for index in range(4):
        assert (max(row[index] for row in positions) - min(row[index] for row in positions)) * .6719 < 8


@pytest.mark.parametrize('show_map', [False, True])
def test_horizontal_rule_between_header_and_players(show_map):
    rows = online_table([entry('Ciano'), entry('Curalzinho', 4, 'Tribo de Curalzinho')], POLICY, show_map, NOW)
    assert rows[0].startswith('NOME')
    assert set(rows[1]) == {'-'}
    assert rows[2].startswith('Ciano') and rows[3].startswith('Curalzinho')
    target = (min(width(row) for row in rows if '|' in row) + max(width(row) for row in rows if '|' in row)) / 2
    assert abs(width(rows[1]) - target) <= (ADVANCES[ord('-')] + KERNING) / 2
