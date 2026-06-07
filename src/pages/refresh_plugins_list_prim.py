"""Atualiza a lista de plugins na aba Plugins (modo primitivo)."""
from __future__ import annotations
import os
from typing import TYPE_CHECKING, Optional
import customtkinter as ctk  # type: ignore[reportMissingImports]
from ..ui_constants import _RED_DARK, _RED_HOVER
if TYPE_CHECKING:
    from ..app import ARKServerManagerApp


def _refresh_arkapi_status(w: dict, app, srv) -> None:
    status_lbl: Optional[ctk.CTkLabel] = w.get("_api_status_lbl")
    if not status_lbl:
        return
    installed = app._is_arkapi_installed(srv.install_dir) if srv.install_dir else False
    status_lbl.configure(
        text="✅  ArkApi instalado" if installed else "❌  ArkApi não encontrado",
        text_color="#66cc77" if installed else "#ff7777",
    )


def _render_plugin_card_header(card, plugin_name: str, plugin_path: str,
                                has_dll: bool, json_files: list,
                                server_id: str, app) -> None:
    icon = "🟢" if has_dll else "🟡"
    ctk.CTkLabel(card, text=icon, font=ctk.CTkFont(size=14), width=28).grid(
        row=0, column=0, padx=(12, 4), pady=(10, 4))
    ctk.CTkLabel(card, text=plugin_name, font=ctk.CTkFont(size=13, weight="bold"),
                 anchor="w").grid(row=0, column=1, padx=4, pady=(10, 4), sticky="ew")
    badge_fr = ctk.CTkFrame(card, fg_color="transparent")
    badge_fr.grid(row=0, column=2, padx=4, pady=(10, 4))
    if has_dll:
        ctk.CTkLabel(badge_fr, text="DLL", text_color="#66aaff",
                     font=ctk.CTkFont(size=9), width=28).pack(side="left", padx=2)
    if json_files:
        ctk.CTkLabel(badge_fr, text="JSON", text_color="#ffcc55",
                     font=ctk.CTkFont(size=9), width=32).pack(side="left", padx=2)
    hdr_btn_fr = ctk.CTkFrame(card, fg_color="transparent")
    hdr_btn_fr.grid(row=0, column=3, padx=(4, 12), pady=(10, 4))
    ctk.CTkButton(hdr_btn_fr, text="📂", width=32, height=28,
                  fg_color="#2a2a4a", hover_color="#3a3a6a",
                  command=lambda p=plugin_path: os.startfile(p)).pack(side="left", padx=2)
    ctk.CTkButton(hdr_btn_fr, text="🗑", width=32, height=28,
                  fg_color=_RED_DARK, hover_color=_RED_HOVER,
                  command=lambda n=plugin_name, sid=server_id: app._delete_plugin(sid, n),
                  ).pack(side="left", padx=2)


def _render_plugin_json_section(card, json_files: list, plugin_path: str, app) -> None:
    if not json_files:
        ctk.CTkLabel(card, text="Sem arquivos de configuração (.json)",
                     text_color="gray40", font=ctk.CTkFont(size=10)).grid(
            row=1, column=0, columnspan=4, padx=(46, 12), pady=(0, 10), sticky="w")
        return
    ctk.CTkFrame(card, height=1, fg_color="#2a2a40").grid(
        row=1, column=0, columnspan=4, padx=12, pady=(0, 4), sticky="ew")
    for jidx, jfile in enumerate(json_files):
        jpath = os.path.join(plugin_path, jfile)
        jrow = ctk.CTkFrame(card, fg_color="transparent")
        jrow.grid(row=2 + jidx, column=0, columnspan=4, padx=(46, 12), pady=2, sticky="ew")
        jrow.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(jrow, text=f"📄  {jfile}", text_color="gray65",
                     font=ctk.CTkFont(family="Courier New", size=11),
                     anchor="w").grid(row=0, column=0, sticky="ew")
        ctk.CTkButton(jrow, text="✏️  Editar", height=26, width=90,
                      fg_color="#333355", hover_color="#444477", font=ctk.CTkFont(size=11),
                      command=lambda p=jpath: app._open_json_editor(p)).grid(row=0, column=1, padx=(8, 0))
    ctk.CTkFrame(card, height=6, fg_color="transparent").grid(
        row=2 + len(json_files), column=0, columnspan=4)


def _render_plugin_card(frame, plugin_name: str, plugin_path: str,
                         has_dll: bool, json_files: list, server_id: str, app) -> None:
    card = ctk.CTkFrame(frame, fg_color="#1a1a2e", corner_radius=8)
    card.pack(fill="x", padx=6, pady=4)
    card.grid_columnconfigure(1, weight=1)
    _render_plugin_card_header(card, plugin_name, plugin_path, has_dll, json_files, server_id, app)
    _render_plugin_json_section(card, json_files, plugin_path, app)


def refresh_plugins_list(app, server_id: str) -> None:
    srv = app.config_manager.get_server(server_id)
    if not srv:
        return
    w = app._server_widgets.get(server_id, {})
    _refresh_arkapi_status(w, app, srv)

    frame: Optional[ctk.CTkScrollableFrame] = w.get("_plugins_list_frame")
    if not frame:
        return
    for child in frame.winfo_children():
        child.destroy()

    if not srv.install_dir:
        ctk.CTkLabel(frame, text="Configure o diretório de instalação do servidor primeiro.",
                     text_color="gray50").pack(pady=20)
        return

    plugins_path = app._plugins_dir(srv.install_dir)
    if not os.path.isdir(plugins_path):
        ctk.CTkLabel(frame, text="Pasta de plugins não encontrada. Instale o ArkApi primeiro.",
                     text_color="gray50").pack(pady=20)
        return

    plugin_folders = sorted(d for d in os.listdir(plugins_path)
                             if os.path.isdir(os.path.join(plugins_path, d)))
    if not plugin_folders:
        ctk.CTkLabel(frame, text="Nenhum plugin instalado.", text_color="gray50").pack(pady=20)
        return

    for plugin_name in plugin_folders:
        plugin_path = os.path.join(plugins_path, plugin_name)
        has_dll     = any(f.lower().endswith(".dll") for f in os.listdir(plugin_path))
        json_files  = sorted(f for f in os.listdir(plugin_path) if f.lower().endswith(".json"))
        _render_plugin_card(frame, plugin_name, plugin_path, has_dll, json_files, server_id, app)
