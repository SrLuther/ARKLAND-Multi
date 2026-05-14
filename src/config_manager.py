"""
Gerencia a configuração persistente do ARKLAND - Server Manager.
As configurações são salvas em %APPDATA%\\ARKLAND-ServerManager\\config.json
Os servidores são salvos em %APPDATA%\\ARKLAND-ServerManager\\servers.json
"""
import json
import os
import uuid
from pathlib import Path
from dataclasses import dataclass, asdict, field, fields
from typing import List, Optional

from .server_config import ServerConfig


@dataclass
class AppConfig:
    # ── Global ────────────────────────────────────────────────────────────────
    steamcmd_path: str = ""                  # Caminho para steamcmd.exe
    default_install_dir: str = ""            # Diretório padrão de instalação
    startup_with_windows: bool = False       # Iniciar com o Windows
    minimize_to_tray: bool = False           # Minimizar para a bandeja ao fechar
    log_debug: bool = False                  # Log verboso
    update_url: str = "https://raw.githubusercontent.com/SrLuther/ARKLAND-Multi/main/version.json"

    # ── Legado (sync cluster) ─────────────────────────────────────────────────
    local_cluster_path: str = ""
    shared_path: str = ""
    sync_interval: int = 5
    machine_name: str = ""
    auto_start: bool = False
    remote_agent_enabled: bool = False
    remote_agent_port: int = 32440
    remote_agent_token: str = ""
    remote_peers: list = field(default_factory=list)
    # Ciclos de sincronização: lista de listas de caminhos
    # Cada ciclo sincroniza todas as suas pastas entre si (N-way)
    sync_cycles: list = field(default_factory=list)


class ConfigManager:
    def __init__(self) -> None:
        self._config_dir = Path(os.environ.get("APPDATA", Path.home())) / "ARKLAND-ServerManager"
        self._config_file   = self._config_dir / "config.json"
        self._servers_file  = self._config_dir / "servers.json"
        self.config = AppConfig()
        self._servers: List[ServerConfig] = []
        self.load()

    # ── Config global ─────────────────────────────────────────────────────────
    _DEFAULT_UPDATE_URL = "https://raw.githubusercontent.com/SrLuther/ARKLAND-Multi/main/version.json"

    def load(self) -> None:
        try:
            if self._config_file.exists():
                with open(self._config_file, "r", encoding="utf-8") as fh:
                    data = json.load(fh)
                valid = {f.name for f in fields(AppConfig)}
                self.config = AppConfig(**{k: v for k, v in data.items() if k in valid})
                if not self.config.update_url:
                    self.config.update_url = self._DEFAULT_UPDATE_URL
                if not isinstance(self.config.remote_peers, list):
                    self.config.remote_peers = []
                if not self.config.remote_agent_token:
                    self.config.remote_agent_token = str(uuid.uuid4())
                    self.save()
                # Migra config legado (local_cluster_path / shared_path) para sync_cycles
                if not self.config.sync_cycles:
                    old_local = self.config.local_cluster_path.strip()
                    old_shared = self.config.shared_path.strip()
                    if old_local or old_shared:
                        self.config.sync_cycles = [[old_local, old_shared]]
        except Exception:
            self.config = AppConfig()
            self.config.remote_agent_token = str(uuid.uuid4())
            self.save()

        self._load_servers()

    def save(self) -> None:
        self._config_dir.mkdir(parents=True, exist_ok=True)
        with open(self._config_file, "w", encoding="utf-8") as fh:
            json.dump(asdict(self.config), fh, indent=2, ensure_ascii=False)  # type: ignore[arg-type]

    # ── Servidores ────────────────────────────────────────────────────────────

    @property
    def servers(self) -> List[ServerConfig]:
        return list(self._servers)

    def _load_servers(self) -> None:
        self._servers = []
        if not self._servers_file.exists():
            return
        try:
            with open(self._servers_file, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            for item in data:
                try:
                    self._servers.append(ServerConfig.from_dict(item))
                except Exception:
                    pass
        except Exception:
            pass

    def save_servers(self) -> None:
        self._config_dir.mkdir(parents=True, exist_ok=True)
        with open(self._servers_file, "w", encoding="utf-8") as fh:
            json.dump([s.to_dict() for s in self._servers], fh, indent=2, ensure_ascii=False)

    def add_server(self, server: ServerConfig) -> None:
        self._servers.append(server)
        self.save_servers()

    def update_server(self, server: ServerConfig) -> None:
        for i, s in enumerate(self._servers):
            if s.id == server.id:
                self._servers[i] = server
                break
        self.save_servers()

    def remove_server(self, server_id: str) -> None:
        self._servers = [s for s in self._servers if s.id != server_id]
        self.save_servers()

    def get_server(self, server_id: str) -> Optional[ServerConfig]:
        for s in self._servers:
            if s.id == server_id:
                return s
        return None
