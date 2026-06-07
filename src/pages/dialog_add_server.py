"""Dialog para adicionar novo servidor ARK (modo primitivo)."""
from __future__ import annotations
import tkinter as tk
from typing import TYPE_CHECKING, Dict, List, Optional
import customtkinter as ctk  # type: ignore[reportMissingImports]
from ..server_config import ServerConfig, ARK_MAPS, ARK_MAP_NAMES
from ..ui_constants import _GREEN_DARK, _GREEN_HOVER
if TYPE_CHECKING:
    from ..app import ARKServerManagerApp


def _do_create_server(app, dlg, fields: dict) -> None:
    """Cria ServerConfig a partir dos campos do diálogo e registra no app."""
    name    = fields["name"].get().strip() or "Servidor ARK"
    map_raw = fields["map"].get()
    map_id  = map_raw.split("(")[-1].rstrip(")") if ("(" in map_raw and map_raw.endswith(")")) else map_raw
    srv = ServerConfig(
        name=name, map=map_id,
        install_dir=fields["install_dir"].get().strip(),
        server_name=name,
        admin_password=fields["admin_pass"].get(),
        rcon_password=fields["admin_pass"].get(),
    )
    try:
        srv.server_port = int(fields["port"].get())
        srv.query_port  = int(fields["qport"].get())
        srv.rcon_port   = int(fields["rport"].get())
    except ValueError:
        pass
    app.config_manager.add_server(srv)
    app.server_manager.add_server(srv)
    app._rebuild_server_sidebar()
    app._refresh_dashboard()
    dlg.destroy()
    app._open_server_panel(srv.id)


def _add_field_row(dlg, fields: dict, app, label: str, key: str, default: str, rn: int,
                   combo: Optional[List] = None, browse: bool = False) -> None:
    """Adiciona uma linha label+widget ao diálogo de criação de servidor."""
    ctk.CTkLabel(dlg, text=label, width=170, anchor="w",
                 text_color="gray60").grid(row=rn, column=0, padx=20, pady=6)
    fields[key] = tk.StringVar(value=default)
    if combo:
        ctk.CTkComboBox(dlg, variable=fields[key], values=combo,
                        width=260, height=34).grid(row=rn, column=1, padx=(0, 20), pady=6, sticky="ew")
    elif browse:
        fr = ctk.CTkFrame(dlg, fg_color="transparent")
        fr.grid(row=rn, column=1, padx=(0, 20), pady=6, sticky="ew")
        fr.grid_columnconfigure(0, weight=1)
        ctk.CTkEntry(fr, textvariable=fields[key], height=34).grid(row=0, column=0, sticky="ew", padx=(0, 6))
        ctk.CTkButton(fr, text="📁", width=34, height=34,
                      command=lambda: app._browse_dir(fields[key])).grid(row=0, column=1)
    else:
        ctk.CTkEntry(dlg, textvariable=fields[key], height=34).grid(
            row=rn, column=1, padx=(0, 20), pady=6, sticky="ew")


def dialog_add_server(app) -> None:
    dlg = ctk.CTkToplevel(app)
    dlg.title("Novo Servidor ARK")
    dlg.geometry("520x500")
    dlg.resizable(False, False)
    dlg.grab_set()
    dlg.grid_columnconfigure(1, weight=1)
    ctk.CTkLabel(dlg, text="Novo Servidor",
                 font=ctk.CTkFont(size=18, weight="bold")).grid(
        row=0, column=0, columnspan=2, padx=20, pady=(20, 16), sticky="w")
    fields: Dict[str, tk.StringVar] = {}
    def fr(label, key, default, rn, combo=None, browse=False):
        _add_field_row(dlg, fields, app, label, key, default, rn, combo=combo, browse=browse)
    fr("Nome do Servidor (label):", "name",       "Meu Servidor ARK", 1)
    fr("Mapa:", "map", "TheIsland", 2, combo=[f"{ARK_MAP_NAMES.get(m, m)} ({m})" for m in ARK_MAPS])
    fr("Diretório de Instalação:", "install_dir", "",     3, browse=True)
    fr("Porta do Servidor:",       "port",        "7777", 4)
    fr("Porta Query:",             "qport",       "27015",5)
    fr("Porta RCON:",              "rport",       "27020",6)
    fr("Senha de Admin:",          "admin_pass",  "",     7)
    ctk.CTkButton(dlg, text="✅  Criar Servidor", height=40,
                  font=ctk.CTkFont(size=14, weight="bold"),
                  fg_color=_GREEN_DARK, hover_color=_GREEN_HOVER,
                  command=lambda: _do_create_server(app, dlg, fields),
                  ).grid(row=8, column=0, columnspan=2, padx=20, pady=(16, 20), sticky="ew")

