"""
Gerencia a configuração persistente do ARKLAND - Server Manager.
As configurações são salvas em %APPDATA%\\ARKLAND-ServerManager\\config.json
Os servidores são salvos em %APPDATA%\\ARKLAND-ServerManager\\servers.json
"""
import json
import os
import shutil
import time
import uuid
from pathlib import Path
from dataclasses import dataclass, asdict, field, fields
from typing import List, Optional

from .server_config import ServerConfig, ClusterProfile

# Paths relativos ao install_dir do servidor ARK ASE a apagar antes do start
# (conteúdo de mods que causa crash). Lista vazia desactiva a limpeza.
DEFAULT_MOD_PATH_BLACKLIST: List[str] = [
    "ShooterGame/Content/Mods/1565015734/Mek",
]


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
    # Painel fixo: webhook dedicado (canal de status ≠ canal de eventos).
    # channel_id = limpeza no boot via discord_bot.token; message_id = edit em runtime.
    status_board_enabled: bool = False
    status_board_webhook_url: str = ""
    status_board_channel_id: str = ""
    status_board_message_id: str = ""


@dataclass
class BackupConfig:
    backup_dir:            str  = ""  # "" = D:\Backups\servers (ARKLAND_BACKUP_ROOT)
    include_savegames:     bool = True
    include_config:        bool = False   # opcional — saves são a prioridade
    limit_backup_count:    bool = True
    max_backup_count:      int  = 10
    exclude_old_backups:   bool = True   # legado — espelha limit_backup_count
    max_backup_days:       int  = 5      # legado — ignorado quando limit_backup_count
    # Omite cópias internas do ARK (.bak / Map_DD.MM.YYYY_HH.MM.SS.ark) do ZIP
    backup_exclude_redundant: bool = True
    rcon_broadcast_mode:   str  = "Broadcast"
    save_message:          str  = "ARKLAND: Auto save em andamento"
    auto_backup:           bool = False
    backup_interval:       str  = "06:00"


@dataclass
class DbBackupConfig:
    enabled:               bool = False
    backup_dir:            str  = ""  # "" = D:\Backups\database (ARKLAND_BACKUP_ROOT)
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


def _as_bool(value: object, default: bool) -> bool:
    """Booleano tolerante ao JSON do config (aceita "false"/"0"/"nao"; ``bool("false")`` seria True)."""
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        low = value.strip().lower()
        if low in ("1", "true", "yes", "y", "sim", "on"):
            return True
        if low in ("0", "false", "no", "n", "nao", "não", "off", ""):
            return False
    return default


