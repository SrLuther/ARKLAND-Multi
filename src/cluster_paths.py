"""Caminhos de cluster Cross-ARK — UNC, launch flags e pasta local por servidor."""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from .server_config import ClusterProfile


def default_local_cluster_dir(install_dir: str) -> str:
    """Pasta padrão onde o ARK grava dados de viagem (ShooterGame/Saved/clusters)."""
    if not (install_dir or "").strip():
        return ""
    return str(Path(install_dir) / "ShooterGame" / "Saved" / "clusters")


def normalize_cluster_path(path: str) -> str:
    """Normaliza separadores e garante prefixo UNC (\\\\) quando aplicável."""
    p = (path or "").strip()
    if not p:
        return ""
    p = p.replace("/", "\\")
    if p.startswith("\\\\"):
        return p
    # //servidor/pasta ou //192.168.x.x/pasta
    if p.startswith("//"):
        return "\\\\" + p[2:]
    # Entrada com uma barra: \servidor\pasta
    if p.startswith("\\") and len(p) > 1 and not p.startswith("\\\\"):
        return "\\" + p
    return p


def is_network_share_path(path: str) -> bool:
    """True se o caminho parece UNC ou unidade de rede mapeada (ex.: Z:\\)."""
    p = normalize_cluster_path(path)
    if p.startswith("\\\\"):
        return True
    if len(p) >= 3 and p[1] == ":" and p[2] == "\\":
        letter = p[0].upper()
        if letter not in ("C", "D", "E", "F", "G", "H", "I", "J", "K", "L", "M",
                          "N", "O", "P", "Q", "R", "S", "T", "U", "V", "W", "X", "Y", "Z"):
            return False
        # Unidade mapeada (Z:) — aceito em cluster de rede
        return letter != "C" or p.lower().startswith("c:\\") is False
    return False


def looks_like_local_drive_path(path: str) -> bool:
    p = normalize_cluster_path(path)
    return len(p) >= 3 and p[1] == ":" and p[2] == "\\" and p[0].upper() in "CDEFGHIJKLMNOPQRSTUVWXYZ"


def resolve_cluster_dir_override(
    prof: "ClusterProfile",
    *,
    install_dir: str = "",
    manual_override: str = "",
) -> str:
    """Resolve -ClusterDirOverride para um servidor.

    Rede + sync: cada máquina usa pasta local do ARK; sync replica para UNC.
    Rede sem sync: UNC compartilhada (igual ASM).
    Local: pasta do perfil.
    """
    if prof.mode == "network" and getattr(prof, "sync_enabled", False):
        local = (manual_override or "").strip()
        if local:
            return normalize_cluster_path(local)
        if install_dir:
            return normalize_cluster_path(default_local_cluster_dir(install_dir))
        return ""
    shared = (prof.cluster_dir or manual_override or "").strip()
    return normalize_cluster_path(shared)


def format_cluster_dir_launch_flag(path: str) -> str:
    """Formata -ClusterDirOverride= para linha de comando (UNC sempre entre aspas)."""
    p = normalize_cluster_path(path)
    if not p:
        return ""
    inner = f"-ClusterDirOverride={p}"
    if p.startswith("\\\\") or " " in p:
        return f'"{inner}"'
    return inner


def validate_network_cluster_dir(prof: "ClusterProfile") -> Optional[str]:
    """Retorna mensagem de aviso se a config de rede parecer incorreta."""
    if prof.mode != "network":
        return None
    shared = normalize_cluster_path(prof.cluster_dir)
    if not shared:
        return "Modo rede: informe a pasta compartilhada (UNC, ex.: \\\\NAS\\ARKCluster)."
    if getattr(prof, "sync_enabled", False):
        return None
    if shared.startswith("\\\\"):
        return None
    if looks_like_local_drive_path(shared) and shared[0].upper() == "C":
        return (
            "Modo rede sem sync: use caminho UNC (\\\\servidor\\pasta) acessível em "
            "TODAS as máquinas — não use C:\\ local de uma só PC."
        )
    return (
        "Modo rede: prefira UNC (\\\\IP-ou-Nome\\Pasta). Caminhos locais só funcionam "
        "com 'Sincronizar pasta local ↔ rede' ativo em cada máquina."
    )


def collect_cluster_dirs_to_ensure(
    prof: "ClusterProfile",
    linked_install_dirs: list[str],
) -> list[str]:
    """Pastas que o Manager pode/ deve criar ao salvar o perfil."""
    dirs: list[str] = []
    if prof.mode == "local":
        if prof.cluster_dir.strip():
            dirs.append(normalize_cluster_path(prof.cluster_dir))
    elif prof.mode == "network":
        if getattr(prof, "sync_enabled", False):
            if prof.local_cluster_dir.strip():
                dirs.append(normalize_cluster_path(prof.local_cluster_dir))
            for inst in linked_install_dirs:
                d = resolve_cluster_dir_override(prof, install_dir=inst)
                if d and not is_network_share_path(d):
                    dirs.append(d)
        elif prof.cluster_dir.strip():
            dirs.append(normalize_cluster_path(prof.cluster_dir))
    # Preserva ordem, remove duplicatas
    return list(dict.fromkeys(d for d in dirs if d))


def ensure_cluster_directories(
    prof: "ClusterProfile",
    linked_install_dirs: list[str],
) -> tuple[list[str], list[str]]:
    """Cria pastas locais/UNC acessíveis. Retorna (criadas, falhas)."""
    import os

    created: list[str] = []
    failed: list[str] = []
    for d in collect_cluster_dirs_to_ensure(prof, linked_install_dirs):
        if os.path.isdir(d):
            continue
        try:
            os.makedirs(d, exist_ok=True)
            created.append(d)
        except OSError:
            failed.append(d)
    return created, failed
