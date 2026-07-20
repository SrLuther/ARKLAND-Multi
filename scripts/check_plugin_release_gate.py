#!/usr/bin/env python3
"""Gate de release: plugins com código alterado exigem bump + CHANGELOG.

Para cada plugin oficial (CustomShop, CustomDinoDeliver, ArkPlayer):
  1. plugin_version.txt, PluginInfo.json (VersionLabel) e plugin_version.h
     têm de estar alinhados.
  2. CHANGELOG.md tem de existir com secção ``## [X.Y.Z]`` da versão actual.
  3. Se ficheiros vigiados (src/, CMakeLists, vcxproj, build*.bat) mudaram
     desde o último commit que alterou plugin_version.txt, a versão actual
     tem de ser *maior* que a versão nesse commit.

Uso:
  python scripts/check_plugin_release_gate.py
  python scripts/check_plugin_release_gate.py --json
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.sync_plugin_versions import (  # noqa: E402
    ALL_PLUGINS,
    read_plugin_version,
)
from src.plugin_versions import (  # noqa: E402
    compare_versions,
    read_plugin_info_version,
)

_SEMVER_HEADER = re.compile(r"^##\s*\[(\d+\.\d+\.\d+)\]", re.MULTILINE)
_VERSION_DEFINE = re.compile(
    r'#\s*define\s+ARKLAND_PLUGIN_VERSION\s+"([^"]+)"'
)

# Ficheiros que alteram o binário / comportamento do plugin (não o catálogo JSON).
_WATCHED_RELATIVE = (
    "src",
    "CMakeLists.txt",
)


def _run_git(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )


def _git_ok(*args: str) -> str | None:
    proc = _run_git(*args)
    if proc.returncode != 0:
        return None
    return (proc.stdout or "").strip()


def last_version_bump_commit(plugin_dir: Path) -> str | None:
    rel = (plugin_dir / "plugin_version.txt").relative_to(ROOT).as_posix()
    return _git_ok("log", "-1", "--format=%H", "--", rel) or None


def version_at_commit(plugin_dir: Path, commit: str) -> str | None:
    rel = (plugin_dir / "plugin_version.txt").relative_to(ROOT).as_posix()
    text = _git_ok("show", f"{commit}:{rel}")
    return text.strip() if text else None


def watched_paths(plugin_dir: Path) -> list[str]:
    paths: list[str] = []
    for name in _WATCHED_RELATIVE:
        candidate = plugin_dir / name
        if candidate.exists():
            paths.append(candidate.relative_to(ROOT).as_posix())
    for pattern in ("*.vcxproj", "*.vcxproj.filters", "build*.bat", "build_cl.bat"):
        for match in plugin_dir.glob(pattern):
            if match.is_file():
                paths.append(match.relative_to(ROOT).as_posix())
    return sorted(set(paths))


def changed_watched_files(plugin_dir: Path, since_commit: str | None) -> list[str]:
    paths = watched_paths(plugin_dir)
    if not paths:
        return []
    if since_commit:
        proc = _run_git("diff", "--name-only", since_commit, "--", *paths)
    else:
        # Sem histórico de bump: qualquer ficheiro vigiado já tracked conta.
        proc = _run_git("ls-files", "--", *paths)
    if proc.returncode != 0:
        return []
    return [line.strip().replace("\\", "/") for line in proc.stdout.splitlines() if line.strip()]


def changelog_versions(plugin_dir: Path) -> set[str]:
    path = plugin_dir / "CHANGELOG.md"
    if not path.is_file():
        return set()
    text = path.read_text(encoding="utf-8")
    return set(_SEMVER_HEADER.findall(text))


def read_header_version(plugin_dir: Path) -> str | None:
    path = plugin_dir / "src" / "plugin_version.h"
    if not path.is_file():
        return None
    match = _VERSION_DEFINE.search(path.read_text(encoding="utf-8"))
    return match.group(1) if match else None


def check_plugin(plugin_dir: Path) -> list[str]:
    errors: list[str] = []
    name = plugin_dir.name
    try:
        current = read_plugin_version(plugin_dir)
    except FileNotFoundError as exc:
        return [f"{name}: {exc}"]

    info_configs = plugin_dir / "configs" / "PluginInfo.json"
    info_bin = plugin_dir / "bin" / "PluginInfo.json"
    label_configs = read_plugin_info_version(info_configs) if info_configs.is_file() else None
    label_bin = read_plugin_info_version(info_bin) if info_bin.is_file() else None
    header = read_header_version(plugin_dir)

    if label_configs != current:
        errors.append(
            f"{name}: configs/PluginInfo.json VersionLabel={label_configs!r} "
            f"!= plugin_version.txt={current!r} "
            f"(corra: python scripts/sync_plugin_versions.py --plugin {name})"
        )
    if label_bin is not None and label_bin != current:
        errors.append(
            f"{name}: bin/PluginInfo.json VersionLabel={label_bin!r} "
            f"!= plugin_version.txt={current!r}"
        )
    if header != current:
        errors.append(
            f"{name}: src/plugin_version.h={header!r} != plugin_version.txt={current!r}"
        )

    changelog_path = plugin_dir / "CHANGELOG.md"
    if not changelog_path.is_file():
        errors.append(
            f"{name}: falta CHANGELOG.md — crie plugin/{name}/CHANGELOG.md "
            f"com secção ## [{current}]"
        )
    else:
        versions = changelog_versions(plugin_dir)
        if current not in versions:
            errors.append(
                f"{name}: CHANGELOG.md sem secção ## [{current}] — "
                "adicione a entrada do bump actual antes do release"
            )

    bump_commit = last_version_bump_commit(plugin_dir)
    previous = version_at_commit(plugin_dir, bump_commit) if bump_commit else None
    changed = changed_watched_files(plugin_dir, bump_commit)

    if changed:
        if previous is None or compare_versions(current, previous) <= 0:
            sample = ", ".join(changed[:5])
            more = f" (+{len(changed) - 5})" if len(changed) > 5 else ""
            errors.append(
                f"{name}: código alterado desde o último bump de versão "
                f"(v{previous or '?'} → ainda v{current}). "
                f"Ficheiros: {sample}{more}. "
                f"Bump plugin_version.txt e documente em CHANGELOG.md, depois "
                f"python scripts/sync_plugin_versions.py --plugin {name}"
            )

    return errors


def check_all() -> list[str]:
    errors: list[str] = []
    for plugin_dir in ALL_PLUGINS:
        if not plugin_dir.is_dir():
            errors.append(f"Plugin em falta: {plugin_dir}")
            continue
        errors.extend(check_plugin(plugin_dir))
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emite resultado em JSON (ok + errors)",
    )
    args = parser.parse_args(argv)

    errors = check_all()
    if args.json:
        print(json.dumps({"ok": not errors, "errors": errors}, ensure_ascii=False, indent=2))
    elif errors:
        print("ERRO: gate de versão dos plugins falhou:\n", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        print(
            "\nCorrija bump + CHANGELOG.md do plugin e sincronize com "
            "scripts/sync_plugin_versions.py antes de _release.ps1.",
            file=sys.stderr,
        )
    else:
        print("OK: gate de versão dos plugins (CustomShop + CustomDinoDeliver + ArkPlayer)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
