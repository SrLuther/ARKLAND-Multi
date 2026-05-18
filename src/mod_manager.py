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
    ) -> None:
        """Baixa/atualiza mods em background.

        Se ``copy_to_mods=False``, o SteamCMD ainda baixa para
        ``steamapps/workshop/``, mas os arquivos NÃO são copiados para
        ``ShooterGame/Content/Mods/`` — útil quando o servidor ainda está
        rodando e os arquivos estariam bloqueados pelo Windows.
        Chame ``copy_downloaded_mods()`` depois que o servidor parar.
        """
        with self._lock:
            if self._active:
                self._on_log("Já existe um download em progresso.", "warning")
                return
            self._active = True
        thread = threading.Thread(
            target=self._download_worker,
            args=(mod_ids, install_dir, on_done, copy_to_mods),
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
                shutil.copytree(src_dir, dst_dir)
                dot_mod_dest = mods_dir / f"{mod_id}.mod"
                src_dot_mod = self._find_dot_mod(src_dir, mod_id)
                if src_dot_mod:
                    shutil.copy2(src_dot_mod, dot_mod_dest)
                    self._on_log(f"Mod {mod_id}: arquivo .mod copiado.", "debug")
                elif self._create_dot_mod_from_mod_info(src_dir, mod_id, dot_mod_dest):
                    self._on_log(f"Mod {mod_id}: .mod gerado a partir de mod.info.", "debug")
                else:
                    self._on_log(
                        f"[ATENÇÃO] Mod {mod_id}: mod.info não encontrado — "
                        "o ARK pode ignorar este mod. Tente re-baixar.", "error"
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
    ) -> None:
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
                                shutil.copytree(src_mod, dst_mod)
                                dot_mod_dest = mods_dir / f"{mod_id}.mod"
                                src_dot_mod = self._find_dot_mod(src_mod, mod_id)
                                if src_dot_mod:
                                    shutil.copy2(src_dot_mod, dot_mod_dest)
                                    self._on_log(f"Mod {mod_id}: arquivo .mod copiado.", "debug")
                                elif self._create_dot_mod_from_mod_info(src_mod, mod_id, dot_mod_dest):
                                    self._on_log(f"Mod {mod_id}: .mod gerado a partir de mod.info.", "debug")
                                else:
                                    self._on_log(
                                        f"[ATENÇÃO] Mod {mod_id}: mod.info não encontrado — "
                                        "o ARK pode ignorar este mod. Tente re-baixar.", "error"
                                    )
                                self._on_log(f"Mod {mod_id} copiado para pasta de Mods.", "info")
                                copy_ok = True
                            except Exception as copy_exc:
                                self._on_log(f"Aviso: falha ao copiar mod {mod_id}: {copy_exc}", "warning")
                        else:
                            self._on_log(f"Aviso: pasta do Workshop não encontrada para mod {mod_id}.", "warning")
                        if copy_ok:
                            self._on_log(f"Mod {mod_id} baixado com sucesso.", "info")
                            self._on_progress(mod_id, "installed")
                        else:
                            self._on_log(f"Mod {mod_id}: download OK mas não foi instalado na pasta de Mods.", "error")
                            self._on_progress(mod_id, "error")
                            success = False
                    else:
                        # copy_to_mods=False: apenas verifica se o download chegou
                        if src_mod.exists():
                            self._on_log(f"Mod {mod_id} baixado para Workshop (cópia pendente).", "info")
                            self._on_progress(mod_id, "installed")
                        else:
                            self._on_log(f"Mod {mod_id}: download OK mas pasta Workshop não encontrada.", "error")
                            self._on_progress(mod_id, "error")
                            success = False
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
        with self._lock:
            if self._active:
                self._on_log("Já existe uma operação em progresso.", "warning")
                return
            self._active = True
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
        """Verifica se o mod está instalado (pasta E arquivo .mod presentes).
        Se a pasta existe mas o .mod está ausente e mod.info está dentro da pasta,
        gera um .mod binário válido a partir do mod.info (auto-reparo).
        """
        base = Path(install_dir) / "ShooterGame" / "Content" / "Mods"
        mod_folder = base / mod_id
        dot_mod = base / f"{mod_id}.mod"
        if not mod_folder.exists():
            return False
        if dot_mod.exists():
            return True
        # Auto-reparo: gera .mod binário correto a partir de mod.info
        if (mod_folder / "mod.info").exists():
            if self._create_dot_mod_from_mod_info(mod_folder, mod_id, dot_mod):
                self._on_log(
                    f"Mod {mod_id}: .mod ausente, auto-gerado a partir de mod.info.", "info"
                )
                return True
        return False

    @staticmethod
    def _find_dot_mod(workshop_mod_dir: Path, mod_id: str) -> Optional[Path]:
        """Procura um arquivo .mod já pronto em múltiplos locais:
        1) ao lado da pasta no workshop  (346110/{mod_id}.mod)  — Steam client
        2) dentro da pasta do mod        (346110/{mod_id}/{mod_id}.mod)
        3) qualquer *.mod dentro da pasta do mod
        Retorna o caminho encontrado ou None.
        Quando None e mod.info existir, use _create_dot_mod_from_mod_info.
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
            uint32  modPathLen (inclui null terminator)
            char[]  modPath    ("../../../ShooterGame/Content/Mods/{modid}\\0")
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
            mod_path = f"../../../ShooterGame/Content/Mods/{mod_id}\x00".encode("utf-8")

            with open(dest, "wb") as f:
                # ModID como dois uint32 LE (equivalente a uint64)
                f.write(struct.pack("<I", mod_id_int & 0xFFFFFFFF))
                f.write(struct.pack("<I", (mod_id_int >> 32) & 0xFFFFFFFF))
                # Nome do mod (FString: len + bytes com null terminator)
                f.write(struct.pack("<I", len(mod_name)))
                f.write(mod_name)
                # Caminho do mod
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
