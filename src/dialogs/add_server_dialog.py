from __future__ import annotations

import tkinter as tk
from tkinter import messagebox
from typing import TYPE_CHECKING

import customtkinter as ctk  # type: ignore[reportMissingImports]

from ..ui_constants import _GREEN_DARK, _GREEN_HOVER

if TYPE_CHECKING:
    from ..app import ARKServerManagerApp


def dialog_add_server(app: "ARKServerManagerApp") -> None:
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

    def field_row(label: str, key: str, default: str, rn: int,
                  combo: Optional[List] = None, browse: bool = False) -> None:
        ctk.CTkLabel(dlg, text=label, width=170, anchor="w",
                     text_color="gray60").grid(row=rn, column=0, padx=20, pady=6)
        fields[key] = tk.StringVar(value=default)
        if combo:
            ctk.CTkComboBox(dlg, variable=fields[key], values=combo,
                            width=260, height=34).grid(
                row=rn, column=1, padx=(0, 20), pady=6, sticky="ew")
        elif browse:
            fr = ctk.CTkFrame(dlg, fg_color="transparent")
            fr.grid(row=rn, column=1, padx=(0, 20), pady=6, sticky="ew")
            fr.grid_columnconfigure(0, weight=1)
            ctk.CTkEntry(fr, textvariable=fields[key], height=34).grid(
                row=0, column=0, sticky="ew", padx=(0, 6))
            ctk.CTkButton(fr, text="📁", width=34, height=34,
                          command=lambda: app._browse_dir(fields[key])).grid(row=0, column=1)
        else:
            ctk.CTkEntry(dlg, textvariable=fields[key], height=34).grid(
                row=rn, column=1, padx=(0, 20), pady=6, sticky="ew")

    # ── Sugestão automática de diretório ────────────────────────────
    def _suggest_install_dir() -> str:
        base = (app.config_manager.config.default_install_dir or "").strip()
        if not base:
            return ""
        from pathlib import Path as _Path
        servers_root = _Path(base) / "Servidores"
        n = len(app.config_manager.servers) + 1
        # Encontra o próximo número não ocupado
        while True:
            candidate = servers_root / f"Servidor {n:02d}"
            if not candidate.exists():
                return str(candidate)
            n += 1

    field_row("Nome do Servidor (label):", "name",       "Meu Servidor ARK", 1)
    field_row("Mapa:", "map", "TheIsland", 2, combo=[
        f"{ARK_MAP_NAMES.get(m, m)} ({m})" for m in ARK_MAPS])
    field_row("Diretório de Instalação:", "install_dir", _suggest_install_dir(), 3, browse=True)

    # Porta do Servidor + Porta Par ────────────────────────────────────────
    ctk.CTkLabel(dlg, text="Porta do Servidor:", width=170, anchor="w",
                 text_color="gray60").grid(row=4, column=0, padx=20, pady=6)
    fields["port"]      = tk.StringVar(value="7777")
    fields["peer_port"] = tk.StringVar(value="7778")
    _dlg_sp_fr = ctk.CTkFrame(dlg, fg_color="transparent")
    _dlg_sp_fr.grid(row=4, column=1, padx=(0, 20), pady=6, sticky="ew")
    _dlg_sp_fr.grid_columnconfigure(0, weight=1)
    ctk.CTkEntry(_dlg_sp_fr, textvariable=fields["port"], height=34).grid(
        row=0, column=0, sticky="ew")
    ctk.CTkLabel(_dlg_sp_fr, text="Par:",
                 text_color="gray55",
                 font=ctk.CTkFont(size=11)).grid(row=0, column=1, padx=(10, 4))
    ctk.CTkLabel(_dlg_sp_fr, textvariable=fields["peer_port"],
                 font=ctk.CTkFont(size=13, weight="bold"),
                 text_color="#7ec8e3").grid(row=0, column=2, padx=(0, 4))

    def _dlg_update_peer(*_):
        try:
            fields["peer_port"].set(str(int(fields["port"].get()) + 1))
        except ValueError:
            pass
    fields["port"].trace_add("write", _dlg_update_peer)

    field_row("Porta Query:",             "qport",       "27015",            5)
    field_row("Porta RCON:",              "rport",       "27020",            6)
    field_row("Senha de Admin:",          "admin_pass",  "",                 7)

    def _create():
        name = fields["name"].get().strip() or "Servidor ARK"
        map_raw = fields["map"].get()
        if "(" in map_raw and map_raw.endswith(")"):
            map_id = map_raw.split("(")[-1].rstrip(")")
        else:
            map_id = map_raw

        try:
            _sp = int(fields["port"].get())
            _qp = int(fields["qport"].get())
            _rp = int(fields["rport"].get())
            _port_errs = app._validate_server_ports("", _sp, _qp, _rp)
            if _port_errs:
                messagebox.showerror(
                    "Conflito de Portas",
                    "Corrija os conflitos antes de criar o servidor:\n\n"
                    + "\n".join(f"• {e}" for e in _port_errs),
                    parent=dlg,
                )
                return
        except ValueError:
            pass

        srv = ServerConfig(
            name           = name,
            map            = map_id,
            install_dir    = fields["install_dir"].get().strip(),
            server_name    = name,
            admin_password = fields["admin_pass"].get(),
            rcon_password  = fields["admin_pass"].get(),
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

    ctk.CTkButton(
        dlg, text="✅  Criar Servidor", height=40,
        font=ctk.CTkFont(size=14, weight="bold"),
        fg_color=_GREEN_DARK, hover_color=_GREEN_HOVER,
        command=_create,
    ).grid(row=8, column=0, columnspan=2, padx=20, pady=(16, 20), sticky="ew")

