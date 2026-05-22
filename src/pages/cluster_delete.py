from __future__ import annotations
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from ..app import ARKServerManagerApp


def cluster_delete(app: "ARKServerManagerApp", cluster_id: str) -> None:
    from tkinter import messagebox
    prof = app.config_manager.get_cluster(cluster_id)
    if not prof:
        return
    linked_count = len(app.config_manager.servers_in_cluster(cluster_id))
    msg = f"Excluir o perfil \"{prof.name}\"?"
    if linked_count:
        msg += f"\n\n{linked_count} servidor(es) serão desvinculados do cluster."
    if not messagebox.askyesno("Confirmar Exclusão", msg, parent=app):
        return
    app.config_manager.remove_cluster(cluster_id)
    app._cluster_sync_stop(cluster_id)
    app._cluster_selected_id = ""
    app._clusters_refresh_list()
    for w in app._cluster_detail_fr.winfo_children():
        w.destroy()

