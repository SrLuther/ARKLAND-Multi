"""Persistência do bot embutido (arquivos simples em ``%APPDATA%/ARKLAND-ServerManager/obobonic``)."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Dict, List

from .logic import DEFAULT_BADWORDS, parse_badwords

BADWORDS_FILENAME = "palavroes.txt"
VOICE_STATE_FILENAME = "voice_temp_channels.json"


def ensure_data_dir(data_dir: Path) -> Path:
    """Cria a pasta de dados e semeia ``palavroes.txt`` (somente se ainda não existir)."""
    data_dir.mkdir(parents=True, exist_ok=True)
    words_path = data_dir / BADWORDS_FILENAME
    if not words_path.exists():
        words_path.write_text("\n".join(DEFAULT_BADWORDS) + "\n", encoding="utf-8")
    return data_dir


def load_badwords(data_dir: Path) -> List[str]:
    """Lê a lista de palavrões; levanta ``FileNotFoundError`` se o arquivo sumiu."""
    path = data_dir / BADWORDS_FILENAME
    return parse_badwords(path.read_text(encoding="utf-8"))


def _atomic_write(path: Path, text: str) -> None:
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def load_temp_channels(data_dir: Path) -> Dict[int, int]:
    """Salas temporárias rastreadas ``{channel_id: owner_id}`` (tolerante a arquivo ruim)."""
    path = data_dir / VOICE_STATE_FILENAME
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if not isinstance(raw, dict):
        return {}
    out: Dict[int, int] = {}
    for k, v in raw.items():
        try:
            out[int(k)] = int(v)
        except (TypeError, ValueError):
            continue
    return out


def save_temp_channels(data_dir: Path, channels: Dict[int, int]) -> None:
    try:
        data_dir.mkdir(parents=True, exist_ok=True)
        payload = {str(k): int(v) for k, v in channels.items()}
        _atomic_write(data_dir / VOICE_STATE_FILENAME, json.dumps(payload, indent=2))
    except OSError:
        pass  # estado auxiliar: nunca derruba o bot
