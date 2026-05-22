from __future__ import annotations
import tkinter as tk
from typing import TYPE_CHECKING
import customtkinter as ctk  # type: ignore[reportMissingImports]
from ..ui_constants import _GREEN_DARK, _GREEN_HOVER, _RED_DARK, _RED_HOVER, _CARD_BG, _BG
from tkinter import messagebox
from ..remote_agent import parse_identity_code
if TYPE_CHECKING:
    from ..app import ARKServerManagerApp


def refresh_remote_instances_list(app: "ARKServerManagerApp") -> None:
    """Reconstrói a lista de máquinas remotas salvas."""
    if not hasattr(app, "_remote_instances_frame"):
        return
    frame = app._remote_instances_frame
    for w in frame.winfo_children():
        w.destroy()

    instances = app.config_manager.config.remote_instances
    if not instances:
        ctk.CTkLabel(frame, text="Nenhuma máquina remota adicionada ainda.",
                     text_color="gray55").grid(row=0, column=0, padx=4, pady=8, sticky="w")
        return

    # Favoritos primeiro
    sorted_instances = sorted(instances, key=lambda x: (not x.get("favorite", False)))

    for i, inst in enumerate(sorted_instances):
        is_fav   = inst.get("favorite", False)
        has_tok  = bool(inst.get("token", ""))
        card_bg  = "#1c1c2e" if is_fav else _CARD_BG
        card = ctk.CTkFrame(frame, corner_radius=10, fg_color=card_bg)
        card.grid(row=i, column=0, padx=0, pady=4, sticky="ew")
        card.grid_columnconfigure(1, weight=1)

        name_row = ctk.CTkFrame(card, fg_color="transparent")
        name_row.grid(row=0, column=0, padx=14, pady=(12, 0), sticky="w")
        fav_icon = "⭐" if is_fav else "☆"
        ctk.CTkLabel(name_row, text=fav_icon,
                     font=ctk.CTkFont(size=14)).pack(side="left", padx=(0, 4))
        ctk.CTkLabel(name_row, text=inst.get("name", "?"),
                     font=ctk.CTkFont(size=13, weight="bold")).pack(side="left")

        sub_txt = f"{inst.get('host', '?')}:{inst.get('port', '?')}"
        if not has_tok:
            sub_txt += "  🔒 token não salvo"
        ctk.CTkLabel(card, text=sub_txt,
                     text_color="gray55" if has_tok else "#ffaa44",
                     font=ctk.CTkFont(size=11)).grid(
            row=1, column=0, padx=14, pady=(0, 12), sticky="w")

        btn_fr = ctk.CTkFrame(card, fg_color="transparent")
        btn_fr.grid(row=0, column=2, rowspan=2, padx=10, pady=8)

        def _open(i=inst) -> None:
            tok = i.get("token", "")
            if not tok:
                # Pede autenticação (não é favorito)
                _ask_token_and_connect(i)
            else:
                app._open_remote_control(i)

        def _ask_token_and_connect(i=inst) -> None:
            dlg = tk.Toplevel(app)
            dlg.title(f"Autenticar — {i.get('name', '?')}")
            dlg.geometry("480x200")
            dlg.configure(bg=_BG)
            dlg.grab_set()
            dlg.resizable(False, False)
            ctk.CTkLabel(
                dlg,
                text=f"Esta conexão não possui token salvo.\n"
                     f"Cole o código de identidade de '{i.get('name', '?')}' para continuar:",
                text_color="gray70", wraplength=440,
            ).pack(padx=20, pady=(20, 6), anchor="w")
            code_sv = tk.StringVar()
            ctk.CTkEntry(dlg, textvariable=code_sv, height=34, width=440,
                         font=ctk.CTkFont(family="Consolas", size=10),
                         placeholder_text="eyJuIjoi...").pack(padx=20)
            err_var = tk.StringVar()
            ctk.CTkLabel(dlg, textvariable=err_var,
                         text_color="#ff6666", font=ctk.CTkFont(size=11)).pack(
                padx=20, pady=(4, 0), anchor="w")

            def _confirm() -> None:
                try:
                    data = parse_identity_code(code_sv.get())
                except ValueError as exc:
                    err_var.set(str(exc))
                    return
                dlg.destroy()
                temp = dict(i)
                temp["host"]  = data["h"]
                temp["port"]  = data["p"]
                temp["token"] = data["t"]
                app._open_remote_control(temp)

            ctk.CTkButton(dlg, text="✔  Conectar", height=36,
                          fg_color=_GREEN_DARK, hover_color=_GREEN_HOVER,
                          command=_confirm).pack(pady=12)

        def _toggle_fav(i=inst) -> None:
            i["favorite"] = not i.get("favorite", False)
            if not i["favorite"]:
                # Ao desmarcar favorito, remove o token
                i.pop("token", None)
            app.config_manager.save()
            app._refresh_remote_instances_list()

        def _remove(i=inst) -> None:
            if messagebox.askyesno(
                "Remover conexão",
                f"Remover '{i.get('name', '?')}' da lista de máquinas remotas?",
                parent=app,
            ):
                app.config_manager.config.remote_instances.remove(i)
                app.config_manager.save()
                app._refresh_remote_instances_list()

        fav_btn_text = "⭐" if is_fav else "☆"
        fav_btn_clr  = "#3a3010" if is_fav else "#2a2a44"
        fav_btn_hov  = "#5a4a10" if is_fav else "#3a3a54"
        ctk.CTkButton(btn_fr, text=fav_btn_text, width=32, height=32,
                      fg_color=fav_btn_clr, hover_color=fav_btn_hov,
                      command=_toggle_fav).pack(side="left", padx=(0, 4))
        ctk.CTkButton(btn_fr, text="🔗  Conectar", height=32,
                      fg_color=_GREEN_DARK, hover_color=_GREEN_HOVER,
                      command=_open).pack(side="left", padx=(0, 6))
        ctk.CTkButton(btn_fr, text="🗑", width=32, height=32,
                      fg_color=_RED_DARK, hover_color=_RED_HOVER,
                      command=_remove).pack(side="left")

