"""Exportação e importação de perfis Cross-ARK entre máquinas."""
from __future__ import annotations

import json
import uuid
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..app import ARKServerManagerApp

from ..server_config import ClusterProfile

FORMAT_ID = "arkland-cluster-profile"
FORMAT_VERSION = 1


def snapshot_profile_from_ui(app: "ARKServerManagerApp", cluster_id: str) -> ClusterProfile | None:
    """Lê o perfil salvo + alterações pendentes nos widgets do painel."""
    prof = app.config_manager.get_cluster(cluster_id)
    if not prof:
        return None
    snap = ClusterProfile.from_dict(prof.to_dict())
    if getattr(app, "_cluster_selected_id", "") != cluster_id:
        return snap

    import tkinter as tk

    dw = getattr(app, "_cluster_detail_widgets", {}) or {}
    if not dw:
        return snap

    snap.name = dw.get("name", tk.StringVar(value=snap.name)).get().strip() or snap.name
    snap.mode = dw.get("mode", tk.StringVar(value=snap.mode)).get()
    snap.cluster_id = dw.get("cluster_id", tk.StringVar(value=snap.cluster_id)).get().strip() or snap.cluster_id
    snap.cluster_dir = dw.get("cluster_dir", tk.StringVar(value=snap.cluster_dir)).get().strip()
    for key in (
        "prevent_download_survivors", "prevent_download_items", "prevent_download_dinos",
        "prevent_upload_survivors", "prevent_upload_items", "prevent_upload_dinos",
        "no_transfer_from_filtering", "cross_ark_allow_foreign_dino_downloads",
        "enable_tribute_downloads", "sync_enabled",
    ):
        var = dw.get(key)
        if var is not None:
            setattr(snap, key, bool(var.get()))
    snap.local_cluster_dir = dw.get("local_cluster_dir", tk.StringVar(value=snap.local_cluster_dir)).get().strip()
    try:
        snap.sync_interval = max(5, int(dw.get("sync_interval_var", tk.StringVar(value="30")).get()))
    except ValueError:
        pass
    return snap


def collect_server_hints(app: "ARKServerManagerApp", cluster_id: str) -> list[dict[str, Any]]:
    """Mapas vinculados — referência para vincular na outra máquina."""
    from .cluster_helpers import iter_linkable_servers

    hints: list[dict[str, Any]] = []
    for item in iter_linkable_servers(app, cluster_id):
        if not item.is_linked:
            continue
        import tkinter as tk

        dw = getattr(app, "_cluster_detail_widgets", {}) or {}
        alt_var = dw.get(f"alt_{item.widget_key}")
        alt_save = alt_var.get().strip() if alt_var is not None else item.alt_save_directory_name
        hints.append({
            "name": item.name,
            "map": item.map_label,
            "port": item.port,
            "alt_save_directory_name": alt_save,
            "kind": item.kind,
        })
    return hints


def build_export_document(app: "ARKServerManagerApp", cluster_id: str) -> dict[str, Any]:
    prof = snapshot_profile_from_ui(app, cluster_id)
    if not prof:
        raise ValueError("Perfil de cluster não encontrado.")
    payload = prof.to_dict()
    payload.pop("id", None)
    return {
        "format": FORMAT_ID,
        "version": FORMAT_VERSION,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "source_host": __import__("platform").node(),
        "profile": payload,
        "linked_servers": collect_server_hints(app, cluster_id),
        "notes": (
            "Importe este arquivo em outro PC com ARKLAND. O Cluster ID deve permanecer "
            "idêntico. Ajuste a pasta de viagem (UNC ou sync) conforme o acesso desta máquina."
        ),
    }


def export_cluster_profile(app: "ARKServerManagerApp", cluster_id: str, path: str) -> None:
    doc = build_export_document(app, cluster_id)
    Path(path).write_text(json.dumps(doc, indent=2, ensure_ascii=False), encoding="utf-8")


def parse_import_document(raw: str) -> tuple[ClusterProfile, list[dict[str, Any]], dict[str, Any]]:
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("Arquivo inválido: esperado objeto JSON.")

    if data.get("format") == FORMAT_ID:
        prof_data = data.get("profile") or {}
        hints = list(data.get("linked_servers") or [])
        meta = {k: v for k, v in data.items() if k not in ("profile", "linked_servers")}
    elif "cluster_id" in data and "name" in data:
        prof_data = data
        hints = []
        meta = {}
    else:
        raise ValueError("Arquivo não reconhecido como perfil de cluster ARKLAND.")

    prof = ClusterProfile.from_dict(prof_data)
    prof.id = str(uuid.uuid4())
    if not prof.cluster_id.strip():
        raise ValueError("O perfil importado não contém Cluster ID.")
    return prof, hints, meta


def merge_imported_profile(app: "ARKServerManagerApp", prof: ClusterProfile) -> ClusterProfile:
    """Evita nomes duplicados e registra o perfil."""
    existing_names = {c.name for c in app.config_manager.clusters}
    if prof.name in existing_names:
        prof.name = f"{prof.name} (importado)"
        n = 2
        while prof.name in existing_names:
            prof.name = f"{prof.name.rsplit(' (', 1)[0]} (importado {n})"
            n += 1
    app.config_manager.add_cluster(prof)
    return prof


def import_cluster_profile_from_file(app: "ARKServerManagerApp", path: str) -> tuple[ClusterProfile, list[dict[str, Any]], dict[str, Any]]:
    raw = Path(path).read_text(encoding="utf-8")
    prof, hints, meta = parse_import_document(raw)
    prof = merge_imported_profile(app, prof)
    return prof, hints, meta
