"""Dialog: editar blocos INI de um mod específico."""
from __future__ import annotations

import tkinter as tk
from tkinter import messagebox
from typing import TYPE_CHECKING

import customtkinter as ctk  # type: ignore[reportMissingImports]

from ..ui_constants import _BLUE, _BLUE_HOVER, _CARD_BG, _GREEN_DARK, _GREEN_HOVER

if TYPE_CHECKING:
    from ..app import ARKServerManagerApp


def open_mod_ini_dialog(app: "ARKServerManagerApp", server_id: str, mod_id: str) -> None:
    srv = app.config_manager.get_server(server_id)
    if not srv:
        return

    cfg      = srv.mod_ini_configs.get(mod_id, {})
    mod_name = srv.mod_names.get(mod_id, "")

    dlg = ctk.CTkToplevel(app)
    mod_label = f"{mod_name} ({mod_id})" if mod_name else mod_id
    dlg.title(f"Configurações INI — Mod {mod_label}")
    dlg.geometry("720x600")
    dlg.resizable(True, True)
    dlg.grab_set()
    dlg.grid_columnconfigure(0, weight=1)
    dlg.grid_rowconfigure(3, weight=1)
    dlg.grid_rowconfigure(5, weight=1)

    # ── Cabeçalho ─────────────────────────────────────────────────────────
    ctk.CTkLabel(
        dlg, text="⚙️  Configurações INI do Mod",
        font=ctk.CTkFont(size=16, weight="bold"),
    ).grid(row=0, column=0, padx=20, pady=(16, 2), sticky="w")

    name_fr = ctk.CTkFrame(dlg, fg_color="transparent")
    name_fr.grid(row=1, column=0, padx=20, pady=(0, 8), sticky="ew")
    name_fr.grid_columnconfigure(1, weight=1)
    ctk.CTkLabel(name_fr, text="Nome do mod:", text_color="gray60", width=110,
                 anchor="w").grid(row=0, column=0, sticky="w")
    name_var = tk.StringVar(value=mod_name)
    ctk.CTkEntry(name_fr, textvariable=name_var, height=32,
                 placeholder_text="Ex: Structures Plus").grid(
        row=0, column=1, sticky="ew", padx=(8, 0))

    ctk.CTkLabel(
        dlg,
        text="Cole abaixo os blocos de configuração fornecidos pelo autor do mod. "
             "Eles serão adicionados ao final dos respectivos arquivos INI do servidor.",
        text_color="gray50", font=ctk.CTkFont(size=11), wraplength=680, justify="left",
    ).grid(row=2, column=0, padx=20, pady=(0, 6), sticky="w")

    # ── Picker de seções cadastradas ──────────────────────────────────────
    def _show_section_picker(target_box: ctk.CTkTextbox) -> None:
        from ..ark_ini import sections_to_ini_text as _sections_to_ini_text
        all_secs: list = []
        for fk, src_label in [("game", "Game.ini"), ("gus", "GUS.ini")]:
            for sec in srv.custom_ini_sections.get(fk, []):
                all_secs.append({
                    "section": sec.get("section", ""),
                    "entries": sec.get("entries", []),
                    "source":  src_label,
                })

        if not all_secs:
            messagebox.showinfo(
                "Seções", "Nenhuma seção personalizada cadastrada no painel INI.",
                parent=dlg,
            )
            return

        picker = ctk.CTkToplevel(dlg)
        picker.title("Inserir seções cadastradas")
        picker.geometry("440x420")
        picker.resizable(True, True)
        picker.grab_set()
        picker.grid_columnconfigure(0, weight=1)
        picker.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(
            picker, text="Selecione as seções a inserir:",
            font=ctk.CTkFont(size=13, weight="bold"),
        ).grid(row=0, column=0, padx=16, pady=(14, 4), sticky="w")

        scroll = ctk.CTkScrollableFrame(picker, fg_color="transparent")
        scroll.grid(row=1, column=0, padx=12, pady=4, sticky="nsew")
        scroll.grid_columnconfigure(0, weight=1)

        for sec in all_secs:
            var = tk.BooleanVar(value=False)
            sec["_var"] = var
            row_fr = ctk.CTkFrame(scroll, fg_color=_CARD_BG, corner_radius=6)
            row_fr.pack(fill="x", pady=2, padx=2)
            row_fr.grid_columnconfigure(1, weight=1)
            ctk.CTkCheckBox(
                row_fr, text="", variable=var, width=28,
                checkmark_color="white", fg_color=_GREEN_DARK, hover_color=_GREEN_HOVER,
            ).grid(row=0, column=0, padx=(8, 0), pady=6)
            ctk.CTkLabel(
                row_fr,
                text=f"[{sec['section']}]",
                font=ctk.CTkFont(size=12, weight="bold"),
                anchor="w",
            ).grid(row=0, column=1, padx=(6, 4), pady=6, sticky="w")
            ctk.CTkLabel(
                row_fr,
                text=sec["source"],
                font=ctk.CTkFont(size=10),
                text_color="gray50",
                anchor="e",
            ).grid(row=0, column=2, padx=(0, 10), pady=6, sticky="e")

        btn_fr2 = ctk.CTkFrame(picker, fg_color="transparent")
        btn_fr2.grid(row=2, column=0, padx=16, pady=(4, 14), sticky="e")

        def _insert() -> None:
            selected = [s for s in all_secs if s.get("_var") and s["_var"].get()]
            if not selected:
                messagebox.showwarning("Inserir", "Selecione ao menos uma seção.", parent=picker)
                return
            lines: list[str] = []
            for s in selected:
                lines.append(_sections_to_ini_text([
                    {"section": s["section"], "entries": s["entries"]}
                ]).strip())
            insert_text = "\n\n".join(lines)
            existing = target_box.get("0.0", "end").strip()
            target_box.delete("0.0", "end")
            target_box.insert("0.0", (existing + "\n\n" + insert_text).strip() if existing else insert_text)
            picker.destroy()

        ctk.CTkButton(
            btn_fr2, text="Cancelar", width=90, height=32,
            fg_color="gray30", hover_color="gray40",
            command=picker.destroy,
        ).pack(side="left", padx=(0, 8))
        ctk.CTkButton(
            btn_fr2, text="✅  Inserir selecionadas", width=180, height=32,
            fg_color=_GREEN_DARK, hover_color=_GREEN_HOVER,
            command=_insert,
        ).pack(side="left")

    # ── Game.ini ──────────────────────────────────────────────────────────
    game_hdr = ctk.CTkFrame(dlg, fg_color="transparent")
    game_hdr.grid(row=3, column=0, padx=20, pady=(4, 2), sticky="ew")
    game_hdr.grid_columnconfigure(0, weight=1)
    ctk.CTkLabel(
        game_hdr, text="📄  Game.ini",
        font=ctk.CTkFont(size=13, weight="bold"),
    ).grid(row=0, column=0, sticky="w")
    ctk.CTkButton(
        game_hdr, text="📋  Inserir seção...", width=150, height=26,
        fg_color=_BLUE, hover_color=_BLUE_HOVER,
        font=ctk.CTkFont(size=11),
        command=lambda: _show_section_picker(game_ini_box),
    ).grid(row=0, column=1, sticky="e")

    game_ini_box = ctk.CTkTextbox(dlg, font=ctk.CTkFont(family="Courier New", size=12))
    game_ini_box.grid(row=4, column=0, padx=20, pady=(0, 8), sticky="nsew")
    game_ini_box.insert("0.0", cfg.get("game_ini", ""))
    dlg.grid_rowconfigure(4, weight=1)

    # ── GameUserSettings.ini ──────────────────────────────────────────────
    gus_hdr = ctk.CTkFrame(dlg, fg_color="transparent")
    gus_hdr.grid(row=5, column=0, padx=20, pady=(4, 2), sticky="ew")
    gus_hdr.grid_columnconfigure(0, weight=1)
    ctk.CTkLabel(
        gus_hdr, text="📄  GameUserSettings.ini",
        font=ctk.CTkFont(size=13, weight="bold"),
    ).grid(row=0, column=0, sticky="w")
    ctk.CTkButton(
        gus_hdr, text="📋  Inserir seção...", width=150, height=26,
        fg_color=_BLUE, hover_color=_BLUE_HOVER,
        font=ctk.CTkFont(size=11),
        command=lambda: _show_section_picker(gus_ini_box),
    ).grid(row=0, column=1, sticky="e")

    gus_ini_box = ctk.CTkTextbox(dlg, font=ctk.CTkFont(family="Courier New", size=12))
    gus_ini_box.grid(row=6, column=0, padx=20, pady=(0, 8), sticky="nsew")
    gus_ini_box.insert("0.0", cfg.get("gus_ini", ""))
    dlg.grid_rowconfigure(6, weight=1)

    # ── Botões ────────────────────────────────────────────────────────────
    btn_fr = ctk.CTkFrame(dlg, fg_color="transparent")
    btn_fr.grid(row=7, column=0, padx=20, pady=(0, 16), sticky="e")

    def _save():
        game_txt = game_ini_box.get("0.0", "end").strip()
        gus_txt  = gus_ini_box.get("0.0", "end").strip()
        name_txt = name_var.get().strip()
        if name_txt:
            srv.mod_names[mod_id] = name_txt
        else:
            srv.mod_names.pop(mod_id, None)
        if game_txt or gus_txt:
            srv.mod_ini_configs[mod_id] = {"game_ini": game_txt, "gus_ini": gus_txt}
        else:
            srv.mod_ini_configs.pop(mod_id, None)
        app.config_manager.update_server(srv)
        app._refresh_mods_list(server_id)
        dlg.destroy()

    def _apply_to_files():
        _save()
        from ..ark_ini import ArkIniManager
        mgr = ArkIniManager(srv.install_dir)
        try:
            mgr.apply_mod_ini_configs(srv.mod_ini_configs)
            messagebox.showinfo(
                "INI Aplicado",
                "Configurações dos mods aplicadas nos arquivos INI do servidor.",
                parent=app,
            )
        except Exception as exc:
            messagebox.showerror("Erro", str(exc), parent=app)

    ctk.CTkButton(
        btn_fr, text="Cancelar", width=100, height=36,
        fg_color="gray30", hover_color="gray40",
        command=dlg.destroy,
    ).pack(side="left", padx=(0, 8))
    ctk.CTkButton(
        btn_fr, text="💾  Salvar", width=110, height=36,
        fg_color=_GREEN_DARK, hover_color=_GREEN_HOVER,
        command=_save,
    ).pack(side="left", padx=(0, 8))
    ctk.CTkButton(
        btn_fr, text="✅  Salvar e Aplicar nos INIs", width=200, height=36,
        fg_color=_BLUE, hover_color=_BLUE_HOVER,
        command=_apply_to_files,
    ).pack(side="left")
