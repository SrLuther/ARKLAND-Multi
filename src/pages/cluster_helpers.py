"""Helpers do painel Clusters Cross-ARK (servidores TEK + legado)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable, Optional

if TYPE_CHECKING:
    from ..app import ARKServerManagerApp
    from ..asm_engine.asm_server_config import AsmServerConfig
    from ..server_config import ClusterProfile, ServerConfig


@dataclass
class LinkableServer:
    kind: str          # "asm" | "legacy"
    server_id: str
    name: str
    map_label: str
    port: int
    widget_key: str
    is_linked: bool
    alt_save_directory_name: str = ""
    other_cluster_name: str = ""  # perfil concorrente, se houver


def get_linkable_server_cfg(app: "ARKServerManagerApp", item: LinkableServer):
    if item.kind == "asm":
        mgr = getattr(app, "asm_config_manager", None)
        return mgr.get_server(item.server_id) if mgr else None
    return app.config_manager.get_server(item.server_id)


def asm_servers(app: "ARKServerManagerApp") -> list["AsmServerConfig"]:
    mgr = getattr(app, "asm_config_manager", None)
    if mgr is None:
        return []
    return list(mgr.servers)


def iter_linkable_servers(app: "ARKServerManagerApp", cluster_id: str) -> list[LinkableServer]:
    items: list[LinkableServer] = []
    linked_asm = {s.id for s in asm_servers_in_cluster(app, cluster_id)}
    linked_legacy = {s.id for s in legacy_servers_in_cluster(app, cluster_id)}
    clusters_by_id = {c.id: c.name for c in app.config_manager.clusters}

    for srv in asm_servers(app):
        map_label = (srv.server_map or "").replace("_P", "").replace("_", " ")
        pid = (getattr(srv, "cluster_profile_id", "") or "").strip()
        other = ""
        if pid and pid != cluster_id:
            other = clusters_by_id.get(pid, "outro perfil")
        items.append(
            LinkableServer(
                kind="asm",
                server_id=srv.id,
                name=srv.name or "Servidor",
                map_label=map_label or "?",
                port=int(getattr(srv, "server_port", 0) or 0),
                widget_key=f"asm_{srv.id}",
                is_linked=srv.id in linked_asm,
                alt_save_directory_name=(getattr(srv, "alt_save_directory_name", "") or "savegame"),
                other_cluster_name=other,
            )
        )

    for srv in app.config_manager.servers:
        map_label = (srv.map or "").replace("_P", "").replace("_", " ")
        pid = (srv.cluster_profile_id or "").strip()
        other = ""
        if pid and pid != cluster_id:
            other = clusters_by_id.get(pid, "outro perfil")
        items.append(
            LinkableServer(
                kind="legacy",
                server_id=srv.id,
                name=srv.name or "Servidor",
                map_label=map_label or "?",
                port=int(getattr(srv, "server_port", 0) or 0),
                widget_key=f"srv_{srv.id}",
                is_linked=srv.id in linked_legacy,
                alt_save_directory_name=(srv.alt_save_directory_name or "savegame"),
                other_cluster_name=other,
            )
        )
    return items


def asm_servers_in_cluster(app: "ARKServerManagerApp", cluster_id: str) -> list["AsmServerConfig"]:
    return [
        s for s in asm_servers(app)
        if getattr(s, "cluster_profile_id", "") == cluster_id
    ]


def legacy_servers_in_cluster(app: "ARKServerManagerApp", cluster_id: str) -> list["ServerConfig"]:
    return [s for s in app.config_manager.servers if s.cluster_profile_id == cluster_id]


def count_linked_servers(app: "ARKServerManagerApp", cluster_id: str) -> int:
    return len(legacy_servers_in_cluster(app, cluster_id)) + len(
        asm_servers_in_cluster(app, cluster_id)
    )


def build_cluster_sync_cycles(
    app: "ARKServerManagerApp",
    prof: "ClusterProfile",
    cluster_id: str,
) -> list[list[str]]:
    """Monta ciclos local ↔ rede para servidores vinculados nesta instância do Manager."""
    from ..cluster_paths import normalize_cluster_path, resolve_cluster_dir_override

    net = normalize_cluster_path(prof.cluster_dir)
    if not net:
        return []

    if prof.mode == "network" and prof.sync_enabled:
        local_dirs: list[str] = []
        for srv in asm_servers_in_cluster(app, cluster_id):
            local = resolve_cluster_dir_override(prof, install_dir=srv.install_dir or "")
            if local and local not in local_dirs:
                local_dirs.append(local)
        for srv in legacy_servers_in_cluster(app, cluster_id):
            local = resolve_cluster_dir_override(prof, install_dir=srv.install_dir or "")
            if local and local not in local_dirs:
                local_dirs.append(local)
        if not local_dirs and prof.local_cluster_dir.strip():
            local_dirs.append(normalize_cluster_path(prof.local_cluster_dir))
        return [[local, net] for local in local_dirs]

    local = normalize_cluster_path(prof.local_cluster_dir)
    if local:
        return [[local, net]]
    return []


def apply_profile_to_asm_server(srv: "AsmServerConfig", prof: "ClusterProfile") -> None:
    from ..cluster_paths import resolve_cluster_dir_override

    srv.cross_ark_cluster_id = prof.cluster_id
    srv.cluster_dir_override = resolve_cluster_dir_override(
        prof, install_dir=srv.install_dir or ""
    )
    srv.no_transfer_from_filtering = prof.no_transfer_from_filtering
    srv.prevent_download_survivors = prof.prevent_download_survivors
    srv.prevent_download_items = prof.prevent_download_items
    srv.prevent_download_dinos = prof.prevent_download_dinos
    srv.prevent_upload_survivors = prof.prevent_upload_survivors
    srv.prevent_upload_items = prof.prevent_upload_items
    srv.prevent_upload_dinos = prof.prevent_upload_dinos
    srv.cross_ark_allow_foreign_dino_downloads = prof.cross_ark_allow_foreign_dino_downloads
    srv.enable_tribute_downloads = prof.enable_tribute_downloads


def apply_profile_to_legacy_server(srv: "ServerConfig", prof: "ClusterProfile") -> None:
    from ..cluster_paths import resolve_cluster_dir_override

    srv.cluster.enabled = True
    srv.cluster.cluster_id = prof.cluster_id
    srv.cluster.cluster_dir_override = resolve_cluster_dir_override(
        prof, install_dir=srv.install_dir or ""
    )
    srv.cluster.no_transfer_from_filtering = prof.no_transfer_from_filtering
    srv.cluster.prevent_download_survivors = prof.prevent_download_survivors
    srv.cluster.prevent_download_items = prof.prevent_download_items
    srv.cluster.prevent_download_dinos = prof.prevent_download_dinos
    adv = srv.advanced_settings
    adv.prevent_upload_survivors = prof.prevent_upload_survivors
    adv.prevent_upload_items = prof.prevent_upload_items
    adv.prevent_upload_dinos = prof.prevent_upload_dinos
    adv.no_transfer_from_filtering = prof.no_transfer_from_filtering
    adv.prevent_download_survivors = prof.prevent_download_survivors
    adv.prevent_download_items = prof.prevent_download_items
    adv.prevent_download_dinos = prof.prevent_download_dinos


def apply_cluster_profile_to_asm_cfg(
    srv: "AsmServerConfig",
    get_cluster: Callable[[str], Optional["ClusterProfile"]],
) -> None:
    pid = (getattr(srv, "cluster_profile_id", "") or "").strip()
    if not pid:
        return
    prof = get_cluster(pid)
    if prof and prof.cluster_id:
        apply_profile_to_asm_server(srv, prof)


def manual_asm_without_profile(app: "ARKServerManagerApp") -> list["AsmServerConfig"]:
    return [
        s for s in asm_servers(app)
        if (s.cross_ark_cluster_id or "").strip()
        and not (getattr(s, "cluster_profile_id", "") or "").strip()
    ]
