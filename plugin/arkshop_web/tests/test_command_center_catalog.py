"""Contract checks for the static admin command catalog and UI integration."""
from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_admin_command_catalog_has_portuguese_descriptions_and_compatibility() -> None:
    catalog = json.loads((ROOT / "static" / "ark_admin_commands.json").read_text(encoding="utf-8"))
    assert len(catalog) == 238
    assert len({(item["name"], tuple(item["compatibility"])) for item in catalog}) == len(catalog)
    assert all(item.get("description_pt", "").strip() for item in catalog)
    assert all(item.get("label_pt", "").strip() for item in catalog)
    assert all(item.get("syntax") and item.get("source_url") for item in catalog)
    assert all(item.get("compatibility") for item in catalog)
    assert all(isinstance(item.get("parameters"), list) for item in catalog)
    assert all(parameter.get("label_pt", "").strip() for item in catalog for parameter in item["parameters"])


def test_admin_command_center_is_integrated_as_admin_only_and_manual_copy() -> None:
    page = (ROOT / "static" / "index.html").read_text(encoding="utf-8")
    script = (ROOT / "static" / "command-center.js").read_text(encoding="utf-8")
    assert 'data-page="command-center"' in page
    assert 'id="page-command-center" class="page admin-only"' in page
    assert 'onclick="commandCenterCopy()"' in script
    assert "never executes commands" in script
    assert '"/api/admin/map-members/online"' in script
    assert '"/api/servers"' in script


def test_ase_is_default_and_player_id_is_not_aliased_to_steam_id() -> None:
    script = (ROOT / "static" / "command-center.js").read_text(encoding="utf-8")
    assert 'command.compatibility || []).includes("ASE")' in script
    assert "SteamID64" in script
    assert "Player ID numérico" in script
    assert "if (player && isSteam) value = player.steam_id" in script
    assert "if (player && isPlayerId)" not in script
