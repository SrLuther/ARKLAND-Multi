from __future__ import annotations
from typing import TYPE_CHECKING
import datetime
import json
from tkinter import filedialog
from tkinter import messagebox
if TYPE_CHECKING:
    from ..app import ARKServerManagerApp


def export_profile(app: "ARKServerManagerApp") -> None:
    import datetime
    path = filedialog.asksaveasfilename(
        parent=app,
        title="Exportar Perfil ARKLAND",
        defaultextension=".arkprofile",
        filetypes=[
            ("Perfil ARKLAND", "*.arkprofile"),
            ("JSON", "*.json"),
            ("Todos os arquivos", "*.*"),
        ],
        initialfile=f"arkland-perfil-{datetime.date.today()}.arkprofile",
    )
    if not path:
        return
    try:
        app.config_manager.export_profile(path)
        n = len(app.config_manager.servers)
        messagebox.showinfo(
            "Perfil exportado",
            f"{n} servidor(es) exportado(s) com sucesso:\n{path}",
            parent=app,
        )
    except Exception as exc:
        messagebox.showerror("Erro ao exportar", str(exc), parent=app)

