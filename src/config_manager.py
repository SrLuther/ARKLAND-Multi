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

from .server_config import ServerConfig, ClusterProfile


@dataclass
class DiscordNotifyConfig:
    """Configuração de notificações Discord via webhook."""
    enabled: bool       = False
    webhook_url: str    = ""
    sender_name: str    = "ARKLAND"
    notify_start: bool  = True   # Iniciando + Online
    notify_stop: bool   = True   # Parado + Encerrando
    notify_crash: bool  = True   # Crash detectado
    notify_update: bool = True   # Atualização concluída (mod auto-updater)
    notify_backup: bool = False  # Backup concluído


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
    remote_agent_name: str = ""          # Nome de exibição desta instância
    remote_peers: list = field(default_factory=list)
    remote_instances: list = field(default_factory=list)  # Lista de conexões remotas salvas
    # Ciclos de sincronização: lista de listas de caminhos
    # Cada ciclo sincroniza todas as suas pastas entre si (N-way)
    sync_cycles: list = field(default_factory=list)
    discord_notify: DiscordNotifyConfig = field(default_factory=DiscordNotifyConfig)


class ConfigManager:
    def __init__(self) -> None:
        self._config_dir = Path(os.environ.get("APPDATA", Path.home())) / "ARKLAND-ServerManager"
        self._config_file    = self._config_dir / "config.json"
        self._servers_file   = self._config_dir / "servers.json"
        self._clusters_file  = self._config_dir / "clusters.json"
        self.config = AppConfig()
        self._servers: List[ServerConfig] = []
        self._clusters: List[ClusterProfile] = []
        self.load()

    # ── Config global ─────────────────────────────────────────────────────────
    _DEFAULT_UPDATE_URL = "https://raw.githubusercontent.com/SrLuther/ARKLAND-Multi/main/version.json"

    def load(self) -> None:
        try:
            if self._config_file.exists():
                with open(self._config_file, "r", encoding="utf-8") as fh:
                    data = json.load(fh)
                valid = {f.name for f in fields(AppConfig)}
                raw = {k: v for k, v in data.items() if k in valid}
                discord_raw = raw.pop("discord_notify", None)
                self.config = AppConfig(**raw)
                if isinstance(discord_raw, dict):
                    dc_valid = {f.name for f in fields(DiscordNotifyConfig)}
                    for k, v in discord_raw.items():
                        if k in dc_valid:
                            setattr(self.config.discord_notify, k, v)
                if not self.config.update_url:
                    self.config.update_url = self._DEFAULT_UPDATE_URL
                if not isinstance(self.config.remote_peers, list):
                    self.config.remote_peers = []
                if not isinstance(self.config.remote_instances, list):
                    self.config.remote_instances = []
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
        self._load_clusters()

    def save(self) -> None:
        self._config_dir.mkdir(parents=True, exist_ok=True)
        tmp = self._config_file.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(asdict(self.config), fh, indent=2, ensure_ascii=False)  # type: ignore[arg-type]
        tmp.replace(self._config_file)

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
        tmp = self._servers_file.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump([s.to_dict() for s in self._servers], fh, indent=2, ensure_ascii=False)
        tmp.replace(self._servers_file)

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

    # ── Perfis de Cluster (Cross-ARK) ─────────────────────────────────────────

    @property
    def clusters(self) -> List[ClusterProfile]:
        return list(self._clusters)

    def _load_clusters(self) -> None:
        self._clusters = []
        if not self._clusters_file.exists():
            return
        try:
            with open(self._clusters_file, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            for item in data:
                try:
                    self._clusters.append(ClusterProfile.from_dict(item))
                except Exception:
                    pass
        except Exception:
            pass

    def save_clusters(self) -> None:
        self._config_dir.mkdir(parents=True, exist_ok=True)
        tmp = self._clusters_file.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump([c.to_dict() for c in self._clusters], fh, indent=2, ensure_ascii=False)
        tmp.replace(self._clusters_file)

    def add_cluster(self, cluster: ClusterProfile) -> None:
        self._clusters.append(cluster)
        self.save_clusters()

    def update_cluster(self, cluster: ClusterProfile) -> None:
        for i, c in enumerate(self._clusters):
            if c.id == cluster.id:
                self._clusters[i] = cluster
                break
        self.save_clusters()

    def remove_cluster(self, cluster_id: str) -> None:
        self._clusters = [c for c in self._clusters if c.id != cluster_id]
        # Desvincula servidores que apontavam para este cluster
        for srv in self._servers:
            if srv.cluster_profile_id == cluster_id:
                srv.cluster_profile_id = ""
        self.save_clusters()
        self.save_servers()

    def get_cluster(self, cluster_id: str) -> Optional[ClusterProfile]:
        for c in self._clusters:
            if c.id == cluster_id:
                return c
        return None

    def servers_in_cluster(self, cluster_id: str) -> List[ServerConfig]:
        """Retorna todos os servidores vinculados a um perfil de cluster."""
        return [s for s in self._servers if s.cluster_profile_id == cluster_id]

    # ── Perfil (exportar / importar) ──────────────────────────────────────────

    def export_profile(self, path: "str | Path") -> None:
        """Exporta todos os servidores para um arquivo .arkprofile (JSON)."""
        import datetime
        profile = {
            "arkland_profile_version": 1,
            "exported_at": datetime.datetime.now().isoformat(timespec="seconds"),
            "servers": [s.to_dict() for s in self._servers],
        }
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        with open(target, "w", encoding="utf-8") as fh:
            json.dump(profile, fh, indent=2, ensure_ascii=False)

    def import_profile(self, path: "str | Path", replace: bool = False) -> List[ServerConfig]:
        """
        Importa servidores de um arquivo .arkprofile.
        replace=True  → substitui todos os servidores existentes.
        replace=False → adiciona aos existentes (gera novo ID em caso de conflito).
        Retorna a lista de ServerConfig importados.
        """
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        if data.get("arkland_profile_version", 0) < 1:
            raise ValueError("Arquivo de perfil inválido ou versão não suportada.")
        existing_ids = {s.id for s in self._servers}
        imported: List[ServerConfig] = []
        for item in data.get("servers", []):
            try:
                srv = ServerConfig.from_dict(item)
                if srv.id in existing_ids:
                    srv.id = str(uuid.uuid4())
                imported.append(srv)
                existing_ids.add(srv.id)
            except Exception:
                pass
        if replace:
            self._servers = list(imported)
        else:
            self._servers.extend(imported)
        self.save_servers()
        return imported
