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
class EnvironmentConfig:
    enabled: bool = False
    root_path: str = ""      # caminho completo até "ARKLAND SERVER"
    created_at: str = ""


@dataclass
class DiscordNotifyConfig:
    enabled: bool = False
    webhook_url: str = ""
    sender_name: str = "ARKLAND"
    notify_start: bool = True
    notify_stop: bool = True
    notify_crash: bool = True
    notify_update: bool = True
    notify_backup: bool = False
    mod_changelog_webhook: str = ""


@dataclass
class BackupConfig:
    backup_dir:            str  = ""
    include_savegames:     bool = True
    include_config:        bool = True
    limit_backup_count:    bool = True
    max_backup_count:      int  = 10
    exclude_old_backups:   bool = True   # legado — espelha limit_backup_count
    max_backup_days:       int  = 5      # legado — ignorado quando limit_backup_count
    rcon_broadcast_mode:   str  = "Broadcast"
    save_message:          str  = "ARKLAND: Auto save em andamento"
    auto_backup:           bool = False
    backup_interval:       str  = "06:00"


@dataclass
class DbBackupConfig:
    enabled:               bool = False
    backup_dir:            str  = ""
    interval_hours:        int  = 6
    limit_backup_count:    bool = True
    max_backup_count:      int  = 10
    include_arkshop:       bool = True
    include_permissions:   bool = True


@dataclass
class AutoUpdateConfig:
    cache_dir:                   str  = ""
    update_interval:             str  = "01:00"
    smart_cache_copy:            bool = True
    validate_server_files:       bool = True
    update_in_parallel:          bool = True
    update_delay_seconds:        int  = 10
    show_update_reason:          bool = True
    update_reason_prefix:        str  = "Server Update Reason:"
    replace_restart_after_update: bool = False


@dataclass
class ShutdownConfig:
    check_online_players:    bool = True
    send_msgs_to_client:     bool = True
    grace_period_minutes:    int  = 15
    msg1:                    str  = "ARKLAND: Auto save em andamento"
    msg2:                    str  = "Vamos desligar em {minutes} minutos. Fica atento"
    msg3:                    str  = "Um salvamento será feito..."
    save_message:            str  = "Procure um local seguro pois tu vai ser desconectado do servidor"
    cancel_message:          str  = "Desligamento cancelado"
    show_reason_all_msgs:    bool = True


@dataclass
class AlertMessagesConfig:
    server_stopped:       str  = "O servidor parou"
    server_shutting_down: str  = "O servidor está desligando."
    server_started:       str  = "O servidor está desligado."
    include_ip_port:      bool = True
    ip_port_format:       str  = "{ipaddress}:{port}"
    backup_error:         str  = "Erro no processo de backup"
    shutdown_error:       str  = "Erro no desligamento do servidor"
    restart_error:        str  = "Erro na reinicialização do servidor"
    update_error:         str  = "Erro na atualização do servidor"
    update_result:        str  = "Atualizações:"
    server_update_msg:    str  = "Atualização de servidor"
    server_status:        str  = "Server Status:"
    mod_update_detected:  str  = "Mods atualizados detectados:"
    players_changed:      str  = "Conectados:"
    dino_respawn:         str  = "Matando dinos selvagens..."


@dataclass
class ObobonicBotConfig:
    """Bot Discord oBobonicClean — pasta externa gerenciada pelo painel TEK."""
    project_path: str = r"C:\Users\Ciano\Documents\oBobonicClean"
    start_hidden: bool = True
    auto_start: bool = False
    auto_restart_on_crash: bool = False
    health_check_before_start: bool = True


@dataclass
class DiscordBotConfig:
    enabled:              bool  = False
    token:                str   = ""
    server_id:            str   = ""
    prefix:               str   = "asm!"
    log_level:            str   = "Informações"
    alias_all_profiles:   str   = "all"
    allow_backup:         bool  = True
    allow_update:         bool  = True
    allow_restart:        bool  = True
    allow_shutdown:       bool  = True
    allow_start:          bool  = True
    allow_stop:           bool  = True
    allow_all_bots:       bool  = True
    whitelist:            list  = field(default_factory=list)


@dataclass
class BroadcastTekConfig:
    """Configuração global do painel Broadcasts TEK."""
    scheduler_enabled: bool = False
    interval_minutes: int = 30
    random_order: bool = False
    target_server_ids: list = field(default_factory=list)       # vazio = todos
    enabled_message_ids: list = field(default_factory=list)     # vazio = todas
    last_sent_at: float = 0.0
    rotation_index: int = 0


@dataclass
class ShopGlobalConfig:
    """Loja central cross-cluster (host na LAN ou cliente apontando para host remoto)."""
    mode: str = "client"                  # "host" | "client" — loja remota = client
    central_url: str = "https://arkland.com.br"  # URL da loja (servidor remoto)
    public_url: str = "https://arkland.com.br"  # Domínio público da loja
    host_ip: str = "192.168.15.51"        # IP LAN do servidor remoto (banco/loja)
    public_ip: str = "179.185.19.88"      # IP público do servidor remoto
    port: int = 27199
    api_key: str = ""
    delivery_mode: str = "plugin"         # plugin | rcon
    catalog_config_path: str = ""         # catálogo mestre Items/Kits
    machine_label: str = ""               # ex: "Maquina-A"
    auto_sync_on_save: bool = True
    cross_chat_enabled: bool = True          # chat cluster automático entre mapas (CustomShop)
    # Banco de pedidos (arkshop_web)
    orders_db_url: str = ""
    orders_db_host: str = "192.168.15.51"
    orders_db_port: int = 3306
    orders_db_name: str = "arkshop"
    orders_db_user: str = ""
    orders_db_password: str = ""


