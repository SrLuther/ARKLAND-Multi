from __future__ import annotations

import os
import tempfile
from pathlib import Path

import paramiko

from .profile_store import default_ssh_dir


def host_key_name(host: str, port: int) -> str:
    return host if int(port) == 22 else f"[{host}]:{int(port)}"


def fingerprint_sha256(key: paramiko.PKey) -> str:
    import base64

    digest = base64.b64encode(__import__("hashlib").sha256(key.asbytes()).digest()).decode("ascii").rstrip("=")
    return f"SHA256:{digest}"


class HostKeyStore:
    """Application-owned OpenSSH-format known_hosts file."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = Path(path) if path else default_ssh_dir() / "known_hosts"

    def get(self, host: str, port: int) -> paramiko.PKey | None:
        if not self.path.exists():
            return None
        keys = paramiko.HostKeys()
        keys.load(str(self.path))
        host_keys = keys.lookup(host_key_name(host, port))
        return next(iter(host_keys.values())) if host_keys else None

    def get_for_type(self, host: str, port: int, key_type: str) -> paramiko.PKey | None:
        if not self.path.exists():
            return None
        keys = paramiko.HostKeys()
        keys.load(str(self.path))
        host_keys = keys.lookup(host_key_name(host, port))
        return host_keys.get(key_type) if host_keys else None

    def trust(self, host: str, port: int, key: paramiko.PKey) -> None:
        host_name = host_key_name(host, port)
        keys = paramiko.HostKeys()
        if self.path.exists():
            keys.load(str(self.path))
        current = keys.lookup(host_name)
        if current and key.get_name() in current:
            existing = current[key.get_name()]
            if existing.asbytes() != key.asbytes():
                raise ValueError("A chave deste host já é conhecida e é diferente. Conexão bloqueada.")
            return
        keys.add(host_name, key.get_name(), key)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="wb", dir=self.path.parent, prefix=f"{self.path.name}.", suffix=".tmp", delete=False
            ) as fh:
                tmp = Path(fh.name)
            keys.save(str(tmp))
            with tmp.open("r+b") as fh:
                os.fsync(fh.fileno())
            os.replace(tmp, self.path)
        except Exception:
            if tmp:
                tmp.unlink(missing_ok=True)
            raise
