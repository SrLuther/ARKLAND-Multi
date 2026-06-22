"""Teste de visibilidade Cross-ARK — simula listagem do obelisco/terminal antes de iniciar."""
from __future__ import annotations

import re
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from .asm_engine.asm_server_config import AsmServerConfig
    from .server_config import ClusterProfile, ServerConfig

from .cluster_paths import (
    is_network_share_path,
    normalize_cluster_path,
    resolve_cluster_dir_override,
)

_TRANSFER_SUFFIXES = {".arkprofile", ".arktribe", ".arkcharactersave"}
_STEAM_ID_FILE = re.compile(r"^\d{17}$")


@dataclass
class ClusterMemberInfo:
    kind: str
    server_id: str
    name: str
    map_label: str
    port: int
    cluster_dir: str
    shared_dir: str
    launch_cluster_id: str
    launch_ok: bool
    launch_notes: list[str] = field(default_factory=list)
    path_ok: bool = False
    path_note: str = ""
    running: bool = False


@dataclass
class TransferFileInfo:
    relative_path: str
    kind: str
    size: int
    modified: float
    hint: str


@dataclass
class VisibilityEdge:
    viewer: str
    target: str
    status: str  # ok | warn | error
    detail: str


@dataclass
class ClusterTravelTestResult:
    profile_name: str
    cluster_id: str
    shared_dir: str
    members: list[ClusterMemberInfo] = field(default_factory=list)
    transfers: list[TransferFileInfo] = field(default_factory=list)
    visibility: list[VisibilityEdge] = field(default_factory=list)
    checks: list[tuple[str, str, str]] = field(default_factory=list)  # status, title, detail
    simulated_listings: dict[str, list[str]] = field(default_factory=dict)


def _shared_cluster_dir(prof: "ClusterProfile") -> str:
    if prof.mode == "network" and getattr(prof, "sync_enabled", False):
        return normalize_cluster_path(prof.cluster_dir)
    if prof.mode == "network":
        return normalize_cluster_path(prof.cluster_dir)
    return normalize_cluster_path(prof.cluster_dir)


def probe_path_read_write(path: str) -> tuple[bool, str]:
    p = Path(normalize_cluster_path(path))
    if not path.strip():
        return False, "Caminho vazio"
    try:
        p.mkdir(parents=True, exist_ok=True)
        token = uuid.uuid4().hex[:8]
        test_file = p / f".arkland_cluster_probe_{token}.tmp"
        payload = f"arkland-probe-{token}"
        test_file.write_text(payload, encoding="utf-8")
        if test_file.read_text(encoding="utf-8") != payload:
            return False, "Leitura após escrita falhou"
        test_file.unlink(missing_ok=True)
        return True, "Leitura e escrita OK"
    except OSError as exc:
        return False, str(exc)


def _classify_transfer_file(path: Path) -> str:
    name = path.name.lower()
    if name.endswith(".arkprofile") or _STEAM_ID_FILE.match(path.stem):
        return "Sobrevivente"
    if name.endswith(".arktribe"):
        return "Tribo"
    if name.endswith(".arkcharactersave"):
        return "Personagem"
    return "Dado de viagem"


def _transfer_roots(shared_dir: str, cluster_id: str) -> list[Path]:
    base = Path(normalize_cluster_path(shared_dir))
    roots: list[Path] = []
    if not base.exists():
        return roots
    cid_path = base / cluster_id
    if cid_path.is_dir():
        roots.append(cid_path)
    clusters_sub = base / "clusters" / cluster_id
    if clusters_sub.is_dir():
        roots.append(clusters_sub)
    # Alguns hosts usam apenas a raiz do override
    if not roots:
        roots.append(base)
    return roots


