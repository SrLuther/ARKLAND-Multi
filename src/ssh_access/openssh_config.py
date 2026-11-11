"""Opt-in, reversible integration with the current user's OpenSSH config."""
from __future__ import annotations

import fnmatch
import glob
import os
import re
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

from .models import SSHProfile
from .profile_store import default_ssh_dir


_BEGIN = "# BEGIN ARKLAND MANAGED SSH INCLUDE"
_END = "# END ARKLAND MANAGED SSH INCLUDE"
_INCLUDE_LINE = re.compile(r"^\s*Include\s+(.+?)\s*$", re.IGNORECASE)
_HOST_LINE = re.compile(r"^\s*Host\s+(.+?)\s*$", re.IGNORECASE)


def default_openssh_config() -> Path:
    return Path.home() / ".ssh" / "config"


def _effective_patterns(patterns: list[str], alias: str) -> bool:
    positives = [p for p in patterns if not p.startswith("!")]
    negatives = [p[1:] for p in patterns if p.startswith("!")]
    return any(fnmatch.fnmatchcase(alias.casefold(), p.casefold()) for p in positives) and not any(
        fnmatch.fnmatchcase(alias.casefold(), p.casefold()) for p in negatives
    )


def _has_alias(config_file: Path, alias: str, visited: set[Path] | None = None) -> bool:
    visited = visited or set()
    try:
        file_path = config_file.resolve()
        if file_path in visited or not file_path.is_file():
            return False
        visited.add(file_path)
        lines = file_path.read_text(encoding="utf-8-sig").splitlines()
    except (OSError, UnicodeError):
        return False
    in_managed = False
    for line in lines:
        stripped = line.strip()
        if stripped == _BEGIN:
            in_managed = True
            continue
        if stripped == _END:
            in_managed = False
            continue
        if in_managed:
            continue
        include = _INCLUDE_LINE.match(line)
        if include:
            value = include.group(1).strip().strip('"\'')
            if "%" in value:
                continue
            include_path = Path(value.replace("/", os.sep).replace("\\", os.sep))
            if not include_path.is_absolute():
                include_path = file_path.parent / include_path
            children = [Path(item) for item in glob.glob(str(include_path))] if any(ch in str(include_path) for ch in "*?[") else [include_path]
            for child in children:
                if _has_alias(child, alias, visited):
                    return True
        host = _HOST_LINE.match(line)
        if host and _effective_patterns(host.group(1).split(), alias):
            # A broad Host * block is not an alias definition; exact and
            # patterned names are treated as conflicts to avoid shadowing.
            patterns = host.group(1).split()
            if any(alias.casefold() == p.casefold() for p in patterns if not p.startswith("!")):
                return True
    return False


def _atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix=f"{path.name}.", suffix=".tmp", delete=False) as fh:
            tmp = Path(fh.name)
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    except Exception:
        if tmp:
            tmp.unlink(missing_ok=True)
        raise


def _secure_openssh_file(path: Path) -> None:
    """Apply OpenSSH-compatible ACLs to app-owned files on Windows.

    OpenSSH rejects generated config files with inherited Owner Rights ACLs on
    some Windows installations. Limit access to the current user, SYSTEM and
    local Administrators; never modify the user's existing ~/.ssh/config ACL.
    """
    if os.name != "nt":
        return
    executable = shutil.which("icacls")
    user = os.environ.get("USERDOMAIN")
    username = os.environ.get("USERNAME")
    if not executable or not username:
        raise OSError("N\u00e3o foi poss\u00edvel localizar icacls/usu\u00e1rio para proteger o arquivo SSH gerenciado.")
    principal = f"{user}\\{username}" if user else username
    proc = subprocess.run(
        [executable, str(path), "/inheritance:r", "/grant:r",
         f"{principal}:(F)", "*S-1-5-18:(F)", "*S-1-5-32-544:(F)"],
        capture_output=True, text=True, timeout=10, check=False,
    )
    if proc.returncode != 0:
        raise OSError(f"N\u00e3o foi poss\u00edvel restringir as permiss\u00f5es do arquivo SSH: {(proc.stderr or proc.stdout).strip()}")


