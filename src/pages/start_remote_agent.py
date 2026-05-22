from __future__ import annotations
from typing import TYPE_CHECKING
from ..ui_constants import _hostname
from ..remote_agent import RemoteAgent
from tkinter import messagebox
if TYPE_CHECKING:
    from ..app import ARKServerManagerApp


def start_remote_agent(app: "ARKServerManagerApp") -> None:
    """Inicia (ou reinicia) o RemoteAgent com as configurações atuais."""
    cfg = app.config_manager.config
    if app._remote_agent and app._remote_agent.is_running:
        app._remote_agent.stop()
        app._remote_agent = None
    try:
        app._remote_agent = RemoteAgent(
            server_manager=app.server_manager,
            sync_engine=app._sync_engine,
            port=cfg.remote_agent_port,
            token=cfg.remote_agent_token,
            name=cfg.remote_agent_name or _hostname(),
        )
        app._remote_agent.start()
        cfg.remote_agent_enabled = True
        app.config_manager.save()
    except OSError as exc:
        messagebox.showerror(
            "Agente Remoto",
            f"Não foi possível iniciar o agente na porta {cfg.remote_agent_port}:\n{exc}",
            parent=app,
        )
        app._remote_agent = None

