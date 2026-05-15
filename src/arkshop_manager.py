"""
Gerenciador de configuração do ArkShop.
Responsável por carregar, salvar e fornecer acesso estruturado ao config.json do plugin.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional


# ── Estruturas padrão ────────────────────────────────────────────────────────

_DEFAULT_CONFIG: Dict[str, Any] = {
    "Mysql": {
        "UseMysql": False,
        "MysqlHost": "127.0.0.1",
        "MysqlUser": "",
        "MysqlPass": "",
        "MysqlDB": "arkshop",
        "MysqlPort": 3306,
    },
    "General": {
        "Discord": {
            "Enabled": False,
            "SenderName": "ArkShop",
            "URL": "",
        },
        "TimedPointsReward": {
            "Enabled": False,
            "Interval": 30,
            "StackRewards": True,
            "Groups": {
                "Default": {"Amount": 25},
            },
        },
        "ItemsPerPage": 15,
        "ShopDisplayTime": 15.0,
        "ShopTextSize": 1.3,
        "DbPathOverride": "",
        "DefaultKit": "",
        "GiveDinosInCryopods": True,
        "UseSoulTraps": False,
        "CryoLimitedTime": False,
        "UseOriginalTradeCommandWithUI": False,
        "PreventUseNoglin": True,
        "PreventUseUnconscious": True,
        "PreventUseHandcuffed": True,
        "PreventUseCarried": True,
    },
    "Kits": {},
    "ShopItems": {},
    "SellItems": {},
    "Messages": {},
}

# Rótulos amigáveis para as chaves booleanas de General
GENERAL_BOOL_LABELS: List[tuple[str, str]] = [
    ("GiveDinosInCryopods",           "Entregar dinos em cryopods"),
    ("UseSoulTraps",                  "Usar Soul Traps (DinoStorage2)"),
    ("CryoLimitedTime",               "Tempo limitado no cryo"),
    ("UseOriginalTradeCommandWithUI", "Usar /trade original com UI"),
    ("PreventUseNoglin",              "Bloquear uso com Noglin"),
    ("PreventUseUnconscious",         "Bloquear uso inconsciente"),
    ("PreventUseHandcuffed",          "Bloquear uso algemado"),
    ("PreventUseCarried",             "Bloquear uso sendo carregado"),
]


class ArkShopManager:
    """Carrega e persiste o config.json do ArkShop."""

    def __init__(self) -> None:
        self._path: Optional[Path] = None
        self._data: Dict[str, Any] = {}

    # ── Arquivo ──────────────────────────────────────────────────────────────

    @property
    def path(self) -> Optional[Path]:
        return self._path

    @property
    def is_loaded(self) -> bool:
        return bool(self._data)

    def load(self, path: str | Path) -> None:
        """Lê o arquivo e armazena internamente."""
        p = Path(path)
        with open(p, "r", encoding="utf-8") as fh:
            self._data = json.load(fh)
        self._path = p

    def load_data(self, data: Dict[str, Any]) -> None:
        """Carrega configuração a partir de um dict (ex.: de um preset)."""
        import copy
        self._data = copy.deepcopy(data)

    def save(self, path: Optional[str | Path] = None) -> None:
        """Serializa e grava no arquivo (usa self._path se não informado)."""
        target = Path(path) if path else self._path
        if target is None:
            raise ValueError("Nenhum caminho de arquivo definido.")
        target.parent.mkdir(parents=True, exist_ok=True)
        with open(target, "w", encoding="utf-8") as fh:
            json.dump(self._data, fh, indent=4, ensure_ascii=False)
        self._path = target

    def save_raw(self, raw_json: str, path: Optional[str | Path] = None) -> None:
        """Valida e grava JSON bruto, atualizando self._data."""
        self._data = json.loads(raw_json)   # valida antes de gravar
        self.save(path)

    def to_json_str(self) -> str:
        """Retorna o conteúdo atual como texto JSON indentado."""
        return json.dumps(self._data, indent=4, ensure_ascii=False)

    # ── Getters / Setters por seção ──────────────────────────────────────────

    def get_section(self, *keys: str) -> Any:
        obj = self._data
        for k in keys:
            if not isinstance(obj, dict):
                return None
            obj = obj.get(k)
        return obj

    def set_section(self, value: Any, *keys: str) -> None:
        obj = self._data
        for k in keys[:-1]:
            obj = obj.setdefault(k, {})
        obj[keys[-1]] = value

    # ── MySQL ────────────────────────────────────────────────────────────────

    @property
    def mysql(self) -> Dict[str, Any]:
        return self._data.get("Mysql", {})

    def set_mysql(self, field: str, value: Any) -> None:
        self._data.setdefault("Mysql", {})[field] = value

    # ── General ──────────────────────────────────────────────────────────────

    @property
    def general(self) -> Dict[str, Any]:
        return self._data.get("General", {})

    def set_general(self, field: str, value: Any) -> None:
        self._data.setdefault("General", {})[field] = value

    @property
    def timed_groups(self) -> Dict[str, Dict[str, int]]:
        return (
            self._data
            .get("General", {})
            .get("TimedPointsReward", {})
            .get("Groups", {})
        )

    def set_timed_groups(self, groups: Dict[str, Dict[str, int]]) -> None:
        (
            self._data
            .setdefault("General", {})
            .setdefault("TimedPointsReward", {})
        )["Groups"] = groups

    # ── Kits ─────────────────────────────────────────────────────────────────

    @property
    def kits(self) -> Dict[str, Any]:
        return self._data.get("Kits", {})

    def set_kit(self, kit_id: str, kit_data: Dict[str, Any]) -> None:
        self._data.setdefault("Kits", {})[kit_id] = kit_data

    def delete_kit(self, kit_id: str) -> None:
        self._data.get("Kits", {}).pop(kit_id, None)

    # ── ShopItems ────────────────────────────────────────────────────────────

    @property
    def shop_items(self) -> Dict[str, Any]:
        return self._data.get("ShopItems", {})

    def set_shop_item(self, item_id: str, item_data: Dict[str, Any]) -> None:
        self._data.setdefault("ShopItems", {})[item_id] = item_data

    def delete_shop_item(self, item_id: str) -> None:
        self._data.get("ShopItems", {}).pop(item_id, None)

    # ── Messages ─────────────────────────────────────────────────────────────

    @property
    def messages(self) -> Dict[str, str]:
        return self._data.get("Messages", {})

    def set_message(self, key: str, value: str) -> None:
        self._data.setdefault("Messages", {})[key] = value
