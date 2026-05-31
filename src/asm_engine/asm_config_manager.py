"""
AsmConfigManager — persistência de servidores TEK.
Dados salvos separados do PRIMITIVE em:
  %APPDATA%\\ARKLAND-ServerManager\\asm_servers.json
"""
from __future__ import annotations

import json
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from .asm_server_config import AsmServerConfig


class AsmConfigManager:
    """Gerencia a lista de servidores TEK (AsmServerConfig)."""

    def __init__(self) -> None:
        self._config_dir = Path(os.environ.get("APPDATA", Path.home())) / "ARKLAND-ServerManager"
        self._servers_file = self._config_dir / "asm_servers.json"
        self._servers: List[AsmServerConfig] = []
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
            for item in data:
                try:
                    self._servers.append(AsmServerConfig.from_dict(item))
                except Exception:
                    pass
        except Exception:
            pass

    def save(self) -> None:
        self._config_dir.mkdir(parents=True, exist_ok=True)
        tmp = self._servers_file.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump([s.to_dict() for s in self._servers], fh, indent=2, ensure_ascii=False)
        tmp.replace(self._servers_file)

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
        self._servers.append(server)
        self.save()

    def update_server(self, server: AsmServerConfig) -> None:
        for i, s in enumerate(self._servers):
            if s.id == server.id:
                self._servers[i] = server
                break
        self.save()

    def remove_server(self, server_id: str) -> None:
        self._servers = [s for s in self._servers if s.id != server_id]
        self.save()

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
