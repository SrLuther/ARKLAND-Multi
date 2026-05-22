from __future__ import annotations
import tkinter as tk
from typing import TYPE_CHECKING
from tkinter import messagebox
if TYPE_CHECKING:
    from ..app import ARKServerManagerApp


def add_admin_id(app: "ARKServerManagerApp", server_id: str) -> None:
    w = app._server_widgets.get(server_id, {})
    var: Optional[tk.StringVar] = w.get("new_admin_id")
    if not var:
        return
    steam_id = var.get().strip()
    if not steam_id:
        return
    if not steam_id.isdigit() or len(steam_id) < 15:
        messagebox.showwarning(
            "Steam ID inválido",
            "Informe um Steam ID válido (somente números, mínimo 15 dígitos).",
            parent=app,
        )
        return
    srv = app.config_manager.get_server(server_id)
    if not srv:
        return
    if steam_id in srv.admin_ids:
        messagebox.showinfo("Já existe", f"O ID {steam_id} já está na lista.", parent=app)
        var.set("")
        return
    srv.admin_ids.append(steam_id)
    # Salva o nome resolvido se o preview mostra um nome válido
    w = app._server_widgets.get(server_id, {})
    lbl = w.get("_admin_name_preview")
    if lbl:
        preview = lbl.cget("text")
        if preview.startswith("✅  "):
            clean = app._sanitize_steam_name(preview[3:].strip())
            if clean:
                srv.admin_names[steam_id] = clean
    app.config_manager.update_server(srv)
    app._write_allowed_admins(server_id)
    var.set("")
    lbl = w.get("_admin_name_preview")
    if lbl:
        lbl.configure(text="", text_color="gray50")
    app._refresh_admins_list(server_id)

