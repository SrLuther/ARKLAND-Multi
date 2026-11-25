from __future__ import annotations

from src.asm_engine.asm_ini_manager import _launch_dash_flags
from src.asm_engine.asm_server_config import AsmServerConfig
from src.server_config import ServerConfig


def test_new_save_format_flag_is_emitted_for_both_server_models():
    asm_cfg = AsmServerConfig(use_new_save_format=True)
    legacy_cfg = ServerConfig(use_new_save_format=True)

    assert "-newsaveformat" in _launch_dash_flags(asm_cfg)
    assert "-newsaveformat" in legacy_cfg.build_launch_args()


def test_new_save_format_takes_precedence_over_old_format():
    asm_cfg = AsmServerConfig(use_new_save_format=True, use_old_save_format=True)
    legacy_cfg = ServerConfig(use_new_save_format=True, use_old_save_format=True)

    asm_flags = _launch_dash_flags(asm_cfg)
    legacy_args = legacy_cfg.build_launch_args()

    assert "-newsaveformat" in asm_flags
    assert "-oldsaveformat" not in asm_flags
    assert "-newsaveformat" in legacy_args
    assert "-oldsaveformat" not in legacy_args


def test_new_save_format_defaults_off_and_persists_in_asm_profile():
    cfg = AsmServerConfig()
    assert cfg.use_new_save_format is False

    restored = AsmServerConfig.from_dict(cfg.to_dict() | {"use_new_save_format": True})

    assert restored.use_new_save_format is True
