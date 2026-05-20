"""
Gerenciador do plugin CustomShop para ARK: Survival Evolved (ArkApi).

Responsável por:
- Detectar se o ArkApi está instalado no servidor
- Instalar / desinstalar o plugin CustomShop
- Carregar e salvar o config.json do plugin
"""
from __future__ import annotations

import json
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import mysql.connector  # type: ignore[import-untyped]
    _MYSQL_AVAILABLE = True
except ImportError:
    _MYSQL_AVAILABLE = False


_PLUGIN_NAME = "CustomShop"

# Caminhos relativos dentro de uma instalação ARK
_WIN64_REL  = Path("ShooterGame") / "Binaries" / "Win64"
_ARKAPI_REL = _WIN64_REL / "ArkApi"

# Configuração padrão gerada na primeira instalação
_DEFAULT_CONFIG: Dict[str, Any] = {
    "Settings": {
        "ShopName":           "ARKLAND Shop",
        "UiKey":              "F3",
        "StartingPoints":     100,
        "DisableSellButton":  True,
        "DisableTradeButton": False,
    },
    "Database": {
        "Host":     "127.0.0.1",
        "Port":     3306,
        "User":     "arkland",
        "Password": "",
        "Database": "arkland_shop",
    },
    "Items": {
        "metal_ingot_100": {
            "Type":           "item",
            "Price":          10,
            "Description":    "100x Metal Ingot",
            "Blueprint":      "/Game/PrimalEarth/CoreBlueprints/Resources/PrimalItemResource_MetalIngot.PrimalItemResource_MetalIngot",
            "Quantity":       100,
            "Quality":        0.0,
            "ForceBlueprint": False,
        },
    },
    "Kits": {
        "starter": {
            "Price":         0,
            "Description":   "Kit inicial gratuito — um por conta",
            "DefaultAmount": 1,
            "Items": [
                {
                    "Blueprint":      "/Game/PrimalEarth/CoreBlueprints/Resources/PrimalItemResource_MetalIngot.PrimalItemResource_MetalIngot",
                    "Quantity":       200,
                    "Quality":        0.0,
                    "ForceBlueprint": False,
                },
            ],
            "Commands": [],
        },
    },
}


# ── Utilitários internos ─────────────────────────────────────────────────────

def _resolve_plugin_dlls() -> List[Path]:
    """Retorna todos os arquivos DLL do plugin (CustomShop + dependências)."""
    if getattr(sys, "frozen", False):
        base = Path(getattr(sys, "_MEIPASS", ""))
        plugins_dir = base / "plugins"
    else:
        # Modo desenvolvimento: raiz do workspace
        plugins_dir = Path(__file__).parent.parent / "plugin" / _PLUGIN_NAME / "bin"
    return list(plugins_dir.glob("*.dll")) if plugins_dir.exists() else []


def _resolve_dll_source() -> Optional[Path]:
    """Retorna o caminho da DLL principal (CustomShop.dll)."""
    dlls = _resolve_plugin_dlls()
    for p in dlls:
        if p.name.lower() == f"{_PLUGIN_NAME.lower()}.dll":
            return p
    return None


