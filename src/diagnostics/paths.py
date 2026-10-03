"""Caminhos e preferências do módulo de diagnóstico.

Tudo fica sob ``%APPDATA%\\ARKLAND-ServerManager\\`` (mesma pasta de ``config.json``):

* ``logs\\arkland.log`` (+ rotações ``.1`` … ``.5``)
* ``diagnostics\\`` — pacotes .zip gerados
* ``diagnostics.json`` — preferências do diagnóstico (nível de log, webhook Discord)

As funções leem ``%APPDATA%`` a cada chamada (testes podem trocar a variável).
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any, Dict

APP_DIR_NAME = "ARKLAND-ServerManager"
LOG_FILE_NAME = "arkland.log"
PREFS_FILE_NAME = "diagnostics.json"

DEFAULT_PREFS: Dict[str, Any] = {
    "log_level": "INFO",
    # URL do webhook do Discord para envio manual do pacote (segredo — mascarada no .zip).
    "discord_webhook_url": "",
}


def app_data_dir() -> Path:
    """Pasta de dados do app (a mesma usada por ConfigManager/AsmConfigManager)."""
    return Path(os.environ.get("APPDATA", Path.home())) / APP_DIR_NAME


def logs_dir() -> Path:
    return app_data_dir() / "logs"


def log_file_path() -> Path:
    return logs_dir() / LOG_FILE_NAME


def diagnostics_dir() -> Path:
    return app_data_dir() / "diagnostics"


def prefs_path() -> Path:
    return app_data_dir() / PREFS_FILE_NAME


def load_prefs() -> Dict[str, Any]:
    """Lê ``diagnostics.json`` (tolerante: arquivo ausente/corrompido → padrões)."""
    prefs = dict(DEFAULT_PREFS)
    try:
        p = prefs_path()
        if p.is_file():
            data = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                prefs.update({k: v for k, v in data.items() if k in DEFAULT_PREFS})
    except Exception:  # noqa: BLE001 — logging ainda pode não estar pronto
        pass
    return prefs


def save_prefs(**changes: Any) -> Dict[str, Any]:
    """Atualiza e grava (atômico) ``diagnostics.json``. Devolve as prefs finais."""
    prefs = load_prefs()
    for k, v in changes.items():
        if k in DEFAULT_PREFS:
            prefs[k] = v
    target = prefs_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".diag-", suffix=".tmp", dir=str(target.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(prefs, fh, indent=2, ensure_ascii=False)
        os.replace(tmp, target)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
    return prefs
