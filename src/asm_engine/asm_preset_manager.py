"""
AsmPresetManager — salva/aplica subconjuntos de configuração como presets reutilizáveis.
Presets ficam em %APPDATA%\\ARKLAND-ServerManager\\presets\\*.json
"""
from __future__ import annotations

import json
import os
from dataclasses import fields
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, TYPE_CHECKING

from .asm_config_categories import (
    PRESET_CATEGORIES,
    PRESET_CATEGORY_LABELS,
    get_preset_category_fields,
)

if TYPE_CHECKING:
    from .asm_server_config import AsmServerConfig


class AsmPresetManager:
    """Exporta/importa subconjuntos de config como presets reutilizáveis."""

    def __init__(self) -> None:
        self._dir = (
            Path(os.environ.get("APPDATA", Path.home()))
            / "ARKLAND-ServerManager"
            / "presets"
        )

    def _path(self, name: str) -> Path:
        safe = "".join(c if c.isalnum() or c in "-_ " else "_" for c in name)
        return self._dir / f"{safe}.json"

    def list_presets(self) -> List[Dict[str, Any]]:
        if not self._dir.exists():
            return []
        result = []
        for p in sorted(self._dir.glob("*.json")):
            try:
                with open(p, encoding="utf-8") as fh:
                    data = json.load(fh)
                result.append({
                    "name":        data.get("name", p.stem),
                    "created_at":  data.get("created_at", ""),
                    "categories":  data.get("categories", []),
                    "description": data.get("description", ""),
                    "path":        str(p),
                })
            except Exception:
                pass
        return result

    def save_preset(
        self,
        name: str,
        srv: "AsmServerConfig",
        categories: List[str],
        description: str = "",
    ) -> None:
        """Salva um preset com os campos das categorias indicadas."""
        all_fields: set[str] = set()
        for cat in categories:
            all_fields.update(get_preset_category_fields(cat))

        valid = {f.name for f in fields(srv)}
        values: Dict[str, Any] = {}
        for f_name in all_fields:
            if f_name in valid:
                values[f_name] = getattr(srv, f_name)

        payload = {
            "version":     "1.1",
            "name":        name,
            "created_at":  datetime.now().isoformat(timespec="seconds"),
            "categories":  categories,
            "description": description,
            "values":      values,
        }
        self._dir.mkdir(parents=True, exist_ok=True)
        with open(self._path(name), "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2, ensure_ascii=False)

    def load_preset(self, name_or_path: str, srv: "AsmServerConfig") -> None:
        """Aplica um preset ao servidor (sem sobrescrever campos fora do preset)."""
        p = Path(name_or_path)
        if not p.is_absolute():
            p = self._path(name_or_path)
        with open(p, encoding="utf-8") as fh:
            payload = json.load(fh)
        values: Dict[str, Any] = payload.get("values", {})
        valid = {f.name for f in fields(srv)}
        for k, v in values.items():
            if k in valid:
                try:
                    setattr(srv, k, v)
                except Exception:
                    pass

    def delete_preset(self, name: str) -> None:
        p = self._path(name)
        if p.exists():
            p.unlink()


def format_preset_categories(categories: List[str]) -> str:
    """Rótulos legíveis para exibição na UI."""
    return ", ".join(PRESET_CATEGORY_LABELS.get(c, c) for c in categories)
