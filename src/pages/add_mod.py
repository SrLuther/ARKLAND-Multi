from __future__ import annotations
import tkinter as tk
from typing import TYPE_CHECKING
from tkinter import messagebox
if TYPE_CHECKING:
    from ..app import ARKServerManagerApp


def add_mod(app: "ARKServerManagerApp", server_id: str, mod_name: str = "") -> None:
    w = app._server_widgets.get(server_id, {})
    raw = w.get("new_mod_id", tk.StringVar()).get().strip()

    # Suporta IDs separados por vírgula, ponto-e-vírgula ou espaço
    parts = [p.strip() for p in raw.replace(";", ",").replace(" ", ",").split(",") if p.strip()]
    if not parts:
        messagebox.showwarning("Mod inválido", "Informe pelo menos um ID numérico.", parent=app)
        return

    invalid = [p for p in parts if not p.isdigit()]
    if invalid:
        messagebox.showwarning(
            "Mod inválido",
            f"Os seguintes IDs não são válidos: {', '.join(invalid)}",
            parent=app,
        )
        return

    srv = app.config_manager.get_server(server_id)
    if not srv:
        return

    added: list[str] = []
    for mod_id in parts:
        if mod_id not in srv.mods:
            srv.mods.append(mod_id)
            added.append(mod_id)

    # mod_name só aplica quando um único mod é adicionado via diálogo de busca
    if mod_name and len(parts) == 1:
        srv.mod_names[parts[0]] = mod_name

    app.config_manager.update_server(srv)
    w["new_mod_id"].set("")
    app._refresh_mods_list(server_id)

    to_fetch = [m for m in added if m not in srv.mod_names]
    if to_fetch:
        app._fetch_mod_names_async(server_id, to_fetch)

