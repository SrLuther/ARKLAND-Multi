"""
Gerencia a configuração persistente do ARKLAND-Multi.
As configurações são salvas em %APPDATA%\\ARKLAND-Multi\\config.json
"""
import json
import os
from pathlib import Path
from dataclasses import dataclass, asdict, field


@dataclass
class AppConfig:
    local_cluster_path: str = ""   # Pasta ARK Cluster local
    shared_path: str = ""          # Pasta compartilhada entre as máquinas
    sync_interval: int = 5         # Intervalo de sync em segundos
    machine_name: str = ""         # Nome/label desta máquina
    auto_start: bool = True        # Iniciar sync automático ao abrir
    log_debug: bool = False        # Mostrar ciclos sem alterações no log
    update_url: str = "https://raw.githubusercontent.com/SrLuther/ARKLAND-Multi/main/version.json"
    startup_with_windows: bool = False  # Iniciar o programa com o Windows
    # ── Agente remoto (lado servidor) ──────────────────────────────────────────
    remote_agent_enabled: bool = False  # Expor API HTTP para controle remoto
    remote_agent_port: int = 19567      # Porta do agente HTTP
    remote_agent_token: str = ""        # Token de autenticação Bearer
    # ── Peers remotos (lado cliente) ──────────────────────────────────────────
    remote_peers: list = field(default_factory=list)  # Lista de dicts {name, host, port, token}


class ConfigManager:
    def __init__(self) -> None:
        self._config_dir = Path(os.environ.get("APPDATA", Path.home())) / "ARKLAND-Multi"
        self._config_file = self._config_dir / "config.json"
        self.config = AppConfig()
        self.load()

    # ------------------------------------------------------------------
    _DEFAULT_UPDATE_URL = "https://raw.githubusercontent.com/SrLuther/ARKLAND-Multi/main/version.json"

    def load(self) -> None:
        try:
            if self._config_file.exists():
                with open(self._config_file, "r", encoding="utf-8") as fh:
                    data = json.load(fh)
                valid = AppConfig.__dataclass_fields__.keys()
                self.config = AppConfig(**{k: v for k, v in data.items() if k in valid})
                # Migração: garante que a URL de atualização nunca fique vazia
                if not self.config.update_url:
                    self.config.update_url = self._DEFAULT_UPDATE_URL
                # Migração: remote_peers pode vir como null de configs antigas
                if not isinstance(self.config.remote_peers, list):
                    self.config.remote_peers = []
        except Exception:
            self.config = AppConfig()

    def save(self) -> None:
        self._config_dir.mkdir(parents=True, exist_ok=True)
        with open(self._config_file, "w", encoding="utf-8") as fh:
            json.dump(asdict(self.config), fh, indent=2, ensure_ascii=False)
