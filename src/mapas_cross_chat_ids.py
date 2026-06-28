"""IDs fixos CrossChat por pasta MAPAS — arquivo local, fora do sync do catálogo."""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict

_PROJECT_ROOT = Path(__file__).resolve().parent.parent

DEFAULT_MAPAS_CROSS_CHAT_IDS: Dict[str, str] = {
    "AL": "ALPS",
    "AM": "AMISSA",
    "VL": "THE VOLCANO",
    "BR": "BRIGHAMIA",
    "G2": "GENESIS 2",
    "CI": "CRYSTAL ISLES",
}


def mapas_cross_chat_ids_file() -> Path:
    return (
        Path(os.environ.get("APPDATA", Path.home()))
        / "ARKLAND-ServerManager"
        / "mapas_cross_chat_ids.json"
    )


def bundled_template_path() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS) / "config" / "mapas_cross_chat_ids.json"  # type: ignore[attr-defined]
    return _PROJECT_ROOT / "config" / "mapas_cross_chat_ids.json"


def ensure_mapas_cross_chat_ids_file() -> Path:
    path = mapas_cross_chat_ids_file()
    if path.is_file():
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    tpl = bundled_template_path()
    if tpl.is_file():
        path.write_text(tpl.read_text(encoding="utf-8"), encoding="utf-8")
    else:
        payload = {
            "_info": "Chave = pasta em MAPAS\\. Valor = CrossChat.ServerId.",
            **DEFAULT_MAPAS_CROSS_CHAT_IDS,
        }
        path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    return path


def load_mapas_cross_chat_ids() -> Dict[str, str]:
    path = ensure_mapas_cross_chat_ids_file()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return dict(DEFAULT_MAPAS_CROSS_CHAT_IDS)
    out: Dict[str, str] = {}
    for key, value in data.items():
        if str(key).startswith("_"):
            continue
        folder = str(key).strip().upper()
        server_id = str(value).strip()
        if folder and server_id:
            out[folder] = server_id[:64]
    return out or dict(DEFAULT_MAPAS_CROSS_CHAT_IDS)


def mapas_folder_from_path(raw: str) -> str:
    """Extrai a sigla da pasta em MAPAS\\<sigla>\\..."""
    if not raw:
        return ""
    parts = re.split(r"[\\/]+", raw.strip())
    for i, part in enumerate(parts):
        if part.upper() == "MAPAS" and i + 1 < len(parts):
            candidate = parts[i + 1].strip()
            if candidate:
                return candidate
    return ""


def lookup_cross_chat_server_id(folder: str) -> str:
    """Lookup direto pela sigla da pasta (AL, BR, …)."""
    if not folder:
        return ""
    return load_mapas_cross_chat_ids().get(folder.strip().upper(), "")


def resolve_cross_chat_server_id(
    *,
    install_dir: str = "",
    config_path: str = "",
) -> str:
    """Resolve ServerId: pasta MAPAS → entrada em mapas_cross_chat_ids.json."""
    paths = [config_path]
    if install_dir:
        paths.append(install_dir)
        if not config_path:
            paths.append(
                str(
                    Path(install_dir)
                    / "ShooterGame/Binaries/Win64/ArkApi/Plugins/CustomShop/config.json"
                )
            )
    for raw in paths:
        folder = mapas_folder_from_path(raw)
        if folder:
            hit = lookup_cross_chat_server_id(folder)
            if hit:
                return hit
    return ""


def resolve_cross_chat_server_id_from_server(srv: Any) -> str:
    config_path = (getattr(srv, "customshop_config_path", "") or "").strip()
    install_dir = (getattr(srv, "install_dir", "") or "").strip()
    return resolve_cross_chat_server_id(
        install_dir=install_dir,
        config_path=config_path,
    )
