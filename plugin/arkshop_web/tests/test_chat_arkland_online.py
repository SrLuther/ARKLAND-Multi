from datetime import datetime, timedelta
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from chat_arkland_online import online_table, width
from chat_arkland_online_metrics import ADVANCES

NOW = datetime(2026, 11, 26, 21)
POLICY = {'ShowTribes': True, 'ShowOnlineTime': True}


def entry(name, id=1, tribe='BOT', map='Valguero OmG', minutes=50):
    return {'name': name, 'public_id': id, 'tribe_name': tribe, 'map': map,
            'connected_at': NOW - timedelta(minutes=minutes)}


def test_absolute_column_stops_and_centered_row_widths():
    rows = online_table([entry('Ciano'), entry('FLP', 2, 'The Hunter'),
                         entry('Santh', 3, 'Tribo de Santh'),
                         entry('Curalzinho', 4, 'Tribo de Curalzinho', 'Alps P.F.')], POLICY, True, NOW)
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
    assert ('Valguero' in rows[1]) == map


def test_long_wide_names_clip_without_truncating_id_or_hours():
    rows = online_table([entry('W' * 100, 123456789012, 'M' * 100, minutes=600000)], POLICY, True, NOW)
    assert rows[1].split('|')[0].strip().endswith('...')
    assert rows[1].split('|')[1].strip() == '123456789012'
    assert rows[1].split('|')[2].strip().endswith('...')
    assert rows[1].split('|')[4].strip() == '10000h00m'
    assert '|' == rows[1][-1]


def test_unicode_separators_and_absent_tribe_or_connection():
    player = entry('João | Águia', tribe='')
    player['connected_at'] = None
    rows = online_table([player], POLICY, True, NOW)
    assert rows[1].split('|')[0].strip() == 'João / Águia'
    assert rows[1].split('|')[2].strip() == '--'
    assert rows[1].split('|')[4].strip() == '0h00m'
    assert width('WWWW') > width('iiii')
    assert width('é') > 0 and width('a\u0301') == width('a')


def test_empty_page_is_still_a_valid_header():
    assert len(online_table([], POLICY, True, NOW)) == 1
