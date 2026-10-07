"""Base Primal Fear: quatro blocos, com chefes fora do cálculo."""
from __future__ import annotations

import json
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

import market_economy as me
from primal_fear_secondary import primal_fear_base_ladder

_HTML = Path(__file__).resolve().parents[1] / "static" / "index.html"
_BOSS_REASON = (
    "Não entra no cálculo. São chefes não domesticáveis. "
    "Ficam de fora para evitar desgaste na base de preço."
)


def _ankylo_root() -> int:
    data = json.loads(me._bundled_defaults_path().read_text(encoding="utf-8"))
    anky = next(row for row in data["species"] if row["species_key"] == "ankylosaurus")
    return int(anky["root_value"])


def _block(ladder: dict, block_id: str) -> dict:
    return next(block for block in ladder["blocks"] if block["id"] == block_id)


def _row(block: dict, label: str) -> dict:
    return next(row for row in block["rows"] if row["label"] == label)


def _part(block: dict, label: str, name: str | None = None) -> dict:
    parts = _row(block, label)["parts"]
    if name is None:
        return parts[0]
    return next(part for part in parts if part["name"] == name)


def test_main_line_vanilla_below_toxic_below_alpha_and_bosses_stay_unpriced():
    root = _ankylo_root()
    assert root > 0
    ladder = primal_fear_base_ladder(root, cap=me.ECONOMY_TABLE_CAP)
    assert [block["id"] for block in ladder["blocks"]] == [
        "progression",
        "parallels",
        "expansions",
        "bosses",
    ]

    line = _block(ladder, "progression")
    assert [row["label"] for row in line["rows"]] == [
        "Vanilla",
        "Toxic",
        "Alpha",
        "Elemental Básico",
        "Apex",
        "Elemental Avançado",
        "Fabled",
        "Omega",
        "Celestial e Demonic",
        "Chaos e Spirit",
    ]
    vanilla = _part(line, "Vanilla")
    toxic = _part(line, "Toxic")
    alpha = _part(line, "Alpha")
    apex = _part(line, "Apex")
    fabled = _part(line, "Fabled")
    omega = _part(line, "Omega")
    assert vanilla["multiplier"] == 1 and vanilla["index"] == 0.2
    assert toxic["multiplier"] == 3 and toxic["index"] == 0.6
    assert alpha["multiplier"] == 5 and alpha["index"] == 1
    assert vanilla["index"] < toxic["index"] < alpha["index"]
    assert vanilla["reference"] < toxic["reference"] < alpha["reference"]
    assert apex["index"] == 2
    assert apex["reference"] == 2 * alpha["reference"]
    assert fabled["multiplier"] == 16 and fabled["index"] == 3.2
    assert omega["multiplier"] == 13 and omega["index"] == 2.6
    labels = [row["label"] for row in line["rows"]]
    assert labels.index("Fabled") < labels.index("Omega")
    assert omega["reference"] < fabled["reference"]
    assert _part(line, "Celestial e Demonic", "Celestial")["index"] == 5.5
    assert _part(line, "Celestial e Demonic", "Demonic")["multiplier"] == 27.5
    assert _part(line, "Chaos e Spirit", "Chaos")["index"] == 8
    assert _part(line, "Chaos e Spirit", "Spirit")["multiplier"] == 40

    expansions = _block(ladder, "expansions")
    noxious = _part(expansions, "Noxious")
    fey = _part(expansions, "Fey")
    assert noxious["inherited_from"] == "Toxic"
    assert noxious["index"] == toxic["index"] == 0.6
    assert noxious["reference"] == toxic["reference"]
    assert fey["inherited_from"] == "Celestial / Demonic"
    assert fey["index"] == 5.5
    assert fey["multiplier"] == 27.5

    parallels = _block(ladder, "parallels")
    assert [row["label"] for row in parallels["rows"]] == [
        "Elder",
        "Malin",
        "Buffoon",
        "Primal Tek",
        "Corrupted",
        "Miscellaneous",
    ]
    for row in parallels["rows"]:
        part = row["parts"][0]
        if row["label"] == "Primal Tek":
            assert part["multiplier"] == 12 and part["index"] == 2.4
            assert part["inherited_from"] is None
            index_dec = (Decimal("12") / Decimal(5)).quantize(Decimal("0.1"))
            expected = int((Decimal(root) * index_dec).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
            assert part["reference"] == min(expected, 600_000)
        else:
            assert part["multiplier"] is None
            assert part["index"] is None
            assert part["reference"] is None

    bosses = _block(ladder, "bosses")
    assert bosses["priced"] is False
    assert bosses["intro"] == _BOSS_REASON
    assert [row["label"] for row in bosses["rows"]] == [
        "Mini Bosses",
        "Primals",
        "Origins",
        "Emperor e Empress",
        "Guardians",
        "Gods/Creators",
        "Colossus",
        "Pikkon's Revenge",
    ]
    for row in bosses["rows"]:
        part = row["parts"][0]
        assert part["multiplier"] is None
        assert part["index"] is None
        assert part["reference"] is None

    capped = primal_fear_base_ladder(200_000, cap=600_000)
    capped_line = _block(capped, "progression")
    assert _part(capped_line, "Vanilla")["reference"] < _part(capped_line, "Toxic")["reference"]
    assert _part(capped_line, "Toxic")["reference"] < _part(capped_line, "Alpha")["reference"]
    assert _part(capped_line, "Chaos e Spirit", "Chaos")["reference"] == 600_000
    assert _part(_block(capped, "bosses"), "Mini Bosses")["reference"] is None


def test_base_tab_keeps_bosses_visible_outside_the_price():
    html = _HTML.read_text(encoding="utf-8")
    assert 'data-market-economy-tab="pf"' in html
    assert "Base Primal Fear" in html
    assert 'data-market-economy-tab="caps"' in html
    assert "Por espécie" in html
    assert "Simulador" in html
    start = html.find("function renderMarketEconomyPfBase")
    end = html.find("function renderMarketEconomySpecies", start)
    fn = html[start:end]
    assert "me-pf-bosses" in fn
    assert "block.priced !== false" in fn
    assert "block.intro" in fn
    assert "ladder.steps" not in fn
    assert "Fabled / Omega" not in fn
