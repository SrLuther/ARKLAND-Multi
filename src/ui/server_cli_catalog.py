"""Searchable catalog of official ASE dedicated-server startup arguments."""
from __future__ import annotations

import json
import re
from pathlib import Path
from tkinter import messagebox, ttk
import tkinter as tk
from typing import Callable

_CATALOG_PATH = Path(__file__).resolve().parents[1] / "data" / "ark_ase_server_cli_catalog.json"
_CATALOG_URL = "https://ark.wiki.gg/wiki/Server_configuration"
_PLACEHOLDER_RE = re.compile(r"<[^<>]+>")


def load_server_cli_catalog() -> list[dict[str, str | bool]]:
    try:
        document = json.loads(_CATALOG_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return []
    return [item for item in document.get("entries", []) if isinstance(item, dict) and item.get("argument")]


def build_cli_argument(entry: dict, value: str = "") -> str:
    """Fill a documented argument template without allowing extra CLI tokens."""
    argument = str(entry.get("argument") or entry.get("key") or "").strip()
    if not argument:
        raise ValueError("Argumento ausente no catálogo.")
    if any(char in value for char in "\r\n"):
        raise ValueError("O valor do argumento não pode conter quebras de linha.")
    placeholders = _PLACEHOLDER_RE.findall(argument)
    if placeholders:
        if not value.strip():
            raise ValueError("Informe um valor para este argumento.")
        argument = _PLACEHOLDER_RE.sub(value.strip(), argument)
    elif value.strip():
        if "=" in argument:
            argument = f"{argument}{value.strip()}"
        else:
            raise ValueError("Este argumento não recebe um valor separado.")
    if "<" in argument or ">" in argument:
        raise ValueError("Preencha todos os marcadores entre < >.")
    return argument


def open_server_cli_catalog(parent: tk.Misc, on_append: Callable[[str], None]) -> None:
    entries = load_server_cli_catalog()
    if not entries:
        messagebox.showerror("Catálogo indisponível", "Não foi possível carregar o catálogo de argumentos ASE.", parent=parent)
        return

    dialog = tk.Toplevel(parent)
    dialog.title("Argumentos oficiais de inicialização — ARK: Survival Evolved")
    dialog.geometry("1050x700")
    dialog.minsize(820, 540)
    dialog.transient(parent)
    dialog.grab_set()

    root = ttk.Frame(dialog, padding=12)
    root.pack(fill="both", expand=True)
    root.columnconfigure(0, weight=1)
    root.rowconfigure(2, weight=1)
    ttk.Label(root, text=f"Catálogo ASE: {len(entries)} argumentos documentados", font=("Segoe UI", 11, "bold")).grid(row=0, column=0, sticky="w")
    search = tk.StringVar()
    ttk.Label(root, text="Pesquise por argumento ou descrição:").grid(row=1, column=0, sticky="w", pady=(6, 0))
    search_entry = ttk.Entry(root, textvariable=search)
    search_entry.grid(row=1, column=0, sticky="e", pady=(6, 8))

    frame = ttk.Frame(root)
    frame.grid(row=2, column=0, sticky="nsew")
    frame.columnconfigure(0, weight=1)
    frame.rowconfigure(0, weight=1)
    columns = ("syntax", "argument", "since", "default")
    tree = ttk.Treeview(frame, columns=columns, show="headings", selectmode="browse")
    for col, title, width in (("syntax", "Formato", 100), ("argument", "Argumento", 370), ("since", "Versão ASE", 100), ("default", "Valor padrão", 150)):
        tree.heading(col, text=title)
        tree.column(col, width=width, minwidth=90, stretch=col == "argument")
    ys = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
    xs = ttk.Scrollbar(frame, orient="horizontal", command=tree.xview)
    tree.configure(yscrollcommand=ys.set, xscrollcommand=xs.set)
    tree.grid(row=0, column=0, sticky="nsew")
    ys.grid(row=0, column=1, sticky="ns")
    xs.grid(row=1, column=0, sticky="ew")

    selected: list[dict | None] = [None]
    displayed: dict[str, dict] = {}
    details = tk.StringVar(value="Selecione um argumento para ver os detalhes.")
    ttk.Label(root, textvariable=details, wraplength=1000, justify="left").grid(row=3, column=0, sticky="ew", pady=(8, 6))
    val_row = ttk.Frame(root)
    val_row.grid(row=4, column=0, sticky="ew", pady=(0, 8))
    val_row.columnconfigure(1, weight=1)
    ttk.Label(val_row, text="Valor do argumento:").grid(row=0, column=0, sticky="w", padx=(0, 8))
    value = tk.StringVar()
    ttk.Entry(val_row, textvariable=value).grid(row=0, column=1, sticky="ew")

    def populate(*_args) -> None:
        tree.delete(*tree.get_children())
        displayed.clear()
        query = search.get().strip().casefold()
        for index, item in enumerate(entries):
            text = f"{item.get('argument','')} {item.get('description','')} {item.get('since','')}".casefold()
            if query and query not in text:
                continue
            iid = str(index)
            displayed[iid] = item
            tree.insert("", "end", iid=iid, values=("? no mapa" if item.get("syntax") == "question" else "- separado", item.get("argument"), item.get("since", ""), item.get("default", "")))

    def select(_event=None) -> None:
        selected[0] = displayed.get(tree.focus())
        item = selected[0]
        if not item:
            return
        value.set("")
        details.set(f"{item.get('description','')}\nFonte: {_CATALOG_URL}")

    def append() -> None:
        item = selected[0]
        if not item:
            messagebox.showinfo("Selecione um argumento", "Escolha uma linha do catálogo.", parent=dialog)
            return
        try:
            argument = build_cli_argument(item, value.get())
        except ValueError as exc:
            messagebox.showerror("Argumento inválido", str(exc), parent=dialog)
            return
        on_append(argument)
        dialog.destroy()

    search.trace_add("write", populate)
    tree.bind("<<TreeviewSelect>>", select)
    tree.bind("<Double-1>", lambda _event: append())
    populate()
    buttons = ttk.Frame(root)
    buttons.grid(row=5, column=0, sticky="e")
    ttk.Button(buttons, text="Adicionar aos argumentos extras", command=append).pack(side="right", padx=(8, 0))
    ttk.Button(buttons, text="Fechar", command=dialog.destroy).pack(side="right")
    search_entry.focus_set()
