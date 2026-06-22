"""Testes das categorias de preset/import ASM."""
from src.asm_engine.asm_config_categories import (
    PRESET_CATEGORIES,
    get_preset_category_fields,
    iter_preset_categories,
    resolve_preset_category,
)
from src.asm_engine.asm_preset_manager import AsmPresetManager, format_preset_categories
from src.asm_engine.asm_server_config import AsmServerConfig


def test_all_import_categories_available_as_presets():
    slugs = [slug for slug, _ in iter_preset_categories()]
    assert len(slugs) == 22
    assert "senhas_mods" in slugs
    assert "custom_game_ini" in slugs
    assert "pgm" in slugs


def test_legacy_preset_category_aliases():
    assert resolve_preset_category("players") == "jogadores"
    assert resolve_preset_category("rules") == "regras"
    old_fields = set(get_preset_category_fields("players"))
    new_fields = set(get_preset_category_fields("jogadores"))
    assert old_fields == new_fields


def test_preset_categories_exclude_identity_fields():
    full = set(PRESET_CATEGORIES["full"])
    assert "server_port" not in full
    assert "install_dir" not in full
    assert "session_name" not in full


def test_save_preset_includes_engramas(tmp_path, monkeypatch):
    monkeypatch.setattr(AsmPresetManager, "__init__", lambda self: None)
    pm = AsmPresetManager()
    pm._dir = tmp_path

    srv = AsmServerConfig()
    srv.auto_unlock_all_engrams = True
    srv.engram_entries_raw = "TestEngram=1"

    pm.save_preset("test", srv, ["engramas"])
    payload = (tmp_path / "test.json").read_text(encoding="utf-8")
    assert "auto_unlock_all_engrams" in payload
    assert "engram_entries_raw" in payload


def test_format_preset_categories_uses_labels():
    text = format_preset_categories(["jogadores", "players", "pgm"])
    assert "Jogadores" in text
    assert "PGM" in text
