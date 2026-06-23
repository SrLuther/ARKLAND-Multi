from __future__ import annotations

from datetime import date
from tkinter import filedialog, messagebox
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..app_tek import ARKServerManagerApp


def broadcast_export(app: "ARKServerManagerApp") -> None:
    from .broadcast_profile_io import export_broadcast_library, get_library

    if not get_library(app):
        messagebox.showwarning(
            "Biblioteca vazia",
            "Cadastre mensagens antes de exportar.",
            parent=app,
        )
        return

    path = filedialog.asksaveasfilename(
        parent=app,
        title="Exportar biblioteca de broadcasts",
        defaultextension=".arkbroadcast",
        filetypes=[
            ("Biblioteca de broadcasts ARKLAND", "*.arkbroadcast"),
            ("JSON", "*.json"),
            ("Todos os arquivos", "*.*"),
        ],
        initialfile=f"broadcasts-{date.today().isoformat()}.arkbroadcast",
    )
    if not path:
        return
    try:
        export_broadcast_library(app, path)
        messagebox.showinfo(
            "Biblioteca exportada",
            f"Arquivo salvo.\n\nCopie para o outro PC e use «Importar» na aba Broadcasts.\n\n{path}",
            parent=app,
        )
    except Exception as exc:
        messagebox.showerror("Erro ao exportar", str(exc), parent=app)


def broadcast_import(app: "ARKServerManagerApp") -> None:
    from .broadcast_profile_io import import_broadcast_library_from_file

    path = filedialog.askopenfilename(
        parent=app,
        title="Importar biblioteca de broadcasts",
        filetypes=[
            ("Biblioteca de broadcasts ARKLAND", "*.arkbroadcast"),
            ("JSON", "*.json"),
            ("Todos os arquivos", "*.*"),
        ],
    )
    if not path:
        return

    replace = messagebox.askyesnocancel(
        "Modo de importação",
        "Sim = substituir toda a biblioteca local\n"
        "Não = mesclar (atualiza por ID, adiciona novos)\n"
        "Cancelar = abortar",
        parent=app,
    )
    if replace is None:
        return

    try:
        added, updated, meta = import_broadcast_library_from_file(
            app, path, replace=bool(replace),
        )
    except Exception as exc:
        messagebox.showerror("Erro ao importar", str(exc), parent=app)
        return

    app._broadcast_library_refresh()
    lines = []
    if replace:
        lines.append(f"Biblioteca substituída ({added} mensagem(ns)).")
    else:
        lines.append(f"Importação concluída: {added} nova(s), {updated} atualizada(s).")
    src = meta.get("source_host")
    if src:
        lines.append(f"Exportado de: {src}")
    messagebox.showinfo("Biblioteca importada", "\n".join(lines), parent=app)
    app._toast("Biblioteca de broadcasts atualizada.", kind="info")
