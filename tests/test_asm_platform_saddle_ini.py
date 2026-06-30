"""INI de platform saddle / torretas no Tek Strider (ASM TEK)."""
from __future__ import annotations

from src.asm_engine.asm_ini_manager import INI_MAP, write_ini
from src.asm_engine.asm_server_config import AsmServerConfig
from src.ui.server_field_labels import get_field_meta


def test_ini_map_platform_saddle_keys():
  assert INI_MAP["override_structure_platform_prevention"] == (
      "GUS", "ServerSettings", "OverrideStructurePlatformPrevention", {}
  )
  assert INI_MAP["allow_platform_saddle_multi_floors"] == (
      "Game", "GameMode", "bAllowPlatformSaddleMultiFloors", {}
  )
  assert INI_MAP["limit_turrets_in_range"][0:3] == (
      "Game", "GameMode", "bLimitTurretsInRange",
  )


def test_platform_saddle_field_discoverable_by_search():
  meta = get_field_meta("override_structure_platform_prevention")
  assert "stryder" in meta.search_text.lower()
  assert "torreta" in meta.search_text.lower()
  assert meta.section == "Estruturas"


def test_write_ini_emits_platform_saddle_override(tmp_path):
  cfg = AsmServerConfig()
  cfg.install_dir = str(tmp_path)
  cfg.override_structure_platform_prevention = True
  cfg.per_platform_max_structures_multiplier = 2.0
  cfg.allow_platform_saddle_multi_floors = True

  write_ini(cfg)

  gus = (
      tmp_path
      / "ShooterGame"
      / "Saved"
      / "Config"
      / "WindowsServer"
      / "GameUserSettings.ini"
  )
  game = gus.parent / "Game.ini"
  assert gus.is_file()
  assert game.is_file()

  gus_text = gus.read_text(encoding="utf-16")
  game_text = game.read_text(encoding="utf-16")

  assert "OverrideStructurePlatformPrevention=True" in gus_text
  assert "PerPlatformMaxStructuresMultiplier=2" in gus_text
  assert "bAllowPlatformSaddleMultiFloors=True" in game_text
