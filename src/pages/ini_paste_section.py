from __future__ import annotations
import tkinter as tk
from typing import TYPE_CHECKING
import customtkinter as ctk  # type: ignore[reportMissingImports]
from ..ui_constants import _GREEN_DARK, _GREEN_HOVER
if TYPE_CHECKING:
    from ..app import ARKServerManagerApp


def ini_paste_section(app: "ARKServerManagerApp", server_id: str, file_key: str) -> None:
    """Abre diálogo para colar um bloco INI completo (uma ou mais seções)."""
    dlg = ctk.CTkToplevel(app)
    dlg.title("Colar Seção INI")
    dlg.geometry("600x400")
    dlg.resizable(True, True)
    dlg.grab_set()
    dlg.grid_columnconfigure(0, weight=1)
    dlg.grid_rowconfigure(1, weight=1)

    # Instrução
    ctk.CTkLabel(
        dlg,
        text="Cole o bloco INI abaixo. Pode conter uma ou mais seções.",
        text_color="gray60",
        font=ctk.CTkFont(size=11),
    ).grid(row=0, column=0, padx=16, pady=(14, 4), sticky="w")

    txt = ctk.CTkTextbox(dlg, font=ctk.CTkFont(family="Consolas", size=12),
                         fg_color="#1a1a28", border_width=1, border_color="#3a3a5a")
    txt.grid(row=1, column=0, sticky="nsew", padx=16, pady=(0, 6))

    # Placeholder – inserido e removido ao focar
    _PLACEHOLDER = "[NomeDaSeção]\nChave=Valor\nChave2=Valor2"
    txt.insert("1.0", _PLACEHOLDER)
    txt.configure(text_color="gray45")

    def _on_focus_in(_e):
        if txt.get("1.0", "end-1c") == _PLACEHOLDER:
            txt.delete("1.0", "end")
            txt.configure(text_color="#e0e0f0")

    def _on_focus_out(_e):
        if not txt.get("1.0", "end-1c").strip():
            txt.insert("1.0", _PLACEHOLDER)
            txt.configure(text_color="gray45")

    txt.bind("<FocusIn>",  _on_focus_in)
    txt.bind("<FocusOut>", _on_focus_out)

    # Feedback label
    fb_var = tk.StringVar()
    fb_lbl = ctk.CTkLabel(dlg, textvariable=fb_var, text_color="#ffaa44",
                          font=ctk.CTkFont(size=11))
    fb_lbl.grid(row=2, column=0, padx=16, sticky="w")

    def _import():
        raw = txt.get("1.0", "end-1c").strip()
        if not raw or raw == _PLACEHOLDER:
            fb_var.set("⚠ Cole algum conteúdo antes de importar.")
            return

        parsed = parse_ini_text_to_sections(raw)
        if not parsed:
            fb_var.set("⚠ Nenhuma seção válida encontrada. Verifique o formato.")
            return

        w = app._server_widgets.get(server_id, {})
        data = w.get(f"_ini_{file_key}_data", [])
        _ = w.get(f"_ini_{file_key}_secscroll")

        imported = 0
        last_sec_name = None
        for sec in parsed:
            sec_name = sec.get("section", "").strip()
            if not sec_name:
                continue
            # Se a seção já existe, mescla as entradas
            existing = next((s for s in data if s["section"] == sec_name), None)
            if existing:
                existing_keys = {e["key"] for e in existing["entries"]}
                for entry in sec.get("entries", []):
                    if entry["key"] not in existing_keys:
                        existing["entries"].append({"key": entry["key"], "value": entry["value"]})
                    else:
                        # Atualiza valor existente
                        for e in existing["entries"]:
                            if e["key"] == entry["key"]:
                                e["value"] = entry["value"]
                                break
            else:
                new_sec = {
                    "section":  sec_name,
                    "mod_id":   None,
                    "mod_name": "Personalizado",
                    "entries":  [{"key": e["key"], "value": e["value"]}
                                 for e in sec.get("entries", [])],
                }
                data.append(new_sec)
            imported += 1
            last_sec_name = sec_name

        app._ini_rebuild_section_list(server_id, file_key)
        if last_sec_name:
            app._ini_select_section(server_id, file_key, last_sec_name)
        dlg.destroy()

    btn_fr = ctk.CTkFrame(dlg, fg_color="transparent")
    btn_fr.grid(row=3, column=0, padx=16, pady=(2, 14), sticky="e")
    ctk.CTkButton(btn_fr, text="Cancelar", width=90, height=30,
                  fg_color="gray30", hover_color="gray40",
                  command=dlg.destroy).pack(side="left", padx=(0, 8))
    ctk.CTkButton(btn_fr, text="✅ Importar", width=110, height=30,
                  fg_color=_GREEN_DARK, hover_color=_GREEN_HOVER,
                  command=_import).pack(side="left")

