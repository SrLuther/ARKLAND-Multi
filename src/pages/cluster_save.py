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
    prof.prevent_upload_survivors   = bool(dw.get("prevent_upload_survivors", tk.BooleanVar()).get())
    prof.prevent_upload_items       = bool(dw.get("prevent_upload_items",     tk.BooleanVar()).get())
    prof.prevent_upload_dinos       = bool(dw.get("prevent_upload_dinos",     tk.BooleanVar()).get())
    prof.no_transfer_from_filtering = bool(dw.get("no_transfer_from_filtering", tk.BooleanVar()).get())
    prof.cross_ark_allow_foreign_dino_downloads = bool(
        dw.get("cross_ark_allow_foreign_dino_downloads", tk.BooleanVar()).get()
    )
    prof.enable_tribute_downloads = bool(dw.get("enable_tribute_downloads", tk.BooleanVar(value=True)).get())
    prof.sync_enabled      = bool(dw.get("sync_enabled", tk.BooleanVar()).get())
    prof.local_cluster_dir = dw.get("local_cluster_dir", tk.StringVar()).get().strip()
    try:
        prof.sync_interval = max(5, int(dw.get("sync_interval_var", tk.StringVar(value="30")).get()))
    except ValueError:
        pass

    app.config_manager.update_cluster(prof)

    from ..cluster_paths import validate_network_cluster_dir
    net_warn = validate_network_cluster_dir(prof)
    if net_warn:
        app._toast(net_warn, kind="warning")

    linked_install_dirs: list[str] = []

    from .cluster_helpers import (
        apply_profile_to_asm_server,
        apply_profile_to_legacy_server,
        iter_linkable_servers,
    )
    from ..cluster_paths import ensure_cluster_directories

    linkable = iter_linkable_servers(app, cluster_id)
    linked_asm = 0
    asm_mgr = getattr(app, "asm_config_manager", None)
    if asm_mgr is not None:
        for item in linkable:
            if item.kind != "asm":
                continue
            var = dw.get(item.widget_key)
            if var is None:
                continue
            srv = asm_mgr.get_server(item.server_id)
            if srv is None:
                continue
            should_link = bool(var.get())
            alt_var = dw.get(f"alt_{item.widget_key}")
            if should_link:
                if alt_var is not None:
                    alt = alt_var.get().strip()
                    if alt:
                        srv.alt_save_directory_name = alt
                srv.cluster_profile_id = cluster_id
                apply_profile_to_asm_server(srv, prof)
                asm_mgr.update_server(srv)
                linked_asm += 1
                if srv.install_dir:
                    linked_install_dirs.append(srv.install_dir)
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
    for item in linkable:
        if item.kind != "legacy":
            continue
        var = dw.get(item.widget_key)
        if var is None:
            continue
        srv = app.config_manager.get_server(item.server_id)
        if srv is None:
            continue
        should_link = bool(var.get())
        alt_var = dw.get(f"alt_{item.widget_key}")
        if should_link:
            if alt_var is not None:
                alt = alt_var.get().strip()
                if alt:
                    srv.alt_save_directory_name = alt
            srv.cluster_profile_id = cluster_id
            apply_profile_to_legacy_server(srv, prof)
            app.config_manager.update_server(srv)
            app.server_manager.update_server_config(srv)
            linked_legacy += 1
            if srv.install_dir:
                linked_install_dirs.append(srv.install_dir)
        elif srv.cluster_profile_id == cluster_id:
            srv.cluster_profile_id = ""
            app.config_manager.update_server(srv)
            app.server_manager.update_server_config(srv)

    created_dirs, failed_dirs = ensure_cluster_directories(prof, linked_install_dirs)
    if created_dirs:
        preview = "\n".join(created_dirs[:4])
        extra = f"\n… +{len(created_dirs) - 4}" if len(created_dirs) > 4 else ""
        app._toast(f"Pastas do cluster criadas:\n{preview}{extra}", kind="info")
    if failed_dirs:
        preview = "\n".join(failed_dirs[:3])
        app._toast(
            f"Não foi possível criar/acessar:\n{preview}\n"
            "UNC: crie o compartilhamento no NAS/Windows e teste no Explorer.",
            kind="warning",
        )

    app._cluster_sync_restart(prof.id)

    app._clusters_refresh_list()
    app._cluster_build_detail(prof)
    total = linked_asm + linked_legacy
    app._toast(
        f'Perfil "{prof.name}" salvo — {total} mapa(s) receberão a mesma configuração. '
        "Reinicie os servidores para aplicar.",
        kind="info",
    )
