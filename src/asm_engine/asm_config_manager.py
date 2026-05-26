"""
AsmConfigManager — persistência de servidores TEK.
Dados salvos separados do PRIMITIVE em:
  %APPDATA%\\ARKLAND-ServerManager\\asm_servers.json
"""
from __future__ import annotations

import json
import os
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
