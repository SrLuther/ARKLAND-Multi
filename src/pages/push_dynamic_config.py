from __future__ import annotations
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from ..app import ARKServerManagerApp
from ..ark_ini import build_dynamic_config


def push_dynamic_config(app: "ARKServerManagerApp", server_id: str) -> None:
    """Atualiza o conteúdo INI servido para um servidor — aplicado na próxima poll do ARK."""
    srv = app.config_manager.get_server(server_id)
    if not srv:
        return
    if not app._dynamic_config_server.is_running:
        ok = app._dynamic_config_server.start()
        if not ok:
            app._global_log(
                f"[{srv.name}] Não foi possível iniciar o servidor HTTP de config dinâmica "
                f"(porta {app._dynamic_config_server.port} em uso?).", "error")
            return
    content = build_dynamic_config(srv)
    app._dynamic_config_server.update(server_id, content)
    url = app._dynamic_config_server.get_url(server_id)
    app._global_log(
        f"[{srv.name}] Config dinâmica atualizada → {url} "
        f"(ARK aplicará na próxima poll, ~2 min).", "info")
    # Atualiza label de URL na UI se o painel estiver aberto
    w = app._server_widgets.get(server_id, {})
    url_var = w.get("_dyn_url_var")
    if url_var:
        url_var.set(url)

