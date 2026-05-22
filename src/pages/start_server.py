from __future__ import annotations
from typing import TYPE_CHECKING
from tkinter import messagebox
if TYPE_CHECKING:
    from ..app import ARKServerManagerApp


def start_server(app: "ARKServerManagerApp", server_id: str) -> None:
    app._save_server_config(server_id, silent=True)
    srv = app.config_manager.get_server(server_id)
    if not srv:
        return

    # Verifica mods sem arquivo .mod (ARK ignora silenciosamente sem ele)
    if srv.mods and srv.install_dir:
        missing_dot_mod = [
            mid for mid in srv.mods
            if not app.mod_manager.check_mod_installed(srv.install_dir, mid)
        ]
        if missing_dot_mod:
            ids_str = ", ".join(missing_dot_mod)
            ans = messagebox.askyesno(
                "Mods incompletos",
                f"Os seguintes mods estão com arquivo .mod ausente e o ARK não os carregará:\n\n"
                f"{ids_str}\n\n"
                "Baixe os mods novamente na aba Mods antes de iniciar.\n\n"
                "Deseja iniciar mesmo assim?",
                parent=app,
            )
            if not ans:
                return

    if srv and srv.auto_update_on_start and app.mod_manager.is_steamcmd_available() and srv.install_dir:
        app._global_log(f"[{srv.name}] Atualizando servidor via SteamCMD antes de iniciar...", "info")
        def _on_update_done(ok: bool) -> None:
            if ok:
                app._global_log(f"[{srv.name}] Atualização concluída. Iniciando servidor...", "info")
            else:
                app._global_log(f"[{srv.name}] Atualização falhou, iniciando servidor mesmo assim...", "warning")
            app.after(0, lambda: app.server_manager.start_server(server_id))
        app.mod_manager.install_server(
            srv.install_dir, validate=False, on_done=_on_update_done,
            branch_name=srv.branch_name, branch_password=srv.branch_password,
        )
    else:
        app.server_manager.start_server(server_id)

