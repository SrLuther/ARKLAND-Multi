"""Testes do gate de release dos plugins."""
from __future__ import annotations

import json
from pathlib import Path

import scripts.check_plugin_release_gate as gate
from scripts.sync_plugin_versions import ALL_PLUGINS, sync_plugin_info, write_plugin_version
from src.plugin_versions import expected_plugin_version, get_bundled_plugin_version


def test_official_plugins_have_changelog_for_current_version() -> None:
    for plugin_dir in ALL_PLUGINS:
        versions = gate.changelog_versions(plugin_dir)
        current = (plugin_dir / "plugin_version.txt").read_text(encoding="utf-8").strip()
        assert current in versions, f"{plugin_dir.name}: CHANGELOG sem ## [{current}]"


def test_plugin_version_files_aligned() -> None:
    for plugin_dir in ALL_PLUGINS:
        errors = [
            e
            for e in gate.check_plugin(plugin_dir)
            if "código alterado" not in e
        ]
        assert not errors, errors


def test_bundled_versions_match_plugin_version_txt() -> None:
    assert get_bundled_plugin_version("CustomShop") == expected_plugin_version("CustomShop")
    assert get_bundled_plugin_version("CustomDinoDeliver") == expected_plugin_version(
        "CustomDinoDeliver"
    )
    assert get_bundled_plugin_version("ArkPlayer") == expected_plugin_version("ArkPlayer")
    assert expected_plugin_version("ArkPlayer") == "1.0.0"


def test_changelog_versions_parser(tmp_path: Path) -> None:
    (tmp_path / "CHANGELOG.md").write_text(
        "# Changelog\n\n## [1.2.3] - 2026-01-01\n\n- foo\n\n## [1.2.2] - 2026-01-01\n",
        encoding="utf-8",
    )
    assert gate.changelog_versions(tmp_path) == {"1.2.3", "1.2.2"}


def test_check_plugin_detects_missing_changelog_section(
    tmp_path: Path, monkeypatch
) -> None:
    plugin = tmp_path / "FakePlugin"
    (plugin / "src").mkdir(parents=True)
    (plugin / "configs").mkdir()
    (plugin / "bin").mkdir()
    write_plugin_version(plugin, "1.0.0")
    # PluginInfo mínimo
    info = {
        "FullName": "Fake",
        "Description": "test",
        "Version": 1.0,
        "VersionLabel": "1.0.0",
        "MinApiVersion": 0.0,
    }
    text = json.dumps(info, indent=2) + "\n"
    (plugin / "configs" / "PluginInfo.json").write_text(text, encoding="utf-8")
    (plugin / "bin" / "PluginInfo.json").write_text(text, encoding="utf-8")
    (plugin / "src" / "plugin_version.h").write_text(
        '#pragma once\n#define ARKLAND_PLUGIN_VERSION "1.0.0"\n',
        encoding="utf-8",
    )
    (plugin / "CHANGELOG.md").write_text(
        "# Changelog\n\n## [0.9.0] - 2026-01-01\n\n- old\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(gate, "last_version_bump_commit", lambda _p: None)
    monkeypatch.setattr(gate, "changed_watched_files", lambda _p, _c: [])

    errors = gate.check_plugin(plugin)
    assert any("CHANGELOG.md sem secção ## [1.0.0]" in e for e in errors)


def test_check_plugin_requires_bump_when_src_changed(
    tmp_path: Path, monkeypatch
) -> None:
    plugin = tmp_path / "FakePlugin"
    (plugin / "src").mkdir(parents=True)
    (plugin / "configs").mkdir()
    write_plugin_version(plugin, "1.0.0")
    info = {
        "FullName": "Fake",
        "Description": "test",
        "Version": 1.0,
        "VersionLabel": "1.0.0",
        "MinApiVersion": 0.0,
    }
    (plugin / "configs" / "PluginInfo.json").write_text(
        json.dumps(info, indent=2) + "\n", encoding="utf-8"
    )
    sync_plugin_info(plugin, "1.0.0")
    (plugin / "CHANGELOG.md").write_text(
        "# Changelog\n\n## [1.0.0] - 2026-01-01\n\n- baseline\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(gate, "last_version_bump_commit", lambda _p: "abc123")
    monkeypatch.setattr(gate, "version_at_commit", lambda _p, _c: "1.0.0")
    monkeypatch.setattr(
        gate,
        "changed_watched_files",
        lambda _p, _c: ["plugin/FakePlugin/src/Main.cpp"],
    )

    errors = gate.check_plugin(plugin)
    assert any("código alterado desde o último bump" in e for e in errors)
