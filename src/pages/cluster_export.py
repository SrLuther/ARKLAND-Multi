from __future__ import annotations

from datetime import date
from tkinter import filedialog, messagebox
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..app import ARKServerManagerApp


def cluster_export(app: "ARKServerManagerApp", cluster_id: str) -> None:
    from .cluster_profile_io import export_cluster_profile, snapshot_profile_from_ui

    prof = snapshot_profile_from_ui(app, cluster_id)
    if not prof:
        app._toast("Perfil não encontrado.", kind="warning")
        return

    safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in prof.name)[:40]
    path = filedialog.asksaveasfilename(
        parent=app,
        title="Exportar perfil de cluster",
        defaultextension=".arkcluster",
        filetypes=[
            ("Perfil de cluster ARKLAND", "*.arkcluster"),
            ("JSON", "*.json"),
            ("Todos os arquivos", "*.*"),
        ],
        initialfile=f"cluster-{safe_name}-{date.today().isoformat()}.arkcluster",
    )
    if not path:
        return
    try:
        export_cluster_profile(app, cluster_id, path)
        messagebox.showinfo(
            "Perfil exportado",
            f"Perfil «{prof.name}» exportado.\n\n"
            f"Copie o arquivo para o outro PC e use «Importar perfil» no menu Clusters.\n\n"
            f"{path}",
            parent=app,
        )
    except Exception as exc:
        messagebox.showerror("Erro ao exportar", str(exc), parent=app)
