import pytest

from src.asm_engine.level_progression import (
    DinoProgression,
    PlayerProgression,
)


def test_player_table_keeps_rows_independent_and_derives_engram_totals():
    player = PlayerProgression.from_thresholds(
        [0, 100, 270, 360], [0, 8, 8, 12], first_level=7, enabled=True, max_xp=400
    )

    assert player.enabled is True
    assert [row.level for row in player.levels] == [7, 8, 9, 10]
    assert player.engram_total_before(10) == 16
    assert player.levels[2].xp_required == 270
    assert player.validate() == []


def test_dino_table_has_its_own_level_range_and_xp_cap():
    dino = DinoProgression.from_thresholds(
        [6_840_703, 7_695_791], first_level=200, enabled=True, max_xp=8_000_000
    )

    assert [(row.level, row.xp_required) for row in dino.levels] == [
        (200, 6_840_703),
        (201, 7_695_791),
    ]
    assert dino.validate() == []


@pytest.mark.parametrize(
    "xp,points",
    [([1, 2], [8]), ([2, 1], [8, 8]), ([1, -1], [8, 8])],
)
def test_player_import_rejects_mismatched_or_invalid_ramps(xp, points):
    with pytest.raises(ValueError):
        PlayerProgression.from_thresholds(xp, points)


def test_player_and_dino_models_do_not_share_mutable_levels():
    player = PlayerProgression.from_thresholds([0], [0], enabled=True)
    dino = DinoProgression.from_thresholds([0], enabled=False)

    player.levels[0].xp_required = 250

    assert dino.levels[0].xp_required == 0
    assert dino.enabled is False
