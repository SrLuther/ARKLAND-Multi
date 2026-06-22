from __future__ import annotations

import tkinter as tk
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..app import ARKServerManagerApp


def cluster_save(app: "ARKServerManagerApp", cluster_id: str) -> None:
    prof = app.config_manager.get_cluster(cluster_id)
    if not prof:
        return
    dw = app._cluster_detail_widgets

    prof.name       = dw.get("name",       tk.StringVar()).get().strip() or prof.name
    prof.mode       = dw.get("mode",       tk.StringVar()).get()
    prof.cluster_id = dw.get("cluster_id", tk.StringVar()).get().strip() or prof.cluster_id
    prof.cluster_dir = dw.get("cluster_dir", tk.StringVar()).get().strip()
    prof.prevent_download_survivors = bool(dw.get("prevent_download_survivors", tk.BooleanVar()).get())
    prof.prevent_download_items     = bool(dw.get("prevent_download_items",     tk.BooleanVar()).get())
    prof.prevent_download_dinos     = bool(dw.get("prevent_download_dinos",     tk.BooleanVar()).get())
    prof.no_transfer_from_filtering = bool(dw.get("no_transfer_from_filtering", tk.BooleanVar()).get())
    prof.sync_enabled      = bool(dw.get("sync_enabled", tk.BooleanVar()).get())
    prof.local_cluster_dir = dw.get("local_cluster_dir", tk.StringVar()).get().strip()
    try:
        prof.sync_interval = max(5, int(dw.get("sync_interval_var", tk.StringVar(value="30")).get()))
    except ValueError:
        pass

    app.config_manager.update_cluster(prof)
    app._cluster_sync_restart(prof.id)

    if prof.cluster_dir and prof.mode != "network":
        import os as _os
        _cl_dir_normalized = prof.cluster_dir.replace("/", "\\")
        if not _os.path.isdir(_cl_dir_normalized):
            try:
                _os.makedirs(_cl_dir_normalized, exist_ok=True)
                app._toast(f"📁 Pasta do cluster criada:\n{_cl_dir_normalized}", kind="info")
            except Exception as _exc:
                app._toast(f"⚠️ Não foi possível criar a pasta do cluster:\n{_exc}", kind="warning")

    from .cluster_helpers import apply_profile_to_asm_server

    linked_asm = 0
    asm_mgr = getattr(app, "asm_config_manager", None)
    if asm_mgr is not None:
        for srv in asm_mgr.servers:
            var = dw.get(f"asm_{srv.id}")
            if var is None:
                continue
            should_link = bool(var.get())
            if should_link:
                srv.cluster_profile_id = cluster_id
                apply_profile_to_asm_server(srv, prof)
                asm_mgr.update_server(srv)
                linked_asm += 1
                try:
                    from ..asm_engine.asm_ini_manager import write_ini
                    if srv.install_dir:
                        write_ini(srv)
                except Exception:
                    pass
            elif getattr(srv, "cluster_profile_id", "") == cluster_id:
                srv.cluster_profile_id = ""
                asm_mgr.update_server(srv)

    linked_legacy = 0
    for srv in app.config_manager.servers:
        var = dw.get(f"srv_{srv.id}")
        if var is None:
            continue
        should_link = bool(var.get())
        if should_link:
            srv.cluster_profile_id = cluster_id
            srv.cluster.enabled = True
            srv.cluster.cluster_id = prof.cluster_id
            srv.cluster.cluster_dir_override = prof.cluster_dir
            srv.cluster.no_transfer_from_filtering = prof.no_transfer_from_filtering
            srv.cluster.prevent_download_survivors = prof.prevent_download_survivors
            srv.cluster.prevent_download_items = prof.prevent_download_items
            srv.cluster.prevent_download_dinos = prof.prevent_download_dinos
            app.config_manager.update_server(srv)
            app.server_manager.update_server_config(srv)
            linked_legacy += 1
        elif srv.cluster_profile_id == cluster_id:
            srv.cluster_profile_id = ""
            app.config_manager.update_server(srv)
            app.server_manager.update_server_config(srv)

    app._clusters_refresh_list()
    app._cluster_build_detail(prof)
    total = linked_asm + linked_legacy
    app._toast(
        f'Perfil "{prof.name}" salvo — {total} servidor(es) vinculado(s). '
        "Reinicie os mapas para aplicar o cluster.",
        kind="info",
    )