def scan_transfer_files(shared_dir: str, cluster_id: str) -> list[TransferFileInfo]:
    results: list[TransferFileInfo] = []
    seen: set[str] = set()
    for root in _transfer_roots(shared_dir, cluster_id):
        if not root.is_dir():
            continue
        for f in root.rglob("*"):
            if not f.is_file():
                continue
            rel = str(f.relative_to(root)).replace("\\", "/")
            low = f.name.lower()
            if not (
                low.endswith(tuple(_TRANSFER_SUFFIXES))
                or _STEAM_ID_FILE.match(f.stem)
            ):
                continue
            key = str(f.resolve()) if f.exists() else rel
            if key in seen:
                continue
            seen.add(key)
            try:
                st = f.stat()
                size, mtime = st.st_size, st.st_mtime
            except OSError:
                size, mtime = 0, 0.0
            parent = f.parent.name
            results.append(
                TransferFileInfo(
                    relative_path=rel,
                    kind=_classify_transfer_file(f),
                    size=size,
                    modified=mtime,
                    hint=parent if parent.isdigit() or len(parent) > 8 else "compartilhado",
                )
            )
    results.sort(key=lambda x: x.modified, reverse=True)
    return results


def _asm_launch_cluster_info(srv: "AsmServerConfig") -> tuple[str, str, list[str]]:
    notes: list[str] = []
    try:
        from .asm_engine.asm_ini_manager import build_launch_args

        args = build_launch_args(srv)
    except Exception as exc:
        return "", "", [f"Não foi possível montar linha de comando: {exc}"]

    cid = (srv.cross_ark_cluster_id or "").strip()
    cdir = normalize_cluster_path(srv.cluster_dir_override or "")
    joined = " ".join(args)

    if f"-clusterid={cid}" not in joined and cid:
        notes.append("Flag -clusterid ausente na linha de comando gerada")
    if cdir and "ClusterDirOverride" not in joined:
        notes.append("Flag -ClusterDirOverride ausente na linha de comando gerada")
    if not cid:
        notes.append("Cluster ID vazio no servidor")
    if not cdir:
        notes.append("Pasta do cluster vazia no servidor")

    return cid, cdir, notes


def _legacy_launch_cluster_info(
    srv: "ServerConfig", prof: Optional["ClusterProfile"]
) -> tuple[str, str, list[str]]:
    notes: list[str] = []
    if prof:
        cid = prof.cluster_id
        cdir = resolve_cluster_dir_override(prof, install_dir=srv.install_dir or "")
    else:
        cid = srv.cluster.cluster_id
        cdir = normalize_cluster_path(srv.cluster.cluster_dir_override)

    if not srv.cluster.enabled and not prof:
        notes.append("Cluster desabilitado neste servidor")
    if not cid:
        notes.append("Cluster ID vazio")
    if not cdir:
        notes.append("Pasta do cluster vazia")

    try:
        from .server_config import ServerConfig as _SC

        args = _SC.build_launch_args(srv, cluster_profile=prof)
        if cid and f"-clusterid={cid}" not in args:
            notes.append("Flag -clusterid ausente na linha de comando")
        if cdir and "ClusterDirOverride" not in args:
            notes.append("Flag -ClusterDirOverride ausente na linha de comando")
    except Exception as exc:
        notes.append(f"Linha de comando: {exc}")

    return cid, cdir, notes


def _server_running(install_dir: str) -> bool:
    if not install_dir:
        return False
    try:
        import psutil

        needle = install_dir.lower().replace("/", "\\")
        for proc in psutil.process_iter(["name", "exe", "cmdline"]):
            try:
                name = (proc.info.get("name") or "").lower()
                if "shootergameserver" not in name:
                    continue
                exe = (proc.info.get("exe") or "").lower()
                cmd = " ".join(proc.info.get("cmdline") or []).lower()
                if needle in exe or needle in cmd:
                    return True
            except (psutil.Error, OSError):
                continue
    except ImportError:
        pass
    return False


