from __future__ import annotations
from typing import TYPE_CHECKING
from ..ui_constants import _hostname
from ..remote_agent import local_ip, make_identity_code
if TYPE_CHECKING:
    from ..app import ARKServerManagerApp


def refresh_identity_code(app: "ARKServerManagerApp") -> None:
    """Atualiza o campo de código de identidade com os dados atuais."""
    if not getattr(app, "_remote_code_var", None):
        return
    cfg = app.config_manager.config
    name  = cfg.remote_agent_name or _hostname()
    port  = cfg.remote_agent_port
    token = cfg.remote_agent_token
    local = local_ip()
    # Um IP privado (192.168/10/172.16) no código nao pode ser acessado
    # de outro local. Permite anunciar o IP publico/DDNS configurado no app.
    host = str(getattr(cfg, "remote_agent_host", "") or "").strip() or local
    code  = make_identity_code(name, host, port, token)
    app._remote_code_var.set(code)
    if getattr(app, "_remote_ip_var", None):
        app._remote_ip_var.set(f"Endereco no codigo: {host} | IP local: {local}")

