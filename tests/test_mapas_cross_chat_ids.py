"""Testes do mapeamento fixo MAPAS → CrossChat.ServerId."""

from pathlib import Path

from src.mapas_cross_chat_ids import (
    DEFAULT_MAPAS_CROSS_CHAT_IDS,
    load_mapas_cross_chat_ids,
    mapas_folder_from_path,
    resolve_cross_chat_server_id,
)


def test_resolve_from_install_dir():
    sid = resolve_cross_chat_server_id(
        install_dir=r"C:\ARKLAND SERVER\MAPAS\AL\ShooterGame",
    )
    assert sid == "ALPS"


def test_resolve_from_config_path():
    sid = resolve_cross_chat_server_id(
        config_path=(
            r"C:\ARKLAND SERVER\MAPAS\VL\ShooterGame\Binaries\Win64"
            r"\ArkApi\Plugins\CustomShop\config.json"
        ),
    )
    assert sid == "THE VOLCANO"


def test_unknown_folder_returns_empty():
    assert resolve_cross_chat_server_id(install_dir=r"C:\ARKLAND SERVER\MAPAS\XX") == ""


def test_load_from_custom_file(tmp_path, monkeypatch):
    cfg = tmp_path / "mapas_cross_chat_ids.json"
    cfg.write_text('{"BR": "BRIGHAMIA", "AL": "ALPS"}', encoding="utf-8")
    monkeypatch.setattr(
        "src.mapas_cross_chat_ids.ensure_mapas_cross_chat_ids_file",
        lambda: cfg,
    )
    assert load_mapas_cross_chat_ids() == {"BR": "BRIGHAMIA", "AL": "ALPS"}


def test_defaults_match_arkland():
    assert DEFAULT_MAPAS_CROSS_CHAT_IDS["BR"] == "BRIGHAMIA"
    assert DEFAULT_MAPAS_CROSS_CHAT_IDS["G2"] == "GENESIS 2"


def test_mapas_folder_extraction():
    assert mapas_folder_from_path(r"C:\ARKLAND SERVER\MAPAS\CI\foo") == "CI"
