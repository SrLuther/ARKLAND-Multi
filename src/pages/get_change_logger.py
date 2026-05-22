from __future__ import annotations
import os
from typing import TYPE_CHECKING
from pathlib import Path
from ..change_logger import ChangeLogger
if TYPE_CHECKING:
    from ..app import ARKServerManagerApp


def get_change_logger(app: "ARKServerManagerApp", server_id: str) -> "ChangeLogger":
    """Retorna (ou cria) o ChangeLogger para o servidor."""
    if not hasattr(app, "_change_loggers"):
        app._change_loggers: dict = {}
    if server_id not in app._change_loggers:
        log_dir = Path(os.environ.get("APPDATA", "~")).expanduser() \
            / "ARKLAND-ServerManager" / "logs"
        app._change_loggers[server_id] = ChangeLogger(log_dir, server_id)
    return app._change_loggers[server_id]

