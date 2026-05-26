from __future__ import annotations
import secrets
import threading
from typing import TYPE_CHECKING
from ..ui_constants import _hostname
from ..remote_agent import RemoteAgent, RemoteClient, UdpDiscovery, local_ip
from tkinter import messagebox
if TYPE_CHECKING:
    from ..app import ARKServerManagerApp


def start_remote_agent(app: "ARKServerManagerApp") -> None:
    """Inicia (ou reinicia) o RemoteAgent e a descoberta LAN com as configurações atuais."""
    cfg = app.config_manager.config

    # Garante que há sempre um token — sem token o agente rejeita tudo
    if not cfg.remote_agent_token:
        cfg.remote_agent_token = secrets.token_urlsafe(12)
        app.config_manager.save()
        app._refresh_identity_code()

    # Para instâncias anteriores
    if app._remote_agent and app._remote_agent.is_running:
        app._remote_agent.stop()
        app._remote_agent = None
    if getattr(app, "_udp_discovery", None):
        app._udp_discovery.stop()
        app._udp_discovery = None

    try:
        name = cfg.remote_agent_name or _hostname()
        app._remote_agent = RemoteAgent(
            server_manager=app.server_manager,
            sync_engine=app._sync_engine,
            port=cfg.remote_agent_port,
            token=cfg.remote_agent_token,
            name=name,
        )
        app._remote_agent.start()

        # Inicia descoberta UDP na rede local
        app._udp_discovery = UdpDiscovery(
            name=name,
            host=local_ip(),
            agent_port=cfg.remote_agent_port,
        )
        app._udp_discovery.start()

        cfg.remote_agent_enabled = True
        app.config_manager.save()
        _schedule_self_test(app, cfg.remote_agent_port)
    except OSError as exc:
        messagebox.showerror(
            "Agente Remoto",
            f"Não foi possível iniciar o agente na porta {cfg.remote_agent_port}:\n{exc}",
            parent=app,
        )
        app._remote_agent = None


def _schedule_self_test(app: "ARKServerManagerApp", port: int) -> None:
    """Após 2 s, testa alcance local do agente e avisa se necessário."""
    def _test() -> None:
        import time
        time.sleep(2.0)
        client = RemoteClient("127.0.0.1", port, token="", timeout=3.0)
        ok = client.ping()
        if not ok:
            app.after(0, lambda: messagebox.showwarning(
                "Agente Remoto",
                f"O agente foi iniciado na porta {port}, mas não respondeu ao teste local.\n\n"
                "Possíveis causas:\n"
                "• O Windows Firewall está bloqueando a porta.\n"
                "• Outra aplicação já está usando essa porta.\n\n"
                "Libere a porta no Windows Defender Firewall → "
                "Regras de Entrada → Nova Regra → Porta → TCP → "
                f"{port}.",
                parent=app,
            ))
    threading.Thread(target=_test, daemon=True).start()

