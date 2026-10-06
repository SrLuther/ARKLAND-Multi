"""Índice de blueprints: detecção, dedupe e filtro no sqlite."""
from __future__ import annotations

import os
import sys
from pathlib import Path

from sqlalchemy import create_engine, text

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from blueprint_index_service import (  # noqa: E402
    BlueprintIndexError,
    add_manual_blueprint,
    class_from_blueprint,
    collect_blueprint_index,
    delete_manual_blueprint,
    list_blueprint_index,
    rows_from_trees,
    sync_blueprint_index,
    update_manual_blueprint,
)

_REX = "/Game/PrimalEarth/Dinos/Rex/Rex_Character_BP.Rex_Character_BP"
_REX_WRAPPED = (
    "Blueprint'/Game/PrimalEarth/Dinos/Rex/Rex_Character_BP.Rex_Character_BP_C'"
)
_METAL = (
    "/Game/PrimalEarth/CoreBlueprints/Resources/"
    "PrimalItemResource_Metal.PrimalItemResource_Metal"
)
_REPLICATOR = (
    "/Game/PrimalEarth/CoreBlueprints/Items/Structures/Misc/"
    "PrimalItemStructure_TekReplicator.PrimalItemStructure_TekReplicator"
)
_WEIRD = "/Game/Mods/CustomPack/Foo/WeirdToken_BP.WeirdToken_BP"
_SERVICE = Path(__file__).resolve().parents[1] / "blueprint_index_service.py"
_ROUTES = Path(__file__).resolve().parents[1] / "blueprint_index_routes.py"
_HTML = Path(__file__).resolve().parents[1] / "static" / "index.html"
_FICHA_JS = Path(__file__).resolve().parents[1] / "static" / "primal_fear_ficha.js"


def _sample_rows() -> list[dict]:
    catalog = {
        "Items": {
            "rex_femea": {
                "Name": "Rex",
                "Type": "dino",
                "Blueprint": _REX,
            },
            "metal": {
                "Name": "Metal",
                "Type": "item",
                "Blueprint": _METAL,
            },
        },
        "Kits": {
            "kit_rex": {
                "Name": "Kit Rex",
                "Dinos": [{"Blueprint": _REX_WRAPPED}],
                "Commands": [
                    {"Command": "cheat AddExperience 1000000 0 0"},
                    {
                        "Command": (
                            'cheat UnlockEngram "Blueprint\''
                            + _REPLICATOR
                            + '\'"'
                        )
                    },
                    {
                        "Type": "command",
                        "Command": f'cheat GiveItem "{_WEIRD}" 1 0 0',
                    },
                ],
            }
        },
    }
    engram = {"Name": "Rifle", "entry": "EngramEntry_WeaponRifle_C"}
    vanilla = {
        "species": [{"species_key": "giga", "display_name": "Giganotossauro"}]
    }
    junk = {"blueprint_path": "/bp", "display_name": "Lixo"}
    return rows_from_trees(
        [
            (catalog, "catalog"),
            (engram, "asm_known_engrams"),
            (vanilla, "official_vanilla"),
            (junk, "market_species"),
        ]
    )


def _engine(tmp_path):
    return create_engine(f"sqlite:///{tmp_path / 'bidx.sqlite'}")


def test_extrai_game_engram_dedupe_e_ignora_lixo():
    rows = _sample_rows()
    norms = [row["ident_norm"] for row in rows]
    assert len(norms) == len(set(norms))
    rex = next(row for row in rows if row["identifier"] == _REX)
    assert rex["kind"] == "dino"
    assert rex["display_name"] == "Rex"
    assert rex["token"] == "rex_femea"
    assert set(rex["sources"]) == {"catalog_items", "catalog_kits"}
    assert not rex["identifier"].endswith("_C")
    metal = next(row for row in rows if row["identifier"] == _METAL)
    assert metal["kind"] == "item"
    replicator = next(row for row in rows if row["identifier"] == _REPLICATOR)
    assert replicator["kind"] == "estrutura"
    assert "catalog_comandos" in replicator["sources"]
    weird = next(row for row in rows if row["identifier"] == _WEIRD)
    assert weird["kind"] == "comando"
    rifle = next(row for row in rows if row["identifier"] == "EngramEntry_WeaponRifle_C")
    assert rifle["kind"] == "engrama"
    assert rifle["display_name"] == "Rifle"
    assert "asm_known_engrams" in rifle["sources"]
    assert all(row["display_name"] != "Giganotossauro" for row in rows)
    assert all(row["identifier"] != "/bp" for row in rows)
    assert all(
        row["identifier"].startswith("/Game/") or row["identifier"].startswith("EngramEntry_")
        for row in rows
    )
    assert not any("AddExperience" in row["identifier"] for row in rows)


