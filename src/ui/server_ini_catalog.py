"""Searchable ASE server INI settings catalog and editor dialog."""
from __future__ import annotations

import json
import re
from pathlib import Path
from tkinter import messagebox, ttk
import tkinter as tk
from typing import Callable


_CATALOG_PATH = Path(__file__).resolve().parents[1] / "data" / "ark_ase_server_ini_catalog.json"
_CATALOG_URL = "https://ark.wiki.gg/wiki/Server_configuration"


def load_server_ini_catalog(file_name: str | None = None) -> list[dict[str, str]]:
    """Load documented ASE INI settings bundled with the application."""
    try:
        document = json.loads(_CATALOG_PATH.read_text(encoding="utf-8"))
        entries = document.get("entries", [])
    except (OSError, ValueError, TypeError):
        return []
    result = [
        entry for entry in entries
        if isinstance(entry, dict)
        and entry.get("file") in {"GameUserSettings.ini", "Game.ini"}
        and entry.get("key") and entry.get("section")
    ]
    if file_name:
        result = [entry for entry in result if entry["file"] == file_name]
    return result


def validate_catalog_value(value: str, value_type: str) -> str | None:
    """Validate simple scalar types while leaving ARK-specific expressions alone."""
    if any(char in value for char in "\r\n"):
        return "O valor precisa ficar em uma única linha."
    normalized = (value_type or "").casefold()
    if "boolean" in normalized or normalized.strip() in {"bool", "boolean"}:
        if value.casefold() not in {"true", "false"}:
            return "Informe True ou False para uma opção booleana."
    elif re.search(r"\b(integer|int)\b", normalized):
        try:
            int(value)
        except ValueError:
            return "Informe um número inteiro."
    elif re.search(r"\b(float|decimal|number)\b", normalized):
        try:
            float(value)
        except ValueError:
            return "Informe um número válido."
    return None


