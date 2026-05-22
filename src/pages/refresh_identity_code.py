from __future__ import annotations
from typing import TYPE_CHECKING
from ..ui_constants import _hostname
from ..remote_agent import local_ip, make_identity_code
if TYPE_CHECKING:
    from ..app import ARKServerManagerApp


def refresh_identity_code(app: "ARKServerManagerApp") -> None:
    """Atualiza o campo de código de identidade com os dados atuais."""
    if not hasattr(app, "_remote_code_var"):
        return
    cfg = app.config_manager.config
    name  = cfg.remote_agent_name or _hostname()
    port  = cfg.remote_agent_port
    token = cfg.remote_agent_token
    ip    = local_ip()
    code  = make_identity_code(name, ip, port, token)
    app._remote_code_var.set(code)
    if hasattr(app, "_remote_ip_var"):
        app._remote_ip_var.set(f"IP local detectado: {ip}")

