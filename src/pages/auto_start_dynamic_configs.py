from __future__ import annotations
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from ..app import ARKServerManagerApp
from ..ark_ini import build_dynamic_config


def auto_start_dynamic_configs(app: "ARKServerManagerApp") -> None:
    """Inicia o HTTP server e popula config para servidores com dynamic_config_enabled=True."""
    enabled = [s for s in app.config_manager.servers if s.dynamic_config_enabled]
    if not enabled:
        return
    ok = app._dynamic_config_server.start()
    if not ok:
        app._global_log(
            f"Aviso: não foi possível iniciar o servidor HTTP de config dinâmica "
            f"(porta {app._dynamic_config_server.port} em uso?). "
            f"DynamicConfigURL não estará disponível.", "warning")
        return
    for srv in enabled:
        content = build_dynamic_config(srv)
        app._dynamic_config_server.update(srv.id, content)
    app._global_log(
        f"Config dinâmica ativa para {len(enabled)} servidor(es) "
        f"→ http://127.0.0.1:{app._dynamic_config_server.port}/", "info")

