"""
AsmConfigManager — persistência de servidores TEK.
Dados salvos separados do PRIMITIVE em:
  %APPDATA%\\ARKLAND-ServerManager\\asm_servers.json
"""
from __future__ import annotations

import json
import logging
import os
import shutil
import tempfile
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from .asm_server_config import AsmServerConfig
from ..diagnostics.events import CAT_CONFIG, diag_event

_LOG = logging.getLogger("arkland")
_REPLACE_RETRY_DELAYS = (0.05, 0.1, 0.2, 0.4, 0.8)


def _replace_with_retry(source: Path, destination: Path) -> None:
    """Retry brief Windows sharing violations without risking a partial JSON."""
    for attempt, delay in enumerate((*_REPLACE_RETRY_DELAYS, None)):
        try:
            os.replace(source, destination)
            return
        except OSError as exc:
            winerror = getattr(exc, "winerror", None)
            if winerror not in (5, 32) or delay is None:
                raise
            _LOG.warning(
                "asm_servers.json esta temporariamente bloqueado; nova tentativa %d/%d",
                attempt + 1,
                len(_REPLACE_RETRY_DELAYS),
            )
            time.sleep(delay)


class AsmConfigManager:
    """Gerencia a lista de servidores TEK (AsmServerConfig)."""

    def __init__(self) -> None:
        self._config_dir = Path(os.environ.get("APPDATA", Path.home())) / "ARKLAND-ServerManager"
        self._servers_file = self._config_dir / "asm_servers.json"
        self._servers: List[AsmServerConfig] = []
        # The UI can save from callbacks and worker threads. Keep mutation and
        # replacement serialized within this manager instance.
        self._save_lock = threading.RLock()
        self.load()
        # FolderManager exposto depois da importação circular ser evitada
        from .asm_folder_manager import AsmFolderManager  # noqa: PLC0415
        self.folder_manager = AsmFolderManager(self)

    # ── Persistência ────────────────────────────────────────────────────────

    def load(self) -> None:
        self._servers = []
        if not self._servers_file.exists():
            return
        try:
            with open(self._servers_file, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            migrated_profiles = []
            for item in data:
                try:
                    server = AsmServerConfig.from_dict(item)
                    self._servers.append(server)
                    if getattr(server, "_player_cap_migrated_legacy_total", False):
                        migrated_profiles.append(server.name)
                except Exception:
                    _LOG.warning("asm_servers.json: perfil inválido ignorado (id=%r)",
                                 item.get("id") if isinstance(item, dict) else None, exc_info=True)
            if migrated_profiles:
                _LOG.warning(
                    "Migração de cap total legado aplicada: %s",
                    ", ".join(migrated_profiles),
                )
                try:
                    self.save()
                except Exception:
                    _LOG.exception(
                        "A migração de cap foi aplicada em memória, mas não pôde ser persistida; será repetida no próximo início"
                    )
        except Exception:
            _LOG.exception("Falha ao ler %s — lista de servidores TEK ficará vazia", self._servers_file)
            try:
                stamp = time.strftime("%Y%m%d-%H%M%S")
                backup = self._servers_file.with_name(f"{self._servers_file.name}.corrupt-{stamp}")
                suffix = 1
                while backup.exists():
                    backup = self._servers_file.with_name(f"{self._servers_file.name}.corrupt-{stamp}-{suffix}")
                    suffix += 1
                shutil.copy2(self._servers_file, backup)
            except OSError:
                _LOG.exception("Falha ao preservar %s", self._servers_file)
        diag_event(CAT_CONFIG, "asm_servers.json carregado", servers=len(self._servers),
                   file=str(self._servers_file))

    def save(self) -> None:
        with self._save_lock:
            self._config_dir.mkdir(parents=True, exist_ok=True)
            tmp: Path | None = None
            try:
                with tempfile.NamedTemporaryFile(
                    mode="w",
                    encoding="utf-8",
                    dir=self._config_dir,
                    prefix=f"{self._servers_file.name}.",
                    suffix=".tmp",
                    delete=False,
                ) as fh:
                    tmp = Path(fh.name)
                    json.dump([s.to_dict() for s in self._servers], fh, indent=2, ensure_ascii=False)
                    fh.flush()
                    os.fsync(fh.fileno())
                _replace_with_retry(tmp, self._servers_file)
            except Exception:
                if tmp is not None:
                    try:
                        tmp.unlink(missing_ok=True)
                    except OSError:
                        pass
                _LOG.exception("Falha ao gravar %s", self._servers_file)
                raise
        diag_event(CAT_CONFIG, "asm_servers.json salvo", servers=len(self._servers),
                   file=str(self._servers_file))

    # ── CRUD ─────────────────────────────────────────────────────────────────

    @property
    def servers(self) -> List[AsmServerConfig]:
        return list(self._servers)

    def get_server(self, server_id: str) -> Optional[AsmServerConfig]:
        for s in self._servers:
            if s.id == server_id:
                return s
        return None

    def add_server(self, server: AsmServerConfig) -> None:
        with self._save_lock:
            self._servers.append(server)
            try:
                self.save()
            except Exception:
                self._servers.pop()
                raise

    def update_server(self, server: AsmServerConfig) -> None:
        with self._save_lock:
            for i, s in enumerate(self._servers):
                if s.id == server.id:
                    self._servers[i] = server
                    try:
                        self.save()
                    except Exception:
                        self._servers[i] = s
                        raise
                    break

    def remove_server(self, server_id: str) -> None:
        with self._save_lock:
            previous = self._servers
            self._servers = [s for s in previous if s.id != server_id]
            try:
                self.save()
            except Exception:
                self._servers = previous
                raise

    # ── S3.4 — Export / Import / Clone ────────────────────────────────────────

    def export_server(self, server_id: str, path: str) -> None:
        """Exporta AsmServerConfig como .arkprofile JSON."""
        srv = self.get_server(server_id)
        if srv is None:
            raise ValueError(f"Servidor {server_id!r} não encontrado.")
        payload = {
            "version": "1.0",
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "created_by": "ARKLAND-Multi",
            "server": srv.to_dict(),
        }
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2, ensure_ascii=False)

    def import_server(self, path: str) -> AsmServerConfig:
        """Importa .arkprofile → novo servidor com novo UUID."""
        with open(path, "r", encoding="utf-8") as fh:
            payload = json.load(fh)
        data = payload.get("server", payload)   # compatível com raw JSON também
        srv = AsmServerConfig.from_dict(data)
        srv.id = str(uuid.uuid4())              # novo UUID para evitar colisão
        srv.name = f"{srv.name} (importado)"
        self.add_server(srv)
        return srv

    def clone_server(self, server_id: str, new_name: str) -> AsmServerConfig:
        """Clona servidor com novo UUID, novo nome e install_dir vazio."""
        srv = self.get_server(server_id)
        if srv is None:
            raise ValueError(f"Servidor {server_id!r} não encontrado.")
        data = srv.to_dict()
        data["id"] = str(uuid.uuid4())
        data["name"] = new_name
        data["install_dir"] = ""
        clone = AsmServerConfig.from_dict(data)
        self.add_server(clone)
        return clone