def test_filtro_le_sqlite(tmp_path):
    engine = _engine(tmp_path)
    rows = _sample_rows()
    sync_blueprint_index(engine, force=True, rows=rows)
    dinos = list_blueprint_index(engine, q="REX", kind="dino")
    assert dinos["total"] == 1
    assert dinos["rows"][0]["identifier"] == _REX
    engrams = list_blueprint_index(engine, q="EngramEntry_WeaponRifle", kind="engrama")
    assert engrams["total"] == 1
    assert engrams["rows"][0]["display_name"] == "Rifle"
    by_token = list_blueprint_index(engine, q="rex_femea")
    assert by_token["total"] == 1
    by_source = list_blueprint_index(engine, source="asm_known_engrams")
    assert by_source["total"] == 1
    assert by_source["rows"][0]["kind"] == "engrama"
    comandos = list_blueprint_index(engine, source="catalog_comandos")
    assert {row["kind"] for row in comandos["rows"]} == {"estrutura", "comando"}
    assert list_blueprint_index(engine, q="giga")["total"] == 0
    assert list_blueprint_index(engine, kind="item")["total"] == 1
    sync_blueprint_index(engine, force=True, rows=rows[:1])
    assert list_blueprint_index(engine)["total"] == 1


def test_banco_market_species_sem_lixo_e_sem_apagar_outra_tabela(tmp_path):
    engine = _engine(tmp_path)
    with engine.begin() as conn:
        conn.execute(
            text(
                "CREATE TABLE players (steam_id TEXT PRIMARY KEY, points INT)"
            )
        )
        conn.execute(text("INSERT INTO players (steam_id, points) VALUES ('9', 5)"))
        conn.execute(
            text(
                "CREATE TABLE market_species ("
                "blueprint_path TEXT, display_name TEXT, species_key TEXT)"
            )
        )
        conn.execute(
            text(
                "INSERT INTO market_species (blueprint_path, display_name, species_key) "
                "VALUES (:path, :name, :key)"
            ),
            [
                {"path": _REX, "name": "Rex DB", "key": "rex_db"},
                {"path": "/bp", "name": "Lixo", "key": "lixo"},
                {"path": "", "name": "Vazio", "key": "vazio"},
                {
                    "path": "EngramEntry_SaddleRex_C",
                    "name": "Sela de Rex",
                    "key": "sela",
                },
            ],
        )
        conn.execute(
            text(
                "CREATE TABLE market_species_aliases ("
                "blueprint_path TEXT, variant_label TEXT)"
            )
        )
        conn.execute(
            text(
                "INSERT INTO market_species_aliases (blueprint_path, variant_label) "
                "VALUES (:path, :label)"
            ),
            {"path": _REX_WRAPPED, "label": "Variante"},
        )
    packed = collect_blueprint_index(
        repo_root=tmp_path,
        include_live=False,
        include_bundled=False,
        engine=engine,
    )
    assert packed["errors"] == []
    rows = packed["rows"]
    assert len(rows) == 2
    rex = next(row for row in rows if row["identifier"] == _REX)
    assert rex["kind"] == "dino"
    assert rex["display_name"] == "Rex DB"
    assert rex["token"] == "rex_db"
    assert set(rex["sources"]) == {"market_species", "market_aliases"}
    saddle = next(row for row in rows if row["identifier"] == "EngramEntry_SaddleRex_C")
    assert saddle["kind"] == "engrama"
    assert saddle["display_name"] == "Sela de Rex"
    sync_blueprint_index(engine, force=True, rows=rows)
    with engine.connect() as conn:
        points = conn.execute(text("SELECT points FROM players WHERE steam_id = '9'")).scalar()
        species = conn.execute(text("SELECT COUNT(*) FROM market_species")).scalar()
    assert points == 5
    assert species == 4
    skipped = sync_blueprint_index(engine)
    assert skipped["skipped"] is True
    assert list_blueprint_index(engine, q="rex_db")["total"] == 1


