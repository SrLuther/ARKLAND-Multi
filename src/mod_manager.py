"""
Gerenciador de mods do Steam Workshop para ARK: Survival Evolved.
Usa o SteamCMD para baixar e atualizar mods.
ARK AppID: 376030 (servidor) / Workshop AppID: 346110 (jogo)
"""
from __future__ import annotations

import shutil
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
        self._on_log        = on_log or (lambda m, lvl: None)
        self._on_progress   = on_progress or (lambda mod_id, status: None)
        self._active        = False
        self._lock          = threading.Lock()
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
        copy_to_mods: bool = True,
        on_log: Optional[Callable[[str, str], None]] = None,
        on_progress: Optional[Callable[[str, str], None]] = None,
        show_console: bool = False,
    ) -> None:
        """Baixa/atualiza mods em background.

        Se ``copy_to_mods=False``, o SteamCMD ainda baixa para
        ``steamapps/workshop/``, mas os arquivos NÃO são copiados para
        ``ShooterGame/Content/Mods/`` — útil quando o servidor ainda está
        rodando e os arquivos estariam bloqueados pelo Windows.
        Chame ``copy_downloaded_mods()`` depois que o servidor parar.

        ``on_log`` e ``on_progress``, se fornecidos, são combinados com os
        callbacks globais da instância (não os substituem).
        ``show_console=True`` exibe a janela do SteamCMD para o usuário.
        """
        # Combina callbacks de override com os globais da instância
        _base_log = self._on_log
        _base_progress = self._on_progress
        if on_log is not None:
            def _eff_log(m: str, lvl: str = "info") -> None:
                _base_log(m, lvl)
                on_log(m, lvl)
        else:
            _eff_log = _base_log  # type: ignore[assignment]
        if on_progress is not None:
            def _eff_progress(mid: str, st: str) -> None:
                _base_progress(mid, st)
                on_progress(mid, st)
        else:
            _eff_progress = _base_progress  # type: ignore[assignment]

        with self._lock:
            if self._active:
                _eff_log("Já existe um download em progresso.", "warning")
                if on_done:
                    on_done(False)
                return
            self._active = True
        _eff_log(f"⏳ Preparando download de {len(mod_ids)} mod(s) em um único SteamCMD…", "info")
        _eff_log("A auto-atualização do SteamCMD pode levar 1–2 min antes do progresso aparecer.", "info")
        thread = threading.Thread(
            target=self._download_worker,
            args=(mod_ids, install_dir, on_done, copy_to_mods, _eff_log, _eff_progress, show_console),
            daemon=True,
            name="ModDownloadThread",
        )
        thread.start()
        self._thread = thread

    def copy_downloaded_mods(
        self,
        mod_ids: List[str],
        install_dir: str,
    ) -> bool:
        """Copia mods já baixados pelo SteamCMD para ShooterGame/Content/Mods/.

        Copia tanto a pasta {mod_id}/ quanto o arquivo {mod_id}.mod que o
        servidor ARK exige para carregar o mod.
        Deve ser chamado APÓS o servidor parar para evitar file locking.
        Retorna True se todos copiados com sucesso.
        """
        success = True
        for mod_id in mod_ids:
            mod_id = mod_id.strip()
            src_dir  = Path(install_dir) / "steamapps" / "workshop" / "content" / _ARK_GAME_ID / mod_id
            mods_dir = Path(install_dir) / "ShooterGame" / "Content" / "Mods"
            dst_dir  = mods_dir / mod_id
            if not src_dir.exists():
                self._on_log(f"Aviso: pasta do Workshop não encontrada para mod {mod_id}.", "warning")
                success = False
                continue
            try:
                mods_dir.mkdir(parents=True, exist_ok=True)
                if dst_dir.exists():
                    shutil.rmtree(dst_dir)
                # O SteamCMD baixa mods com subpasta WindowsNoEditor/ (e LinuxNoEditor/).
                # O ARK servidor espera o conteúdo na RAIZ de Content/Mods/<mod_id>/.
                # Copiar src_dir inteiro resultaria em Content/Mods/<id>/WindowsNoEditor/ — incorreto.
                win_src = src_dir / "WindowsNoEditor"
                effective_src = win_src if win_src.exists() else src_dir
                shutil.copytree(effective_src, dst_dir)
                dot_mod_dest = mods_dir / f"{mod_id}.mod"
                src_dot_mod = (
                    self._find_dot_mod(src_dir, mod_id)
                    or self._find_official_dot_mod(mod_id)
                )
                if src_dot_mod:
                    shutil.copy2(src_dot_mod, dot_mod_dest)
                    self._on_log(f"Mod {mod_id}: arquivo .mod copiado de {src_dot_mod.parent}.", "debug")
                elif self._create_dot_mod_from_mod_info(src_dir, mod_id, dot_mod_dest):
                    self._on_log(f"Mod {mod_id}: arquivo .mod gerado a partir do mod.info (Steam Client ausente).", "info")
                else:
                    self._on_log(
                        f"[ATEN\u00c7\u00c3O] Mod {mod_id}: arquivo .mod n\u00e3o encontrado e mod.info ausente. "
                        "Re-baixe o mod ou subscreva-o no Steam Client.",
                        "error"
                    )
                self._on_log(f"Mod {mod_id} instalado em Mods/.", "info")
            except Exception as exc:
                self._on_log(f"Erro ao instalar mod {mod_id}: {exc}", "error")
                success = False
        return success

    def _download_worker(
        self,
        mod_ids: List[str],
        install_dir: str,
        on_done: Optional[Callable[[bool], None]],
        copy_to_mods: bool = True,
        on_log: Optional[Callable[[str, str], None]] = None,
        on_progress: Optional[Callable[[str, str], None]] = None,
        show_console: bool = False,
    ) -> None:
        _log = on_log or self._on_log
        _progress = on_progress or self._on_progress

        steamcmd = self.get_steamcmd_exe()
        if not steamcmd:
            _log("SteamCMD não encontrado. Configure o caminho nas configurações.", "error")
            self._active = False
            if on_done:
                on_done(False)
            return

        valid_ids = [m.strip() for m in mod_ids if m.strip().isdigit()]
        for mod_id in mod_ids:
            mid = mod_id.strip()
            if mid and not mid.isdigit():
                _log(f"ID de mod inválido: {mid}", "warning")

        if not valid_ids:
            self._active = False
            if on_done:
                on_done(False)
            return

        for mod_id in valid_ids:
            _progress(mod_id, "updating")

        cmd = [steamcmd, "+force_install_dir", install_dir, "+login", "anonymous"]
        for mod_id in valid_ids:
            cmd += ["+workshop_download_item", _ARK_GAME_ID, mod_id, "validate"]
        cmd.append("+quit")

        success = True
        try:
            if show_console:
                _log("Abrindo janela do SteamCMD…", "info")
                proc = subprocess.Popen(cmd, creationflags=subprocess.CREATE_NEW_CONSOLE)
                proc.wait()
            else:
                proc = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    bufsize=1,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                )
                if proc.stdout:
                    for line in proc.stdout:
                        line = line.rstrip()
                        if line:
                            _log(f"[SteamCMD] {line}", "debug")
                proc.wait()

            if proc.returncode != 0:
                _log(f"SteamCMD retornou código {proc.returncode}.", "error")
                for mod_id in valid_ids:
                    _progress(mod_id, "error")
                self._active = False
                if on_done:
                    on_done(False)
                return

            _log(f"SteamCMD concluído — instalando {len(valid_ids)} mod(s) na pasta do servidor…", "info")
            for mod_id in valid_ids:
                src_mod = Path(install_dir) / "steamapps" / "workshop" / "content" / _ARK_GAME_ID / mod_id
                if copy_to_mods:
                    mods_dir = Path(install_dir) / "ShooterGame" / "Content" / "Mods"
                    dst_mod  = mods_dir / mod_id
                    copy_ok = False
                    if src_mod.exists():
                        try:
                            mods_dir.mkdir(parents=True, exist_ok=True)
                            if dst_mod.exists():
                                shutil.rmtree(dst_mod)
                            win_src = src_mod / "WindowsNoEditor"
                            effective_src = win_src if win_src.exists() else src_mod
                            shutil.copytree(effective_src, dst_mod)
                            dot_mod_dest = mods_dir / f"{mod_id}.mod"
                            src_dot_mod = (
                                self._find_dot_mod(src_mod, mod_id)
                                or self._find_official_dot_mod(mod_id)
                            )
                            if src_dot_mod:
                                shutil.copy2(src_dot_mod, dot_mod_dest)
                            elif self._create_dot_mod_from_mod_info(src_mod, mod_id, dot_mod_dest):
                                _log(f"Mod {mod_id}: arquivo .mod gerado a partir do mod.info.", "info")
                            else:
                                _log(
                                    f"[ATENÇÃO] Mod {mod_id}: arquivo .mod não encontrado e mod.info ausente.",
                                    "error",
                                )
                            _log(f"Mod {mod_id} instalado em Mods/.", "info")
                            copy_ok = True
                        except Exception as copy_exc:
                            _log(f"Falha ao copiar mod {mod_id}: {copy_exc}", "warning")
                    else:
                        _log(f"Pasta do Workshop não encontrada para mod {mod_id}.", "warning")
                    if copy_ok:
                        _progress(mod_id, "installed")
                    else:
                        _progress(mod_id, "error")
                        success = False
                elif src_mod.exists():
                    _log(f"Mod {mod_id} baixado para Workshop (cópia pendente).", "info")
                    _progress(mod_id, "installed")
                else:
                    _log(f"Mod {mod_id}: pasta Workshop não encontrada.", "error")
                    _progress(mod_id, "error")
                    success = False
        except Exception as exc:
            _log(f"Exceção ao executar SteamCMD: {exc}", "error")
            for mod_id in valid_ids:
                _progress(mod_id, "error")
            success = False

        self._active = False
        _log("Download de mods concluído.", "info")
        if on_done:
            on_done(success)

    # ── Instalação do servidor via SteamCMD ────────────────────────────────────

    def install_server(
        self,
        install_dir: str,
        validate: bool = False,
        on_done: Optional[Callable[[bool], None]] = None,
        branch_name: str = "",
        branch_password: str = "",
        show_console: bool = False,
    ) -> None:
        """Instala ou atualiza o servidor ARK Dedicated via SteamCMD."""
        with self._lock:
            if self._active:
                self._on_log("Já existe uma operação em progresso.", "warning")
                return
            self._active = True
        self._on_log("⏳ Iniciando instalação/atualização do servidor via SteamCMD…", "info")
        self._on_log("A auto-atualização do SteamCMD pode levar 1–2 min antes do download aparecer.", "info")
        thread = threading.Thread(
            target=self._install_server_worker,
            args=(install_dir, validate, on_done, branch_name, branch_password, show_console),
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
        branch_name: str = "",
        branch_password: str = "",
        show_console: bool = False,
    ) -> None:
        steamcmd = self.get_steamcmd_exe()
        if not steamcmd:
            self._on_log("SteamCMD não encontrado.", "error")
            self._active = False
            if on_done:
                on_done(False)
            return

        self._on_log(f"Instalando servidor ARK em: {install_dir}", "info")
        app_update_args = ["+app_update", _ARK_SERVER_ID]
        _branch = (branch_name or "").strip()
        if _branch:
            app_update_args += ["-beta", _branch]
            if branch_password:
                app_update_args += ["-betapassword", branch_password]
        else:
            app_update_args += ["-beta", "public"]
        if validate:
            app_update_args.append("validate")

        cmd = [
            steamcmd,
            "+force_install_dir", install_dir,
            "+login", "anonymous",
            *app_update_args,
            "+quit",
        ]

        try:
            if show_console:
                self._on_log("Abrindo janela do SteamCMD…", "info")
                proc = subprocess.Popen(cmd, creationflags=subprocess.CREATE_NEW_CONSOLE)
                proc.wait()
            else:
                proc = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    bufsize=1,
                    creationflags=subprocess.CREATE_NO_WINDOW,
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
        """Verifica se o mod está instalado (pasta E arquivo .mod presentes).
        Se a pasta existe mas o .mod está ausente, tenta restaurar do cache do Steam Client.
        """
        base = Path(install_dir) / "ShooterGame" / "Content" / "Mods"
        mod_folder = base / mod_id
        dot_mod = base / f"{mod_id}.mod"
        if not mod_folder.exists():
            return False
        if dot_mod.exists():
            return True
        # Auto-reparo: usa .mod oficial do Steam Client
        official = self._find_official_dot_mod(mod_id)
        if official:
            try:
                shutil.copy2(official, dot_mod)
                self._on_log(f"Mod {mod_id}: .mod ausente, restaurado do Steam Client.", "info")
                return True
            except Exception:
                pass
        # Fallback: gera .mod a partir do mod.info do SteamCMD (modPath vazio — formato correto)
        workshop_dir = mod_folder  # <install_dir>/ShooterGame/Content/Mods/<mod_id>/
        if self._create_dot_mod_from_mod_info(workshop_dir, mod_id, dot_mod):
            self._on_log(f"Mod {mod_id}: .mod gerado a partir do mod.info (Steam Client ausente).", "info")
            return True
        self._on_log(
            f"[ATENÇÃO] Mod {mod_id}: arquivo .mod ausente, Steam Client sem cache e mod.info não encontrado. "
            "Re-baixe o mod na aba Mods.", "warning"
        )
        return False

    def repair_mod_files(self, install_dir: str, mod_ids: List[str]) -> int:
        """Substitui arquivos .mod locais pelos oficiais do Steam Client.

        Deve ser chamado em servidores já instalados para corrigir .mod gerados
        pelo ARKLAND com formato incorreto.
        Retorna o número de arquivos .mod substituídos com sucesso.
        """
        repaired = 0
        mods_dir = Path(install_dir) / "ShooterGame" / "Content" / "Mods"
        for mod_id in mod_ids:
            mod_id = mod_id.strip()
            if not mod_id.isdigit():
                continue
            dot_mod    = mods_dir / f"{mod_id}.mod"
            mod_folder = mods_dir / mod_id
            if not mod_folder.exists():
                continue
            official = self._find_official_dot_mod(mod_id)
            if official:
                try:
                    shutil.copy2(official, dot_mod)
                    self._on_log(f"Mod {mod_id}: .mod oficial copiado de {official.parent}.", "info")
                    repaired += 1
                except Exception as exc:
                    self._on_log(f"Mod {mod_id}: falha ao copiar .mod oficial ({exc}).", "warning")
            else:
                self._on_log(
                    f"Mod {mod_id}: .mod oficial não encontrado no Steam Client — baixe o mod pelo Steam Client.",
                    "warning"
                )
        return repaired

    @staticmethod
    def _find_official_dot_mod(mod_id: str) -> Optional[Path]:
        """Procura o arquivo .mod oficial no cache de Workshop do Steam Client local.

        O Steam Client cria arquivos .mod corretos automaticamente ao subscrever
        um item do Workshop. Usar esses arquivos evita ter de gerar um .mod
        manualmente (o gerado pode ter sutis diferenças de formato que impedem o
        ARK de montar o mod corretamente no VFS).

        Tenta localizar o Steam Client via Registro do Windows e verifica todas
        as bibliotecas listadas em steamapps/libraryfolders.vdf.
        """
        try:
            import winreg
        except ImportError:
            return None
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
                dot_mod = lib / "workshop" / "content" / _ARK_GAME_ID / f"{mod_id}.mod"
                if dot_mod.exists():
                    return dot_mod
        return None

    @staticmethod
    def _find_dot_mod(workshop_mod_dir: Path, mod_id: str) -> Optional[Path]:
        """Procura um arquivo .mod já pronto em múltiplos locais:
        1) ao lado da pasta no workshop  (346110/{mod_id}.mod)  — Steam client
        2) dentro da pasta do mod        (346110/{mod_id}/{mod_id}.mod)
        3) qualquer *.mod dentro da pasta do mod
        Retorna o caminho encontrado ou None.
        Quando None e mod.info existir, use _find_official_dot_mod ou _create_dot_mod_from_mod_info.
        """
        # 1 — ao lado da pasta (localização padrão do Steam client)
        candidate = workshop_mod_dir.parent / f"{mod_id}.mod"
        if candidate.exists():
            return candidate
        # 2 — dentro da pasta com o mesmo nome
        candidate = workshop_mod_dir / f"{mod_id}.mod"
        if candidate.exists():
            return candidate
        # 3 — qualquer *.mod dentro da pasta
        for f in workshop_mod_dir.glob("*.mod"):
            return f
        return None

    @staticmethod
    def _create_dot_mod_from_mod_info(workshop_mod_dir: Path, mod_id: str, dest: Path) -> bool:
        """Gera um arquivo .mod binário válido para o ARK a partir do mod.info do SteamCMD.

        O SteamCMD baixa mod.info mas NÃO cria o .mod externo. Os dois têm formatos
        binários distintos — copiar mod.info diretamente como .mod causa crash no ARK
        (BufferCount=0 / leitura inválida).

        Formato mod.info (leitura, little-endian):
            uint32  nameLen    (inclui null terminator)
            char[]  modName    (nameLen bytes, null-terminated — nome do mod)
            uint32  numMaps
            for each map:
                uint32  mapFileLen  (inclui null terminator)
                char[]  mapFilePath (null-terminated)

        Formato .mod (escrita, little-endian — baseado no arkmanager/doExtractMod):
            uint32  modID_lo   (32 bits baixos do ID)
            uint32  modID_hi   (32 bits altos; normalmente 0)
            uint32  modNameLen (inclui null terminator)
            char[]  modName    (null-terminated, lido do cabeçalho do mod.info)
            uint32  modPathLen (1, string vazia)
            char[]  modPath    ("\\0" — vazio, conforme formato oficial do Steam Client)
            uint32  numMaps
            for each map:
                uint32  mapFileLen
                char[]  mapFilePath (null-terminated)
            bytes   \\x33\\xFF\\x22\\xFF\\x02\\x00\\x00\\x00\\x01  (magic footer)
            bytes   conteúdo de modmeta.info (ou metadados padrão ModType=1)
        """
        import struct
        mod_info_path = workshop_mod_dir / "mod.info"
        if not mod_info_path.exists():
            return False
        try:
            raw = mod_info_path.read_bytes()
            offset = 0
            if len(raw) < 4:
                return False

            # Cabeçalho: comprimento do nome do mod (inclui null terminator)
            name_len = struct.unpack_from('<I', raw, offset)[0]
            offset += 4
            if offset + name_len > len(raw):
                return False
            mod_name = raw[offset: offset + name_len]  # inclui null terminator
            offset += name_len

            # Número de maps
            if offset + 4 > len(raw):
                return False
            num_maps = struct.unpack_from('<I', raw, offset)[0]
            offset += 4

            # Entradas de map
            maps: list[bytes] = []
            for _ in range(num_maps):
                if offset + 4 > len(raw):
                    break
                map_file_len = struct.unpack_from('<I', raw, offset)[0]
                offset += 4
                if offset + map_file_len > len(raw):
                    break
                maps.append(raw[offset: offset + map_file_len])  # inclui null terminator
                offset += map_file_len

            mod_id_int = int(mod_id)
            # O Steam Client oficial grava modPath como string vazia (\x00, len=1).
            # Gravar um caminho preenchido pode causar comportamento indesejado no ARK.
            mod_path = b"\x00"  # string vazia — formato idêntico ao Steam Client

            with open(dest, "wb") as f:
                # ModID como dois uint32 LE (equivalente a uint64)
                f.write(struct.pack("<I", mod_id_int & 0xFFFFFFFF))
                f.write(struct.pack("<I", (mod_id_int >> 32) & 0xFFFFFFFF))
                # Nome do mod (FString: len + bytes com null terminator)
                f.write(struct.pack("<I", len(mod_name)))
                f.write(mod_name)
                # Caminho do mod — vazio, seguindo formato oficial do Steam Client
                f.write(struct.pack("<I", len(mod_path)))
                f.write(mod_path)
                # Maps
                f.write(struct.pack("<I", len(maps)))
                for m in maps:
                    f.write(struct.pack("<I", len(m)))
                    f.write(m)
                # Magic footer (9 bytes)
                f.write(b"\x33\xFF\x22\xFF\x02\x00\x00\x00\x01")
                # modmeta.info ou metadados padrão (ModType=1, game mod)
                modmeta_path = workshop_mod_dir / "modmeta.info"
                if modmeta_path.exists():
                    f.write(modmeta_path.read_bytes())
                else:
                    f.write(b"\x01\x00\x00\x00\x08\x00\x00\x00ModType\x00\x02\x00\x00\x001\x00")
            return True
        except Exception:
            return False

    def get_installed_mod_size(self, install_dir: str, mod_id: str) -> float:
        """Retorna tamanho do mod em MB, ou 0 se não instalado."""
        mod_path = Path(install_dir) / "ShooterGame" / "Content" / "Mods" / mod_id
        if not mod_path.exists():
            return 0.0
        total = sum(f.stat().st_size for f in mod_path.rglob("*") if f.is_file())
        return round(total / (1024 * 1024), 2)
