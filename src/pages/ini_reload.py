from __future__ import annotations
import tkinter as tk
from typing import TYPE_CHECKING
import customtkinter as ctk  # type: ignore[reportMissingImports]
if TYPE_CHECKING:
    from ..app import ARKServerManagerApp
from ..ark_ini import parse_ini_text_to_sections


def ini_reload(app: "ARKServerManagerApp", server_id: str, file_key: str) -> None:
    """Recarrega os dados de mod_ini_configs + custom_ini_sections e reconstrói a lista."""
    srv = app.config_manager.get_server(server_id)
    if not srv:
        return
    w = app._server_widgets.get(server_id, {})

    all_sections: list = []
    # Seções vindas dos mods
    ini_key = f"{file_key}_ini"
    for mod_id, cfg in srv.mod_ini_configs.items():
        raw = cfg.get(ini_key, "")
        if raw.strip():
            mod_name = srv.mod_names.get(mod_id, f"Mod {mod_id}")
            for sec in parse_ini_text_to_sections(raw):
                sec["mod_id"] = mod_id
                sec["mod_name"] = mod_name
                all_sections.append(sec)
    # Seções personalizadas (sem mod)
    for sec in srv.custom_ini_sections.get(file_key, []):
        all_sections.append({
            "section": sec.get("section", ""),
            "entries": [dict(e) for e in sec.get("entries", [])],
            "mod_id": None,
            "mod_name": "Personalizado",
        })

    w[f"_ini_{file_key}_data"] = all_sections
    w[f"_ini_{file_key}_sel_section"] = None
    sec_name_var = w.get(f"_ini_{file_key}_sec_name_var")
    if sec_name_var:
        sec_name_var.set("")

    # Limpa o painel KV
    kv_scroll = w.get(f"_ini_{file_key}_kvscroll")
    if kv_scroll:
        for ch in kv_scroll.winfo_children():
            ch.destroy()

    # Reconstrói lista de seções
    sec_scroll = w.get(f"_ini_{file_key}_secscroll")
    if sec_scroll is None:
        return
    for ch in sec_scroll.winfo_children():
        ch.destroy()

    if not all_sections:
        ctk.CTkLabel(sec_scroll,
                     text="Nenhuma seção encontrada.\n"
                          "Adicione uma seção ou configure\n"
                          "o INI de algum mod.",
                     text_color="gray40", font=ctk.CTkFont(size=10),
                     justify="center").pack(pady=20, padx=8)
        return

    for sec in all_sections:
        app._ini_render_section_item(server_id, file_key, sec_scroll, sec)