def build_member_info(
    *,
    kind: str,
    server_id: str,
    name: str,
    map_label: str,
    port: int,
    install_dir: str,
    prof: "ClusterProfile",
    launch_cid: str,
    launch_cdir: str,
    launch_notes: list[str],
) -> ClusterMemberInfo:
    shared = _shared_cluster_dir(prof)
    path_ok, path_note = probe_path_read_write(launch_cdir)
    if prof.mode == "network" and prof.sync_enabled and shared != launch_cdir:
        shared_ok, shared_note = probe_path_read_write(shared)
        if not shared_ok:
            path_ok = False
            path_note = f"Local: {path_note}; Rede: {shared_note}"
        elif path_ok:
            path_note = f"Local: {path_note}; Rede: {shared_note}"

    expected_cid = prof.cluster_id.strip()
    if launch_cid != expected_cid:
        launch_notes.append(
            f"Cluster ID divergente (esperado '{expected_cid}', servidor '{launch_cid}')"
        )

    return ClusterMemberInfo(
        kind=kind,
        server_id=server_id,
        name=name,
        map_label=map_label,
        port=port,
        cluster_dir=launch_cdir,
        shared_dir=shared,
        launch_cluster_id=launch_cid,
        launch_ok=not launch_notes,
        launch_notes=launch_notes,
        path_ok=path_ok,
        path_note=path_note,
        running=_server_running(install_dir),
    )


def compute_visibility(members: list[ClusterMemberInfo]) -> list[VisibilityEdge]:
    edges: list[VisibilityEdge] = []
    for viewer in members:
        for target in members:
            if viewer.server_id == target.server_id:
                continue
            label = f"{target.name} ({target.map_label})"
            if not viewer.launch_ok or not target.launch_ok:
                edges.append(VisibilityEdge(
                    viewer=f"{viewer.name} ({viewer.map_label})",
                    target=label,
                    status="error",
                    detail="Configuração de cluster incompleta em um dos mapas",
                ))
                continue
            if viewer.launch_cluster_id != target.launch_cluster_id:
                edges.append(VisibilityEdge(
                    viewer=f"{viewer.name} ({viewer.map_label})",
                    target=label,
                    status="error",
                    detail="Cluster ID diferente — não apareceriam no terminal",
                ))
                continue
            if normalize_cluster_path(viewer.shared_dir) != normalize_cluster_path(target.shared_dir):
                edges.append(VisibilityEdge(
                    viewer=f"{viewer.name} ({viewer.map_label})",
                    target=label,
                    status="error",
                    detail="Pastas compartilhadas diferentes — uploads não seriam vistos",
                ))
                continue
            if not viewer.path_ok or not target.path_ok:
                edges.append(VisibilityEdge(
                    viewer=f"{viewer.name} ({viewer.map_label})",
                    target=label,
                    status="warn",
                    detail="Pasta inacessível em um dos lados — viagem pode falhar",
                ))
                continue
            if not target.running:
                edges.append(VisibilityEdge(
                    viewer=f"{viewer.name} ({viewer.map_label})",
                    target=label,
                    status="warn",
                    detail="Mapa offline — no jogo só lista servidores online; dados antigos podem aparecer",
                ))
                continue
            edges.append(VisibilityEdge(
                viewer=f"{viewer.name} ({viewer.map_label})",
                target=label,
                status="ok",
                detail="Mesmo cluster, mesma pasta e mapa acessível — visível no terminal",
            ))
    return edges


def simulate_obelisk_listings(
    members: list[ClusterMemberInfo],
    transfers: list[TransferFileInfo],
    visibility: list[VisibilityEdge],
) -> dict[str, list[str]]:
    listings: dict[str, list[str]] = {}
    transfer_lines = []
    for t in transfers[:12]:
        age = time.strftime("%d/%m %H:%M", time.localtime(t.modified)) if t.modified else "?"
        kb = t.size / 1024
        transfer_lines.append(f"• {t.kind}: {t.relative_path} ({kb:.0f} KB, {age})")
    if not transfer_lines:
        transfer_lines.append("• (nenhum upload anterior na pasta compartilhada)")

    for viewer in members:
        lines: list[str] = []
        visible_targets = [
            e for e in visibility
            if e.viewer == f"{viewer.name} ({viewer.map_label})" and e.status == "ok"
        ]
        warn_targets = [
            e for e in visibility
            if e.viewer == f"{viewer.name} ({viewer.map_label})" and e.status == "warn"
        ]
        if visible_targets:
            lines.append("Mapas que apareceriam no terminal (online):")
            for e in visible_targets:
                lines.append(f"  → {e.target}")
        if warn_targets:
            lines.append("Mapas com ressalva:")
            for e in warn_targets:
                lines.append(f"  ⚠ {e.target}: {e.detail}")
        if not visible_targets and not warn_targets and len(members) > 1:
            lines.append("Nenhum outro mapa visível com a configuração atual.")
        lines.append("")
        lines.append("Downloads disponíveis (uploads na pasta compartilhada):")
        lines.extend(transfer_lines)
        listings[f"{viewer.name} ({viewer.map_label})"] = lines
    return listings


