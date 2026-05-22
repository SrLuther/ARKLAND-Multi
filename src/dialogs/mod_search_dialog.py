"""Dialog: buscar mod no Steam Workshop e adicioná-lo a um servidor."""
from __future__ import annotations

import json
import threading
import tkinter as tk
import urllib.parse
import urllib.request
import webbrowser
from typing import TYPE_CHECKING

import customtkinter as ctk  # type: ignore[reportMissingImports]

from ..ui_constants import _BLUE_HOVER, _CARD_BG, _GREEN_DARK, _GREEN_HOVER

if TYPE_CHECKING:
    from ..app import ARKServerManagerApp


def open_mod_search_dialog(app: "ARKServerManagerApp", server_id: str) -> None:
    dlg = ctk.CTkToplevel(app)
    dlg.title("Buscar no Steam Workshop")
    dlg.geometry("640x500")
    dlg.resizable(True, True)
    dlg.grab_set()
    dlg.grid_columnconfigure(0, weight=1)
    dlg.grid_rowconfigure(3, weight=1)

    ctk.CTkLabel(dlg, text="🔍  Buscar Workshop — ARK: Survival Evolved",
                 font=ctk.CTkFont(size=16, weight="bold")).grid(
        row=0, column=0, padx=20, pady=(16, 2), sticky="w")
    ctk.CTkLabel(
        dlg,
        text="Digite um ID numérico para buscar diretamente. Para busca por nome, clique em 🌐 Browser.",
        text_color="gray50", font=ctk.CTkFont(size=11),
    ).grid(row=1, column=0, padx=20, pady=(0, 10), sticky="w")

    search_fr = ctk.CTkFrame(dlg, fg_color="transparent")
    search_fr.grid(row=2, column=0, padx=16, pady=(0, 6), sticky="ew")
    search_fr.grid_columnconfigure(0, weight=1)

    search_var = tk.StringVar()
    search_entry = ctk.CTkEntry(
        search_fr, textvariable=search_var, height=38,
        placeholder_text="ID do mod (ex: 731604991) ou nome para buscar no browser",
    )
    search_entry.grid(row=0, column=0, sticky="ew", padx=(0, 8))
    ctk.CTkButton(search_fr, text="🔍 Buscar", height=38, width=100,
                  fg_color=_GREEN_DARK, hover_color=_GREEN_HOVER,
                  command=lambda: _do_search()).grid(row=0, column=1, padx=(0, 8))
    ctk.CTkButton(search_fr, text="🌐 Browser", height=38, width=100,
                  fg_color="#1a3a6a", hover_color=_BLUE_HOVER,
                  command=lambda: webbrowser.open(
                      "https://steamcommunity.com/app/346110/workshop/"
                  )).grid(row=0, column=2)

    results_frame = ctk.CTkScrollableFrame(dlg, fg_color=_CARD_BG, corner_radius=8)
    results_frame.grid(row=3, column=0, padx=16, pady=(4, 4), sticky="nsew")
    results_frame.grid_columnconfigure(0, weight=1)

    status_lbl = ctk.CTkLabel(dlg, text="", text_color="gray50",
                              font=ctk.CTkFont(size=11))
    status_lbl.grid(row=4, column=0, padx=16, pady=(0, 12), sticky="w")

    def _show_result(title: str, mod_id: str, description: str = "") -> None:
        for child in results_frame.winfo_children():
            child.destroy()
        row_f = ctk.CTkFrame(results_frame, fg_color="#1a1a2e", corner_radius=8)
        row_f.pack(fill="x", padx=8, pady=8)
        row_f.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(row_f, text=f"🔧  {title}",
                     font=ctk.CTkFont(size=14, weight="bold")).grid(
            row=0, column=0, columnspan=2, padx=14, pady=(12, 2), sticky="w")
        ctk.CTkLabel(row_f, text=f"ID: {mod_id}",
                     text_color="gray55",
                     font=ctk.CTkFont(family="Courier New", size=12)).grid(
            row=1, column=0, padx=14, pady=(0, 4), sticky="w")
        if description:
            clean_desc = description.replace("\r", " ").replace("\n", " ").strip()
            preview = (clean_desc[:160] + "…") if len(clean_desc) > 160 else clean_desc
            ctk.CTkLabel(row_f, text=preview, text_color="gray50",
                         font=ctk.CTkFont(size=10),
                         wraplength=560, justify="left").grid(
                row=2, column=0, padx=14, pady=(0, 6), sticky="w")
        btn_row_f = ctk.CTkFrame(row_f, fg_color="transparent")
        btn_row_f.grid(row=3, column=0, padx=10, pady=(0, 12), sticky="w")
        ctk.CTkButton(btn_row_f, text="➕  Adicionar ao Servidor", height=34,
                      fg_color=_GREEN_DARK, hover_color=_GREEN_HOVER,
                      command=lambda t=title, m=mod_id: _add_and_close(m, t)).pack(side="left", padx=(0, 10))
        ctk.CTkButton(btn_row_f, text="🌐  Ver na Steam", height=34,
                      fg_color="#1a3a6a", hover_color=_BLUE_HOVER,
                      command=lambda: app._open_workshop_page(mod_id)).pack(side="left")

    def _add_and_close(mod_id: str, mod_name: str = "") -> None:
        w = app._server_widgets.get(server_id, {})
        if "new_mod_id" in w:
            w["new_mod_id"].set(mod_id)
        app._add_mod(server_id, mod_name=mod_name)
        dlg.destroy()

    def _do_search(*_) -> None:
        query = search_var.get().strip()
        if not query:
            return
        for child in results_frame.winfo_children():
            child.destroy()
        if query.isdigit():
            status_lbl.configure(text="⏳  Buscando mod…")

            def _fetch(qid=query) -> None:
                try:
                    data = urllib.parse.urlencode({
                        "itemcount": "1",
                        "publishedfileids[0]": qid,
                    }).encode()
                    req = urllib.request.Request(
                        "https://api.steampowered.com"
                        "/ISteamRemoteStorage/GetPublishedFileDetails/v1/",
                        data=data,
                        headers={"Content-Type": "application/x-www-form-urlencoded"},
                    )
                    with urllib.request.urlopen(req, timeout=10) as resp:
                        result = json.loads(resp.read().decode())
                    files = result.get("response", {}).get("publishedfiledetails", [])
                    if files and files[0].get("result") == 1:
                        f = files[0]
                        dlg.after(0, lambda: _show_result(
                            f.get("title", "Mod sem nome"),
                            qid,
                            f.get("description", ""),
                        ))
                        dlg.after(0, lambda: status_lbl.configure(text="✅  Mod encontrado."))
                    else:
                        dlg.after(0, lambda: status_lbl.configure(
                            text=f"❌  ID {qid} não encontrado no Workshop."))
                except Exception as exc:
                    err_msg = str(exc)
                    dlg.after(0, lambda m=err_msg: status_lbl.configure(
                        text=f"⚠️  Erro ao buscar: {m}"))

            threading.Thread(target=_fetch, daemon=True).start()
        else:
            url = (
                "https://steamcommunity.com/workshop/browse/?appid=346110"
                f"&searchtext={urllib.parse.quote(query)}&section=readytouseitems"
            )
            webbrowser.open(url)
            status_lbl.configure(
                text="🌐  Busca por texto aberta no navegador. Cole o ID do mod no campo acima.")

    search_entry.bind("<Return>", _do_search)
