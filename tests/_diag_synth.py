"""Dados sintéticos (tmp_path) compartilhados pelos testes de diagnóstico — sem segredos reais."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

SECRET_ADMIN = "SuperAdminPw-123"
SECRET_SERVER_PW = "JoinPw-456"
SECRET_API_KEY = "shop-api-key-abcdef123456"
SECRET_WEBHOOK = "https://discord.com/api/webhooks/123456789012345678/AbCdEf_ghIJkl-MNop0123456789"
SECRET_PLUGIN_TOKEN = "plugin-token-zzzzzz999"
SECRET_SMTP = "smtp-pass-qwerty"


def make_server_dir(
    root: Path,
    *,
    exe: bool = True,
    arkapi: bool = True,
    loader: bool = True,
    plugins: Optional[Dict[str, Dict[str, Any]]] = None,
    permissions: bool = False,
    game_ini: Optional[str] = "",
    gus_ini: Optional[str] = None,
) -> Path:
    """Cria uma instalação ARK falsa. ``plugins``: nome -> {"dll": bool, "config": str|None}."""
    win64 = root / "ShooterGame" / "Binaries" / "Win64"
    win64.mkdir(parents=True, exist_ok=True)
    if exe:
        (win64 / "ShooterGameServer.exe").write_bytes(b"MZ")
    ini_dir = root / "ShooterGame" / "Saved" / "Config" / "WindowsServer"
    ini_dir.mkdir(parents=True, exist_ok=True)
    if gus_ini is None:
        gus_ini = f"[ServerSettings]\nServerAdminPassword={SECRET_ADMIN}\nServerPassword={SECRET_SERVER_PW}\n"
    if gus_ini:
        (ini_dir / "GameUserSettings.ini").write_text(gus_ini, encoding="utf-8")
    if game_ini is not None:
        (ini_dir / "Game.ini").write_text(game_ini or "[/script/shootergame.shootergamemode]\n", encoding="utf-8")
    if arkapi:
        plugins_dir = win64 / "ArkApi" / "Plugins"
        plugins_dir.mkdir(parents=True, exist_ok=True)
        if loader:
            (win64 / "version.dll").write_bytes(b"MZ")
        for name, spec in (plugins or {}).items():
            folder = plugins_dir / name
            folder.mkdir(parents=True, exist_ok=True)
            if spec.get("dll", True):
                (folder / f"{name}.dll").write_bytes(b"MZ" * 8)
            if spec.get("config") is not None:
                (folder / "config.json").write_text(spec["config"], encoding="utf-8")
        if permissions:
            pdir = plugins_dir / "Permissions"
            pdir.mkdir(parents=True, exist_ok=True)
            (pdir / "Permissions.dll").write_bytes(b"MZ")
    return root


def tek_entry(install_dir: Path, *, id_: str = "aaaaaaaa-1111", name: str = "Island",
              server_port: int = 7777, query_port: int = 27015, rcon_port: int = 27020,
              admin_password: str = SECRET_ADMIN, progressions: Optional[bool] = None,
              raw_sockets: bool = False) -> Dict[str, Any]:
    item: Dict[str, Any] = {
        "id": id_, "name": name, "install_dir": str(install_dir), "server_map": "TheIsland",
        "server_port": server_port, "query_port": query_port, "rcon_port": rcon_port,
        "admin_password": admin_password, "use_raw_sockets": raw_sockets,
    }
    if progressions is not None:
        item["player_level_progressions_enabled"] = progressions
    return item


def write_config_dir(cdir: Path, *, tek: Optional[List[Dict[str, Any]]] = None,
                     classic: Optional[List[Dict[str, Any]]] = None,
                     config: Optional[Dict[str, Any]] = None) -> Path:
    cdir.mkdir(parents=True, exist_ok=True)
    if tek is not None:
        (cdir / "asm_servers.json").write_text(json.dumps(tek), encoding="utf-8")
    if classic is not None:
        (cdir / "servers.json").write_text(json.dumps(classic), encoding="utf-8")
    if config is not None:
        (cdir / "config.json").write_text(json.dumps(config), encoding="utf-8")
    return cdir
