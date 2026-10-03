"""Inspeção do ArkApi (plugins, DLLs, logs) de uma instalação de servidor.

Somente leitura de disco — usado pelo doctor e pelo coletor.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# Plugins que dependem do Permissions.dll (grupos/permissões) para funcionar.
PERMISSIONS_DEPENDENT_PLUGINS = ("ArkEventHunt", "CustomShop", "ArkPlayer", "CustomDinoDeliver")

PERMISSIONS_PLUGIN = "Permissions"


def win64_dir(install_dir: str) -> Path:
    return Path(install_dir) / "ShooterGame" / "Binaries" / "Win64"


def arkapi_dir(install_dir: str) -> Path:
    return win64_dir(install_dir) / "ArkApi"


def plugins_dir(install_dir: str) -> Path:
    return arkapi_dir(install_dir) / "Plugins"


def permissions_dll_path(install_dir: str) -> Path:
    """``ArkApi\\Plugins\\Permissions\\Permissions.dll`` — caminho esperado."""
    return plugins_dir(install_dir) / PERMISSIONS_PLUGIN / "Permissions.dll"


def server_exe_path(install_dir: str) -> Path:
    return win64_dir(install_dir) / "ShooterGameServer.exe"


def arkapi_log_dirs(install_dir: str) -> List[Path]:
    """Pastas candidatas de log do ArkApi (varia conforme a versão do loader)."""
    w64 = win64_dir(install_dir)
    candidates = [arkapi_dir(install_dir) / "Logs", arkapi_dir(install_dir) / "logs",
                  w64 / "logs", w64 / "Logs"]
    seen: List[Path] = []
    for c in candidates:
        if c.is_dir() and c not in seen:
            seen.append(c)
    return seen


@dataclass
class PluginFile:
    name: str
    size: int
    modified: str


@dataclass
class PluginInfo:
    name: str
    path: Path
    dlls: List[PluginFile] = field(default_factory=list)
    main_dll_present: bool = False
    config_present: bool = False
    version: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "path": str(self.path),
            "main_dll_present": self.main_dll_present,
            "config_present": self.config_present,
            "version": self.version,
            "dlls": [f.__dict__ for f in self.dlls],
        }


def _file_entry(p: Path) -> PluginFile:
    st = p.stat()
    return PluginFile(p.name, int(st.st_size),
                      datetime.fromtimestamp(st.st_mtime).isoformat(timespec="seconds"))


def _read_plugin_version(folder: Path) -> Optional[str]:
    info = folder / "PluginInfo.json"
    try:
        if info.is_file():
            data = json.loads(info.read_text(encoding="utf-8-sig"))
            label = data.get("VersionLabel") or data.get("Version")
            return str(label) if label is not None else None
    except Exception:  # noqa: BLE001
        return None
    return None


def list_plugins(install_dir: str) -> List[PluginInfo]:
    """Uma entrada por subpasta de ``ArkApi\\Plugins`` (ordenadas por nome)."""
    root = plugins_dir(install_dir)
    result: List[PluginInfo] = []
    if not root.is_dir():
        return result
    for folder in sorted((p for p in root.iterdir() if p.is_dir()), key=lambda p: p.name.lower()):
        dlls = []
        try:
            dlls = [_file_entry(f) for f in sorted(folder.glob("*.dll"))]
        except OSError:
            pass
        info = PluginInfo(
            name=folder.name,
            path=folder,
            dlls=dlls,
            main_dll_present=(folder / f"{folder.name}.dll").is_file(),
            config_present=(folder / "config.json").is_file(),
            version=_read_plugin_version(folder),
        )
        result.append(info)
    return result
