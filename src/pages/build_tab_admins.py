from __future__ import annotations
import io
import tkinter as tk
from typing import TYPE_CHECKING
import customtkinter as ctk  # type: ignore[reportMissingImports]
from ..ui_constants import _GREEN_DARK, _GREEN_HOVER, _CARD_BG
if TYPE_CHECKING:
    from ..app import ARKServerManagerApp
    from ..server_config import ServerConfig


def build_tab_admins(app: "ARKServerManagerApp", parent, srv: "ServerConfig") -> None:
    parent.grid_columnconfigure(0, weight=1)
    parent.grid_rowconfigure(1, weight=1)

    w = app._server_widgets[srv.id]

    add_card = ctk.CTkFrame(parent, corner_radius=10, fg_color=_CARD_BG)
    add_card.grid(row=0, column=0, padx=12, pady=(12, 6), sticky="ew")
    add_card.grid_columnconfigure(1, weight=1)

    ctk.CTkLabel(add_card, text="👤  Steam ID (64-bit):",
                 text_color="gray60").grid(row=0, column=0, padx=16, pady=(14, 4))
    w["new_admin_id"] = tk.StringVar()
    entry = ctk.CTkEntry(add_card, textvariable=w["new_admin_id"], height=34,
                         placeholder_text="Ex: 76561198000000000")
    entry.grid(row=0, column=1, padx=(0, 8), pady=(14, 4), sticky="ew")
    entry.bind("<Return>", lambda _e: app._add_admin_id(srv.id))

    ctk.CTkButton(
        add_card, text="➕ Adicionar", width=110, height=34,
        fg_color=_GREEN_DARK, hover_color=_GREEN_HOVER,
        command=lambda: app._add_admin_id(srv.id),
    ).grid(row=0, column=2, padx=(0, 16), pady=(14, 4))

    # Label de preview do nome Steam
    w["_admin_name_preview"] = ctk.CTkLabel(
        add_card, text="", text_color="gray50",
        font=ctk.CTkFont(size=11), anchor="w",
    )
    w["_admin_name_preview"].grid(row=1, column=1, padx=(0, 8), pady=(0, 4), sticky="w")

    # Debounce: inicia lookup 1s após parar de digitar
    w["_admin_lookup_after"] = None

    def _on_id_change(*_):
        if w.get("_admin_lookup_after"):
            try:
                app.after_cancel(w["_admin_lookup_after"])
            except Exception:
                pass
        steam_id = w["new_admin_id"].get().strip()
        if not steam_id or not steam_id.isdigit() or len(steam_id) < 15:
            w["_admin_name_preview"].configure(text="", text_color="gray50")
            return
        w["_admin_name_preview"].configure(text="🔍  Buscando...", text_color="gray50")
        w["_admin_lookup_after"] = app.after(900, lambda: app._lookup_admin_preview(srv.id, steam_id))

    w["new_admin_id"].trace_add("write", _on_id_change)

    ctk.CTkLabel(
        add_card,
        text="💡  Cole o Steam ID de 64-bit (17 dígitos). Encontre em steamid.io ou em Detalhes do Perfil no Steam.",
        text_color="gray45", font=ctk.CTkFont(size=10), wraplength=700, justify="left",
    ).grid(row=2, column=0, columnspan=3, padx=16, pady=(0, 10), sticky="w")

    admins_card = ctk.CTkScrollableFrame(parent, corner_radius=10, fg_color=_CARD_BG)
    admins_card.grid(row=1, column=0, padx=12, pady=6, sticky="nsew")
    admins_card.grid_columnconfigure(0, weight=1)
    w["_admins_list_frame"] = admins_card

    actions = ctk.CTkFrame(parent, fg_color="transparent")
    actions.grid(row=2, column=0, padx=12, pady=(4, 12), sticky="ew")
    ctk.CTkButton(
        actions, text="💾  Salvar",
        height=38, fg_color=_GREEN_DARK, hover_color=_GREEN_HOVER,
        command=lambda: app._save_server_config(srv.id),
    ).pack(side="left")
    ctk.CTkLabel(
        actions,
        text="IDs são gravados em ShooterGame/Saved/AllowedCheaterSteamIDs.txt ao salvar.",
        text_color="gray45", font=ctk.CTkFont(size=11),
    ).pack(side="left", padx=12)

    app._refresh_admins_list(srv.id)