def test_fontes_do_repositorio():
    packed = collect_blueprint_index(include_live=False, include_bundled=True, engine=None)
    assert packed["errors"] == []
    rows = packed["rows"]
    assert any(row["identifier"].startswith("/Game/") for row in rows)
    rifle = next(
        (row for row in rows if row["identifier"] == "EngramEntry_WeaponRifle_C"),
        None,
    )
    assert rifle is not None
    assert rifle["kind"] == "engrama"
    assert rifle["display_name"] == "Rifle"
    assert "asm_known_engrams" in rifle["sources"]
    pick = next(row for row in rows if row["identifier"] == "EngramEntry_Pick_Stone_C")
    assert pick["kind"] == "engrama"
    assert pick["display_name"] == "Picareta de Pedra"
    metal = next(
        row for row in rows if row["identifier"] == "EngramEntry_BlueprintStation_Metal_C"
    )
    assert metal["kind"] == "engrama"
    assert "asm_engram_entries" in metal["sources"]
    norms = [row["ident_norm"] for row in rows]
    assert len(norms) == len(set(norms))
    assert all(row["kind"] in {
        "item", "dino", "engrama", "estrutura", "comando", "outro",
    } for row in rows)


def test_pagina_admin_e_rota():
    html = _HTML.read_text(encoding="utf-8")
    assert 'id="page-blueprint-index" class="page admin-only"' in html
    assert 'data-page="blueprint-index"' in html
    assert "admin-only" in html.split('data-page="blueprint-index"')[0][-80:]
    assert "Busca de blueprints" in html
    assert 'id="bidx-class"' in html
    assert ">Observações<" in html
    ficha_js = _FICHA_JS.read_text(encoding="utf-8")
    assert "/api/admin/blueprint-index" in ficha_js
    assert "blueprintClassFrom" in ficha_js
    routes = _ROUTES.read_text(encoding="utf-8")
    assert 'methods=["PATCH"]' in routes
    assert 'methods=["DELETE"]' in routes
    assert "@admin_required" in routes
    assert "/api/admin/blueprint-index" in routes
    service = _SERVICE.read_text(encoding="utf-8")
    assert "usebeacon" not in service
    assert "write_text" not in service
    assert "Game.ini" not in service
    assert "Mapas" not in service


def test_sync_pytest_nao_substitui_sem_force(tmp_path):
    engine = _engine(tmp_path)
    sync_blueprint_index(
        engine,
        force=True,
        rows=[
            {
                "ident_norm": "engramentry_weaponrifle_c",
                "identifier": "EngramEntry_WeaponRifle_C",
                "kind": "engrama",
                "display_name": "Rifle",
                "token": "WeaponRifle",
                "sources": ["asm_known_engrams"],
            }
        ],
    )
    again = sync_blueprint_index(engine)
    assert again["skipped"] is True
    assert again["count"] == 1
    assert list_blueprint_index(engine, kind="engrama")["total"] == 1