def render_profile_config(profile: SSHProfile, known_hosts_path: Path | None = None) -> str:
    profile.validate()
    if not profile.alias:
        raise ValueError("Defina um alias SSH antes de configurar o Codex.")
    known_hosts = (known_hosts_path or (default_ssh_dir() / "known_hosts")).resolve().as_posix()
    lines = [
        f"Host {profile.alias}",
        f"    HostName {profile.host}",
        f"    User {profile.username}",
        f"    Port {int(profile.port)}",
        "    IdentitiesOnly yes",
        "    StrictHostKeyChecking yes",
        f'    UserKnownHostsFile "{known_hosts}"',
        "    ConnectTimeout 10",
        "    ServerAliveInterval 30",
    ]
    if profile.auth_method == "key":
        identity = Path(profile.identity_file).expanduser().resolve().as_posix()
        lines.append(f'    IdentityFile "{identity}"')
    return "\n".join(lines) + "\n"


def _has_managed_alias(managed_dir: Path, alias: str, exclude: Path | None = None) -> bool:
    if not managed_dir.exists():
        return False
    for candidate in managed_dir.glob("*.conf"):
        if exclude is not None and candidate.resolve() == exclude.resolve():
            continue
        try:
            lines = candidate.read_text(encoding="utf-8-sig").splitlines()
        except (OSError, UnicodeError):
            continue
        for line in lines:
            match = _HOST_LINE.match(line)
            if match and any(pattern.casefold() == alias.casefold() for pattern in match.group(1).split()):
                return True
    return False


