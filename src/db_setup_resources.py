"""Recursos e helpers para instalação dos bancos arkland_shop + ark_permission (dev + PyInstaller)."""
from __future__ import annotations

import os
import re
import shutil
import sys
from pathlib import Path
from typing import Any, Optional

_PASSWORD_PLACEHOLDER = "SUA_SENHA_AQUI"
_DB_NAME = "arkland_shop"
_PERM_DB_NAME = "ark_permission"
_SHOP_USER = "arkland"


def project_resource_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS)  # type: ignore[attr-defined]
    return Path(__file__).resolve().parent.parent


def appdata_dir() -> Path:
    return Path(os.environ.get("APPDATA", Path.home())) / "ARKLAND-ServerManager"


def setup_sql_source_path() -> Path:
    """Localiza setup_db.sql no bundle, projeto ou APPDATA."""
    candidates = [
        project_resource_root() / "setup_db.sql",
        Path(__file__).resolve().parent.parent / "setup_db.sql",
    ]
    if getattr(sys, "frozen", False):
        candidates.append(Path(sys.executable).resolve().parent / "setup_db.sql")
    candidates.append(appdata_dir() / "setup_db.sql")
    for path in candidates:
        if path.is_file():
            return path
    return candidates[0]


def ensure_setup_sql_cached() -> Path:
    """Garante cópia em APPDATA para builds e instaladores."""
    target = appdata_dir() / "setup_db.sql"
    if target.is_file():
        return target
    source = setup_sql_source_path()
    if source.is_file():
        try:
            appdata_dir().mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
            return target
        except Exception:
            return source
    return target


def load_setup_sql_template() -> str:
    path = ensure_setup_sql_cached()
    if path.is_file():
        return path.read_text(encoding="utf-8")
    raise FileNotFoundError(
        f"setup_db.sql não encontrado. Esperado em:\n{path}"
    )


def build_setup_sql(arkland_password: str) -> str:
    pwd = arkland_password.strip()
    if not pwd:
        raise ValueError("Defina uma senha para o usuário 'arkland'.")
    return load_setup_sql_template().replace(_PASSWORD_PLACEHOLDER, pwd)


def split_sql_statements(sql: str) -> list[str]:
    """Divide SQL em statements ignorando comentários e linhas vazias."""
    statements: list[str] = []
    for raw in sql.replace("\r\n", "\n").split(";"):
        lines = []
        for line in raw.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("--"):
                continue
            lines.append(line)
        stmt = "\n".join(lines).strip()
        if stmt:
            statements.append(stmt)
    return statements


def execute_setup_sql(conn: Any, arkland_password: str) -> tuple[int, list[str]]:
    """Executa setup no connection pymysql. Retorna (ok_count, errors)."""
    sql = build_setup_sql(arkland_password)
    errors: list[str] = []
    executed = 0
    cur = conn.cursor()
    try:
        for stmt in split_sql_statements(sql):
            try:
                cur.execute(stmt)
                executed += 1
            except Exception as exc:
                errors.append(str(exc))
        conn.commit()
    finally:
        cur.close()
    return executed, errors


def test_connection(
    *,
    host: str,
    port: int,
    user: str,
    password: str,
    database: str = "",
) -> tuple[bool, str]:
    """Testa conexão pymysql; retorna (ok, mensagem)."""
    try:
        import pymysql  # type: ignore[import-untyped]
    except ImportError:
        return False, "pymysql não instalado."

    kwargs: dict = dict(
        host=host or "127.0.0.1",
        port=int(port or 3306),
        user=user,
        password=password,
        connect_timeout=5,
    )
    if database:
        kwargs["database"] = database
    try:
        conn = pymysql.connect(**kwargs)
        conn.close()
        db_msg = f" / {database}" if database else ""
        return True, f"Conectado a {kwargs['host']}:{kwargs['port']}{db_msg}"
    except Exception as exc:
        return False, str(exc)


def database_exists(conn: Any, name: str = _DB_NAME) -> bool:
    cur = conn.cursor()
    try:
        cur.execute("SHOW DATABASES LIKE %s", (name,))
        return cur.fetchone() is not None
    finally:
        cur.close()


def permission_database_exists(conn: Any, name: str = _PERM_DB_NAME) -> bool:
    """Verifica se o banco ark_permission (Permissions.dll) existe."""
    return database_exists(conn, name)


def save_shop_connection_prefs(
    *,
    host: str,
    port: int,
    user: str,
    password: str,
    database: str = _DB_NAME,
    permission_database: str = _PERM_DB_NAME,
) -> None:
    from .pages.db_local_server import DbLocalServer
    from .shop_integration import _is_placeholder_db_password

    if _is_placeholder_db_password(password):
        return

    prefs = DbLocalServer._load_prefs()
    prefs["last_connection"] = {
        "host": host,
        "port": port,
        "user": user,
        "password": password,
        "database": database,
        "permission_database": permission_database,
    }
    prefs["shop_db"] = {
        "host": host,
        "port": port,
        "user": user,
        "password": password,
        "database": database,
        "permission_database": permission_database,
    }
    DbLocalServer._save_prefs(prefs)