def test_manual_edita_exclui_projeto_trava_sync_e_classe(tmp_path):
    assert class_from_blueprint("EngramEntry_WeaponRifle_C") == "EngramEntry_WeaponRifle_C"
    assert class_from_blueprint("PrimalItem_WeaponGun_C") == "PrimalItem_WeaponGun_C"
    assert class_from_blueprint(_REX) == "Rex_Character_BP"
    assert class_from_blueprint(
        "Blueprint'/Game/Mods/A/B.B'"
    ) == "B"

    engine = _engine(tmp_path)
    rows = _sample_rows()
    for row in rows:
        if row["identifier"] == _REX:
            row["display_name"] = "Rex antigo"
    sync_blueprint_index(engine, force=True, rows=rows)
    project = list_blueprint_index(engine, q="Rex antigo", kind="dino")
    assert project["total"] == 1
    locked = project["rows"][0]
    assert locked["editable"] is False
    assert locked["class_name"] == "Rex_Character_BP"
    assert "catalog_items" in locked["sources"]

    def _touch_project():
        return update_manual_blueprint(
            engine,
            ident_norm=locked["ident_norm"],
            identifier=_REX,
            kind="dino",
            display_name="Não muda",
            mod_name="Fora",
            note="não",
        )

    with pytest.raises(BlueprintIndexError) as edited:
        _touch_project()
    assert "já existe no projeto" in edited.value.message
    assert "Atualize na origem" in edited.value.message
    assert "Catálogo — itens" in edited.value.message
    with pytest.raises(BlueprintIndexError) as removed:
        delete_manual_blueprint(engine, ident_norm=locked["ident_norm"])
    assert "Atualize na origem" in removed.value.message
    assert "Catálogo — itens" in removed.value.message
    assert list_blueprint_index(engine, q="Rex antigo")["total"] == 1

    with pytest.raises(BlueprintIndexError) as duplicated:
        add_manual_blueprint(
            engine,
            identifier=_REX,
            kind="dino",
            display_name="Outro rex",
            mod_name="Outro",
            note="",
        )
    assert "Atualize na origem" in duplicated.value.message
    assert "Catálogo — itens" in duplicated.value.message
    other = "/Game/OtherPack/Rex/Rex_Character_BP.Rex_Character_BP"
    with pytest.raises(BlueprintIndexError) as same_class:
        add_manual_blueprint(
            engine,
            identifier=other,
            kind="dino",
            display_name="Rex copiado",
            mod_name="Outro",
            note="",
        )
    assert "Atualize na origem" in same_class.value.message

    path = "/Game/Mods/MeuMod/Dinos/Foo/Foo_Character_BP.Foo_Character_BP"
    created = add_manual_blueprint(
        engine,
        identifier=path,
        kind="dino",
        display_name="Foo manual",
        mod_name="Meu Mod",
        note="não doma",
    )
    assert created["class_name"] == "Foo_Character_BP"
    assert created["editable"] is True
    updated = update_manual_blueprint(
        engine,
        ident_norm=created["ident_norm"],
        identifier=path,
        kind="sela",
        display_name="Foo editado",
        mod_name="Meu Mod",
        note="domado, kibble simples",
    )
    assert updated["display_name"] == "Foo editado"
    assert updated["kind"] == "sela"
    assert updated["class_name"] == "Foo_Character_BP"
    by_mod = list_blueprint_index(engine, q="Meu Mod")
    assert by_mod["total"] == 1
    assert by_mod["rows"][0]["note"] == "domado, kibble simples"
    assert list_blueprint_index(engine, q="Foo_Character_BP")["total"] == 1

    fresh = []
    for row in rows:
        if row["identifier"] == _REX:
            fresh.append({**row, "display_name": "Rex novo"})
        else:
            fresh.append(row)
    sync_blueprint_index(engine, force=True, rows=fresh)
    renewed = list_blueprint_index(engine, q="Rex novo", kind="dino")
    assert renewed["total"] == 1
    assert renewed["rows"][0]["editable"] is False
    assert list_blueprint_index(engine, q="Rex antigo")["total"] == 0
    kept = list_blueprint_index(engine, q="Foo editado")
    assert kept["total"] == 1
    assert kept["rows"][0]["editable"] is True
    assert kept["rows"][0]["mod_name"] == "Meu Mod"
    assert kept["rows"][0]["note"] == "domado, kibble simples"
    assert kept["rows"][0]["sources"] == ["manual"]

    delete_manual_blueprint(engine, ident_norm=created["ident_norm"])
    assert list_blueprint_index(engine, q="Foo editado")["total"] == 0
    assert list_blueprint_index(engine, q="Rex novo")["total"] == 1
