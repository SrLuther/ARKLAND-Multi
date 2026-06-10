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
        show_console: bool = False,
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
        self._run_async(args, on_done, show_console=show_console)

    def validate_server(
        self,
        install_dir: str,
        show_console: bool = False,
        on_done: Optional[Callable[[bool, str], None]] = None,
    ) -> None:
        """Valida e repara os arquivos do servidor (app_update + validate)."""
        self.install_server(
            install_dir, validate=True, show_console=show_console, on_done=on_done,
        )

    def download_mod(
        self,
        mod_id: str,
        install_dir: str,
        show_console: bool = False,
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
            "+workshop_download_item", ARK_WORKSHOP_APP_ID, mod_id,
            "+quit",
        ]

        def _after(success: bool, msg: str) -> None:
            if success:
                ok = self._copy_mod_to_server(mod_id, install_dir)
                if on_done:
                    on_done(ok, "Mod copiado." if ok else f"Mod {mod_id}: pasta workshop não encontrada.")
            elif on_done:
                on_done(False, msg)

        self._run_async(args, _after, show_console=show_console)

    def download_mods(
        self,
        mod_ids: List[str],
        install_dir: str,
        show_console: bool = False,
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

        args = [self._steamcmd, "+login", "anonymous"]
        for mid in mod_ids:
            args += ["+workshop_download_item", ARK_WORKSHOP_APP_ID, mid]
        args.append("+quit")

        def _after(success: bool, msg: str) -> None:
            if success:
                self._on_log(f"SteamCMD concluído — copiando {len(mod_ids)} mod(s) para o servidor…")
                errors = []
                copied = 0
                for mid in mod_ids:
                    try:
                        ok = self._copy_mod_to_server(mid, install_dir)
                        if ok:
                            copied += 1
                        else:
                            errors.append(f"Mod {mid}: pasta não encontrada no workshop")
                    except Exception as exc:
                        errors.append(f"Mod {mid}: {exc}")
                if errors and on_done:
                    extra = f"{copied}/{len(mod_ids)} mod(s) copiados.\n" + "\n".join(errors)
                    on_done(copied > 0, extra)
                elif on_done:
                    on_done(True, f"{copied} mod(s) baixado(s) com sucesso.")
            elif on_done:
                on_done(False, msg)

        self._run_async(args, _after, show_console=show_console)

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
        # +force_install_dir DEVE vir antes de +login (requisito Valve/SteamCMD).
        # Ordem errada faz o download ir para a biblioteca padrão do SteamCMD ou
        # reutilizar manifest antigo — servidor sobe em versão desatualizada (ex: 358.24).
        args = [
            self._steamcmd,
            "+@ShutdownOnFailedCommand", "1",
            "+@NoPromptForPassword", "1",
            "+force_install_dir", install_dir,
            "+login", "anonymous",
            "+app_update", ARK_SERVER_APP_ID,
        ]
        if branch:
            args += ["-beta", branch]
            if branch_password:
                args += ["-betapassword", branch_password]
        if validate:
            args.append("validate")
        args.append("+quit")
        return args

    @staticmethod
    def read_installed_build_id(install_dir: str) -> Optional[str]:
        """Lê buildid do appmanifest_376030.acf na pasta de instalação."""
        manifest = Path(install_dir) / "steamapps" / f"appmanifest_{ARK_SERVER_APP_ID}.acf"
        if not manifest.exists():
            return None
        try:
            import re
            text = manifest.read_text(encoding="utf-8", errors="replace")
            m = re.search(r'"buildid"\s+"(\d+)"', text)
            return m.group(1) if m else None
        except Exception:
            return None

    @staticmethod
    def install_dir_has_server(install_dir: str) -> bool:
        exe = (
            Path(install_dir) / "ShooterGame" / "Binaries" / "Win64" / "ShooterGameServer.exe"
        )
        return exe.exists()

    def _run_async(
        self,
        args: List[str],
        on_done: Optional[Callable[[bool, str], None]],
        show_console: bool = False,
    ) -> None:
        """Executa SteamCMD em thread separada, chamando on_done ao terminar."""
        t = threading.Thread(
            target=self._worker,
            args=(args, on_done, show_console),
            daemon=True,
        )
        t.start()

    def _worker(
        self,
        args: List[str],
        on_done: Optional[Callable[[bool, str], None]],
        show_console: bool = False,
    ) -> None:
        env = os.environ.copy()
        # Remove __COMPAT_LAYER para evitar shims que causam crash (ArkShopUI)
        env.pop("__COMPAT_LAYER", None)

        try:
            with self._lock:
                if show_console:
                    self._on_log("Abrindo janela do SteamCMD…")
                    self._proc = subprocess.Popen(
                        args,
                        env=env,
                        creationflags=subprocess.CREATE_NEW_CONSOLE,
                    )
                else:
                    self._proc = subprocess.Popen(
                        args,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        text=True,
                        encoding="utf-8",
                        errors="replace",
                        bufsize=1,
                        env=env,
                        creationflags=subprocess.CREATE_NO_WINDOW,
                    )

            last_line = ""
            if not show_console and self._proc.stdout:
                for line in self._proc.stdout:
                    line = line.rstrip("\n")
                    if line:
                        last_line = line
                        self._on_log(line)

            self._proc.wait()
            success = self._proc.returncode == 0

            if on_done:
                if success:
                    # Feedback de build instalado (quando app_update foi usado)
                    _idir = ""
                    for i, tok in enumerate(args):
                        if tok == "+force_install_dir" and i + 1 < len(args):
                            _idir = args[i + 1]
                            break
                    if _idir:
                        bid = AsmSteamCmd.read_installed_build_id(_idir)
                        if bid:
                            msg = f"Concluído com sucesso. Build Steam: {bid}"
                        else:
                            msg = (
                                "SteamCMD terminou, mas appmanifest_376030.acf não foi encontrado "
                                f"em {_idir}. Verifique se a pasta de instalação está correta."
                            )
                            success = False
                    else:
                        msg = "Concluído com sucesso."
                else:
                    msg = f"SteamCMD retornou código {self._proc.returncode}. {last_line}"
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

    @staticmethod
    def _find_official_dot_mod(mod_id: str) -> Optional[Path]:
        """Procura o arquivo .mod oficial no cache do Steam Client local."""
        try:
            import re as _re
            steam_dirs: list[Path] = []
            _registry_entries = [
                (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Valve\Steam", "InstallPath"),
                (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Valve\Steam",             "InstallPath"),
                (winreg.HKEY_CURRENT_USER,  r"SOFTWARE\Valve\Steam",             "SteamPath"),
            ]
            for hive, key_path, val_name in _registry_entries:
                try:
                    with winreg.OpenKey(hive, key_path) as _k:
                        _p = Path(winreg.QueryValueEx(_k, val_name)[0])
                        if _p not in steam_dirs:
                            steam_dirs.append(_p)
                except Exception:
                    pass
            for steam_path in steam_dirs:
                libraries: list[Path] = [steam_path / "steamapps"]
                vdf = steam_path / "steamapps" / "libraryfolders.vdf"
                if vdf.exists():
                    try:
                        for m in _re.finditer(
                            r'"path"\s+"([^"]+)"',
                            vdf.read_text(encoding="utf-8", errors="replace"),
                        ):
                            lib = Path(m.group(1)) / "steamapps"
                            if lib not in libraries:
                                libraries.append(lib)
                    except Exception:
                        pass
                for lib in libraries:
                    dot_mod = lib / "workshop" / "content" / ARK_WORKSHOP_APP_ID / f"{mod_id}.mod"
                    if dot_mod.exists():
                        return dot_mod
        except Exception:
            pass
        return None

    @staticmethod
    def _create_dot_mod_from_mod_info(workshop_mod_dir: Path, mod_id: str, dest: Path) -> bool:
        """Gera arquivo .mod binário válido para o ARK a partir do mod.info do SteamCMD."""
        import struct
        mod_info_path = workshop_mod_dir / "mod.info"
        if not mod_info_path.exists():
            return False
        try:
            raw = mod_info_path.read_bytes()
            offset = 0
            if len(raw) < 4:
                return False
            name_len = struct.unpack_from('<I', raw, offset)[0]
            offset += 4
            if offset + name_len > len(raw):
                return False
            mod_name = raw[offset: offset + name_len]
            offset += name_len
            if offset + 4 > len(raw):
                return False
            num_maps = struct.unpack_from('<I', raw, offset)[0]
            offset += 4
            maps: list[bytes] = []
            for _ in range(num_maps):
                if offset + 4 > len(raw):
                    break
                map_file_len = struct.unpack_from('<I', raw, offset)[0]
                offset += 4
                if offset + map_file_len > len(raw):
                    break
                maps.append(raw[offset: offset + map_file_len])
                offset += map_file_len

            mid_int = int(mod_id)
            out = bytearray()
            out += struct.pack('<I', mid_int & 0xFFFFFFFF)
            out += struct.pack('<I', (mid_int >> 32) & 0xFFFFFFFF)
            out += struct.pack('<I', name_len)
            out += mod_name
            # modPath vazio (1 byte = null terminator)
            out += struct.pack('<I', 1)
            out += b'\x00'
            out += struct.pack('<I', len(maps))
            for m in maps:
                out += struct.pack('<I', len(m))
                out += m
            out += b'\x33\xFF\x22\xFF\x02\x00\x00\x00\x01'
            # modmeta.info
            modmeta_path = workshop_mod_dir / "modmeta.info"
            if modmeta_path.exists():
                out += modmeta_path.read_bytes()
            else:
                out += struct.pack('<I', 1)
                out += struct.pack('<I', 8) + b'ModType\x00'
                out += struct.pack('<I', 2) + b'1\x00'

            dest.write_bytes(bytes(out))
            return True
        except Exception:
            return False

    def _copy_mod_to_server(self, mod_id: str, install_dir: str) -> bool:
        """
        Copia mod baixado pelo SteamCMD para a pasta de mods do servidor.
        Cria também o arquivo .mod exigido pelo ARK para carregar o mod.

        Fonte:  ``<steamcmd_dir>/steamapps/workshop/content/346110/<mod_id>/``
        Destino: ``<install_dir>/ShooterGame/Content/Mods/<mod_id>/``
                 ``<install_dir>/ShooterGame/Content/Mods/<mod_id>.mod``

        Retorna True se copiado com sucesso, False se pasta não encontrada.
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
            return False

        mods_dir = Path(install_dir) / "ShooterGame" / "Content" / "Mods"
        mods_dir.mkdir(parents=True, exist_ok=True)
        dest = mods_dir / mod_id

        # O SteamCMD baixa com subpasta WindowsNoEditor/ — o ARK espera
        # o conteúdo na raiz de Content/Mods/<mod_id>/
        win_src = workshop_src / "WindowsNoEditor"
        effective_src = win_src if win_src.exists() else workshop_src

        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(str(effective_src), str(dest))
        self._on_log(f"[OK] Mod {mod_id} copiado para {dest}")

        # Cria o arquivo .mod exigido pelo ARK
        dot_mod_dest = mods_dir / f"{mod_id}.mod"
        # 1) Procura .mod já pronto ao lado da pasta no workshop
        src_dot_mod = workshop_src.parent / f"{mod_id}.mod"
        if not src_dot_mod.exists():
            src_dot_mod = workshop_src / f"{mod_id}.mod"
        if not src_dot_mod.exists():
            # 2) Procura no Steam Client
            src_dot_mod = self._find_official_dot_mod(mod_id)
        if src_dot_mod and Path(src_dot_mod).exists():
            shutil.copy2(str(src_dot_mod), str(dot_mod_dest))
            self._on_log(f"[OK] Mod {mod_id}: arquivo .mod copiado.")
        else:
            # 3) Gera .mod a partir do mod.info do SteamCMD
            if self._create_dot_mod_from_mod_info(workshop_src, mod_id, dot_mod_dest):
                self._on_log(f"[OK] Mod {mod_id}: arquivo .mod gerado a partir do mod.info.")
            else:
                self._on_log(f"[AVISO] Mod {mod_id}: arquivo .mod não criado — mod.info ausente. Re-baixe pelo Steam Client.")

        return True
