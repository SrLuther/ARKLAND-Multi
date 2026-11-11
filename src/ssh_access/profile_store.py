from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Iterable

from .models import SSHProfile


def default_ssh_dir() -> Path:
    return Path(os.environ.get("APPDATA", Path.home())) / "ARKLAND-ServerManager" / "ssh"


class SSHProfileStore:
    """Stores SSH connection metadata; credentials are kept by the OS vault."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = Path(path) if path else default_ssh_dir() / "profiles.json"

    def load(self) -> list[SSHProfile]:
        if not self.path.exists():
            return []
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(payload, list):
                raise ValueError("O arquivo de perfis SSH deve conter uma lista.")
            profiles = [SSHProfile.from_dict(item) for item in payload if isinstance(item, dict)]
            ids = [p.id for p in profiles]
            aliases = [p.alias.casefold() for p in profiles if p.alias]
            if len(ids) != len(set(ids)) or len(aliases) != len(set(aliases)):
                raise ValueError("Há IDs ou aliases duplicados nos perfis SSH.")
            return profiles
        except (OSError, json.JSONDecodeError, TypeError) as exc:
            raise ValueError(f"Não foi possível ler os perfis SSH: {exc}") from exc

    def save(self, profiles: Iterable[SSHProfile]) -> None:
        items = list(profiles)
        payload = [p.to_dict() for p in items]
        ids = [p.id for p in items]
        aliases = [p.alias.casefold() for p in items if p.alias]
        if len(ids) != len(set(ids)) or len(aliases) != len(set(aliases)):
            raise ValueError("IDs e aliases SSH devem ser únicos.")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", newline="\n", dir=self.path.parent,
                prefix=f"{self.path.name}.", suffix=".tmp", delete=False,
            ) as fh:
                tmp = Path(fh.name)
                json.dump(payload, fh, indent=2, ensure_ascii=False)
                fh.write("\n")
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(tmp, self.path)
        except Exception:
            if tmp is not None:
                tmp.unlink(missing_ok=True)
            raise