@dataclass
class ObobonicBotConfig:
    """Bot Discord oBobonic EMBUTIDO no app (administração, moderação e salas de voz).

    Não depende de pasta externa: roda numa thread do próprio app. O token fica no
    config.json, como os demais segredos do app (discord_bot.token, smtp.password…).
    """
    # ── Execução ──────────────────────────────────────────────────────────────
    auto_start: bool = True
    auto_restart_on_crash: bool = False
    # ── Discord ───────────────────────────────────────────────────────────────
    token: str = ""
    client_id: str = ""            # opcional; vazio = derivado do token
    guild_id: str = ""
    command_prefix: str = "!"
    # ── Cogs embutidos ────────────────────────────────────────────────────────
    enable_voice: bool = True
    enable_moderation: bool = True
    lobby_channel_id: str = ""     # lobby das salas de voz temporárias
    logs_channel_id: str = ""      # logs de moderação/admin
    quarantine_role_id: str = ""   # cargo aplicado por !limpezageral
    # ── Migração (config antiga com pasta externa) ────────────────────────────
    legacy_project_path: str = ""  # só para OFERECER importar uma vez; nunca usado em runtime
    legacy_import_done: bool = False

    @classmethod
    def from_dict(cls, data: dict) -> "ObobonicBotConfig":
        """Carrega config nova OU antiga (project_path/start_hidden/health_check_* são ignorados)."""
        defaults = cls()
        kwargs: dict = {}
        for f in fields(cls):
            if f.name not in data:
                continue
            value = data[f.name]
            default = getattr(defaults, f.name)
            if isinstance(default, bool):
                kwargs[f.name] = _as_bool(value, default)
            elif isinstance(default, str):
                kwargs[f.name] = "" if value is None else str(value)
        legacy_path = data.get("project_path")
        if (
            isinstance(legacy_path, str)
            and legacy_path.strip()
            and not kwargs.get("legacy_project_path")
            and not kwargs.get("legacy_import_done")
        ):
            kwargs["legacy_project_path"] = legacy_path.strip()
        return cls(**kwargs)


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
    scheduler_enabled: bool = True
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
    webstore_steam_api_key: str = ""      # Steam Web API — nicknames admin/site (≠ steam_api_key global/mods)
    delivery_mode: str = "plugin"         # plugin | rcon
    catalog_config_path: str = ""         # catálogo mestre Items/Kits
    machine_label: str = ""               # ex: "Maquina-A"
    auto_sync_on_save: bool = True
    cross_chat_enabled: bool = False         # CrossChat integrado desativado — use plugin de terceiros
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
    # oBobonic (bot Discord embutido no app)
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
    # Paths relativos (ao root do servidor) a apagar antes de start/restart
    mod_path_blacklist: list = field(
        default_factory=lambda: list(DEFAULT_MOD_PATH_BLACKLIST)
    )
    # ForceDay / SetDay via RCON — DESATIVADO (crash ASE 361.7). Campo mantido p/ UI.
    force_day_on_start_enabled: bool = False
    force_day_on_start: int = 20


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
                if isinstance(raw.get("obobonic"), dict):
                    raw["obobonic"] = ObobonicBotConfig.from_dict(raw["obobonic"])
                else:
                    raw.pop("obobonic", None)
                _deserialize(SmtpConfig,          "smtp")
                _deserialize(ShopGlobalConfig,    "shop")
                _deserialize(EnvironmentConfig,   "environment")
                _deserialize(BroadcastTekConfig,  "broadcast_tek")
                self.config = AppConfig(**raw)
                from .shop_integration import (
                    is_ephemeral_pyinstaller_path,
                    is_webstore_catalog_path,
                    resolve_persistent_catalog_path,
                )

                shop_cfg = self.config.shop
                if is_ephemeral_pyinstaller_path(shop_cfg.catalog_config_path or "") or is_webstore_catalog_path(
                    shop_cfg.catalog_config_path or ""
                ):
                    shop_cfg.catalog_config_path = str(
                        resolve_persistent_catalog_path(shop_cfg.catalog_config_path, shop=shop_cfg)
                    )
                    self.save()
                if not self.config.update_url:
                    self.config.update_url = self._DEFAULT_UPDATE_URL
                if not isinstance(self.config.remote_peers, list):
                    self.config.remote_peers = []
                if not isinstance(self.config.remote_instances, list):
                    self.config.remote_instances = []
                if not isinstance(self.config.broadcast_library, list):
                    self.config.broadcast_library = []
                if not isinstance(self.config.mod_path_blacklist, list):
                    self.config.mod_path_blacklist = list(DEFAULT_MOD_PATH_BLACKLIST)
                try:
                    day = int(self.config.force_day_on_start)
                except (TypeError, ValueError):
                    day = 20
                self.config.force_day_on_start = max(0, min(day, 2_147_483_647))
                # SetDay via RCON crasha ASE 361.7 — força OFF e persiste se estava ligado.
                _fd_was_on = bool(self.config.force_day_on_start_enabled)
                self.config.force_day_on_start_enabled = False
                if _fd_was_on:
                    self.save()
                if not self.config.remote_agent_token:
                    self.config.remote_agent_token = str(uuid.uuid4())
                    self.save()
                if getattr(self.config.shop, "cross_chat_enabled", False):
                    self.config.shop.cross_chat_enabled = False
                    self.save()
                # Migra config legado (local_cluster_path / shared_path) para sync_cycles
                if not self.config.sync_cycles:
                    old_local = self.config.local_cluster_path.strip()
                    old_shared = self.config.shared_path.strip()
                    if old_local or old_shared:
                        self.config.sync_cycles = [[old_local, old_shared]]
        except Exception:
            import logging as _logging
            _logging.getLogger("arkland").exception(
                "config.json ilegível — recomeçando com padrões (cópia .corrupt-* será criada): %s",
                self._config_file)
            # Config ilegível: guarda cópia antes de recomeçar com os padrões
            # (evita perder silenciosamente todas as opções salvas).
            try:
                if self._config_file.exists():
                    shutil.copy2(
                        self._config_file,
                        self._config_file.with_name(
                            f"{self._config_file.name}.corrupt-{time.strftime('%Y%m%d-%H%M%S')}"
                        ),
                    )
            except OSError:
                pass
            self.config = AppConfig()
            self.config.remote_agent_token = str(uuid.uuid4())
            self.save()

        self._load_servers()
        self._load_clusters()

    def save(self) -> None:
        """Grava o config.json de forma ATÔMICA (tmp + replace) com retentativas.

        A gravação direta (``open(..., "w")``) deixava o arquivo truncado se o app fosse
        encerrado no meio, e uma falha de I/O (antivírus/lock no Windows) passava em
        silêncio dentro de callbacks do Tk — a opção «voltava» ao valor antigo no próximo
        boot. Agora o erro é propagado ao chamador depois de algumas tentativas.
        """
        self._config_dir.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(asdict(self.config), indent=2, ensure_ascii=False)  # type: ignore[arg-type]
        tmp = self._config_file.with_name(self._config_file.name + ".tmp")
        last_exc: Optional[BaseException] = None
        for attempt in range(5):
            try:
                with open(tmp, "w", encoding="utf-8") as fh:
                    fh.write(payload)
                    fh.flush()
                    os.fsync(fh.fileno())
                os.replace(tmp, self._config_file)
                return
            except OSError as exc:
                last_exc = exc
                import logging as _logging
                _logging.getLogger("arkland").warning(
                    "Falha ao gravar config.json (tentativa %d/5): %s", attempt + 1, exc)
                time.sleep(0.15 * (attempt + 1))
        assert last_exc is not None
        import logging as _logging
        _logging.getLogger("arkland").error("config.json NÃO foi gravado após 5 tentativas: %s", last_exc)
        raise last_exc

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
                    import logging as _logging
                    _logging.getLogger("arkland").warning(
                        "servers.json: perfil inválido ignorado (id=%r)",
                        item.get("id") if isinstance(item, dict) else None, exc_info=True)
        except Exception:
            import logging as _logging
            _logging.getLogger("arkland").exception("Falha ao ler %s", self._servers_file)

    def save_servers(self) -> None:
        self._config_dir.mkdir(parents=True, exist_ok=True)
        try:
            with open(self._servers_file, "w", encoding="utf-8") as fh:
                json.dump([s.to_dict() for s in self._servers], fh, indent=2, ensure_ascii=False)
        except Exception:
            import logging as _logging
            _logging.getLogger("arkland").exception("Falha ao gravar %s", self._servers_file)
            raise
        from .diagnostics.events import CAT_CONFIG, diag_event
        diag_event(CAT_CONFIG, "servers.json salvo", servers=len(self._servers), file=str(self._servers_file))

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
