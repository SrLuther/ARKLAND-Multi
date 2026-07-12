"""ActiveEvent — valores oficiais ARK e escrita INI/CLI (TEK + clássico)."""
from __future__ import annotations

from src.asm_engine.asm_ini_manager import (
    INI_MAP,
    _launch_dash_flags,
    _launch_url_params,
    build_launch_args,
    read_ini,
    write_ini,
)
from src.buff_ini_backups import backup_ini_files, restore_ini_from_backup
from src.asm_engine.asm_server_config import AsmServerConfig
from src.server_config import ServerConfig
from src.ui_constants import (
    _ARK_EVENT_LABEL_TO_ID,
    _ARK_EVENT_LEGACY_ALIASES,
    _ARK_OFFICIAL_EVENTS,
    active_event_launch_flag,
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


def test_normalize_active_event_case_insensitive():
    assert normalize_active_event("easter") == "Easter"
    assert normalize_active_event("VDAY") == "vday"
    assert normalize_active_event("fearevolved") == "FearEvolved"
    assert normalize_active_event("loveevolved") == "vday"


def test_active_event_launch_flag():
    assert active_event_launch_flag("Easter") == "-ActiveEvent=Easter"
    assert active_event_launch_flag("vday") == "-ActiveEvent=vday"
    assert active_event_launch_flag("ARKEaster") == "-ActiveEvent=Easter"
    assert active_event_launch_flag("") == ""
    assert active_event_launch_flag("None") == ""


def test_official_events_cover_seasonal_set():
    ids = {eid for eid, _ in _ARK_OFFICIAL_EVENTS if eid}
    assert {"Easter", "vday", "FearEvolved", "Summer", "WinterWonderland", "TurkeyTrial"} <= ids


def test_easter_label_maps_to_official_active_event_id():
    label = "Easter — Páscoa / Eggcellent Adventure 🐣"
    assert _ARK_EVENT_LABEL_TO_ID[label] == "Easter"


def test_launch_uses_dash_active_event_not_url_param():
    """Wiki ASE: -ActiveEvent= (flag). ?ActiveEvent= na travel URL NÃO ativa o evento."""
    cfg = AsmServerConfig()
    cfg.server_map = "TheIsland"
    cfg.active_event = "ARKEaster"
    url = "".join(_launch_url_params(cfg))
    flags = _launch_dash_flags(cfg)
    assert "?ActiveEvent=" not in url
    assert "-ActiveEvent=Easter" in flags
    assert "ARKEaster" not in " ".join(flags)


def test_build_launch_args_includes_dash_active_event():
    cfg = AsmServerConfig()
    cfg.server_map = "TheIsland"
    cfg.active_event = "vday"
    joined = " ".join(build_launch_args(cfg))
    assert "-ActiveEvent=vday" in joined
    assert "?ActiveEvent=" not in joined


def test_additional_args_active_event_does_not_override_profile():
    cfg = AsmServerConfig()
    cfg.server_map = "TheIsland"
    cfg.active_event = "Easter"
    cfg.additional_args = "-ActiveEvent=FearEvolved ?ActiveEvent=Summer"
    joined = " ".join(build_launch_args(cfg))
    assert joined.count("ActiveEvent=") == 1
    assert "-ActiveEvent=Easter" in joined
    assert "FearEvolved" not in joined
    assert "ActiveEvent=Summer" not in joined


def test_server_config_launch_args_use_dash_easter():
    srv = ServerConfig()
    srv.active_event = "ARKEaster"
    args = srv.build_launch_args()
    assert "-ActiveEvent=Easter" in args
    assert "?ActiveEvent=" not in args
    assert "ARKEaster" not in args


def test_server_config_extra_args_cannot_override_active_event():
    srv = ServerConfig()
    srv.active_event = "vday"
    srv.extra_args = "-ActiveEvent=Easter"
    args = srv.build_launch_args()
    assert "-ActiveEvent=vday" in args
    assert args.count("ActiveEvent=") == 1


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


def test_restore_ini_preserves_active_event_after_buff_backup(tmp_path, monkeypatch):
    """Restore de buff não deve apagar ActiveEvent definido no perfil depois do backup."""
    cfg = AsmServerConfig()
    cfg.install_dir = str(tmp_path)
    cfg.active_event = "Easter"
    write_ini(cfg)

    monkeypatch.setattr(
        "src.buff_ini_backups.resolve_ini_backup_root",
        lambda: tmp_path / "BACKUP" / ".ini",
    )
    backup_path = backup_ini_files(cfg, "NoEvent")
    assert backup_path is not None

    cfg.active_event = "Easter"
    write_ini(cfg)

    cfg.active_event = "Easter"
    assert restore_ini_from_backup(cfg, backup_path) is True

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
    assert cfg.active_event == "Easter"


def test_write_ini_active_event_survives_custom_gus_raw(tmp_path):
    """Bloco custom_gus_ini_raw não pode sobrescrever ActiveEvent do perfil."""
    cfg = AsmServerConfig()
    cfg.install_dir = str(tmp_path)
    cfg.active_event = "Easter"
    cfg.custom_gus_ini_raw = "[ServerSettings]\nSomeOtherKey=1\n"

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


def test_write_ini_mirrors_active_event_to_user_config_folder(tmp_path):
    """WindowsServer é canônico; user_config_folder recebe espelho com ActiveEvent."""
    cfg = AsmServerConfig()
    cfg.install_dir = str(tmp_path / "server")
    cfg.user_config_folder = str(tmp_path / "custom_ini")
    cfg.active_event = "Easter"

    write_ini(cfg)

    mirror = tmp_path / "custom_ini" / "GameUserSettings.ini"
    assert mirror.is_file()
    mirror_text = mirror.read_text(encoding="utf-16")
    assert "ActiveEvent=Easter" in mirror_text


def test_read_ini_uses_windows_server_not_stale_custom_folder(tmp_path):
    """read_ini lê WindowsServer (runtime), não pasta custom desatualizada."""
    cfg = AsmServerConfig()
    cfg.install_dir = str(tmp_path / "server")
    cfg.user_config_folder = str(tmp_path / "custom_ini")
    cfg.active_event = "Easter"
    write_ini(cfg)

    custom_gus = tmp_path / "custom_ini" / "GameUserSettings.ini"
    custom_gus.write_text(
        custom_gus.read_text(encoding="utf-16").replace("ActiveEvent=Easter", ""),
        encoding="utf-16",
    )

    cfg.active_event = ""
    read_ini(cfg)
    assert cfg.active_event == "Easter"


def test_funny_map_launch_includes_dash_active_event():
    cfg = AsmServerConfig()
    cfg.server_map = "funny_map"
    cfg.active_event = "Easter"
    joined = " ".join(build_launch_args(cfg))
    assert "funny_map" in joined
    assert "-ActiveEvent=Easter" in joined
    assert "?ActiveEvent=" not in joined


def test_legacy_aliases_cover_removed_wrong_ids():
    assert "ARKEaster" in _ARK_EVENT_LEGACY_ALIASES
    assert "LoveEvolved" in _ARK_EVENT_LEGACY_ALIASES
    assert "Anniversary" in _ARK_EVENT_LEGACY_ALIASES
