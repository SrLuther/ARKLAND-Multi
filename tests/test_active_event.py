"""ActiveEvent — valores oficiais ARK e escrita INI/CLI (TEK + clássico)."""
from __future__ import annotations

from src.asm_engine.asm_ini_manager import INI_MAP, _launch_url_params, write_ini
from src.asm_engine.asm_server_config import AsmServerConfig
from src.server_config import ServerConfig
from src.ui_constants import (
    _ARK_EVENT_LABEL_TO_ID,
    _ARK_EVENT_LEGACY_ALIASES,
    normalize_active_event,
)


def test_normalize_active_event_legacy_aliases():
    assert normalize_active_event("ARKEaster") == "Easter"
    assert normalize_active_event("LoveEvolved") == "vday"
    assert normalize_active_event("Anniversary") == "birthday"
    assert normalize_active_event("SummerBash") == "Summer"
    assert normalize_active_event("FearEvolved") == "FearEvolved"
    assert normalize_active_event("None") == ""
    assert normalize_active_event("") == ""


def test_easter_label_maps_to_official_active_event_id():
    label = "Easter — Páscoa / Eggcellent Adventure 🐣"
    assert _ARK_EVENT_LABEL_TO_ID[label] == "Easter"


def test_launch_url_params_use_normalized_easter():
    cfg = AsmServerConfig()
    cfg.server_map = "TheIsland"
    cfg.active_event = "ARKEaster"
    params = _launch_url_params(cfg)
    joined = "".join(params)
    assert "?ActiveEvent=Easter" in joined
    assert "ARKEaster" not in joined


def test_server_config_launch_args_use_easter():
    srv = ServerConfig()
    srv.active_event = "ARKEaster"
    args = srv.build_launch_args()
    assert "?ActiveEvent=Easter" in args
    assert "ARKEaster" not in args


def test_ini_map_includes_active_event():
    assert INI_MAP["active_event"] == (
        "GUS", "ServerSettings", "ActiveEvent", {"conditional_on": "active_event"}
    )


def test_write_ini_emits_active_event_in_gus(tmp_path):
    cfg = AsmServerConfig()
    cfg.install_dir = str(tmp_path)
    cfg.active_event = "Easter"

    write_ini(cfg)

    gus = (
        tmp_path
        / "ShooterGame"
        / "Saved"
        / "Config"
        / "WindowsServer"
        / "GameUserSettings.ini"
    )
    assert gus.is_file()
    gus_text = gus.read_text(encoding="utf-16")
    assert "ActiveEvent=Easter" in gus_text


def test_write_ini_migrates_legacy_easter_value(tmp_path):
    cfg = AsmServerConfig()
    cfg.install_dir = str(tmp_path)
    cfg.active_event = "ARKEaster"

    write_ini(cfg)

    gus = (
        tmp_path
        / "ShooterGame"
        / "Saved"
        / "Config"
        / "WindowsServer"
        / "GameUserSettings.ini"
    )
    gus_text = gus.read_text(encoding="utf-16")
    assert "ActiveEvent=Easter" in gus_text
    assert "ARKEaster" not in gus_text


def test_asm_config_from_dict_normalizes_legacy_event():
    cfg = AsmServerConfig.from_dict({"active_event": "ARKEaster"})
    assert cfg.active_event == "Easter"


def test_legacy_aliases_cover_removed_wrong_ids():
    assert "ARKEaster" in _ARK_EVENT_LEGACY_ALIASES
    assert "LoveEvolved" in _ARK_EVENT_LEGACY_ALIASES
    assert "Anniversary" in _ARK_EVENT_LEGACY_ALIASES