def open_server_ini_catalog(
    parent: tk.Misc,
    file_name: str,
    on_add: Callable[[str, str, str, bool], None],
) -> None:
    """Open a searchable catalog; selected entries are added to the profile editor."""
    entries = load_server_ini_catalog(file_name)
    if not entries:
        messagebox.showerror("Catálogo indisponível", "Não foi possível carregar o catálogo de configurações.", parent=parent)
        return

    dialog = tk.Toplevel(parent)
    dialog.title(f"Configurações documentadas — {file_name}")
    dialog.geometry("1040x690")
    dialog.minsize(800, 520)
    dialog.transient(parent)
    dialog.grab_set()

    root = ttk.Frame(dialog, padding=12)
    root.pack(fill="both", expand=True)
    root.columnconfigure(0, weight=1)
    root.rowconfigure(2, weight=1)

    ttk.Label(
        root,
        text=f"Catálogo ASE: {len(entries)} opções documentadas em {file_name}",
        font=("Segoe UI", 11, "bold"),
    ).grid(row=0, column=0, sticky="w", pady=(0, 8))
    ttk.Label(root, text="Pesquise por nome, seção, tipo ou descrição:").grid(row=1, column=0, sticky="w")
    search = tk.StringVar()
    search_entry = ttk.Entry(root, textvariable=search)
    search_entry.grid(row=1, column=0, sticky="e", padx=(310, 0), pady=(0, 8))

    table_frame = ttk.Frame(root)
    table_frame.grid(row=2, column=0, sticky="nsew")
    table_frame.columnconfigure(0, weight=1)
    table_frame.rowconfigure(0, weight=1)
    columns = ("section", "key", "type", "default")
    tree = ttk.Treeview(table_frame, columns=columns, show="headings", selectmode="browse")
    for column, label, width in (
        ("section", "Seção", 230),
        ("key", "Configuração", 300),
        ("type", "Tipo", 300),
        ("default", "Padrão documentado", 150),
    ):
        tree.heading(column, text=label)
        tree.column(column, width=width, minwidth=100, stretch=column in {"key", "type"})
    yscroll = ttk.Scrollbar(table_frame, orient="vertical", command=tree.yview)
    xscroll = ttk.Scrollbar(table_frame, orient="horizontal", command=tree.xview)
    tree.configure(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)
    tree.grid(row=0, column=0, sticky="nsew")
    yscroll.grid(row=0, column=1, sticky="ns")
    xscroll.grid(row=1, column=0, sticky="ew")

    by_iid: dict[str, dict[str, str]] = {}
    detail = tk.StringVar(value="Selecione uma opção para ver a descrição e editar seu valor.")
    detail_label = ttk.Label(root, textvariable=detail, wraplength=980, justify="left")
    detail_label.grid(row=3, column=0, sticky="ew", pady=(8, 4))

    edit = ttk.Frame(root)
    edit.grid(row=4, column=0, sticky="ew", pady=(4, 8))
    edit.columnconfigure(1, weight=1)
    ttk.Label(edit, text="Chave (preencha qualquer índice entre < >):").grid(row=0, column=0, sticky="w", padx=(0, 8))
    key_value = tk.StringVar()
    key_entry = ttk.Entry(edit, textvariable=key_value)
    key_entry.grid(row=0, column=1, sticky="ew", padx=(0, 12))
    ttk.Label(edit, text="Valor:").grid(row=0, column=2, sticky="w", padx=(0, 8))
    setting_value = tk.StringVar()
    value_entry = ttk.Entry(edit, textvariable=setting_value)
    value_entry.grid(row=0, column=3, sticky="ew")
    edit.columnconfigure(3, weight=1)

    selected: list[dict[str, str] | None] = [None]

    def populate(*_args) -> None:
        selected[0] = None
        query = search.get().strip().casefold()
        tree.delete(*tree.get_children())
        by_iid.clear()
        for index, entry in enumerate(entries):
            searchable = " ".join(str(entry.get(field, "")) for field in ("section", "key", "type", "default", "description"))
            if query and query not in searchable.casefold():
                continue
            iid = str(index)
            by_iid[iid] = entry
            tree.insert("", "end", iid=iid, values=(entry["section"], entry["key"], entry.get("type", ""), entry.get("default", "")))

    def selection_changed(_event=None) -> None:
        chosen = tree.selection()
        if not chosen:
            selected[0] = None
            return
        entry = by_iid.get(chosen[0])
        selected[0] = entry
        if not entry:
            return
        key_value.set(entry["key"])
        documented_default = entry.get("default", "")
        if documented_default.strip().casefold() in {"n/a", "not applicable", "unknown"}:
            documented_default = ""
        setting_value.set(documented_default)
        description = entry.get("description") or "Sem descrição adicional no catálogo."
        detail.set(f"[{entry['section']}]  {entry.get('type', 'tipo não especificado')} — {description}\nFonte: {_CATALOG_URL}")

    def add_selected() -> None:
        entry = selected[0]
        key = key_value.get().strip()
        value = setting_value.get()
        if not entry:
            messagebox.showinfo("Selecione uma configuração", "Escolha uma linha do catálogo.", parent=dialog)
            return
        if not key or "<" in key or ">" in key or "=" in key:
            messagebox.showerror("Chave incompleta", "Informe uma chave concreta. Substitua os marcadores entre < > pelo índice ou atributo exigido.", parent=dialog)
            return
        if not value.strip():
            messagebox.showerror("Valor não informado", "Informe o valor da configuração antes de adicioná-la ao perfil.", parent=dialog)
            return
        error = validate_catalog_value(value, entry.get("type", ""))
        if error:
            messagebox.showerror("Valor inválido", error, parent=dialog)
            return
        on_add(entry["section"], key, value, bool(entry.get("repeatable")))
        dialog.destroy()

    search.trace_add("write", populate)
    tree.bind("<<TreeviewSelect>>", selection_changed)
    tree.bind("<Double-1>", lambda _event: add_selected())
    populate()
    buttons = ttk.Frame(root)
    buttons.grid(row=5, column=0, sticky="e")
    ttk.Button(buttons, text="Adicionar ao perfil", command=add_selected).pack(side="right", padx=(8, 0))
    ttk.Button(buttons, text="Fechar", command=dialog.destroy).pack(side="right")
    search_entry.focus_set()

