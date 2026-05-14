"""
Gerenciador de mods do Steam Workshop para ARK: Survival Evolved.
Usa o SteamCMD para baixar e atualizar mods.
ARK AppID: 376030 (servidor) / Workshop AppID: 346110 (jogo)
"""
from __future__ import annotations

import os
import subprocess
import threading
from pathlib import Path
from typing import Callable, Dict, List, Optional


_ARK_GAME_ID   = "346110"   # AppID do ARK no Steam (para Workshop)
_ARK_SERVER_ID = "376030"   # AppID do ARK Dedicated Server


class ModInfo:
    def __init__(self, mod_id: str, name: str = "", status: str = "not_installed") -> None:
        self.mod_id   = mod_id
        self.name     = name
        self.status   = status   # not_installed | installed | updating | error
        self.size_mb  = 0.0
        self.last_updated = ""


class ModManager:
    """Gerencia o download e atualização de mods via SteamCMD."""

    def __init__(
        self,
        steamcmd_path: str = "",
        on_log: Optional[Callable[[str, str], None]] = None,
        on_progress: Optional[Callable[[str, str], None]] = None,
    ) -> None:
        self._steamcmd_path = steamcmd_path
        self._on_log        = on_log or (lambda m, l: None)
        self._on_progress   = on_progress or (lambda mod_id, status: None)
        self._active        = False
        self._thread: Optional[threading.Thread] = None
        self._mod_cache: Dict[str, ModInfo] = {}

    # ── Configuração ─────────────────────────────────────────────────────────

    @property
    def steamcmd_path(self) -> str:
        return self._steamcmd_path

    @steamcmd_path.setter
    def steamcmd_path(self, value: str) -> None:
        self._steamcmd_path = value

    def get_steamcmd_exe(self) -> Optional[str]:
        """Retorna o caminho do steamcmd.exe ou None se não encontrado."""
        if self._steamcmd_path:
            p = Path(self._steamcmd_path)
            if p.is_file():
                return str(p)
            exe = p / "steamcmd.exe"
            if exe.exists():
                return str(exe)
        # Tenta encontrar no PATH
        import shutil
        found = shutil.which("steamcmd") or shutil.which("steamcmd.exe")
        return found

    def is_steamcmd_available(self) -> bool:
        return self.get_steamcmd_exe() is not None

    # ── Download de mods ─────────────────────────────────────────────────────

    def download_mods(
        self,
        mod_ids: List[str],
        install_dir: str,
        on_done: Optional[Callable[[bool], None]] = None,
    ) -> None:
        """Baixa/atualiza mods em background."""
        if self._active:
            self._on_log("Já existe um download em progresso.", "warning")
            return
        thread = threading.Thread(
            target=self._download_worker,
            args=(mod_ids, install_dir, on_done),
            daemon=True,
            name="ModDownloadThread",
        )
        thread.start()
        self._thread = thread

    def _download_worker(
        self,
        mod_ids: List[str],
        install_dir: str,
        on_done: Optional[Callable[[bool], None]],
    ) -> None:
        self._active = True
        steamcmd = self.get_steamcmd_exe()
        if not steamcmd:
            self._on_log("SteamCMD não encontrado. Configure o caminho nas configurações.", "error")
            self._active = False
            if on_done:
                on_done(False)
            return

        success = True
        for mod_id in mod_ids:
            mod_id = mod_id.strip()
            if not mod_id.isdigit():
                self._on_log(f"ID de mod inválido: {mod_id}", "warning")
                continue

            self._on_log(f"Baixando mod {mod_id}...", "info")
            self._on_progress(mod_id, "updating")

            cmd = [
                steamcmd,
                "+force_install_dir", install_dir,
                "+login", "anonymous",
                "+workshop_download_item", _ARK_GAME_ID, mod_id, "validate",
                "+quit",
            ]

            try:
                proc = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                )
                if proc.stdout:
                    for line in proc.stdout:
                        line = line.rstrip()
                        if line:
                            self._on_log(f"[SteamCMD] {line}", "debug")
                proc.wait()
                if proc.returncode == 0:
                    # SteamCMD baixa para steamapps/workshop/content/{game_id}/{mod_id}/
                    # ARK lê os mods de ShooterGame/Content/Mods/{mod_id}/
                    src_mod = Path(install_dir) / "steamapps" / "workshop" / "content" / _ARK_GAME_ID / mod_id
                    dst_mod = Path(install_dir) / "ShooterGame" / "Content" / "Mods" / mod_id
                    if src_mod.exists():
                        try:
                            if dst_mod.exists():
                                shutil.rmtree(dst_mod)
                            shutil.copytree(src_mod, dst_mod)
                            self._on_log(f"Mod {mod_id} copiado para pasta de Mods.", "info")
                        except Exception as copy_exc:
                            self._on_log(f"Aviso: falha ao copiar mod {mod_id}: {copy_exc}", "warning")
                    else:
                        self._on_log(f"Aviso: pasta do Workshop não encontrada para mod {mod_id}.", "warning")
                    self._on_log(f"Mod {mod_id} baixado com sucesso.", "info")
                    self._on_progress(mod_id, "installed")
                else:
                    self._on_log(f"Erro ao baixar mod {mod_id} (código {proc.returncode}).", "error")
                    self._on_progress(mod_id, "error")
                    success = False
            except Exception as exc:
                self._on_log(f"Exceção ao executar SteamCMD: {exc}", "error")
                self._on_progress(mod_id, "error")
                success = False

        self._active = False
        self._on_log("Download de mods concluído.", "info")
        if on_done:
            on_done(success)

    # ── Instalação do servidor via SteamCMD ────────────────────────────────────

    def install_server(
        self,
        install_dir: str,
        validate: bool = False,
        on_done: Optional[Callable[[bool], None]] = None,
    ) -> None:
        """Instala ou atualiza o servidor ARK Dedicated via SteamCMD."""
        if self._active:
            self._on_log("Já existe uma operação em progresso.", "warning")
            return
        thread = threading.Thread(
            target=self._install_server_worker,
            args=(install_dir, validate, on_done),
            daemon=True,
            name="ServerInstallThread",
        )
        thread.start()
        self._thread = thread

    def _install_server_worker(
        self,
        install_dir: str,
        validate: bool,
        on_done: Optional[Callable[[bool], None]],
    ) -> None:
        self._active = True
        steamcmd = self.get_steamcmd_exe()
        if not steamcmd:
            self._on_log("SteamCMD não encontrado.", "error")
            self._active = False
            if on_done:
                on_done(False)
            return

        self._on_log(f"Instalando servidor ARK em: {install_dir}", "info")
        cmd = [
            steamcmd,
            "+force_install_dir", install_dir,
            "+login", "anonymous",
            "+app_update", _ARK_SERVER_ID,
        ]
        if validate:
            cmd.append("validate")
        cmd.append("+quit")

        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            if proc.stdout:
                for line in proc.stdout:
                    line = line.rstrip()
                    if line:
                        self._on_log(f"[SteamCMD] {line}", "debug")
            proc.wait()
            ok = proc.returncode == 0
            if ok:
                self._on_log("Servidor instalado/atualizado com sucesso.", "info")
            else:
                self._on_log(f"Erro na instalação (código {proc.returncode}).", "error")
        except Exception as exc:
            self._on_log(f"Exceção ao instalar servidor: {exc}", "error")
            ok = False

        self._active = False
        if on_done:
            on_done(ok)

    def get_mod_workshop_url(self, mod_id: str) -> str:
        return f"https://steamcommunity.com/sharedfiles/filedetails/?id={mod_id}"

    def check_mod_installed(self, install_dir: str, mod_id: str) -> bool:
        """Verifica se o mod já está instalado no diretório."""
        mod_path = Path(install_dir) / "ShooterGame" / "Content" / "Mods" / mod_id
        return mod_path.exists()

    def get_installed_mod_size(self, install_dir: str, mod_id: str) -> float:
        """Retorna tamanho do mod em MB, ou 0 se não instalado."""
        mod_path = Path(install_dir) / "ShooterGame" / "Content" / "Mods" / mod_id
        if not mod_path.exists():
            return 0.0
        total = sum(f.stat().st_size for f in mod_path.rglob("*") if f.is_file())
        return round(total / (1024 * 1024), 2)
