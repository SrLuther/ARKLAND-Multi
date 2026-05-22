from __future__ import annotations
import os
from typing import TYPE_CHECKING
import pathlib
from pathlib import Path
if TYPE_CHECKING:
    from ..app import ARKServerManagerApp


def write_allowed_admins(app: "ARKServerManagerApp", server_id: str) -> None:
    """Grava AllowedCheaterSteamIDs.txt imediatamente, sem depender do botão Salvar."""
    import pathlib
    srv = app.config_manager.get_server(server_id)
    if not srv or not srv.install_dir or not os.path.isdir(srv.install_dir):
        return
    try:
        allowed_path = (
            pathlib.Path(srv.install_dir)
            / "ShooterGame" / "Saved"
            / "AllowedCheaterSteamIDs.txt"
        )
        allowed_path.parent.mkdir(parents=True, exist_ok=True)
        allowed_path.write_text("\n".join(srv.admin_ids), encoding="utf-8")
    except Exception as exc:
        app._global_log(
            f"[{srv.name}] Aviso: não foi possível gravar AllowedCheaterSteamIDs.txt: {exc}",
            "warning",
        )

