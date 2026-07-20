"""Versões dos plugins oficiais ARKLAND — independentes de APP_VERSION."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Literal

_PROJECT_ROOT = Path(__file__).resolve().parent.parent

_WIN64 = Path("ShooterGame") / "Binaries" / "Win64"
_PLUGINS = _WIN64 / "ArkApi" / "Plugins"

OFFICIAL_PLUGINS: dict[str, dict[str, str]] = {
    "CustomShop": {"folder": "CustomShop", "dll": "CustomShop.dll"},
    "CustomDinoDeliver": {"folder": "CustomDinoDeliver", "dll": "CustomDinoDeliver.dll"},
    "ArkPlayer": {"folder": "ArkPlayer", "dll": "ArkPlayer.dll"},
}

# Slug da pasta PluginInfo no bundle PyInstaller (plugins/<slug>/PluginInfo.json)
_BUNDLE_INFO_SLUGS: dict[str, str] = {
    "CustomShop": "customshop",
    "CustomDinoDeliver": "customdino",
    "ArkPlayer": "arkplayer",
}

PluginVersionStatus = Literal["missing", "match", "outdated", "newer", "unknown", "not_installed"]


def parse_version_tuple(version: str | int | float | None) -> tuple[int, ...]:
    if version is None:
        return (0,)
    if isinstance(version, (int, float)):
        text = _decode_arkapi_float_version(float(version))
    else:
        text = str(version).strip().lstrip("vV")
    if not text:
        return (0,)
    parts: list[int] = []
    for piece in text.split("."):
        piece = piece.strip()
        if not piece:
            continue
        try:
            parts.append(int(piece))
        except ValueError:
            return (0,)
    return tuple(parts) or (0,)


def _decode_arkapi_float_version(value: float) -> str:
    """Decodifica Version float ArkApi (M + m*0.1 + p*0.01) para semver."""
    major = int(value)
    remainder = round(value - major, 4)
    minor = int(round(remainder * 10 + 1e-9))
    patch = int(round(remainder * 100 - minor * 10 + 1e-9))
    return f"{major}.{minor}.{patch}"


def format_plugin_version(version: str | int | float | None) -> str:
    if version is None:
        return ""
    if isinstance(version, (int, float)):
        return _decode_arkapi_float_version(float(version))
    return str(version).strip().lstrip("vV")


def compare_versions(left: str | int | float | None, right: str | int | float | None) -> int:
    """Retorna -1 se left < right, 0 se igual, 1 se left > right."""
    a = parse_version_tuple(left)
    b = parse_version_tuple(right)
    length = max(len(a), len(b))
    a_padded = a + (0,) * (length - len(a))
    b_padded = b + (0,) * (length - len(b))
    if a_padded < b_padded:
        return -1
    if a_padded > b_padded:
        return 1
    return 0


def read_plugin_info_version(path: Path) -> str | None:
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    label = data.get("VersionLabel")
    if isinstance(label, str) and label.strip():
        return label.strip()
    if "Version" not in data:
        return None
    return format_plugin_version(data["Version"]) or None


def read_plugin_version_file(plugin_name: str) -> str | None:
    path = _PROJECT_ROOT / "plugin" / plugin_name / "plugin_version.txt"
    if not path.is_file():
        return None
    text = path.read_text(encoding="utf-8").strip()
    return text or None


def plugin_version_status(
    installed: str | None,
    expected: str | None,
    *,
    plugin_present: bool = True,
) -> PluginVersionStatus:
    if not plugin_present:
        return "not_installed"
    if not installed:
        return "missing"
    if not expected:
        return "unknown"
    cmp = compare_versions(installed, expected)
    if cmp == 0:
        return "match"
    if cmp < 0:
        return "outdated"
    return "newer"


def _plugin_configs_info(plugin_name: str) -> Path:
    return _PROJECT_ROOT / "plugin" / plugin_name / "configs" / "PluginInfo.json"


def _plugin_bin_info(plugin_name: str) -> Path:
    return _PROJECT_ROOT / "plugin" / plugin_name / "bin" / "PluginInfo.json"


def bundled_plugin_info_path(plugin_name: str) -> Path | None:
    """Resolve PluginInfo.json embutido no app (PyInstaller ou dev bin/)."""
    if plugin_name not in OFFICIAL_PLUGINS:
        return None

    slug = _BUNDLE_INFO_SLUGS.get(plugin_name, plugin_name.lower())

    if getattr(sys, "frozen", False):
        meipass = Path(sys._MEIPASS)  # type: ignore[attr-defined]
        for candidate in (
            meipass / "plugins" / slug / "PluginInfo.json",
            meipass / "plugin_info" / plugin_name / "PluginInfo.json",
        ):
            if candidate.is_file():
                return candidate

    bin_info = _plugin_bin_info(plugin_name)
    if bin_info.is_file():
        return bin_info

    config_info = _plugin_configs_info(plugin_name)
    if config_info.is_file():
        return config_info
    return None


def expected_plugin_version(plugin_name: str) -> str:
    """Versão esperada conforme PluginInfo.json embutido no app."""
    bundled = get_bundled_plugin_version(plugin_name)
    if bundled:
        return bundled
    from_file = read_plugin_version_file(plugin_name)
    if from_file:
        return from_file
    return ""


def server_plugin_dir(install_dir: str, plugin_name: str) -> Path:
    folder = OFFICIAL_PLUGINS[plugin_name]["folder"]
    return Path(install_dir) / _PLUGINS / folder


def installed_plugin_info_path(install_dir: str, plugin_name: str) -> Path:
    return server_plugin_dir(install_dir, plugin_name) / "PluginInfo.json"


def is_plugin_dll_installed(install_dir: str, plugin_name: str) -> bool:
    if not install_dir or not install_dir.strip():
        return False
    meta = OFFICIAL_PLUGINS.get(plugin_name)
    if not meta:
        return False
    return (server_plugin_dir(install_dir, plugin_name) / meta["dll"]).is_file()


def get_bundled_plugin_version(plugin_name: str) -> str | None:
    path = bundled_plugin_info_path(plugin_name)
    return read_plugin_info_version(path) if path else None


def get_installed_plugin_version(install_dir: str, plugin_name: str) -> str | None:
    return read_plugin_info_version(installed_plugin_info_path(install_dir, plugin_name))


def describe_plugin_version(
    install_dir: str,
    plugin_name: str,
    *,
    short_label: str | None = None,
) -> tuple[PluginVersionStatus, str]:
    """Retorna (status, texto para UI)."""
    label = short_label or plugin_name
    expected = expected_plugin_version(plugin_name) or None
    present = is_plugin_dll_installed(install_dir, plugin_name)
    installed = get_installed_plugin_version(install_dir, plugin_name) if present else None
    status = plugin_version_status(installed, expected, plugin_present=present)

    if status == "not_installed":
        return status, f"{label}: não instalado"
    if status == "missing":
        return status, f"{label}: ⚠️ sem PluginInfo (esperado v{expected})"
    if status == "match":
        return status, f"{label}: ✅ v{installed}"
    if status == "outdated":
        return status, f"{label}: ⚠️ v{installed} (esperado v{expected})"
    if status == "newer":
        return status, f"{label}: ℹ️ v{installed} (bundle v{expected})"
    return status, f"{label}: ? v{installed or '—'}"


OFFICIAL_PLUGIN_NAMES: tuple[str, ...] = tuple(OFFICIAL_PLUGINS.keys())
