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


def asm_servers(app: "ARKServerManagerApp") -> list["AsmServerConfig"]:
    mgr = getattr(app, "asm_config_manager", None)
    if mgr is None:
        return []
    return list(mgr.servers)


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


def iter_linkable_servers(app: "ARKServerManagerApp", cluster_id: str) -> list[LinkableServer]:
    items: list[LinkableServer] = []
    linked_asm = {s.id for s in asm_servers_in_cluster(app, cluster_id)}
    linked_legacy = {s.id for s in legacy_servers_in_cluster(app, cluster_id)}

    for srv in asm_servers(app):
        map_label = (srv.server_map or "").replace("_P", "").replace("_", " ")
        items.append(
            LinkableServer(
                kind="asm",
                server_id=srv.id,
                name=srv.name or "Servidor",
                map_label=map_label or "?",
                port=int(getattr(srv, "server_port", 0) or 0),
                widget_key=f"asm_{srv.id}",
                is_linked=srv.id in linked_asm,
            )
        )

    for srv in app.config_manager.servers:
        map_label = (srv.map or "").replace("_P", "").replace("_", " ")
        items.append(
            LinkableServer(
                kind="legacy",
                server_id=srv.id,
                name=srv.name or "Servidor",
                map_label=map_label or "?",
                port=int(getattr(srv, "server_port", 0) or 0),
                widget_key=f"srv_{srv.id}",
                is_linked=srv.id in linked_legacy,
            )
        )
    return items


def apply_profile_to_asm_server(srv: "AsmServerConfig", prof: "ClusterProfile") -> None:
    srv.cross_ark_cluster_id = prof.cluster_id
    srv.cluster_dir_override = prof.cluster_dir
    srv.no_transfer_from_filtering = prof.no_transfer_from_filtering
    srv.prevent_download_survivors = prof.prevent_download_survivors
    srv.prevent_download_items = prof.prevent_download_items
    srv.prevent_download_dinos = prof.prevent_download_dinos


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
