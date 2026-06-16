from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any, List, Optional

from ..ark_server_files import write_allowed_cheater_steam_ids_safe

if TYPE_CHECKING:
    from ..app import ARKServerManagerApp


def _resolve_server(app: "ARKServerManagerApp", server_id: str) -> Optional[Any]:
    """TEK (AsmServerConfig) ou legado (ServerConfig)."""
    asm_cm = getattr(app, "asm_config_manager", None)
    if asm_cm is not None:
        srv = asm_cm.get_server(server_id)
        if srv is not None:
            return srv
    return app.config_manager.get_server(server_id)


def write_allowed_admins(app: "ARKServerManagerApp", server_id: str) -> None:
    """Grava AllowedCheaterSteamIDs.txt imediatamente, sem depender do botão Salvar."""
    srv = _resolve_server(app, server_id)
    if not srv or not getattr(srv, "install_dir", "") or not os.path.isdir(srv.install_dir):
        return
    admin_ids: List[str] = list(getattr(srv, "admin_ids", None) or [])
    name = getattr(srv, "name", "") or server_id

    def _warn(msg: str) -> None:
        log_fn = getattr(app, "_global_log", None)
        if log_fn:
            log_fn(msg, "warning")

    write_allowed_cheater_steam_ids_safe(
        srv.install_dir,
        admin_ids,
        server_name=name,
        on_warning=_warn,
    )