def _atomic_write(path: Path, data: Dict[str, Any]) -> None:
    """Gravação atômica via arquivo temporário + rename."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)
    tmp.replace(path)


# ── Classe principal ──────────────────────────────────────────────────────────

class PluginManager:
    """Gerencia o ciclo de vida do plugin CustomShop em um servidor ARK."""

    PLUGIN_NAME = _PLUGIN_NAME

    # ── Caminhos ─────────────────────────────────────────────────────────────

    @staticmethod
    def win64_dir(install_dir: str) -> Path:
        """Retorna o diretório Win64 do servidor ARK."""
        return Path(install_dir) / _WIN64_REL

    @staticmethod
    def arkapi_dir(install_dir: str) -> Path:
        """Retorna o diretório raiz do ArkApi dentro da instalação ARK."""
        return Path(install_dir) / _ARKAPI_REL

    @staticmethod
    def plugin_dir(install_dir: str) -> Path:
        """Retorna o diretório do plugin dentro do ArkApi."""
        return Path(install_dir) / _ARKAPI_REL / "Plugins" / _PLUGIN_NAME

    @staticmethod
    def config_path(install_dir: str) -> Path:
        """Retorna o caminho do config.json do plugin."""
        return PluginManager.plugin_dir(install_dir) / "config.json"

    # ── Detecção ─────────────────────────────────────────────────────────────

    @staticmethod
    def is_arkapi_installed(install_dir: str) -> bool:
        """Verifica se o ArkApi está instalado (diretório ArkApi existe)."""
        return PluginManager.arkapi_dir(install_dir).is_dir()

    @staticmethod
    def is_plugin_installed(install_dir: str) -> bool:
        """Verifica se a DLL do plugin está presente no diretório correto."""
        return (PluginManager.plugin_dir(install_dir) / f"{_PLUGIN_NAME}.dll").is_file()

    @staticmethod
    def dll_source() -> Optional[Path]:
        """Retorna o caminho da DLL fonte (bundled ou dev), ou None se não encontrada."""
        return _resolve_dll_source()

    # ── Instalação / remoção ─────────────────────────────────────────────────

    @staticmethod
    def install(install_dir: str, dll_path: Optional[str] = None) -> None:
        """
        Instala o plugin no servidor ARK.

        Cria o diretório do plugin, copia a DLL e gera um config.json padrão
        caso ainda não exista.

        Args:
            install_dir: Diretório raiz do servidor ARK.
            dll_path: Caminho opcional para a DLL. Se None, usa a DLL bundled/dev.

        Raises:
            FileNotFoundError: Se a DLL não for encontrada em nenhuma origem.
        """
        pdir = PluginManager.plugin_dir(install_dir)
        pdir.mkdir(parents=True, exist_ok=True)

        # Resolve a DLL de origem
        src = Path(dll_path) if dll_path else _resolve_dll_source()
        if src is None or not src.is_file():
            raise FileNotFoundError(
                "DLL do CustomShop não encontrada. "
                "Selecione o arquivo manualmente ou recompile o plugin."
            )

        shutil.copy2(str(src), str(pdir / f"{_PLUGIN_NAME}.dll"))

        # Copia DLLs de dependência (libmysql, libcrypto, libssl, …) para Win64/
        # O Windows não busca a pasta do plugin para dependências transitivas;
        # Win64/ está no search path porque é de onde o servidor é executado.
        win64 = PluginManager.win64_dir(install_dir)
        win64.mkdir(parents=True, exist_ok=True)
        for dep in _resolve_plugin_dlls():
            if dep.name.lower() != f"{_PLUGIN_NAME.lower()}.dll":
                shutil.copy2(str(dep), str(win64 / dep.name))

        # Cria config padrão apenas se ainda não existir
        cfg = pdir / "config.json"
        if not cfg.exists():
            _atomic_write(cfg, _DEFAULT_CONFIG)

    @staticmethod
    def uninstall(install_dir: str) -> None:
        """Remove completamente o diretório do plugin."""
        pdir = PluginManager.plugin_dir(install_dir)
        if pdir.exists():
            shutil.rmtree(str(pdir))

    # ── Configuração ─────────────────────────────────────────────────────────

    @staticmethod
    def load_config(install_dir: str) -> Dict[str, Any]:
        """Carrega o config.json do plugin. Retorna configuração padrão se o arquivo não existir."""
        path = PluginManager.config_path(install_dir)
        if not path.exists():
            import copy
            return copy.deepcopy(_DEFAULT_CONFIG)
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)

    @staticmethod
    def save_config(install_dir: str, data: Dict[str, Any]) -> None:
        """Salva o config.json do plugin de forma atômica."""
        _atomic_write(PluginManager.config_path(install_dir), data)

    # ── Conexão MySQL ─────────────────────────────────────────────────────────

    @staticmethod
    def mysql_available() -> bool:
        """Retorna True se mysql-connector-python está instalado."""
        return _MYSQL_AVAILABLE

    @staticmethod
    def _connect(db_cfg: Dict[str, Any]):
        """Abre e retorna uma conexão MySQL usando as configurações fornecidas."""
        if not _MYSQL_AVAILABLE:
            raise RuntimeError(
                "mysql-connector-python não está instalado.\n"
                "Execute: pip install mysql-connector-python"
            )
        return mysql.connector.connect(  # type: ignore[possibly-undefined]
            host=db_cfg.get("Host", "127.0.0.1"),
            port=int(db_cfg.get("Port", 3306)),
            user=db_cfg.get("User", ""),
            password=db_cfg.get("Password", ""),
            database=db_cfg.get("Database", "arkland_shop"),
            connection_timeout=5,
        )

    @staticmethod
    def test_connection(db_cfg: Dict[str, Any]) -> str:
        """Testa a conexão MySQL. Retorna '' em sucesso ou mensagem de erro."""
        try:
            conn = PluginManager._connect(db_cfg)
            conn.close()
            return ""
        except Exception as exc:
            return str(exc)

    # ── Log de transações ─────────────────────────────────────────────────────

    @staticmethod
    def get_transactions(
        db_cfg: Dict[str, Any],
        limit: int = 200,
        type_filter: str = "",
        steam_filter: str = "",
    ) -> List[Dict[str, Any]]:
        """
        Retorna as últimas `limit` transações do banco.

        Colunas: id, ts, type, steam_id, target_id, item_id, amount,
                 points_before, points_after
        """
        rows: List[Dict[str, Any]] = []
        conn = PluginManager._connect(db_cfg)
        try:
            cur = conn.cursor(dictionary=True)
            conditions = []
            params: list = []
            if type_filter:
                conditions.append("type = %s")
                params.append(type_filter)
            if steam_filter:
                conditions.append("(steam_id = %s OR target_id = %s)")
                params += [steam_filter, steam_filter]
            where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
            cur.execute(
                f"SELECT * FROM transactions {where} "
                f"ORDER BY ts DESC LIMIT %s",
                params + [limit],
            )
            rows = cur.fetchall()
            # Convert datetime objects to string for JSON-serialisability
            for r in rows:
                if isinstance(r.get("ts"), datetime):
                    r["ts"] = r["ts"].strftime("%Y-%m-%d %H:%M:%S")
        finally:
            conn.close()
        return rows

    # ── VIP ───────────────────────────────────────────────────────────────────

    @staticmethod
    def get_vip_list(db_cfg: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Retorna todos os jogadores VIP com steam_id, expires, tier, notes."""
        rows: List[Dict[str, Any]] = []
        conn = PluginManager._connect(db_cfg)
        try:
            cur = conn.cursor(dictionary=True)
            cur.execute(
                "SELECT steam_id, "
                "IFNULL(DATE_FORMAT(expires,'%Y-%m-%d %H:%i:%s'), 'permanente') AS expires,"
                "tier, IFNULL(notes,'') AS notes "
                "FROM vip_players ORDER BY expires IS NULL DESC, expires ASC"
            )
            rows = cur.fetchall()
        finally:
            conn.close()
        return rows

    @staticmethod
    def add_vip(
        db_cfg: Dict[str, Any],
        steam_id: str,
        days: int,
        tier: str = "vip",
        notes: str = "",
    ) -> None:
        """Adiciona ou atualiza um VIP. days=0 = permanente."""
        conn = PluginManager._connect(db_cfg)
        try:
            cur = conn.cursor()
            expires_expr = (
                "NULL" if days <= 0
                else f"DATE_ADD(NOW(), INTERVAL {int(days)} DAY)"
            )
            cur.execute(
                "INSERT INTO vip_players (steam_id, expires, tier, notes) "
                f"VALUES (%s, {expires_expr}, %s, %s) "
                "ON DUPLICATE KEY UPDATE "
                f"expires={expires_expr}, tier=%s, notes=%s",
                [steam_id, tier, notes, tier, notes],
            )
            conn.commit()
        finally:
            conn.close()

    @staticmethod
    def remove_vip(db_cfg: Dict[str, Any], steam_id: str) -> bool:
        """Remove um VIP. Retorna True se encontrado e removido."""
        conn = PluginManager._connect(db_cfg)
        try:
            cur = conn.cursor()
            cur.execute("DELETE FROM vip_players WHERE steam_id = %s", (steam_id,))
            conn.commit()
            return cur.rowcount > 0
        finally:
            conn.close()

    @staticmethod
    def get_player_points(db_cfg: Dict[str, Any], steam_id: str) -> Optional[int]:
        """Retorna o saldo de pontos de um jogador, ou None se não encontrado."""
        conn = PluginManager._connect(db_cfg)
        try:
            cur = conn.cursor()
            cur.execute("SELECT points FROM players WHERE steam_id = %s", (steam_id,))
            row = cur.fetchone()
            return row[0] if row else None
        finally:
            conn.close()

    @staticmethod
    def set_player_points(db_cfg: Dict[str, Any], steam_id: str, points: int) -> None:
        """Define o saldo de pontos de um jogador (cria se não existir)."""
        conn = PluginManager._connect(db_cfg)
        try:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO players (steam_id, points) VALUES (%s, %s) "
                "ON DUPLICATE KEY UPDATE points = %s",
                (steam_id, points, points),
            )
            conn.commit()
        finally:
            conn.close()
