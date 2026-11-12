"""Safety primitives for explicit INI edits, imports and synchronization."""
from __future__ import annotations

from datetime import datetime
import ntpath
import os
from pathlib import Path
import tempfile
import json
from types import SimpleNamespace
from typing import Iterable

_UNSET = object()


def normalized_install_path(value: str | os.PathLike[str]) -> str:
    """Normalize Windows install paths even when inspected from another OS."""
    raw = os.fspath(value).strip().replace("/", "\\")
    return ntpath.normcase(ntpath.normpath(raw)) if raw else ""


def find_install_conflicts(
    server_id: str,
    install_dir: str | os.PathLike[str],
    profiles: Iterable[object],
    *,
    target_profile: object | None = None,
) -> list[object]:
    """Find other profiles that point at the same lexical or physical folder."""
    target = Path(install_dir)
    target_norm = normalized_install_path(install_dir)
    conflicts: list[object] = []
    for profile in profiles:
        other_id = str(getattr(profile, "id", "") or "")
        other_path = str(getattr(profile, "install_dir", "") or "")
        if not other_path or profile is target_profile:
            continue
        same = normalized_install_path(other_path) == target_norm
        if not same:
            try:
                same = target.exists() and Path(other_path).exists() and target.samefile(Path(other_path))
            except (OSError, ValueError):
                same = False
        if same:
            conflicts.append(profile)
    return conflicts


def load_tek_profiles_read_only(config_dir: Path | None = None) -> list[object]:
    """Read only TEK install paths for legacy UI conflict checks."""
    base = config_dir or Path(os.environ.get("APPDATA", Path.home())) / "ARKLAND-ServerManager"
    source = base / "asm_servers.json"
    if not source.exists():
        return []
    payload = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError(f"Formato inesperado em {source}; gravação bloqueada por segurança.")
    profiles: list[object] = []
    for item in payload:
        if isinstance(item, dict) and item.get("install_dir"):
            profiles.append(SimpleNamespace(
                id=str(item.get("id", "")),
                name=str(item.get("name", "Perfil TEK")),
                install_dir=str(item["install_dir"]),
            ))
    return profiles


def backup_path_for(path: Path, *, timestamp: str | None = None) -> Path:
    stamp = timestamp or datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    return path.parent / "ArklandIniBackups" / f"{path.name}_{stamp}.bak"


def atomic_replace(path: Path, data: bytes) -> None:
    """Replace bytes through a same-directory temporary file and fsync."""
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_name, path)
    except Exception:
        try:
            os.unlink(temporary_name)
        except OSError:
            pass
        raise


def write_with_backup(
    path: Path,
    data: bytes,
    *,
    expected_original: bytes | None | object = _UNSET,
    timestamp: str | None = None,
) -> Path | None:
    """Back up existing bytes, then atomically write; reject stale editor data."""
    original = path.read_bytes() if path.exists() else None
    if expected_original is not _UNSET and original != expected_original:
        raise RuntimeError("O arquivo mudou desde que foi aberto; reabra-o para evitar sobrescrever alterações recentes.")
    backup: Path | None = None
    if original is not None:
        backup = backup_path_for(path, timestamp=timestamp)
        backup.parent.mkdir(parents=True, exist_ok=True)
        if backup.exists():
            raise FileExistsError(f"Backup já existe: {backup}")
        atomic_replace(backup, original)
    atomic_replace(path, data)
    return backup