def register_codex_alias(
    profile: SSHProfile,
    *,
    config_path: Path | None = None,
    managed_dir: Path | None = None,
    ssh_executable: str = "ssh",
    validate_effective_config: bool = True,
) -> Path:
    """Add an app-owned config file and one marked Include block, preserving all user bytes."""
    profile.validate()
    if profile.auth_method != "key":
        raise ValueError("O alias para o Codex requer autenticação por chave SSH.")
    if not profile.alias:
        raise ValueError("Defina um alias SSH antes de configurar o Codex.")
    config_path = Path(config_path) if config_path else default_openssh_config()
    managed_dir = Path(managed_dir) if managed_dir else default_ssh_dir() / "config.d"
    if config_path.exists() and _has_alias(config_path, profile.alias):
        raise ValueError(f"O alias '{profile.alias}' já existe na configuração OpenSSH. Nenhum arquivo foi alterado.")

    original = config_path.read_bytes() if config_path.exists() else b""
    bom = original.startswith(b"\xef\xbb\xbf")
    try:
        decoded = original.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("A configuração SSH atual não está em UTF-8; foi preservada sem alterações.") from exc
    newline = "\r\n" if "\r\n" in decoded else "\n"
    include_glob = (managed_dir.resolve() / "*.conf").as_posix()
    managed_block = newline.join((_BEGIN, f'Include "{include_glob}"', _END))
    has_begin, has_end = _BEGIN in decoded, _END in decoded
    if has_begin != has_end:
        raise ValueError("O bloco gerenciado no ~/.ssh/config está incompleto. O arquivo foi preservado; revise-o manualmente.")
    has_block = has_begin and has_end

    config_path.parent.mkdir(parents=True, exist_ok=True)
    managed_dir.mkdir(parents=True, exist_ok=True)
    profile_path = managed_dir / f"{profile.id}.conf"
    if _has_managed_alias(managed_dir, profile.alias, exclude=profile_path):
        raise ValueError(f"O alias '{profile.alias}' já está definido em outro arquivo gerenciado pelo ARKLAND.")
    previous_profile = profile_path.read_bytes() if profile_path.exists() else None
    profile_backup: Path | None = None
    if previous_profile is not None:
        stamp = time.strftime("%Y%m%d-%H%M%S")
        profile_backup = profile_path.with_name(f"{profile_path.name}.backup-{stamp}")
        suffix = 1
        while profile_backup.exists():
            profile_backup = profile_path.with_name(f"{profile_path.name}.backup-{stamp}-{suffix}")
            suffix += 1
        shutil.copy2(profile_path, profile_backup)
    _atomic_write(profile_path, render_profile_config(profile).replace("\n", newline).encode("utf-8"))
    try:
        _secure_openssh_file(profile_path)
    except OSError:
        if previous_profile is None:
            profile_path.unlink(missing_ok=True)
        else:
            _atomic_write(profile_path, previous_profile)
        raise

    config_bytes = original
    if not has_block:
        prefix = b"" if not original or original.endswith((b"\n", b"\r")) else newline.encode("ascii")
        new_text = prefix.decode("ascii") + managed_block + newline
        payload = original + new_text.encode("utf-8")
        if bom and original == b"\xef\xbb\xbf":
            payload = original + managed_block.encode("utf-8") + newline.encode("ascii")
        stamp = time.strftime("%Y%m%d-%H%M%S")
        backup = config_path.with_name(f"{config_path.name}.arkland-backup-{stamp}")
        suffix = 1
        while backup.exists():
            backup = config_path.with_name(f"{config_path.name}.arkland-backup-{stamp}-{suffix}")
            suffix += 1
        if config_path.exists():
            shutil.copy2(config_path, backup)
        _atomic_write(config_path, payload)
        config_bytes = payload

    if validate_effective_config:
        proc = subprocess.run(
            [ssh_executable, "-F", str(config_path), "-G", profile.alias],
            capture_output=True, text=True, timeout=15, check=False,
        )
        if proc.returncode != 0:
            if config_bytes != original:
                _atomic_write(config_path, original)
            if previous_profile is None:
                profile_path.unlink(missing_ok=True)
            else:
                _atomic_write(profile_path, previous_profile)
            detail = (proc.stderr or proc.stdout).strip()
            raise RuntimeError(f"OpenSSH rejeitou o alias; configuração revertida. {detail}")
        effective = {}
        for line in proc.stdout.splitlines():
            key, _, value = line.partition(" ")
            effective[key.casefold()] = value.strip().strip('"')
        expected = {"hostname": profile.host.casefold(), "user": profile.username.casefold(), "port": str(int(profile.port))}
        mismatches = [key for key, value in expected.items() if effective.get(key) != value]
        if mismatches:
            if config_bytes != original:
                _atomic_write(config_path, original)
            if previous_profile is None:
                profile_path.unlink(missing_ok=True)
            else:
                _atomic_write(profile_path, previous_profile)
            raise RuntimeError(
                "A configuração OpenSSH existente alteraria o destino efetivo do alias ("
                + ", ".join(mismatches)
                + "). A configuração foi revertida; revise os blocos Host existentes."
            )
    return profile_path


def unregister_codex_alias(profile: SSHProfile, managed_dir: Path | None = None) -> Path | None:
    """Archive and remove only the alias file owned by this ARKLAND profile."""
    managed_dir = Path(managed_dir) if managed_dir else default_ssh_dir() / "config.d"
    profile_path = managed_dir / f"{profile.id}.conf"
    if not profile_path.is_file():
        return None
    stamp = time.strftime("%Y%m%d-%H%M%S")
    backup = profile_path.with_name(f"{profile_path.name}.arkland-backup-{stamp}")
    suffix = 1
    while backup.exists():
        backup = profile_path.with_name(f"{profile_path.name}.arkland-backup-{stamp}-{suffix}")
        suffix += 1
    shutil.copy2(profile_path, backup)
    profile_path.unlink()
    return backup
