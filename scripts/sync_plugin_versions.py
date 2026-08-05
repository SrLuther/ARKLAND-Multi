"""Sincroniza plugin_version.txt -> PluginInfo.json (configs/ e bin/).

Uso:
  --plugin NAME [--increment] [--set X.Y.Z]   um plugin
  --all                                       todos os plugins (sem alterar txt)
  --from-app                                  define todos = APP_VERSION e sincroniza
"""
from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VERSION_PY = ROOT / "src" / "version.py"
PLUGIN_DIRS: dict[str, Path] = {
    "customshop": ROOT / "plugin" / "CustomShop",
    "customdino": ROOT / "plugin" / "CustomDinoDeliver",
    "customdinodeliver": ROOT / "plugin" / "CustomDinoDeliver",
    "arkplayer": ROOT / "plugin" / "ArkPlayer",
    "arkeventhunt": ROOT / "plugin" / "ArkEventHunt",
}
ALL_PLUGINS = (
    ROOT / "plugin" / "CustomShop",
    ROOT / "plugin" / "CustomDinoDeliver",
    ROOT / "plugin" / "ArkPlayer",
    ROOT / "plugin" / "ArkEventHunt",
)

_SEMVER = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")


def _parse_semver(text: str) -> tuple[int, int, int]:
    m = _SEMVER.match((text or "").strip())
    if not m:
        raise ValueError(f"Versão inválida (use X.Y.Z): {text!r}")
    return int(m.group(1)), int(m.group(2)), int(m.group(3))


def _format_semver(major: int, minor: int, patch: int) -> str:
    return f"{major}.{minor}.{patch}"


def _semver_to_arkapi_float(ver: str) -> float:
    """Codifica semver para float ArkApi (aprox.; use VersionLabel para semver completo)."""
    major, minor, patch = _parse_semver(ver)
    # ArkApi legado: um dígito por componente — VersionLabel guarda o semver real.
    m1 = min(minor, 9)
    p1 = min(patch, 9)
    return round(major + m1 * 0.1 + p1 * 0.01, 4)


def _load_app_version() -> str:
    src = VERSION_PY.read_text(encoding="utf-8-sig")
    tree = ast.parse(src)
    for node in tree.body:
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            if node.target.id == "APP_VERSION" and isinstance(node.value, ast.Constant):
                return str(node.value.value)
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "APP_VERSION":
                    if isinstance(node.value, ast.Constant):
                        return str(node.value.value)
    raise RuntimeError("APP_VERSION não encontrado em src/version.py")


def read_plugin_version(plugin_dir: Path) -> str:
    path = plugin_dir / "plugin_version.txt"
    if not path.is_file():
        raise FileNotFoundError(f"plugin_version.txt ausente: {path}")
    return path.read_text(encoding="utf-8").strip()


def write_plugin_version(plugin_dir: Path, version: str) -> None:
    _parse_semver(version)
    (plugin_dir / "plugin_version.txt").write_text(version + "\n", encoding="utf-8")


def increment_patch(version: str) -> str:
    major, minor, patch = _parse_semver(version)
    return _format_semver(major, minor, patch + 1)


def sync_plugin_info(plugin_dir: Path, version: str) -> None:
    _parse_semver(version)
    info_path = plugin_dir / "configs" / "PluginInfo.json"
    if not info_path.is_file():
        raise FileNotFoundError(f"PluginInfo.json ausente: {info_path}")

    data = json.loads(info_path.read_text(encoding="utf-8"))
    data["Version"] = _semver_to_arkapi_float(version)
    data["VersionLabel"] = version

    indent = 4 if plugin_dir.name == "CustomShop" else 2
    text = json.dumps(data, indent=indent, ensure_ascii=False) + "\n"
    info_path.write_text(text, encoding="utf-8")

    bin_dir = plugin_dir / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    (bin_dir / "PluginInfo.json").write_text(text, encoding="utf-8")

    header_path = plugin_dir / "src" / "plugin_version.h"
    header_path.write_text(
        "#pragma once\n"
        f'#define ARKLAND_PLUGIN_VERSION "{version}"\n',
        encoding="utf-8",
    )


def resolve_plugin_dir(name: str) -> Path:
    key = name.strip().lower().replace("_", "").replace("-", "")
    if key in PLUGIN_DIRS:
        return PLUGIN_DIRS[key]
    candidate = ROOT / "plugin" / name
    if candidate.is_dir():
        return candidate
    raise SystemExit(f"Plugin desconhecido: {name}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--plugin",
        help="CustomShop | CustomDinoDeliver | ArkPlayer | ArkEventHunt | caminho",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Sincroniza todos os plugins a partir de plugin_version.txt",
    )
    parser.add_argument(
        "--from-app",
        action="store_true",
        help="Define plugin_version.txt = APP_VERSION para todos e sincroniza",
    )
    parser.add_argument(
        "--increment",
        action="store_true",
        help="Incrementa patch em plugin_version.txt antes de sincronizar",
    )
    parser.add_argument(
        "--set",
        metavar="X.Y.Z",
        help="Define plugin_version.txt manualmente (sem incremento)",
    )
    args = parser.parse_args(argv)

    if args.from_app:
        app_ver = _load_app_version()
        for plugin_dir in ALL_PLUGINS:
            write_plugin_version(plugin_dir, app_ver)
            sync_plugin_info(plugin_dir, app_ver)
            print(f"{plugin_dir.name}: plugin_version.txt + PluginInfo.json -> v{app_ver}")
        return 0

    if args.all:
        for plugin_dir in ALL_PLUGINS:
            version = read_plugin_version(plugin_dir)
            sync_plugin_info(plugin_dir, version)
            print(f"{plugin_dir.name}: PluginInfo.json -> v{version}")
        return 0

    if not args.plugin:
        parser.error("informe --plugin, --all ou --from-app")

    plugin_dir = resolve_plugin_dir(args.plugin)
    if args.set:
        version = args.set.strip()
        write_plugin_version(plugin_dir, version)
    else:
        version = read_plugin_version(plugin_dir)
        if args.increment:
            version = increment_patch(version)
            write_plugin_version(plugin_dir, version)

    sync_plugin_info(plugin_dir, version)
    print(f"{plugin_dir.name}: PluginInfo.json -> v{version}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