@dataclass
class SmtpConfig:
    host:                       str  = ""
    port:                       int  = 25
    use_ssl:                    bool = False
    use_default_credentials:    bool = False
    username:                   str  = ""
    password:                   str  = ""
    from_address:               str  = ""
    to_address:                 str  = ""
    notify_auto_backup:         bool = False
    notify_auto_update:         bool = False
    notify_auto_shutdown:       bool = False
    notify_shutdown_restart:    bool = False


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
    machine_public_ip: str = ""              # IP público desta máquina (paridade ASM)
    auto_start: bool = False
    remote_agent_enabled: bool = False
    remote_agent_name: str = ""
    remote_agent_port: int = 32440
    remote_agent_token: str = ""
    remote_peers: list = field(default_factory=list)
    # Ciclos de sincronização: lista de listas de caminhos
    # Cada ciclo sincroniza todas as suas pastas entre si (N-way)
    sync_cycles: list = field(default_factory=list)
    # Steam Web API
    steam_api_key: str = ""
    # Remote instances salvas (lista de dicts com name/host/port/token/favorite)
    remote_instances: list = field(default_factory=list)
    # Discord webhook (notificações simples)
    discord_notify: DiscordNotifyConfig = field(default_factory=DiscordNotifyConfig)
    # Backup
    backup: BackupConfig = field(default_factory=BackupConfig)
    db_backup: DbBackupConfig = field(default_factory=DbBackupConfig)
    # Auto-update
    auto_update: AutoUpdateConfig = field(default_factory=AutoUpdateConfig)
    # Shutdown
    shutdown: ShutdownConfig = field(default_factory=ShutdownConfig)
    # Mensagens de alerta
    alert_messages: AlertMessagesConfig = field(default_factory=AlertMessagesConfig)
    # Discord Bot
    discord_bot: DiscordBotConfig = field(default_factory=DiscordBotConfig)
    # oBobonicClean (bot Discord externo)
    obobonic: ObobonicBotConfig = field(default_factory=ObobonicBotConfig)
    # SMTP
    smtp: SmtpConfig = field(default_factory=SmtpConfig)
    # Loja cross-cluster
    shop: ShopGlobalConfig = field(default_factory=ShopGlobalConfig)
    # Ambiente padronizado ARKLAND SERVER
    environment: EnvironmentConfig = field(default_factory=EnvironmentConfig)
    # Biblioteca global de broadcasts (TEK — sincronizável via .arkbroadcast)
    broadcast_library: list = field(default_factory=list)
    broadcast_tek: BroadcastTekConfig = field(default_factory=BroadcastTekConfig)


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

                def _deserialize(dc_cls, key):
                    if key in raw and isinstance(raw[key], dict):
                        dc_f = {f.name for f in fields(dc_cls)}
                        raw[key] = dc_cls(**{k: v for k, v in raw[key].items() if k in dc_f})

                _deserialize(DiscordNotifyConfig, "discord_notify")
                _deserialize(BackupConfig,        "backup")
                _deserialize(DbBackupConfig,      "db_backup")
                _deserialize(AutoUpdateConfig,    "auto_update")
                _deserialize(ShutdownConfig,      "shutdown")
                _deserialize(AlertMessagesConfig, "alert_messages")
                _deserialize(DiscordBotConfig,    "discord_bot")
                _deserialize(ObobonicBotConfig,   "obobonic")
                _deserialize(SmtpConfig,          "smtp")
                _deserialize(ShopGlobalConfig,    "shop")
                _deserialize(EnvironmentConfig,   "environment")
                _deserialize(BroadcastTekConfig,  "broadcast_tek")
                self.config = AppConfig(**raw)
                if not self.config.update_url:
                    self.config.update_url = self._DEFAULT_UPDATE_URL
                if not isinstance(self.config.remote_peers, list):
                    self.config.remote_peers = []
                if not isinstance(self.config.remote_instances, list):
                    self.config.remote_instances = []
                if not isinstance(self.config.broadcast_library, list):
                    self.config.broadcast_library = []
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

    # ── Clusters ──────────────────────────────────────────────────────────────

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
        with open(self._clusters_file, "w", encoding="utf-8") as fh:
            json.dump([c.to_dict() for c in self._clusters], fh, indent=2, ensure_ascii=False)

    def add_cluster(self, prof: ClusterProfile) -> None:
        self._clusters.append(prof)
        self.save_clusters()

    def update_cluster(self, prof: ClusterProfile) -> None:
        for i, c in enumerate(self._clusters):
            if c.id == prof.id:
                self._clusters[i] = prof
                break
        self.save_clusters()

    def remove_cluster(self, cluster_id: str) -> None:
        self._clusters = [c for c in self._clusters if c.id != cluster_id]
        self.save_clusters()

    def get_cluster(self, cluster_id: str) -> Optional[ClusterProfile]:
        for c in self._clusters:
            if c.id == cluster_id:
                return c
        return None

    def servers_in_cluster(self, cluster_id: str) -> List[ServerConfig]:
        return [s for s in self._servers if s.cluster_profile_id == cluster_id]
