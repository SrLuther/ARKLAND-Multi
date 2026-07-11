"""Testes da blacklist de paths de mods (limpeza pré-start)."""
from __future__ import annotations

from pathlib import Path

from src.config_manager import DEFAULT_MOD_PATH_BLACKLIST
from src.mod_manager import ModManager, normalize_mod_path_blacklist


def test_default_blacklist_includes_mek():
    assert any(
        p.replace("\\", "/").endswith("1565015734/Mek")
        for p in DEFAULT_MOD_PATH_BLACKLIST
    )


def test_normalize_none_uses_default():
    assert normalize_mod_path_blacklist(None) == list(DEFAULT_MOD_PATH_BLACKLIST)


def test_normalize_empty_disables():
    assert normalize_mod_path_blacklist([]) == []


def test_normalize_backslashes():
    assert normalize_mod_path_blacklist(
        [r"ShooterGame\Content\Mods\1\Mek"]
    ) == ["ShooterGame/Content/Mods/1/Mek"]


def test_purge_removes_mek_keeps_mod_parent(tmp_path: Path):
    install = tmp_path / "server"
    mek = install / "ShooterGame" / "Content" / "Mods" / "1565015734" / "Mek"
    sibling = install / "ShooterGame" / "Content" / "Mods" / "1565015734" / "Other"
    mek.mkdir(parents=True)
    sibling.mkdir(parents=True)
    (mek / "crash.uasset").write_bytes(b"x")
    (sibling / "ok.uasset").write_bytes(b"y")

    removed = ModManager.purge_blacklisted_mod_paths(str(install))

    assert "ShooterGame/Content/Mods/1565015734/Mek" in removed
    assert not mek.exists()
    assert sibling.exists()
    assert (sibling / "ok.uasset").is_file()
    assert (install / "ShooterGame" / "Content" / "Mods" / "1565015734").is_dir()


def test_purge_noop_when_missing(tmp_path: Path):
    install = tmp_path / "server"
    install.mkdir()
    logs: list[tuple[str, str]] = []
    removed = ModManager.purge_blacklisted_mod_paths(
        str(install),
        on_log=lambda msg, level: logs.append((msg, level)),
    )
    assert removed == []
    assert logs == []


def test_purge_rejects_traversal(tmp_path: Path):
    install = tmp_path / "server"
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.txt").write_text("nope", encoding="utf-8")
    install.mkdir()
    logs: list[tuple[str, str]] = []

    removed = ModManager.purge_blacklisted_mod_paths(
        str(install),
        ["../outside"],
        on_log=lambda msg, level: logs.append((msg, level)),
    )

    assert removed == []
    assert outside.exists()
    assert any("inválido" in m for m, _ in logs)


def test_purge_custom_path(tmp_path: Path):
    install = tmp_path / "server"
    target = install / "ShooterGame" / "Content" / "Mods" / "999" / "Bad"
    target.mkdir(parents=True)
    (target / "f.bin").write_bytes(b"z")

    removed = ModManager.purge_blacklisted_mod_paths(
        str(install),
        ["ShooterGame/Content/Mods/999/Bad"],
    )

    assert removed == ["ShooterGame/Content/Mods/999/Bad"]
    assert not target.exists()
    assert (install / "ShooterGame" / "Content" / "Mods" / "999").is_dir()


def test_purge_empty_list_skips_default(tmp_path: Path):
    install = tmp_path / "server"
    mek = install / "ShooterGame" / "Content" / "Mods" / "1565015734" / "Mek"
    mek.mkdir(parents=True)

    removed = ModManager.purge_blacklisted_mod_paths(str(install), [])

    assert removed == []
    assert mek.exists()
