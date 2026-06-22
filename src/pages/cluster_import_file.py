from __future__ import annotations

from tkinter import filedialog, messagebox
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..app import ARKServerManagerApp


def cluster_import_file(app: "ARKServerManagerApp") -> None:
    from .cluster_profile_io import import_cluster_profile_from_file

    path = filedialog.askopenfilename(
        parent=app,
        title="Importar perfil de cluster",
        filetypes=[
            ("Perfil de cluster ARKLAND", "*.arkcluster"),
            ("JSON", "*.json"),
            ("Todos os arquivos", "*.*"),
        ],
    )
    if not path:
        return
    try:
        prof, hints, meta = import_cluster_profile_from_file(app, path)
    except Exception as exc:
        messagebox.showerror("Erro ao importar", str(exc), parent=app)
        return

    app._cluster_selected_id = prof.id
    app._clusters_refresh_list()
    app._cluster_build_detail(prof)

    lines = [
        f"Perfil «{prof.name}» importado.",
        f"Cluster ID: {prof.cluster_id}",
        f"Pasta de viagem: {prof.cluster_dir or '(não definida)'}",
        "",
        "Nesta máquina:",
        "1. Confira se a pasta UNC é acessível (ou ative sync).",
        "2. Marque os mapas locais equivalentes e salve.",
        "3. Reinicie os servidores.",
    ]
    if prof.mode == "network" and prof.sync_enabled:
        lines.insert(4, "Sync ativo: deixe o ARKLAND aberto em cada PC do cluster.")
    src = meta.get("source_host")
    if src:
        lines.extend(["", f"Exportado de: {src}"])
    if hints:
        lines.extend(["", "Mapas na máquina de origem (vincule os equivalentes aqui):"])
        for h in hints:
            lines.append(
                f"  • {h.get('name', '?')} — {h.get('map', '?')} :{h.get('port', '?')}  "
                f"saves: {h.get('alt_save_directory_name', '?')}"
            )

    messagebox.showinfo("Perfil importado", "\n".join(lines), parent=app)
    app._toast(f"Perfil importado: {prof.name}", kind="info")
