"""Importação ÚNICA e OPCIONAL de dados do projeto antigo (oBobonicClean).

Nada aqui é lido em runtime pelo bot: só roda quando o usuário aceita importar
(diálogo no primeiro acesso ao painel ou botão «Importar dados do bot antigo»).
Segredos nunca são escritos em log; as funções devolvem apenas NOMES dos campos
importados.
"""
from __future__ import annotations

import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from .settings import validate_token_value
from .storage import BADWORDS_FILENAME, ensure_data_dir

_ENV_KEY_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_CONFIG_DEFAULT_RE = re.compile(
    r"""^\s*([A-Z][A-Z0-9_]*)\s*=\s*get_int_env\(\s*["']([A-Z0-9_]+)["']\s*,\s*(\d+)\s*\)""",
    re.MULTILINE,
)

# chave do .env/config.py antigo → campo de ObobonicBotConfig
LEGACY_KEY_MAP: Dict[str, str] = {
    "DISCORD_TOKEN": "token",
    "GUILD_ID": "guild_id",
    "LOBBY_CHANNEL_ID": "lobby_channel_id",
    "CANAL_LOGS_ID": "logs_channel_id",
    "QUARANTINE_ROLE_ID": "quarantine_role_id",
}

_ID_FIELDS = ("guild_id", "lobby_channel_id", "logs_channel_id", "quarantine_role_id")


@dataclass
class LegacyData:
    """Valores relevantes encontrados na pasta antiga."""
    folder: Path
    values: Dict[str, str] = field(default_factory=dict)      # campo da config → valor
    badwords_path: Optional[Path] = None

    @property
    def has_token(self) -> bool:
        return bool(self.values.get("token"))

    @property
    def has_anything(self) -> bool:
        return bool(self.values) or self.badwords_path is not None


def parse_env_text(text: str) -> Dict[str, str]:
    """Parser simples de ``.env`` (KEY=VALUE, comentários #, aspas opcionais)."""
    result: Dict[str, str] = {}
    for line in (text or "").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, _, value = stripped.partition("=")
        key = key.strip()
        if key.startswith("export "):
            key = key[len("export "):].strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        if _ENV_KEY_RE.match(key):
            result[key] = value
    return result


def parse_config_py_defaults(text: str) -> Dict[str, str]:
    """Defaults numéricos de ``config.py`` (``X = get_int_env("X", 123)``) → ``{"X": "123"}``."""
    out: Dict[str, str] = {}
    for _name, env_key, default in _CONFIG_DEFAULT_RE.findall(text or ""):
        out[env_key] = default
    return out


def find_legacy_badwords(folder: Path) -> Optional[Path]:
    for candidate in (folder / ".bancos" / BADWORDS_FILENAME, folder / BADWORDS_FILENAME):
        if candidate.is_file():
            return candidate
    return None


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def collect_legacy_values(folder: Path) -> LegacyData:
    """Lê (somente leitura) ``.env`` e ``config.py`` da pasta antiga."""
    data = LegacyData(folder=folder)
    if not folder.is_dir():
        return data
    merged: Dict[str, str] = {}
    # Defaults de config.py (menor prioridade) e depois o .env (maior prioridade).
    cfg_path = folder / "config.py"
    if cfg_path.is_file():
        merged.update(parse_config_py_defaults(_read_text(cfg_path)))
    env_path = folder / ".env"
    if env_path.is_file():
        merged.update({k: v for k, v in parse_env_text(_read_text(env_path)).items() if v.strip()})
    for legacy_key, field_name in LEGACY_KEY_MAP.items():
        value = (merged.get(legacy_key) or "").strip()
        if not value:
            continue
        if field_name == "token":
            ok, _msg = validate_token_value(value)
            if not ok:
                continue
        elif field_name in _ID_FIELDS and not value.isdigit():
            continue
        data.values[field_name] = value
    data.badwords_path = find_legacy_badwords(folder)
    return data


def apply_legacy_to_config(cfg: Any, data: LegacyData, *, overwrite: bool = False) -> List[str]:
    """Copia os valores para ``cfg`` (ObobonicBotConfig). Devolve os campos alterados.

    Sem ``overwrite``, só preenche campos que ainda estão vazios.
    """
    changed: List[str] = []
    for field_name, value in data.values.items():
        current = (getattr(cfg, field_name, "") or "").strip()
        if current and not overwrite:
            continue
        if current == value:
            continue
        setattr(cfg, field_name, value)
        changed.append(field_name)
    return changed


def import_badwords(data: LegacyData, data_dir: Path, *, overwrite: bool = False) -> bool:
    """Importa ``palavroes.txt`` antigo para a pasta de dados do app.

    Por padrão faz MERGE (união, sem perder palavras já existentes); com ``overwrite``
    substitui o arquivo atual pelo antigo.
    """
    if data.badwords_path is None:
        return False
    ensure_data_dir(data_dir)
    dest = data_dir / BADWORDS_FILENAME
    if overwrite:
        shutil.copy2(data.badwords_path, dest)
        return True
    from .logic import parse_badwords

    existing = parse_badwords(_read_text(dest))
    incoming = parse_badwords(_read_text(data.badwords_path))
    merged = existing + [w for w in incoming if w not in set(existing)]
    if merged == existing:
        return False
    dest.write_text("\n".join(merged) + "\n", encoding="utf-8")
    return True


def should_offer_legacy_import(cfg: Any) -> bool:
    """Oferece importar uma vez: há pasta antiga registrada, ainda não decidido e sem token novo."""
    if getattr(cfg, "legacy_import_done", False):
        return False
    folder = (getattr(cfg, "legacy_project_path", "") or "").strip()
    if not folder:
        return False
    if (getattr(cfg, "token", "") or "").strip():
        return False
    data = collect_legacy_values(Path(folder))
    return data.has_token