def run_cluster_travel_test(
    prof: "ClusterProfile",
    asm_servers: list["AsmServerConfig"],
    legacy_servers: list["ServerConfig"],
) -> ClusterTravelTestResult:
    result = ClusterTravelTestResult(
        profile_name=prof.name,
        cluster_id=prof.cluster_id,
        shared_dir=_shared_cluster_dir(prof),
    )

    if not prof.cluster_id.strip():
        result.checks.append(("error", "Cluster ID vazio", "Defina o mesmo ID em todos os mapas"))
    if not result.shared_dir:
        result.checks.append(("error", "Pasta compartilhada vazia", "Configure a pasta de viagem no perfil"))

    for srv in asm_servers:
        cid, cdir, notes = _asm_launch_cluster_info(srv)
        map_label = (srv.server_map or "").replace("_P", "").replace("_", " ")
        result.members.append(
            build_member_info(
                kind="asm",
                server_id=srv.id,
                name=srv.name or "Servidor",
                map_label=map_label or "?",
                port=int(getattr(srv, "server_port", 0) or 0),
                install_dir=srv.install_dir or "",
                prof=prof,
                launch_cid=cid,
                launch_cdir=cdir,
                launch_notes=notes,
            )
        )

    for srv in legacy_servers:
        cid, cdir, notes = _legacy_launch_cluster_info(srv, prof)
        map_label = (srv.map or "").replace("_P", "").replace("_", " ")
        result.members.append(
            build_member_info(
                kind="legacy",
                server_id=srv.id,
                name=srv.name or "Servidor",
                map_label=map_label or "?",
                port=int(getattr(srv, "server_port", 0) or 0),
                install_dir=srv.install_dir or "",
                prof=prof,
                launch_cid=cid,
                launch_cdir=cdir,
                launch_notes=notes,
            )
        )

    if len(result.members) < 2:
        result.checks.append((
            "warn",
            "Menos de 2 mapas vinculados",
            "Vincule pelo menos dois servidores para testar viagem entre mapas",
        ))

    if result.shared_dir:
        ok, note = probe_path_read_write(result.shared_dir)
        sev = "ok" if ok else "error"
        result.checks.append((sev, "Pasta compartilhada (rede)", note))
        if prof.mode == "network" and is_network_share_path(result.shared_dir) and not ok:
            result.checks.append((
                "error",
                "UNC inacessível nesta máquina",
                "Abra o caminho no Explorer ou crie o compartilhamento no NAS",
            ))

    unique_shared = {normalize_cluster_path(m.shared_dir) for m in result.members if m.shared_dir}
    if len(unique_shared) > 1:
        result.checks.append((
            "error",
            "Pastas compartilhadas divergentes",
            "Todos os mapas devem usar a mesma pasta de rede: " + ", ".join(sorted(unique_shared)),
        ))

    unique_cid = {m.launch_cluster_id for m in result.members if m.launch_cluster_id}
    if len(unique_cid) > 1:
        result.checks.append((
            "error",
            "Cluster ID divergente entre mapas",
            "IDs encontrados: " + ", ".join(sorted(unique_cid)),
        ))
    elif len(unique_cid) == 1 and prof.cluster_id.strip() not in unique_cid:
        result.checks.append((
            "warn",
            "Cluster ID do perfil vs servidores",
            f"Perfil: {prof.cluster_id}; servidores: {next(iter(unique_cid))}",
        ))

    if result.shared_dir and prof.cluster_id:
        result.transfers = scan_transfer_files(result.shared_dir, prof.cluster_id)

    result.visibility = compute_visibility(result.members)
    result.simulated_listings = simulate_obelisk_listings(
        result.members, result.transfers, result.visibility
    )

    if prof.sync_enabled and prof.mode == "network":
        engines_note = "Sync ativo — confirme que o ARKLAND está aberto em cada máquina"
        result.checks.append(("warn", "Modo sync", engines_note))

    return result
