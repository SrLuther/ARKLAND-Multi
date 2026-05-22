"""Dialog: clonar configurações de um servidor para outros."""
from __future__ import annotations

import copy
import tkinter as tk
from tkinter import messagebox
from typing import TYPE_CHECKING

import customtkinter as ctk  # type: ignore[reportMissingImports]

from ..ui_constants import _GREEN_DARK, _GREEN_HOVER

if TYPE_CHECKING:
    from ..app import ARKServerManagerApp


def open_clone_config_dialog(app: "ARKServerManagerApp", source_server_id: str) -> None:
    """Copia TODAS as configurações de um servidor para outros,
    preservando apenas: nome interno, install_dir, session name e portas."""
    src = app.config_manager.get_server(source_server_id)
    if not src:
        return

    other_servers = [s for s in app.config_manager.servers if s.id != source_server_id]
    if not other_servers:
        messagebox.showinfo("Sem outros servidores",
                            "Nenhum outro servidor cadastrado.", parent=app)
        return

    dlg = ctk.CTkToplevel(app)
    dlg.title("Clonar Configurações")
    dlg.geometry("500x440")
    dlg.resizable(False, False)
    dlg.grab_set()

    ctk.CTkLabel(
        dlg, text=f"Clonar configurações de  '{src.name}'  para:",
        font=ctk.CTkFont(size=14, weight="bold"),
    ).pack(padx=24, pady=(20, 4), anchor="w")

    ctk.CTkLabel(
        dlg,
        text="Serão copiados: mapa, senhas, mods, multiplicadores, configurações\n"
             "avançadas, cluster, admins, backup e argumentos extras.\n"
             "Preservados no destino: nome, diretório, session name e portas.",
        text_color="gray55", font=ctk.CTkFont(size=10), justify="left",
    ).pack(padx=24, pady=(0, 12), anchor="w")

    chk_vars: dict = {}
    scroll_f = ctk.CTkScrollableFrame(dlg, fg_color="transparent", height=220)
    scroll_f.pack(fill="both", expand=True, padx=20, pady=4)

    for s in other_servers:
        var = tk.BooleanVar(value=True)
        chk_vars[s.id] = var
        row_f = ctk.CTkFrame(scroll_f, fg_color="transparent")
        row_f.pack(fill="x", pady=2)
        ctk.CTkCheckBox(
            row_f, text=s.name,
            variable=var,
            checkmark_color="white", fg_color=_GREEN_DARK, hover_color=_GREEN_HOVER,
        ).pack(side="left", padx=8)
        ctk.CTkLabel(
            row_f,
            text=s.install_dir if s.install_dir else "(sem diretório)",
            text_color="gray45" if s.install_dir else "#ff6666",
            font=ctk.CTkFont(size=10),
        ).pack(side="left", padx=(4, 0))

    btn_row = ctk.CTkFrame(dlg, fg_color="transparent")
    btn_row.pack(pady=(12, 20))

    def _do_clone():
        targets = [s for s in other_servers if chk_vars[s.id].get()]
        if not targets:
            messagebox.showwarning("Nada selecionado",
                                   "Selecione ao menos um servidor.", parent=dlg)
            return

        # Campos que NÃO devem ser copiados (identidade do servidor destino)
        _KEEP = {"id", "name", "install_dir", "server_name",
                 "server_port", "query_port", "rcon_port"}

        src_dict = src.to_dict()
        updated = 0
        for dst in targets:
            dst_dict = dst.to_dict()
            merged = {k: (dst_dict[k] if k in _KEEP else copy.deepcopy(v))
                      for k, v in src_dict.items()}
            new_cfg = type(dst).from_dict(merged)
            app.config_manager.update_server(new_cfg)
            app.server_manager.update_server_config(new_cfg)
            frame_key = f"server_{dst.id}"
            if frame_key in app._frames:
                app._rebuild_server_panel(dst.id)
            updated += 1

        dlg.destroy()
        messagebox.showinfo(
            "Clonagem concluída",
            f"Configurações copiadas para {updated} servidor(es).\n"
            "Salve cada servidor para gerar os arquivos .ini no disco.",
            parent=app,
        )

    ctk.CTkButton(
        btn_row, text="📋  Clonar", width=130, height=38,
        fg_color=_GREEN_DARK, hover_color=_GREEN_HOVER,
        command=_do_clone,
    ).pack(side="left", padx=(0, 10))
    ctk.CTkButton(
        btn_row, text="Cancelar", width=100, height=38,
        fg_color="#3a3a5a", hover_color="#252540",
        command=dlg.destroy,
    ).pack(side="left")
