"""
AsmSteamCmd — integração com SteamCMD para install/update/validate de
servidores ARK e download de mods Workshop.

ARK Dedicated Server App ID : 376030
ARK Workshop Content App ID  : 346110
"""
from __future__ import annotations

import os
import shutil
import subprocess
import threading
import winreg
from pathlib import Path
from typing import Callable, List, Optional


# ---------------------------------------------------------------------------
# Constantes públicas
# ---------------------------------------------------------------------------

ARK_SERVER_APP_ID  = "376030"
ARK_WORKSHOP_APP_ID = "346110"

_STEAMCMD_DEFAULT_PATHS = [
    r"C:\steamcmd\steamcmd.exe",
    r"C:\SteamCMD\steamcmd.exe",
    r"C:\Program Files (x86)\Steam\steamcmd.exe",
]


# ---------------------------------------------------------------------------
# AsmSteamCmd
# ---------------------------------------------------------------------------

class AsmSteamCmd:
    """
    Gerencia install/update/validate de servidores ARK e download de mods
    via SteamCMD.  Todas as operações longas rodam em thread separada.

    Parâmetros
    ----------
    steamcmd_path : str | None
        Caminho para steamcmd.exe.  Se ``None``, tenta localizar automaticamente.
    on_log : callable[[str], None] | None
        Callback invocado para cada linha de saída do SteamCMD.
        Chamado na thread filha — use ``after()`` para atualizar UI.
    """

    def __init__(
        self,
        steamcmd_path: Optional[str] = None,
        on_log: Optional[Callable[[str], None]] = None,
    ) -> None:
        self._steamcmd = steamcmd_path or self.find_steamcmd()
        self._on_log   = on_log or (lambda _: None)
        self._lock     = threading.Lock()
        self._proc: Optional[subprocess.Popen] = None  # type: ignore[type-arg]

    # ------------------------------------------------------------------
    # Localização do SteamCMD
    # ------------------------------------------------------------------

    @staticmethod
    def find_steamcmd() -> Optional[str]:
        """
        Tenta localizar steamcmd.exe:

        1. Registro Steam: ``SteamPath\\steamapps\\common\\...``
        2. Caminhos padrão ``_STEAMCMD_DEFAULT_PATHS``
        3. PATH do sistema (shutil.which)

        Retorna o caminho completo ou ``None`` se não encontrado.
        """
        # 1. Registro do Steam → pasta de instalação
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                                r"Software\Valve\Steam") as key:
                steam_path, _ = winreg.QueryValueEx(key, "SteamPath")
            candidate = Path(steam_path) / "steamcmd.exe"
            if candidate.exists():
                return str(candidate)
        except OSError:
            pass

        # 2. Caminhos padrão
        for path in _STEAMCMD_DEFAULT_PATHS:
            if Path(path).exists():
                return path

        # 3. PATH do sistema
        return shutil.which("steamcmd") or shutil.which("steamcmd.exe")

    @property
    def steamcmd_path(self) -> Optional[str]:
        return self._steamcmd

    @property
    def is_available(self) -> bool:
        return bool(self._steamcmd and Path(self._steamcmd).exists())

    # ------------------------------------------------------------------
    # API pública
    # ------------------------------------------------------------------

    def install_server(
        self,
        install_dir: str,
        branch: str = "",
        branch_password: str = "",
        validate: bool = False,
        on_done: Optional[Callable[[bool, str], None]] = None,
    ) -> None:
        """
        Instala ou atualiza o servidor ARK via SteamCMD (thread separada).

        Equivalente ao botão "Install/Update" do ASM.

        Parâmetros
        ----------
        install_dir     : diretório de destino da instalação
        branch          : nome do branch beta (ex: ``"experimental"``) ou ``""``
        branch_password : senha do branch, se necessário
        validate        : se ``True`` adiciona ``validate`` ao app_update
        on_done         : callback ``(success: bool, message: str)``
        """
        if not self.is_available:
            if on_done:
                on_done(False, "steamcmd.exe não encontrado. Configure o caminho em Configurações.")
            return

        args = self._build_install_args(install_dir, branch, branch_password, validate)
        self._run_async(args, on_done)

    def validate_server(
        self,
        install_dir: str,
        on_done: Optional[Callable[[bool, str], None]] = None,
    ) -> None:
        """Valida e repara os arquivos do servidor (app_update + validate)."""
        self.install_server(install_dir, validate=True, on_done=on_done)

    def download_mod(
        self,
        mod_id: str,
        install_dir: str,
        on_done: Optional[Callable[[bool, str], None]] = None,
    ) -> None:
        """
        Baixa ou atualiza um mod do Workshop Steam e o copia para a pasta
        de mods do servidor.

        SteamCMD baixa para:
            ``Steam\\steamapps\\workshop\\content\\346110\\<mod_id>\\``

        Depois copia para:
            ``<install_dir>\\ShooterGame\\Content\\Mods\\<mod_id>\\``
        """
        if not self.is_available:
            if on_done:
                on_done(False, "steamcmd.exe não encontrado.")
            return

        args = [
            self._steamcmd,
            "+login", "anonymous",
            f"+workshop_download_item {ARK_WORKSHOP_APP_ID} {mod_id}",
            "+quit",
        ]

        def _after(success: bool, msg: str) -> None:
            if success:
                self._copy_mod_to_server(mod_id, on_done)
            elif on_done:
                on_done(False, msg)

        self._run_async(args, _after)

    def download_mods(
        self,
        mod_ids: List[str],
        install_dir: str,
        on_done: Optional[Callable[[bool, str], None]] = None,
    ) -> None:
        """Baixa múltiplos mods em um único processo SteamCMD."""
        if not self.is_available:
            if on_done:
                on_done(False, "steamcmd.exe não encontrado.")
            return

        if not mod_ids:
            if on_done:
                on_done(True, "Nenhum mod para baixar.")
            return

        items = " ".join(
            f"+workshop_download_item {ARK_WORKSHOP_APP_ID} {mid}"
            for mid in mod_ids
        )
        args = [
            self._steamcmd,
            "+login", "anonymous",
            items,
            "+quit",
        ]

        def _after(success: bool, msg: str) -> None:
            if success:
                errors = []
                for mid in mod_ids:
                    try:
                        self._copy_mod_to_server(mid, install_dir)
                    except Exception as exc:
                        errors.append(f"Mod {mid}: {exc}")
                if errors and on_done:
                    on_done(False, "\n".join(errors))
                elif on_done:
                    on_done(True, f"{len(mod_ids)} mod(s) baixado(s) com sucesso.")
            elif on_done:
                on_done(False, msg)

        self._run_async(args, _after)

    def abort(self) -> None:
        """Interrompe o processo SteamCMD em execução, se houver."""
        with self._lock:
            if self._proc and self._proc.poll() is None:
                self._proc.terminate()

    # ------------------------------------------------------------------
    # Internos
    # ------------------------------------------------------------------

    def _build_install_args(
        self,
        install_dir: str,
        branch: str,
        branch_password: str,
        validate: bool,
    ) -> List[str]:
        app_update = f"+app_update {ARK_SERVER_APP_ID}"
        if branch:
            app_update += f" -beta {branch}"
            if branch_password:
                app_update += f" -betapassword {branch_password}"
        if validate:
            app_update += " validate"

        return [
            self._steamcmd,
            "+login", "anonymous",
            f"+force_install_dir {install_dir}",
            app_update,
            "+quit",
        ]

    def _run_async(
        self,
        args: List[str],
        on_done: Optional[Callable[[bool, str], None]],
    ) -> None:
        """Executa SteamCMD em thread separada, chamando on_done ao terminar."""
        t = threading.Thread(target=self._worker, args=(args, on_done), daemon=True)
        t.start()

    def _worker(
        self,
        args: List[str],
        on_done: Optional[Callable[[bool, str], None]],
    ) -> None:
        env = os.environ.copy()
        # Remove __COMPAT_LAYER para evitar shims que causam crash (ArkShopUI)
        env.pop("__COMPAT_LAYER", None)

        try:
            with self._lock:
                self._proc = subprocess.Popen(
                    args,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    env=env,
                )

            last_line = ""
            for line in self._proc.stdout:  # type: ignore[union-attr]
                line = line.rstrip("\n")
                if line:
                    last_line = line
                    self._on_log(line)

            self._proc.wait()
            success = self._proc.returncode == 0

            if on_done:
                msg = "Concluído com sucesso." if success else f"SteamCMD retornou código {self._proc.returncode}. {last_line}"
                on_done(success, msg)

        except Exception as exc:
            self._on_log(f"[ERRO] {exc}")
            if on_done:
                on_done(False, str(exc))
        finally:
            with self._lock:
                self._proc = None

    @staticmethod
    def _get_steamcmd_workshop_dir() -> Optional[Path]:
        """
        Tenta encontrar a pasta workshop do Steam onde o SteamCMD baixa os mods.
        Geralmente: ``C:\\Steam\\steamapps\\workshop\\content\\346110\\``
        """
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                                r"Software\Valve\Steam") as key:
                steam_path, _ = winreg.QueryValueEx(key, "SteamPath")
            workshop = Path(steam_path) / "steamapps" / "workshop" / "content" / ARK_WORKSHOP_APP_ID
            if workshop.exists():
                return workshop
        except OSError:
            pass

        # SteamCMD standalone (pasta ao lado do exe)
        if _STEAMCMD_DEFAULT_PATHS:
            for p in _STEAMCMD_DEFAULT_PATHS:
                candidate = Path(p).parent / "steamapps" / "workshop" / "content" / ARK_WORKSHOP_APP_ID
                if candidate.exists():
                    return candidate
        return None

    def _copy_mod_to_server(self, mod_id: str, install_dir: str) -> None:
        """
        Copia mod baixado pelo SteamCMD para a pasta de mods do servidor.
        Fonte:  ``<steamcmd_dir>/steamapps/workshop/content/346110/<mod_id>/``
        Destino: ``<install_dir>/ShooterGame/Content/Mods/<mod_id>/``
        """
        # Localiza pasta workshop relativa ao steamcmd.exe
        steamcmd_dir = Path(self._steamcmd).parent
        workshop_src = steamcmd_dir / "steamapps" / "workshop" / "content" / ARK_WORKSHOP_APP_ID / mod_id

        # Fallback: pasta do Steam instalado
        if not workshop_src.exists():
            alt = self._get_steamcmd_workshop_dir()
            if alt:
                workshop_src = alt / mod_id

        if not workshop_src.exists():
            self._on_log(f"[AVISO] Pasta do mod {mod_id} não encontrada em {workshop_src}")
            return

        dest = Path(install_dir) / "ShooterGame" / "Content" / "Mods" / mod_id
        dest.mkdir(parents=True, exist_ok=True)
        shutil.copytree(str(workshop_src), str(dest), dirs_exist_ok=True)
        self._on_log(f"[OK] Mod {mod_id} copiado para {dest}")
