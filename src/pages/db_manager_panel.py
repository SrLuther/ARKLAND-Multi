"""Gerenciador de banco de dados MySQL/MariaDB integrado ao ARKLAND."""
from __future__ import annotations

import subprocess
import sys
import threading
import tkinter as tk
import tkinter.ttk as ttk
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional

import customtkinter as ctk  # type: ignore[reportMissingImports]

from ..db_setup_resources import (
    _DB_NAME,
    _PERM_DB_NAME,
    database_exists,
    ensure_mysql_user_both_hosts,
    ensure_setup_sql_cached,
    load_setup_sql_template,
    permission_database_exists,
    save_shop_connection_prefs,
)
from ..shop_integration import (
    DEFAULT_REMOTE_SHOP_HOST,
    iter_shop_servers,
    permissions_dll_installed,
    resolve_shop_db_password,
)
from ..ui_constants import get_theme
from .db_local_server import DbLocalServer
from .db_setup_wizard import show_db_setup_wizard

if TYPE_CHECKING:
    from ..app_tek import ARKTEKApp

_LOCAL_DB_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})
_CELL_DISPLAY_MAX = 200
_TREE_INSERT_BATCH = 25


def _configure_db_browser_ttk(theme: dict) -> None:
    """Treeviews ttk com cores do tema ativo (clam permite fieldbackground no Windows)."""
    style = ttk.Style()
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass

    tv_bg = theme.get("input_bg", theme["card_bg"])
    tv_fg = theme["text_primary"]
    head_bg = theme.get("card_border", theme["separator"])
    head_fg = theme["text_secondary"]
    sel_bg = theme.get("accent_hover", theme.get("accent_muted_bg", "#164e63"))
    sel_fg = theme.get("accent_label", theme["accent"])

    for prefix, font in (("DB", ("Segoe UI", 10)),
                         ("Data", ("Consolas", 10)),
                         ("Struct", ("Consolas", 10))):
        style.configure(
            f"{prefix}.Treeview",
            background=tv_bg,
            foreground=tv_fg,
            fieldbackground=tv_bg,
            rowheight=26,
            font=font,
            borderwidth=0,
        )
        style.configure(
            f"{prefix}.Treeview.Heading",
            background=head_bg,
            foreground=head_fg,
            font=("Segoe UI", 10, "bold"),
            relief="flat",
        )
        style.map(
            f"{prefix}.Treeview",
            background=[("selected", sel_bg)],
            foreground=[("selected", sel_fg)],
        )


def _db_scrollbar(parent, orient: str, command, theme: dict) -> tk.Scrollbar:
    """Scrollbar nativa com cores do tema — evita faixa branca do ttk no Windows."""
    return tk.Scrollbar(
        parent,
        orient=orient,
        command=command,
        bg=theme.get("card_border", theme["separator"]),
        troughcolor=theme["bg"],
        activebackground=theme["accent"],
        highlightthickness=0,
        borderwidth=0,
        width=12,
    )


def _ttk_tree_host(parent, bg: str, *, horizontal_scroll: bool = False) -> tk.Frame:
    """Frame tk puro — ttk.Treeview redimensiona mal dentro de CTkFrame."""
    host = tk.Frame(parent, bg=bg, highlightthickness=1,
                    highlightbackground=bg, highlightcolor=bg)
    host.grid_rowconfigure(0, weight=1)
    host.grid_columnconfigure(0, weight=1)
    if horizontal_scroll:
        host.grid_rowconfigure(1, weight=0)
    return host


def _bind_treeview_fill_rows(
    tree: ttk.Treeview,
    host: tk.Widget,
    *,
    row_px: int = 26,
    min_rows: int = 12,
) -> None:
    """Treeview usa height em linhas, não pixels — ajusta ao redimensionar o host."""
    def _resize(_event: tk.Event | None = None) -> None:
        try:
            h = host.winfo_height()
            if h < row_px * 2:
                return
            rows = max(min_rows, (h - 4) // row_px)
            if int(tree.cget("height")) != rows:
                tree.configure(height=rows)
        except tk.TclError:
            pass

    host.bind("<Configure>", _resize, add="+")
    host.after(80, _resize)
    host.after(400, _resize)


def _is_local_db_host(host: str) -> bool:
    return (host or "").strip().lower() in _LOCAL_DB_HOSTS


def _apply_connection_prefs(state: Any, prefs: dict, *, default_user: str) -> None:
    state.host = prefs.get("host", "127.0.0.1")
    state.port = int(prefs.get("port", 3306))
    state.user = prefs.get("user", default_user)
    state.password = prefs.get("password", "")
    state.database = prefs.get("database", "")


def _is_ephemeral_local_root(prefs: dict) -> bool:
    """Conexão root@localhost gerada pelo auto-connect — não deve sobrescrever prefs da loja."""
    if not prefs:
        return False
    return (
        _is_local_db_host(prefs.get("host", ""))
        and (prefs.get("user") or "root").strip().lower() == "root"
    )


def _shop_config_db_prefs(app: "ARKTEKApp") -> dict:
    """Credenciais MySQL da aba Loja → Web Store (orders_db_*)."""
    try:
        shop = app._shop_config  # type: ignore[attr-defined]
    except Exception:
        return {}
    if not shop:
        return {}
    host = (shop.orders_db_host or "").strip()
    user = (shop.orders_db_user or "").strip()
    if not host and not user:
        return {}
    return {
        "host": host or DEFAULT_REMOTE_SHOP_HOST,
        "port": int(shop.orders_db_port or 3306),
        "user": user or "arkland",
        "password": resolve_shop_db_password(shop),
        "database": (shop.orders_db_name or "").strip() or _DB_NAME,
    }


def _resolve_initial_connection(state: Any, app: "ARKTEKApp", all_prefs: dict) -> None:
    """Prioridade: shop_db remoto → config da loja → shop_db → last_connection (≠ root efêmero)."""
    shop_prefs = all_prefs.get("shop_db") or {}
    conn_prefs = all_prefs.get("last_connection") or {}
    app_shop = _shop_config_db_prefs(app)

    if shop_prefs.get("host") and not _is_local_db_host(shop_prefs.get("host", "")):
        _apply_connection_prefs(state, shop_prefs, default_user="arkland")
        return

    if app_shop.get("host") and not _is_local_db_host(app_shop.get("host", "")):
        _apply_connection_prefs(state, app_shop, default_user="arkland")
        return

    if app_shop.get("user"):
        _apply_connection_prefs(state, app_shop, default_user="arkland")
        return

    if shop_prefs:
        _apply_connection_prefs(state, shop_prefs, default_user="arkland")
        return

    if conn_prefs and not _is_ephemeral_local_root(conn_prefs):
        _apply_connection_prefs(state, conn_prefs, default_user="root")
        return

    if app_shop:
        _apply_connection_prefs(state, app_shop, default_user="arkland")
        return

    state.host = "127.0.0.1"
    state.port = 3306
    state.user = "root"
    state.password = ""
    state.database = _DB_NAME


def _connection_prefs_from_state(state: Any) -> dict:
    return {
        "host": state.host,
        "port": state.port,
        "user": state.user,
        "password": state.password,
        "database": state.database or _DB_NAME,
    }


# ── tentativa de importar pymysql ──────────────────────────────────────────
def _try_import_pymysql():
    """Tenta importar pymysql; retorna (módulo, ok)."""
    try:
        import pymysql  # type: ignore[reportMissingImports]
        import pymysql.cursors
        return pymysql, True
    except ImportError:
        return None, False

pymysql, _PYMYSQL_OK = _try_import_pymysql()


def _install_pymysql_sync() -> bool:
    """Instala pymysql via pip. Retorna True se bem-sucedido."""
    try:
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "pymysql", "--quiet"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        return True
    except Exception:
        return False


# ══════════════════════════════════════════════════════════════════════════════
#  Estado da conexão (por painel — cada instância é independente)
# ══════════════════════════════════════════════════════════════════════════════

class _DBState:
    def __init__(self) -> None:
        self.conn: Any = None
        self.host     = ""
        self.port     = 3306
        self.user     = ""
        self.password = ""
        self.database = ""        # banco inicial (opcional)
        self.selected_db: str = ""
        self.selected_table: str = ""
        self._lock = threading.Lock()

    def is_connected(self) -> bool:
        if not self.conn:
            return False
        try:
            with self._lock:
                self.conn.ping(reconnect=True)
            return True
        except Exception:
            return False

    def close(self) -> None:
        with self._lock:
            if self.conn:
                try:
                    self.conn.close()
                except Exception:
                    pass
                self.conn = None


def _cell_display(value: Any) -> str:
    if value is None:
        return "NULL"
    s = str(value)
    if len(s) > _CELL_DISPLAY_MAX:
        return s[:_CELL_DISPLAY_MAX] + "…"
    return s


# ══════════════════════════════════════════════════════════════════════════════
#  Funções de consulta
# ══════════════════════════════════════════════════════════════════════════════

def _query(state: _DBState, sql: str, args=None) -> list[dict]:
    if not state.conn:
        raise RuntimeError("Sem conexão com o banco de dados.")
    with state._lock:
        try:
            state.conn.ping(reconnect=True)
        except Exception:
            pass
        with state.conn.cursor() as cur:
            cur.execute(sql, args or ())
            return cur.fetchall()  # type: ignore[return-value]


def _execute(state: _DBState, sql: str, args=None) -> int:
    if not state.conn:
        raise RuntimeError("Sem conexão com o banco de dados.")
    with state._lock:
        try:
            state.conn.ping(reconnect=True)
        except Exception:
            pass
        with state.conn.cursor() as cur:
            cur.execute(sql, args or ())
        state.conn.commit()
        return cur.rowcount  # type: ignore[return-value]


def _list_databases(state: _DBState) -> list[str]:
    rows = _query(state, "SHOW DATABASES")
    skip = {"information_schema", "performance_schema", "mysql", "sys"}
    return [r["Database"] for r in rows if r["Database"] not in skip]


def _list_tables(state: _DBState, db: str) -> list[str]:
    rows = _query(state, f"SHOW TABLES FROM `{db}`")
    key = f"Tables_in_{db}"
    return [r[key] for r in rows]


def _table_columns(state: _DBState, db: str, table: str) -> list[dict]:
    return _query(state, f"SHOW FULL COLUMNS FROM `{db}`.`{table}`")


def _table_rows(state: _DBState, db: str, table: str,
                limit: int = 50, offset: int = 0) -> tuple[list[dict], int]:
    rows = _query(state, f"SELECT * FROM `{db}`.`{table}` LIMIT %s OFFSET %s",
                  (limit, offset))
    count_row = _query(state, f"SELECT COUNT(*) AS n FROM `{db}`.`{table}`")
    total = count_row[0]["n"] if count_row else 0
    return rows, total


_CUSTOMSHOP_PLAYERS_DDL = """
CREATE TABLE IF NOT EXISTS players (
  steam_id  VARCHAR(20)  PRIMARY KEY NOT NULL,
  points    INT          NOT NULL DEFAULT 0,
  kits      TEXT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
"""


def _table_field_names(state: _DBState, db: str, table: str) -> set[str]:
    return {str(c.get("Field", "")).lower() for c in _table_columns(state, db, table)}


def _customshop_players_schema_ok(state: _DBState) -> tuple[bool, str]:
    """True se arkland_shop.players tem colunas steam_id + points (CustomShop)."""
    if not state.is_connected():
        return False, "Sem conexão"
    if _DB_NAME not in _list_databases(state):
        return False, f"Banco {_DB_NAME} não existe"
    if "players" not in _list_tables(state, _DB_NAME):
        return False, "Tabela players não existe em arkland_shop"
    cols = _table_field_names(state, _DB_NAME, "players")
    if "steam_id" in cols and "points" in cols:
        return True, ""
    if "steamid" in cols:
        return (
            False,
            "Tabela players em arkland_shop usa schema do Permissions (SteamId) — "
            "CustomShop não consegue inserir jogadores",
        )
    return False, f"Schema inesperado em arkland_shop.players: {', '.join(sorted(cols))}"


def _recreate_customshop_players_table(state: _DBState) -> None:
    _execute(state, f"USE `{_DB_NAME}`")
    _execute(state, "DROP TABLE IF EXISTS players")
    _execute(state, _CUSTOMSHOP_PLAYERS_DDL.strip())


def _sync_shop_players_from_permissions(state: _DBState, starting_points: int = 100) -> int:
    """Cria jogadores no CustomShop a partir de ark_permission.players."""
    if _PERM_DB_NAME not in _list_databases(state):
        raise RuntimeError(f"Banco {_PERM_DB_NAME} não encontrado")
    if "players" not in _list_tables(state, _PERM_DB_NAME):
        raise RuntimeError(f"Tabela players não existe em {_PERM_DB_NAME}")

    perm_cols = _table_field_names(state, _PERM_DB_NAME, "players")
    steam_col = "SteamId" if "steamid" in perm_cols else "steam_id"
    if steam_col.lower() not in perm_cols:
        raise RuntimeError("Coluna SteamId não encontrada em ark_permission.players")

    ok, msg = _customshop_players_schema_ok(state)
    if not ok:
        if "permissions" in msg.lower() or "não existe" in msg.lower() or "inesperado" in msg.lower():
            _recreate_customshop_players_table(state)
        else:
            raise RuntimeError(msg)

    pts = max(0, int(starting_points))
    sql = (
        f"INSERT IGNORE INTO `{_DB_NAME}`.players (steam_id, points, kits) "
        f"SELECT CAST(`{steam_col}` AS CHAR), {pts}, '{{}}' "
        f"FROM `{_PERM_DB_NAME}`.players "
        f"WHERE `{steam_col}` IS NOT NULL AND `{steam_col}` != ''"
    )
    return _execute(state, sql)


_DB_BROWSER_MIN_HEIGHT = 720  # área Dados/Estrutura/SQL — ~3× o mínimo anterior (240px)

def _make_collapsible_card(
    parent: ctk.CTkFrame,
    row: int,
    title: str,
    *,
    card_bg: str,
    accent: str,
    hover_bg: str,
    start_collapsed: bool = True,
    padx: int = 12,
    pady: tuple[int, int] = (10, 0),
) -> tuple[ctk.CTkFrame, ctk.CTkFrame]:
    """Cartão com cabeçalho clicável; retorna (wrapper, frame interno para conteúdo)."""
    wrapper = ctk.CTkFrame(parent, fg_color=card_bg, corner_radius=8)
    wrapper.grid(row=row, column=0, sticky="ew", padx=padx, pady=pady)
    wrapper.grid_columnconfigure(0, weight=1)

    expanded = [not start_collapsed]
    arrow_var = tk.StringVar(value=("▶ " if start_collapsed else "▼ ") + title)
    content = ctk.CTkFrame(wrapper, fg_color="transparent")
    content.grid_columnconfigure(0, weight=1)

    def _toggle() -> None:
        expanded[0] = not expanded[0]
        if expanded[0]:
            arrow_var.set("▼ " + title)
            content.grid(row=1, column=0, sticky="ew", padx=6, pady=(0, 8))
        else:
            arrow_var.set("▶ " + title)
            content.grid_remove()

    ctk.CTkButton(
        wrapper, textvariable=arrow_var, anchor="w",
        fg_color="transparent", hover_color=hover_bg,
        text_color=accent, font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
        height=30, corner_radius=6, command=_toggle,
    ).grid(row=0, column=0, sticky="ew", padx=6, pady=(4, 2))

    if not start_collapsed:
        content.grid(row=1, column=0, sticky="ew", padx=6, pady=(0, 8))

    return wrapper, content


def build_db_manager_panel(app: "ARKTEKApp", parent: ctk.CTkFrame) -> None:
    theme   = get_theme("tek")
    bg      = theme["bg"]
    card_bg = theme["card_bg"]
    accent  = theme["accent"]
    t_pri   = theme["text_primary"]
    t_sec   = theme["text_secondary"]
    t_mut   = theme["text_muted"]
    sep_col = theme["separator"]

    state = _DBState()

    try:
        ensure_setup_sql_cached()
    except Exception:
        pass

    # Carrega credenciais: shop_db / config da loja têm prioridade sobre root local efêmero
    _all_prefs = DbLocalServer._load_prefs()
    _resolve_initial_connection(state, app, _all_prefs)

    parent.grid_rowconfigure(0, weight=0)
    parent.grid_rowconfigure(1, weight=1)
    parent.grid_columnconfigure(0, weight=1)

    local_srv = DbLocalServer()

    # ── Cabeçalho ──────────────────────────────────────────────────────────
    hdr = ctk.CTkFrame(parent, fg_color=card_bg, corner_radius=0, height=44)
    hdr.grid(row=0, column=0, sticky="ew")
    hdr.grid_propagate(False)
    hdr.grid_columnconfigure(99, weight=1)

    ctk.CTkLabel(hdr, text="🗄  Gerenciador de Banco de Dados",
                 font=ctk.CTkFont(family="Segoe UI", size=16, weight="bold"),
                 text_color=accent).grid(row=0, column=0, padx=16, pady=10, sticky="w")

    # ── Corpo rolável (backup + browser não cortam na viewport) ───────────
    body = ctk.CTkScrollableFrame(parent, fg_color=bg, corner_radius=0)
    body.grid(row=1, column=0, sticky="nsew")
    body.grid_columnconfigure(0, weight=1)

    # ── Seção: Servidor Local (colapsável — libera espaço para o browser) ──
    _hover_bg = theme.get("accent_muted_bg", "#164e63")
    _, srv_content = _make_collapsible_card(
        body, 0, "Servidor Local (MariaDB portable)",
        card_bg=card_bg, accent=accent, hover_bg=_hover_bg,
        start_collapsed=True, pady=(6, 0),
    )

    _admin_ok = DbLocalServer.is_admin()
    _admin_badge = ("🛡 Admin" if _admin_ok else "⚠ Sem privilégios de admin")
    _admin_color = "#22c55e" if _admin_ok else "#ef4444"
    _hdr_row = ctk.CTkFrame(srv_content, fg_color="transparent")
    _hdr_row.grid(row=0, column=0, padx=8, pady=(0, 4), sticky="w")
    ctk.CTkLabel(_hdr_row, text=_admin_badge,
                 font=ctk.CTkFont(family="Segoe UI", size=10),
                 text_color=_admin_color).pack(side="left")

    srv_row = ctk.CTkFrame(srv_content, fg_color="transparent")
    srv_row.grid(row=1, column=0, columnspan=100, padx=8, pady=(0, 4), sticky="ew")

    _srv_dot = ctk.CTkLabel(srv_row, text="●", text_color="#ef4444",
                             font=ctk.CTkFont(size=13))
    _srv_dot.grid(row=0, column=0, padx=(0, 4))

    _srv_status_var = tk.StringVar(value="Não instalado")
    _srv_status_lbl = ctk.CTkLabel(srv_row, textvariable=_srv_status_var,
                                    font=ctk.CTkFont(family="Segoe UI", size=11),
                                    text_color=t_sec)
    _srv_status_lbl.grid(row=0, column=1, padx=(0, 16))

    def _make_srv_btn(text, col, **kw):
        b = ctk.CTkButton(srv_row, text=text, width=110, height=28,
                          corner_radius=6,
                          font=ctk.CTkFont(family="Segoe UI", size=10),
                          **kw)
        b.grid(row=0, column=col, padx=(0, 6))
        return b

    _btn_download = _make_srv_btn("⬇ Instalar MariaDB", 2,
                                   fg_color=theme.get("accent_muted_bg", "#164e63"),
                                   text_color=accent)
    _btn_srv_start = _make_srv_btn("▶ Iniciar servidor", 3,
                                    fg_color="#14532d", text_color="#86efac")
    _btn_srv_stop  = _make_srv_btn("■ Parar servidor",  4,
                                    fg_color="#7f1d1d", text_color="#fca5a5")

    # Firewall
    _fw_dot = ctk.CTkLabel(srv_row, text="🔒", font=ctk.CTkFont(size=12))
    _fw_dot.grid(row=0, column=5, padx=(8, 4))
    _fw_var = tk.StringVar(value="Firewall: verificando...")
    ctk.CTkLabel(srv_row, textvariable=_fw_var,
                 font=ctk.CTkFont(family="Segoe UI", size=10),
                 text_color=t_mut).grid(row=0, column=6, padx=(0, 8))
    _btn_fw = ctk.CTkButton(srv_row, text="Abrir porta 3306",
                             width=120, height=28, corner_radius=6,
                             fg_color=theme.get("accent_muted_bg", "#164e63"),
                             text_color=accent,
                             font=ctk.CTkFont(size=10))
    _btn_fw.grid(row=0, column=7, padx=(0, 6))

    # Checkbox auto-start
    _autostart_var = tk.BooleanVar(value=DbLocalServer.get_autostart())
    ctk.CTkCheckBox(srv_row, text="Iniciar com o app",
                    variable=_autostart_var,
                    font=ctk.CTkFont(family="Segoe UI", size=10),
                    text_color=t_sec, checkbox_width=14, checkbox_height=14,
                    fg_color=accent, hover_color=theme["accent_hover"],
                    command=lambda: DbLocalServer.set_autostart(_autostart_var.get())
                    ).grid(row=0, column=8, padx=(8, 0))

    # ── Funções do servidor local ──────────────────────────────────────────

    def _refresh_srv_ui() -> None:
        installed  = local_srv.is_installed()
        running    = local_srv.is_running()
        fw_ok      = DbLocalServer.check_firewall_rule()

        if running:
            _srv_dot.configure(text_color="#22c55e")
            _srv_status_var.set("Rodando  —  127.0.0.1:3306")
        elif installed:
            _srv_dot.configure(text_color="#f59e0b")
            _srv_status_var.set("Instalado / parado")
        else:
            _srv_dot.configure(text_color="#ef4444")
            _srv_status_var.set("Não instalado")

        _btn_download.configure(state="disabled" if installed else "normal")
        _btn_srv_start.configure(state="normal" if (installed and not running) else "disabled")
        _btn_srv_stop.configure(state="normal" if running else "disabled")

        if fw_ok:
            _fw_var.set("Firewall: porta 3306 aberta ✓")
            _fw_dot.configure(text="🔓")
            _btn_fw.configure(state="disabled")
        else:
            _fw_var.set("Firewall: porta 3306 bloqueada")
            _fw_dot.configure(text="🔒")
            _btn_fw.configure(state="normal")

        # Preenche root local só se os campos estiverem vazios e não houver credenciais da loja
        if running and _is_local_db_host(_v_host.get()):
            shop_prefs = DbLocalServer._load_prefs().get("shop_db") or {}
            app_shop = _shop_config_db_prefs(app)
            has_shop_user = (
                (shop_prefs.get("user") or "").strip().lower() not in ("", "root")
                or (app_shop.get("user") or "").strip().lower() not in ("", "root")
            )
            has_remote = (
                (shop_prefs.get("host") and not _is_local_db_host(shop_prefs.get("host", "")))
                or (app_shop.get("host") and not _is_local_db_host(app_shop.get("host", "")))
            )
            current_user = (_v_user.get() or "").strip().lower()
            if not has_remote and not has_shop_user and current_user in ("", "root"):
                if not current_user:
                    _v_user.set("root")
                if not (_v_pass.get() or "").strip():
                    _v_pass.set(local_srv.get_root_password())
            if not (_v_db.get() or "").strip():
                _v_db.set(_DB_NAME)

    def _do_download() -> None:
        _btn_download.configure(state="disabled")
        _srv_status_var.set("Preparando...")

        def _prog(msg: str) -> None:
            parent.after(0, lambda m=msg: _srv_status_var.set(m))

        def _done(ok: bool, msg: str) -> None:
            def _update():
                if ok:
                    _refresh_srv_ui()
                    _do_start()
                else:
                    _srv_status_var.set(f"Erro: {msg}")
                    _btn_download.configure(state="normal")
            parent.after(0, _update)

        local_srv.download_and_install(on_progress=_prog, on_done=_done)

    _after_start_hooks: list = []   # callbacks chamados após start bem-sucedido

    def _do_start() -> None:
        _btn_srv_start.configure(state="disabled")
        _srv_status_var.set("Iniciando...")

        def _worker():
            try:
                ok, msg = local_srv.start()
            except Exception as exc:
                ok, msg = False, str(exc)

            def _update():
                _refresh_srv_ui()
                if ok:
                    for hook in _after_start_hooks:
                        try:
                            hook()
                        except Exception:
                            pass
                else:
                    from tkinter import messagebox
                    messagebox.showerror(
                        "Erro ao iniciar MariaDB",
                        f"{msg}\n\nLog: {local_srv.log_path}",
                        parent=parent,
                    )
            parent.after(0, _update)

        threading.Thread(target=_worker, daemon=True).start()

    def _do_stop() -> None:
        _btn_srv_stop.configure(state="disabled")
        _srv_status_var.set("Parando...")
        threading.Thread(target=lambda: (local_srv.stop(),
                                          parent.after(0, _refresh_srv_ui)),
                          daemon=True).start()

    def _do_firewall() -> None:
        _btn_fw.configure(state="disabled", text="Aplicando...")

        def _worker():
            ok, msg = DbLocalServer.create_firewall_rule()

            def _update():
                if ok:
                    _fw_var.set("Firewall: porta 3306 aberta ✓")
                    _fw_dot.configure(text="🔓")
                    _btn_fw.configure(state="disabled", text="Abrir porta 3306")
                else:
                    _fw_var.set(f"Firewall: {msg[:60]}")
                    _fw_dot.configure(text="🔒")
                    _btn_fw.configure(state="normal", text="Abrir porta 3306")
                from tkinter import messagebox
                if ok:
                    messagebox.showinfo("Firewall", "Porta 3306 liberada com sucesso!", parent=parent)
                else:
                    messagebox.showerror("Firewall — erro", f"Não foi possível criar a regra:\n\n{msg}", parent=parent)

            parent.after(0, _update)

        threading.Thread(target=_worker, daemon=True).start()

    _btn_download.configure(command=_do_download)
    _btn_srv_start.configure(command=_do_start)
    _btn_srv_stop.configure(command=_do_stop)
    _btn_fw.configure(command=_do_firewall)

    # Verifica status inicial em background
    threading.Thread(target=lambda: parent.after(200, _refresh_srv_ui),
                     daemon=True).start()

    # ── Barra de conexão ───────────────────────────────────────────────────
    conn_bar = ctk.CTkFrame(body, fg_color=card_bg, corner_radius=8)
    conn_bar.grid(row=1, column=0, sticky="ew", padx=12, pady=(4, 4))

    _v_host   = tk.StringVar(value=state.host)
    _v_port   = tk.StringVar(value=str(state.port))
    _v_user   = tk.StringVar(value=state.user)
    _v_pass   = tk.StringVar(value=state.password)
    _v_db     = tk.StringVar(value=state.database)
    _v_status = tk.StringVar(value="Desconectado")

    def _lbl(parent, text):
        return ctk.CTkLabel(parent, text=text,
                            font=ctk.CTkFont(family="Segoe UI", size=11),
                            text_color=t_sec)

    def _entry(parent, var, width=120, show=""):
        return ctk.CTkEntry(parent, textvariable=var, width=width,
                            fg_color=theme.get("input_bg", "#1e293b"),
                            text_color=t_pri, border_color=sep_col,
                            show=show,
                            font=ctk.CTkFont(family="Segoe UI", size=11))

    col = 0
    _lbl(conn_bar, "Host").grid(row=0, column=col, padx=(14, 4), pady=10)
    col += 1
    _entry(conn_bar, _v_host, 140).grid(row=0, column=col, padx=(0, 8), pady=10)
    col += 1
    _lbl(conn_bar, "Porta").grid(row=0, column=col, padx=(0, 4))
    col += 1
    _entry(conn_bar, _v_port, 60).grid(row=0, column=col, padx=(0, 8))
    col += 1
    _lbl(conn_bar, "Usuário").grid(row=0, column=col, padx=(0, 4))
    col += 1
    _entry(conn_bar, _v_user, 100).grid(row=0, column=col, padx=(0, 8))
    col += 1
    _lbl(conn_bar, "Senha").grid(row=0, column=col, padx=(0, 4))
    col += 1
    _entry(conn_bar, _v_pass, 100, show="•").grid(row=0, column=col, padx=(0, 8))
    col += 1
    _lbl(conn_bar, "Banco").grid(row=0, column=col, padx=(0, 4))
    col += 1
    _entry(conn_bar, _v_db, 120).grid(row=0, column=col, padx=(0, 12))
    col += 1

    _status_dot = ctk.CTkLabel(conn_bar, text="●", text_color="#ef4444",
                               font=ctk.CTkFont(size=14))
    _status_dot.grid(row=0, column=col, padx=(0, 4))
    col += 1
    _status_lbl = ctk.CTkLabel(conn_bar, textvariable=_v_status,
                               font=ctk.CTkFont(family="Segoe UI", size=11),
                               text_color=t_sec)
    _status_lbl.grid(row=0, column=col, padx=(0, 14))
    col += 1

    conn_bar.grid_columnconfigure(col, weight=1)
    col += 1

    _btn_connect    = ctk.CTkButton(conn_bar, text="Conectar", width=90, height=30,
                                    fg_color=accent, text_color="#000",
                                    font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
                                    corner_radius=6)
    _btn_connect.grid(row=0, column=col, padx=(0, 6), pady=8)
    col += 1
    _btn_disconnect = ctk.CTkButton(conn_bar, text="Desconectar", width=100, height=30,
                                    fg_color=theme.get("danger", "#7f1d1d"),
                                    text_color=t_pri, corner_radius=6,
                                    font=ctk.CTkFont(family="Segoe UI", size=11),
                                    state="disabled")
    _btn_disconnect.grid(row=0, column=col, padx=(0, 6), pady=8)
    col += 1

    _reload_fn_box: list = [lambda: None]
    _btn_reload_db = ctk.CTkButton(conn_bar, text="⟳ Recarregar", width=110, height=30,
                                   fg_color=theme.get("accent_muted_bg", "#164e63"),
                                   text_color=accent, corner_radius=6,
                                   font=ctk.CTkFont(family="Segoe UI", size=11),
                                   state="disabled",
                                   command=lambda: _reload_fn_box[0]())
    _btn_reload_db.grid(row=0, column=col, padx=(0, 6), pady=8)
    col += 1

    _btn_wizard = ctk.CTkButton(conn_bar, text="🧙 Assistente", width=110, height=30,
                                fg_color=theme.get("accent_muted_bg", "#164e63"),
                                text_color=accent, corner_radius=6,
                                font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"))
    _btn_wizard.grid(row=0, column=col, padx=(0, 14), pady=8)

    _connect_ready: list = []
    _pending_connect_after_wizard = [False]

    def _on_wizard_done() -> None:
        prefs = DbLocalServer._load_prefs().get("shop_db", {})
        if prefs:
            _v_host.set(prefs.get("host", "127.0.0.1"))
            _v_port.set(str(prefs.get("port", 3306)))
            _v_user.set(prefs.get("user", "arkland"))
            _v_pass.set(prefs.get("password", ""))
            _v_db.set(prefs.get("database", "arkland_shop"))
        _pending_connect_after_wizard[0] = True
        if _connect_ready:
            fn = _connect_ready[0] if _connect_ready else None
            if fn:
                _pending_connect_after_wizard[0] = False
                fn()

    def _open_wizard_early() -> None:
        show_db_setup_wizard(parent, local_srv, state, on_connected=_on_wizard_done)

    _btn_wizard.configure(command=_open_wizard_early)

    # Status dos bancos ARKLAND (linha 1 da barra de conexão)
    _shop_db_status = tk.StringVar(value=f"{_DB_NAME}: —")
    _perm_db_status = tk.StringVar(value=f"{_PERM_DB_NAME}: —")
    _perm_warn_var = tk.StringVar(value="")

    status_row = ctk.CTkFrame(conn_bar, fg_color="transparent")
    status_row.grid(row=1, column=0, columnspan=20, sticky="ew", padx=14, pady=(0, 8))

    ctk.CTkLabel(status_row, textvariable=_shop_db_status,
                 font=ctk.CTkFont(size=10), text_color=t_sec
                 ).pack(side="left", padx=(0, 12))
    ctk.CTkLabel(status_row, textvariable=_perm_db_status,
                 font=ctk.CTkFont(size=10), text_color=t_sec
                 ).pack(side="left", padx=(0, 12))

    def _switch_db(name: str) -> None:
        _v_db.set(name)

    ctk.CTkButton(status_row, text=_DB_NAME, width=100, height=22,
                  font=ctk.CTkFont(size=10),
                  command=lambda: _switch_db(_DB_NAME)).pack(side="left", padx=(0, 4))
    ctk.CTkButton(status_row, text=_PERM_DB_NAME, width=110, height=22,
                  font=ctk.CTkFont(size=10),
                  command=lambda: _switch_db(_PERM_DB_NAME)).pack(side="left")

    ctk.CTkLabel(conn_bar, textvariable=_perm_warn_var, wraplength=900,
                 font=ctk.CTkFont(size=10), text_color="#f59e0b"
                 ).grid(row=2, column=0, columnspan=20, padx=14, pady=(0, 8), sticky="w")

    def _refresh_bank_status() -> None:
        if not state.is_connected():
            _shop_db_status.set(f"{_DB_NAME}: ✗")
            _perm_db_status.set(f"{_PERM_DB_NAME}: ✗")
            _perm_warn_var.set("")
            return

        def _worker() -> None:
            shop_ok = perm_ok = False
            schema_msg = ""
            try:
                with state._lock:
                    shop_ok = database_exists(state.conn, _DB_NAME)
                    perm_ok = permission_database_exists(state.conn)
                if shop_ok:
                    schema_ok, schema_msg = _customshop_players_schema_ok(state)
                    if schema_ok:
                        schema_msg = ""
            except Exception:
                pass

            def _update() -> None:
                _shop_db_status.set(f"{_DB_NAME}: {'✓' if shop_ok else '✗'}")
                _perm_db_status.set(f"{_PERM_DB_NAME}: {'✓' if perm_ok else '✗'}")

                needs_perm = False
                asm_cm = getattr(app, "asm_config_manager", None)
                cm = getattr(app, "config_manager", None)
                if cm is not None:
                    for _kind, srv in iter_shop_servers(cm, asm_cm):
                        if permissions_dll_installed(getattr(srv, "install_dir", "") or ""):
                            needs_perm = True
                            break
                if schema_msg:
                    _perm_warn_var.set(
                        f"⚠ CustomShop: {schema_msg}. "
                        "Use «Sync jogadores» para recriar a tabela e importar do Permissions."
                    )
                elif needs_perm and not perm_ok:
                    _perm_warn_var.set(
                        "⚠ Permissions.dll instalado — execute Setup limpo ou Assistente "
                        "para criar ark_permission."
                    )
                elif not perm_ok:
                    _perm_warn_var.set(
                        f"Dica: {_PERM_DB_NAME} é usado pelo plugin Permissions (grupos)."
                    )
                else:
                    _perm_warn_var.set("")

            parent.after(0, _update)

        threading.Thread(target=_worker, daemon=True).start()

    parent.after(400, _refresh_bank_status)

    def _db_backup_connection() -> dict:
        try:
            port = int((_v_port.get() or "3306").strip())
        except ValueError:
            port = 3306
        return {
            "host": (_v_host.get() or "").strip(),
            "port": port,
            "user": (_v_user.get() or "").strip(),
            "password": _v_pass.get() or "",
        }

    _, bk_content = _make_collapsible_card(
        body, 2, "💾 Backup Automático do Banco",
        card_bg=card_bg, accent=accent, hover_bg=_hover_bg,
        start_collapsed=True, pady=(4, 4),
    )
    from .db_backup_section import build_db_backup_section
    build_db_backup_section(
        app, bk_content, theme=theme,
        get_connection=_db_backup_connection,
        grid_row=0,
        bare=True,
    )

    # ── Browser (lazy) ─────────────────────────────────────────────────────
    browser_host = ctk.CTkFrame(
        body, fg_color=bg, corner_radius=0, height=_DB_BROWSER_MIN_HEIGHT,
    )
    browser_host.grid(row=3, column=0, sticky="ew", padx=8, pady=(4, 12))
    browser_host.grid_propagate(False)
    browser_host.grid_rowconfigure(0, weight=1)
    browser_host.grid_columnconfigure(0, weight=1)
    _db_loading = ctk.CTkLabel(
        browser_host, text="Carregando painel…",
        font=ctk.CTkFont(family="Segoe UI", size=12),
        text_color=t_sec,
    )
    _db_loading.place(relx=0.5, rely=0.5, anchor="center")

    def _init_browser() -> None:
        try:
            _db_loading.destroy()
        except Exception:
            pass

        _configure_db_browser_ttk(theme)

        # ── Split: árvore esquerda + painel direito ────────────────────────────
        split = ctk.CTkFrame(browser_host, fg_color=bg, corner_radius=0)
        split.grid(row=0, column=0, sticky="nsew")
        split.grid_rowconfigure(0, weight=1)
        split.grid_columnconfigure(0, weight=0, minsize=228)
        split.grid_columnconfigure(1, weight=1)
    
        # ── Painel esquerdo: árvore ────────────────────────────────────────────
        left = ctk.CTkFrame(split, fg_color=card_bg, corner_radius=8)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        left.grid_rowconfigure(1, weight=1)
        left.grid_rowconfigure(2, weight=0)
        left.grid_columnconfigure(0, weight=1)
    
        ctk.CTkLabel(left, text="Databases / Tabelas",
                     font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
                     text_color=accent).grid(row=0, column=0, padx=12, pady=(10, 4), sticky="w")
    
        tree_host = _ttk_tree_host(left, card_bg)
        tree_host.grid(row=1, column=0, columnspan=2, sticky="nsew", padx=4, pady=4)
        _db_tree = ttk.Treeview(tree_host, style="DB.Treeview", show="tree",
                                 selectmode="browse", height=28)
        _db_tree.grid(row=0, column=0, sticky="nsew")
        _bind_treeview_fill_rows(_db_tree, tree_host, min_rows=20)
    
        _tree_scroll = _db_scrollbar(left, "vertical", _db_tree.yview, theme)
        _tree_scroll.grid(row=1, column=1, sticky="ns", pady=4)
        _db_tree.configure(yscrollcommand=_tree_scroll.set)
    
        # Botões de ação rápida
        actions = ctk.CTkFrame(left, fg_color="transparent")
        actions.grid(row=2, column=0, columnspan=2, padx=8, pady=(4, 10), sticky="ew")
        actions.grid_columnconfigure(0, weight=1)
        actions.grid_columnconfigure(1, weight=1)
    
        _btn_setup = ctk.CTkButton(actions, text="🗄 Setup limpo", height=28, corner_radius=6,
                                   fg_color=theme.get("accent_muted_bg", "#164e63"),
                                   text_color=accent,
                                   font=ctk.CTkFont(family="Segoe UI", size=10))
        _btn_setup.grid(row=0, column=0, padx=(0, 4), pady=(0, 4), sticky="ew")
    
        _btn_migrate = ctk.CTkButton(actions, text="📤 Migrar pts", height=28, corner_radius=6,
                                     fg_color=theme.get("accent_muted_bg", "#164e63"),
                                     text_color=accent,
                                     font=ctk.CTkFont(family="Segoe UI", size=10))
        _btn_migrate.grid(row=0, column=1, pady=(0, 4), sticky="ew")
    
        _btn_newuser = ctk.CTkButton(actions, text="👤 Novo Usuário", height=28, corner_radius=6,
                                     fg_color=theme.get("accent_muted_bg", "#164e63"),
                                     text_color=accent,
                                     font=ctk.CTkFont(family="Segoe UI", size=10))
        _btn_newuser.grid(row=1, column=0, padx=(0, 4), pady=(0, 4), sticky="ew")
    
        _btn_rootpwd = ctk.CTkButton(actions, text="🔑 Senha Root", height=28, corner_radius=6,
                                      fg_color=theme.get("accent_muted_bg", "#164e63"),
                                      text_color=accent,
                                      font=ctk.CTkFont(family="Segoe UI", size=10))
        _btn_rootpwd.grid(row=1, column=1, pady=(0, 4), sticky="ew")

        _btn_fix_arkland = ctk.CTkButton(
            actions, text="🔧 Arkland localhost+%", height=28, corner_radius=6,
            fg_color=theme.get("accent_muted_bg", "#164e63"),
            text_color=accent,
            font=ctk.CTkFont(family="Segoe UI", size=10),
            state="disabled",
        )
        _btn_fix_arkland.grid(row=2, column=0, columnspan=2, pady=(0, 4), sticky="ew")

        _btn_sync_players = ctk.CTkButton(actions, text="👥 Sync jogadores", height=28,
                                          corner_radius=6,
                                          fg_color=theme.get("accent_muted_bg", "#164e63"),
                                          text_color=accent,
                                          font=ctk.CTkFont(family="Segoe UI", size=10),
                                          state="disabled")
        _btn_sync_players.grid(row=3, column=0, columnspan=2, pady=(0, 4), sticky="ew")
    
        # ── Painel direito: abas ───────────────────────────────────────────────
        right = ctk.CTkFrame(split, fg_color=card_bg, corner_radius=8)
        right.grid(row=0, column=1, sticky="nsew")
        right.grid_rowconfigure(1, weight=1)
        right.grid_columnconfigure(0, weight=1)
    
        # Barra de abas
        tab_bar = ctk.CTkFrame(right, fg_color="transparent", height=36)
        tab_bar.grid(row=0, column=0, sticky="ew", padx=8, pady=(8, 0))
    
        _active_tab = tk.StringVar(value="dados")
        _tab_frames: dict[str, ctk.CTkFrame] = {}
        _tab_btns: dict[str, ctk.CTkButton] = {}
    
        tab_content = ctk.CTkFrame(right, fg_color="transparent")
        tab_content.grid(row=1, column=0, sticky="nsew", padx=6, pady=(4, 6))
        tab_content.grid_rowconfigure(0, weight=1)
        tab_content.grid_columnconfigure(0, weight=1)
    
        def _show_tab(name: str) -> None:
            _active_tab.set(name)
            for k, f in _tab_frames.items():
                if k == name:
                    f.grid(row=0, column=0, sticky="nsew")
                else:
                    f.grid_remove()
            for k, b in _tab_btns.items():
                b.configure(
                    fg_color=accent if k == name else "transparent",
                    text_color="#000" if k == name else t_sec,
                    font=ctk.CTkFont(family="Segoe UI", size=11,
                                     weight="bold" if k == name else "normal"),
                )
    
        for i, (tab_key, tab_lbl) in enumerate([("dados", "Dados"),
                                                 ("estrutura", "Estrutura"),
                                                 ("sql", "SQL")]):
            b = ctk.CTkButton(tab_bar, text=tab_lbl, width=80, height=28,
                              fg_color="transparent", text_color=t_sec,
                              hover_color=theme["accent_hover"], corner_radius=6,
                              font=ctk.CTkFont(family="Segoe UI", size=11),
                              command=lambda k=tab_key: _show_tab(k))
            b.grid(row=0, column=i, padx=(0, 4))
            _tab_btns[tab_key] = b
    
            f = ctk.CTkFrame(tab_content, fg_color="transparent")
            f.grid(row=0, column=0, sticky="nsew")
            f.grid_rowconfigure(0, weight=1)
            f.grid_columnconfigure(0, weight=1)
            _tab_frames[tab_key] = f
    
        # ── Tab Dados ──────────────────────────────────────────────────────────
        dados_frame = _tab_frames["dados"]
        dados_frame.grid_rowconfigure(0, weight=0)
        dados_frame.grid_rowconfigure(1, weight=1, minsize=_DB_BROWSER_MIN_HEIGHT - 120)
        dados_frame.grid_columnconfigure(0, weight=1)
    
        # Paginação no topo — evita cortar controles quando a janela é baixa
        _page_state = {"offset": 0, "limit": 50, "total": 0}
        _load_gen = [0]
        _page_lbl_var = tk.StringVar(value="")
    
        page_bar = ctk.CTkFrame(dados_frame, fg_color="transparent", height=30)
        page_bar.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 4))
        page_bar.grid_columnconfigure(2, weight=1)
    
        ctk.CTkLabel(page_bar, textvariable=_page_lbl_var,
                     font=ctk.CTkFont(family="Segoe UI", size=10),
                     text_color=t_mut).grid(row=0, column=2, padx=8)
    
        _btn_refresh = ctk.CTkButton(page_bar, text="⟳ Recarregar", width=100, height=26,
                                      fg_color=theme.get("accent_muted_bg", "#164e63"),
                                      text_color=accent, corner_radius=6,
                                      font=ctk.CTkFont(size=10),
                                      command=lambda: _do_reload_db())
        _btn_refresh.grid(row=0, column=0, padx=(0, 4))
    
        _btn_prev = ctk.CTkButton(page_bar, text="◀ Anterior", width=90, height=26,
                                  fg_color=theme.get("accent_muted_bg", "#164e63"),
                                  text_color=accent, corner_radius=6,
                                  font=ctk.CTkFont(size=10))
        _btn_prev.grid(row=0, column=1, padx=(0, 4))
        _btn_next = ctk.CTkButton(page_bar, text="Próximo ▶", width=90, height=26,
                                  fg_color=theme.get("accent_muted_bg", "#164e63"),
                                  text_color=accent, corner_radius=6,
                                  font=ctk.CTkFont(size=10))
        _btn_next.grid(row=0, column=3)

        data_table_host = _ttk_tree_host(dados_frame, card_bg, horizontal_scroll=True)
        data_table_host.grid(row=1, column=0, columnspan=2, sticky="nsew")

        _data_tree = ttk.Treeview(data_table_host, style="Data.Treeview",
                                  show="headings", selectmode="browse", height=28)
        _data_tree.grid(row=0, column=0, sticky="nsew")
        _bind_treeview_fill_rows(_data_tree, data_table_host, min_rows=24)
    
        _data_vscroll = _db_scrollbar(data_table_host, "vertical",
                                        _data_tree.yview, theme)
        _data_vscroll.grid(row=0, column=1, sticky="ns")
        _data_hscroll = _db_scrollbar(data_table_host, "horizontal",
                                        _data_tree.xview, theme)
        _data_hscroll.grid(row=1, column=0, sticky="ew")
        _data_tree.configure(yscrollcommand=_data_vscroll.set,
                             xscrollcommand=_data_hscroll.set)
    
        # ── Tab Estrutura ──────────────────────────────────────────────────────
        struct_frame = _tab_frames["estrutura"]
        struct_frame.grid_rowconfigure(0, weight=1, minsize=_DB_BROWSER_MIN_HEIGHT - 120)
        struct_frame.grid_columnconfigure(0, weight=1)

        struct_host = _ttk_tree_host(struct_frame, card_bg)
        struct_host.grid(row=0, column=0, sticky="nsew")

        _struct_tree = ttk.Treeview(struct_host, style="Struct.Treeview",
                                    show="headings", height=28,
                                    columns=("field", "type", "null", "key",
                                             "default", "extra", "comment"))
        for col_id, col_lbl, col_w in [
            ("field",   "Campo",   140),
            ("type",    "Tipo",    120),
            ("null",    "Null",    50),
            ("key",     "Chave",   60),
            ("default", "Padrão",  100),
            ("extra",   "Extra",   100),
            ("comment", "Comentário", 180),
        ]:
            _struct_tree.heading(col_id, text=col_lbl)
            _struct_tree.column(col_id, width=col_w, minwidth=40)
        _struct_tree.grid(row=0, column=0, sticky="nsew")
        _bind_treeview_fill_rows(_struct_tree, struct_host, min_rows=24)

        struct_vscroll = _db_scrollbar(struct_frame, "vertical",
                                       _struct_tree.yview, theme)
        struct_vscroll.grid(row=0, column=1, sticky="ns")
        _struct_tree.configure(yscrollcommand=struct_vscroll.set)
    
        # ── Tab SQL ────────────────────────────────────────────────────────────
        sql_frame = _tab_frames["sql"]
        sql_frame.grid_rowconfigure(0, weight=0)
        sql_frame.grid_rowconfigure(1, weight=1, minsize=_DB_BROWSER_MIN_HEIGHT - 200)
        sql_frame.grid_columnconfigure(0, weight=1)

        sql_top = ctk.CTkFrame(sql_frame, fg_color="transparent")
        sql_top.grid(row=0, column=0, sticky="ew", pady=(0, 4))
        sql_top.grid_columnconfigure(0, weight=1)

        _sql_editor = ctk.CTkTextbox(
            sql_top, height=72, corner_radius=6,
            fg_color=theme.get("input_bg", "#1e293b"),
            text_color=t_pri, border_color=sep_col, border_width=1,
            font=ctk.CTkFont(family="Consolas", size=12),
            wrap="word",
        )
        _sql_editor.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        _sql_editor.insert("end", "SELECT * FROM players LIMIT 50;")

        sql_btn_col = ctk.CTkFrame(sql_top, fg_color="transparent")
        sql_btn_col.grid(row=0, column=1, sticky="ne")
    
        _btn_exec = ctk.CTkButton(sql_btn_col, text="▶ Executar",
                                  width=100, height=36, corner_radius=6,
                                  fg_color=accent, text_color="#000",
                                  font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"))
        _btn_exec.grid(row=0, column=0, pady=(0, 6))
    
        _btn_clear_sql = ctk.CTkButton(sql_btn_col, text="Limpar",
                                       width=100, height=28, corner_radius=6,
                                       fg_color="transparent", text_color=t_sec,
                                       border_color=sep_col, border_width=1,
                                       font=ctk.CTkFont(size=10))
        _btn_clear_sql.grid(row=1, column=0)
    
        # Resultado do SQL
        sql_result_frame = ctk.CTkFrame(sql_frame, fg_color="transparent")
        sql_result_frame.grid(row=1, column=0, sticky="nsew")
        sql_result_frame.grid_rowconfigure(0, weight=1)
        sql_result_frame.grid_rowconfigure(1, weight=0)
        sql_result_frame.grid_columnconfigure(0, weight=1)

        sql_result_host = _ttk_tree_host(sql_result_frame, card_bg, horizontal_scroll=True)
        sql_result_host.grid(row=0, column=0, sticky="nsew")

        _sql_result_tree = ttk.Treeview(sql_result_host, style="Data.Treeview",
                                        show="headings", selectmode="browse", height=28)
        _sql_result_tree.grid(row=0, column=0, sticky="nsew")
        _bind_treeview_fill_rows(_sql_result_tree, sql_result_host, min_rows=20)
        sql_rv = _db_scrollbar(sql_result_host, "vertical",
                               _sql_result_tree.yview, theme)
        sql_rv.grid(row=0, column=1, sticky="ns")
        sql_rh = _db_scrollbar(sql_result_host, "horizontal",
                               _sql_result_tree.xview, theme)
        sql_rh.grid(row=1, column=0, sticky="ew")
        _sql_result_tree.configure(yscrollcommand=sql_rv.set,
                                   xscrollcommand=sql_rh.set)

        _sql_info_var = tk.StringVar(value="")
        ctk.CTkLabel(sql_result_frame, textvariable=_sql_info_var,
                     font=ctk.CTkFont(family="Segoe UI", size=10),
                     text_color=t_mut).grid(row=1, column=0, sticky="w", pady=(4, 0))
    
        # ── Inicializa a aba ativa ─────────────────────────────────────────────
        _show_tab("dados")
        browser_host.after(200, lambda: split.event_generate("<Configure>"))
    
        # ══════════════════════════════════════════════════════════════════════
        #  Lógica de conexão e atualização
        # ══════════════════════════════════════════════════════════════════════
    
        def _set_status(connected: bool, msg: str = "") -> None:
            if connected:
                _status_dot.configure(text_color="#22c55e")
                extra = ""
                if state.database == _PERM_DB_NAME:
                    extra = " — tabelas do Permissions.dll no 1º start do servidor"
                _v_status.set((msg or "Conectado") + extra)
                _btn_connect.configure(state="disabled")
                _btn_disconnect.configure(state="normal")
                _btn_setup.configure(state="normal")
                _btn_migrate.configure(state="normal")
                _btn_newuser.configure(state="normal")
                _btn_fix_arkland.configure(state="normal")
                _btn_sync_players.configure(state="normal")
                _btn_reload_db.configure(state="normal")
                _refresh_bank_status()
            else:
                _status_dot.configure(text_color="#ef4444")
                _v_status.set(msg or "Desconectado")
                _btn_connect.configure(state="normal")
                _btn_disconnect.configure(state="disabled")
                _btn_sync_players.configure(state="disabled")
                _btn_fix_arkland.configure(state="disabled")
                _btn_reload_db.configure(state="disabled")
                _shop_db_status.set(f"{_DB_NAME}: desconectado")
                _perm_db_status.set(f"{_PERM_DB_NAME}: desconectado")
    
        def _do_connect(*, manual: bool = False) -> None:
            global pymysql, _PYMYSQL_OK  # noqa: PLW0603
    
            state.close()
            state.host     = _v_host.get().strip()
            state.port     = int(_v_port.get().strip() or 3306)
            state.user     = _v_user.get().strip()
            state.password = _v_pass.get()
            state.database = _v_db.get().strip()
            _btn_connect.configure(state="disabled")
    
            def _worker():
                global pymysql, _PYMYSQL_OK  # noqa: PLW0603
    
                # Auto-instala pymysql se necessário
                if not _PYMYSQL_OK:
                    parent.after(0, lambda: _v_status.set("Instalando pymysql..."))
                    ok = _install_pymysql_sync()
                    if ok:
                        _mod, _ok = _try_import_pymysql()
                        pymysql    = _mod
                        _PYMYSQL_OK = _ok
                    if not _PYMYSQL_OK:
                        parent.after(0, lambda: _set_status(
                            False, "Falha ao instalar pymysql"))
                        return
    
                parent.after(0, lambda: _v_status.set("Conectando..."))

                def _try_connect(use_db: bool) -> Any:
                    conn_kwargs: dict = dict(
                        host=state.host, port=state.port,
                        user=state.user, password=state.password,
                        cursorclass=pymysql.cursors.DictCursor,
                        connect_timeout=5,
                    )
                    if use_db and state.database:
                        conn_kwargs["database"] = state.database
                    return pymysql.connect(**conn_kwargs)

                try:
                    try:
                        conn = _try_connect(use_db=True)
                    except Exception as exc1:
                        err1 = str(exc1)
                        if state.database and (
                            "1049" in err1 or "Unknown database" in err1
                        ):
                            conn = _try_connect(use_db=False)
                        else:
                            raise exc1
                    with state._lock:
                        state.conn = conn
                    is_local_root = (
                        _is_local_db_host(state.host)
                        and (state.user or "").strip().lower() == "root"
                    )
                    shop_prefs = DbLocalServer._load_prefs().get("shop_db") or {}
                    shop_is_remote = (
                        shop_prefs.get("host")
                        and not _is_local_db_host(shop_prefs.get("host", ""))
                    )
                    if manual or not (is_local_root and shop_is_remote):
                        prefs = DbLocalServer._load_prefs()
                        conn_entry = _connection_prefs_from_state(state)
                        prefs["last_connection"] = conn_entry
                        # Persiste shop_db quando não for root@localhost efêmero
                        if manual or not is_local_root:
                            prefs["shop_db"] = conn_entry
                        DbLocalServer._save_prefs(prefs)
                    parent.after(0, lambda: _set_status(True,
                        f"Conectado a {state.host}:{state.port}"))
                    parent.after(0, _refresh_tree)
                except Exception as exc:
                    parent.after(0, lambda e=exc: _set_status(False, f"Erro: {e}"))
    
            threading.Thread(target=_worker, daemon=True).start()
    
        def _do_reload_db() -> None:
            if not state.is_connected():
                _v_status.set("Desconectado — conecte antes de recarregar")
                return
            _refresh_tree()
            _refresh_bank_status()
            if state.selected_db and state.selected_table:
                _page_state["offset"] = 0
                _load_gen[0] += 1
                gen = _load_gen[0]
                _load_data(gen)
                _load_structure(gen)
            else:
                _page_lbl_var.set("Árvore atualizada — selecione uma tabela")

        _reload_fn_box[0] = _do_reload_db

        def _do_sync_shop_players() -> None:
            from tkinter import messagebox

            if not state.is_connected():
                messagebox.showwarning("Sem conexão", "Conecte ao banco antes de sincronizar.",
                                       parent=parent)
                return

            schema_ok, schema_msg = _customshop_players_schema_ok(state)
            if not schema_ok:
                if not messagebox.askyesno(
                    "Corrigir tabela players",
                    f"{schema_msg}\n\n"
                    "Recriar arkland_shop.players com o schema do CustomShop e "
                    "importar todos os SteamId de ark_permission.players?",
                    parent=parent,
                ):
                    return

            def _worker():
                try:
                    n = _sync_shop_players_from_permissions(state, starting_points=100)
                    def _done():
                        messagebox.showinfo(
                            "Sync jogadores",
                            f"{n} jogador(es) importado(s) para arkland_shop.players.\n"
                            "Recarregue o plugin CustomShop no servidor (RCON) se já estiver online.",
                            parent=parent,
                        )
                        _do_reload_db()
                    parent.after(0, _done)
                except Exception as exc:
                    parent.after(0, lambda e=exc: messagebox.showerror(
                        "Sync jogadores", str(e), parent=parent))

            threading.Thread(target=_worker, daemon=True).start()

        _btn_sync_players.configure(command=_do_sync_shop_players)

        def _do_disconnect() -> None:
            state.close()
            _db_tree.delete(*_db_tree.get_children())
            _set_status(False)
    
        _btn_connect.configure(command=lambda: _do_connect(manual=True))
        _btn_disconnect.configure(command=_do_disconnect)

        _connect_ready.clear()
        _connect_ready.append(lambda: _do_connect(manual=True))
        if _pending_connect_after_wizard[0]:
            _pending_connect_after_wizard[0] = False
            _do_connect(manual=True)
    
        def _restore_shop_credentials_on_bar() -> None:
            """Evita auto-connect como root quando a loja usa outro usuário/host."""
            if (_v_user.get() or "").strip().lower() not in ("", "root"):
                return
            shop_prefs = DbLocalServer._load_prefs().get("shop_db") or {}
            app_shop = _shop_config_db_prefs(app)
            for source in (shop_prefs, app_shop):
                user = (source.get("user") or "").strip()
                if user and user.lower() != "root":
                    _v_host.set(source.get("host", _v_host.get()))
                    _v_port.set(str(source.get("port", 3306)))
                    _v_user.set(user)
                    _v_pass.set(source.get("password", ""))
                    _v_db.set(source.get("database", _DB_NAME))
                    return

        def _auto_connect() -> None:
            _restore_shop_credentials_on_bar()
            _do_connect(manual=False)

        # ── Auto-start + auto-connect ao inicializar o painel ─────────────────────
        _after_start_hooks.append(_auto_connect)

        if DbLocalServer.get_autostart() and local_srv.is_installed():
            if local_srv.is_running():
                parent.after(500, _auto_connect)
            else:
                threading.Thread(target=_do_start, daemon=True).start()
    
        # ── Árvore de bancos ───────────────────────────────────────────────────
    
        def _refresh_tree() -> None:
            if not state.is_connected():
                _db_tree.delete(*_db_tree.get_children())
                return

            def _worker() -> None:
                tree_data: list[tuple[str, list[str]]] = []
                try:
                    dbs = _list_databases(state)
                    for db in dbs:
                        try:
                            tables = _list_tables(state, db)
                        except Exception:
                            tables = []
                        tree_data.append((db, tables))
                except Exception:
                    return

                def _update() -> None:
                    _db_tree.delete(*_db_tree.get_children())
                    for db, tables in tree_data:
                        node = _db_tree.insert("", "end", iid=f"db_{db}",
                                               text=f"🗄 {db}", open=False,
                                               tags=("db",))
                        for t in tables:
                            _db_tree.insert(node, "end",
                                            iid=f"tbl_{db}__{t}",
                                            text=f"   📋 {t}",
                                            tags=("table", db, t))

                parent.after(0, _update)

            threading.Thread(target=_worker, daemon=True).start()

        def _on_tree_select(event=None) -> None:
            sel = _db_tree.selection()
            if not sel:
                return
            iid = sel[0]
            if iid.startswith("tbl_"):
                parts = iid[4:].split("__", 1)
                if len(parts) == 2:
                    state.selected_db, state.selected_table = parts
                    _page_state["offset"] = 0
                    _load_gen[0] += 1
                    gen = _load_gen[0]
                    _load_data(gen)
                    _load_structure(gen)
    
        _db_tree.bind("<<TreeviewSelect>>", _on_tree_select)
    
        # ── Carregar dados ─────────────────────────────────────────────────────
    
        def _populate_treeview(
            tv: ttk.Treeview,
            rows: list[dict],
            *,
            gen: int | None = None,
            on_done=None,
        ) -> None:
            tv.delete(*tv.get_children())
            if gen is not None and gen != _load_gen[0]:
                return
            if not rows:
                if on_done:
                    on_done()
                return
            cols = list(rows[0].keys())
            tv.configure(columns=cols)
            for c in cols:
                tv.heading(c, text=c)
                tv.column(c, width=max(80, min(300, len(c) * 9)), minwidth=40)
            values_list = [
                [_cell_display(v) for v in row.values()]
                for row in rows
            ]
            idx = [0]

            def _insert_batch() -> None:
                if gen is not None and gen != _load_gen[0]:
                    return
                end = min(idx[0] + _TREE_INSERT_BATCH, len(values_list))
                for i in range(idx[0], end):
                    tv.insert("", "end", values=values_list[i])
                idx[0] = end
                if idx[0] < len(values_list):
                    parent.after(1, _insert_batch)
                elif on_done:
                    on_done()

            _insert_batch()

        def _load_data(gen: int | None = None) -> None:
            if not (state.selected_db and state.selected_table):
                return
            _page_lbl_var.set("Carregando...")
            db, table = state.selected_db, state.selected_table

            def _worker() -> None:
                try:
                    rows, total = _table_rows(state, db, table,
                                              _page_state["limit"],
                                              _page_state["offset"])
                    if gen is not None and gen != _load_gen[0]:
                        return
                    _page_state["total"] = total
                    start = _page_state["offset"] + 1
                    end   = min(_page_state["offset"] + len(rows), total)

                    def _finish_ui() -> None:
                        if gen is not None and gen != _load_gen[0]:
                            return
                        _page_lbl_var.set(
                            f"Mostrando {start}–{end} de {total} linhas   "
                            f"({db}.{table})"
                        )
                        _btn_prev.configure(
                            state="normal" if _page_state["offset"] > 0 else "disabled")
                        _btn_next.configure(
                            state="normal" if end < total else "disabled")

                    def _update() -> None:
                        _populate_treeview(_data_tree, rows, gen=gen, on_done=_finish_ui)

                    parent.after(0, _update)
                except Exception as exc:
                    if gen is not None and gen != _load_gen[0]:
                        return
                    parent.after(0, lambda e=exc: _page_lbl_var.set(f"Erro: {e}"))

            threading.Thread(target=_worker, daemon=True).start()

        def _load_structure(gen: int | None = None) -> None:
            if not (state.selected_db and state.selected_table):
                return
            db, table = state.selected_db, state.selected_table

            def _worker() -> None:
                try:
                    cols = _table_columns(state, db, table)
                except Exception:
                    return
                if gen is not None and gen != _load_gen[0]:
                    return

                def _update() -> None:
                    if gen is not None and gen != _load_gen[0]:
                        return
                    _struct_tree.delete(*_struct_tree.get_children())
                    for c in cols:
                        _struct_tree.insert("", "end", values=(
                            c.get("Field", ""),
                            c.get("Type", ""),
                            c.get("Null", ""),
                            c.get("Key", ""),
                            str(c.get("Default", "")) if c.get("Default") is not None else "NULL",
                            c.get("Extra", ""),
                            c.get("Comment", ""),
                        ))

                parent.after(0, _update)

            threading.Thread(target=_worker, daemon=True).start()
    
        def _prev_page() -> None:
            if _page_state["offset"] >= _page_state["limit"]:
                _page_state["offset"] -= _page_state["limit"]
                _load_gen[0] += 1
                _load_data(_load_gen[0])

        def _next_page() -> None:
            if _page_state["offset"] + _page_state["limit"] < _page_state["total"]:
                _page_state["offset"] += _page_state["limit"]
                _load_gen[0] += 1
                _load_data(_load_gen[0])
    
        _btn_prev.configure(command=_prev_page, state="disabled")
        _btn_next.configure(command=_next_page, state="disabled")
    
        # ── Executar SQL ───────────────────────────────────────────────────────
    
        def _exec_sql() -> None:
            if not state.is_connected():
                _sql_info_var.set("Sem conexão.")
                return
            sql_text = _sql_editor.get("1.0", "end").strip()
            if not sql_text:
                return
            _sql_info_var.set("Executando...")
            _sql_result_tree.delete(*_sql_result_tree.get_children())
    
            # Usa banco selecionado se disponível
            if state.selected_db:
                try:
                    _execute(state, f"USE `{state.selected_db}`")
                except Exception:
                    pass
    
            def _worker():
                try:
                    is_select = sql_text.lstrip().upper().startswith("SELECT")
                    if is_select:
                        rows = _query(state, sql_text)
                        def _update(r=rows):
                            _populate_treeview(_sql_result_tree, r)
                            _sql_info_var.set(f"{len(r)} linha(s) retornada(s)")
                        parent.after(0, _update)
                    else:
                        affected = _execute(state, sql_text)
                        parent.after(0, lambda n=affected:
                            _sql_info_var.set(f"{n} linha(s) afetada(s)"))
                        parent.after(0, _refresh_tree)
                except Exception as exc:
                    parent.after(0, lambda e=exc:
                        _sql_info_var.set(f"Erro: {e}"))
    
            threading.Thread(target=_worker, daemon=True).start()
    
        _btn_exec.configure(command=_exec_sql)
        _btn_clear_sql.configure(command=lambda: (
            _sql_editor.delete("1.0", "end"),
            _sql_result_tree.delete(*_sql_result_tree.get_children()),
            _sql_info_var.set(""),
        ))
    
        # Ctrl+Enter executa SQL
        _sql_editor.bind("<Control-Return>", lambda _: _exec_sql())
    
        # ── Setup banco limpo ──────────────────────────────────────────────────
    
        def _do_setup_db() -> None:
            try:
                sql_text = load_setup_sql_template()
            except FileNotFoundError as exc:
                _show_msg("Arquivo não encontrado", str(exc))
                return
            _show_sql_file_dialog(sql_text, title="Setup — Banco de dados limpo")
    
        def _do_migrate() -> None:
            if not state.is_connected():
                _show_msg("Sem conexão", "Conecte ao banco antes de migrar.")
                return
            try:
                dbs = _list_databases(state)
            except Exception as exc:
                _show_msg("Erro", str(exc))
                return
            _show_migrate_dialog(dbs)
    
        def _do_newuser() -> None:
            if not state.is_connected():
                from tkinter import messagebox
                messagebox.showwarning("Sem conexão", "Conecte ao banco antes de criar usuário.", parent=parent)
                return
    
            dlg = ctk.CTkToplevel(parent)
            dlg.title("Novo Usuário")
            dlg.geometry("380x280")
            dlg.resizable(False, False)
            dlg.grab_set()
            dlg.configure(fg_color=card_bg)
    
            def _row(label, row, show=""):
                ctk.CTkLabel(dlg, text=label,
                             font=ctk.CTkFont(family="Segoe UI", size=11),
                             text_color=t_sec).grid(row=row, column=0, padx=(20, 8), pady=6, sticky="e")
                var = tk.StringVar()
                ctk.CTkEntry(dlg, textvariable=var, width=200, show=show,
                             fg_color=theme.get("input_bg", "#1e293b"),
                             text_color=t_pri, border_color=sep_col,
                             font=ctk.CTkFont(family="Segoe UI", size=11)
                             ).grid(row=row, column=1, padx=(0, 20), pady=6, sticky="w")
                return var
    
            v_usr  = _row("Usuário",  0)
            v_pwd  = _row("Senha",    1, show="•")
            v_host = _row("Host",     2)
            v_db   = _row("Database", 3)
    
            v_usr.set("arkland")
            v_host.set("%")
            v_db.set("arkland_shop")
    
            _result_var = tk.StringVar()
            ctk.CTkLabel(dlg, textvariable=_result_var, wraplength=340,
                         font=ctk.CTkFont(family="Segoe UI", size=10),
                         text_color="#ef4444").grid(row=4, column=0, columnspan=2, padx=20)
    
            def _create():
                usr  = v_usr.get().strip()
                pwd  = v_pwd.get()
                host = v_host.get().strip() or "%"
                db   = v_db.get().strip()
                if not usr or not pwd:
                    _result_var.set("Usuário e senha são obrigatórios.")
                    return
                try:
                    cur = state.conn.cursor()
                    # Cria para o host especificado
                    hosts = [host]
                    # Se host é '%', cria também para 'localhost' (% não cobre localhost no MySQL/MariaDB)
                    if host == "%":
                        hosts.append("localhost")
                    for h in hosts:
                        # CREATE OR REPLACE atualiza senha se usuário já existir
                        cur.execute(f"CREATE OR REPLACE USER '{usr}'@'{h}' IDENTIFIED BY '{pwd}'")
                        if db:
                            cur.execute(f"GRANT ALL PRIVILEGES ON `{db}`.* TO '{usr}'@'{h}'")
                    cur.execute("FLUSH PRIVILEGES")
                    state.conn.commit()
                    _result_var.set("")
                    dlg.destroy()
                    from tkinter import messagebox
                    messagebox.showinfo("Usuário criado",
                        f"Usuário '{usr}' criado para: {', '.join(hosts)}\n"
                        + (f"Permissão total em '{db}'." if db else ""),
                        parent=parent)
                except Exception as exc:
                    _result_var.set(str(exc))
    
            ctk.CTkButton(dlg, text="Criar usuário", height=32, corner_radius=6,
                          fg_color=accent, text_color="#000",
                          font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
                          command=_create
                          ).grid(row=5, column=0, columnspan=2, pady=(8, 16))
    
        def _do_rootpwd() -> None:
            dlg = ctk.CTkToplevel(parent)
            dlg.title("Definir Senha do Root")
            dlg.geometry("360x220")
            dlg.resizable(False, False)
            dlg.grab_set()
            dlg.configure(fg_color=card_bg)
    
            ctk.CTkLabel(dlg, text="Senha atual do root:",
                         font=ctk.CTkFont(family="Segoe UI", size=11),
                         text_color=t_sec).grid(row=0, column=0, padx=20, pady=(20, 4), sticky="e")
            v_old = tk.StringVar(value=local_srv.get_root_password())
            ctk.CTkEntry(dlg, textvariable=v_old, width=180, show="•",
                         fg_color=theme.get("input_bg", "#1e293b"),
                         text_color=t_pri, border_color=sep_col,
                         font=ctk.CTkFont(family="Segoe UI", size=11)
                         ).grid(row=0, column=1, padx=(0, 20), pady=(20, 4))
    
            ctk.CTkLabel(dlg, text="Nova senha:",
                         font=ctk.CTkFont(family="Segoe UI", size=11),
                         text_color=t_sec).grid(row=1, column=0, padx=20, pady=4, sticky="e")
            v_new = tk.StringVar()
            ctk.CTkEntry(dlg, textvariable=v_new, width=180, show="•",
                         fg_color=theme.get("input_bg", "#1e293b"),
                         text_color=t_pri, border_color=sep_col,
                         font=ctk.CTkFont(family="Segoe UI", size=11)
                         ).grid(row=1, column=1, padx=(0, 20), pady=4)
    
            _res = tk.StringVar()
            ctk.CTkLabel(dlg, textvariable=_res, wraplength=320,
                         font=ctk.CTkFont(family="Segoe UI", size=10),
                         text_color="#ef4444").grid(row=2, column=0, columnspan=2, padx=20, pady=4)
    
            def _apply():
                pwd = v_new.get().strip()
                if not pwd:
                    _res.set("Nova senha não pode ser vazia.")
                    return
                ok, msg = local_srv.apply_root_password(pwd)
                if ok:
                    dlg.destroy()
                    from tkinter import messagebox
                    messagebox.showinfo("Senha Root", "Senha do root definida com sucesso!\n"
                                        "Reconecte usando a nova senha.", parent=parent)
                else:
                    _res.set(msg)
    
            ctk.CTkButton(dlg, text="Aplicar", height=32, corner_radius=6,
                          fg_color=accent, text_color="#000",
                          font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
                          command=_apply).grid(row=3, column=0, columnspan=2, pady=12)
    
        def _do_fix_arkland_user() -> None:
            from tkinter import messagebox, simpledialog

            if not state.is_connected():
                messagebox.showwarning(
                    "Sem conexão",
                    "Conecte como root (ou admin) antes de corrigir o usuário arkland.",
                    parent=parent,
                )
                return

            shop = getattr(app.config_manager.config, "shop", None)
            pwd = resolve_shop_db_password(shop) if shop else ""
            if not pwd:
                pwd = simpledialog.askstring(
                    "Senha arkland",
                    "Senha do usuário MySQL 'arkland' (mesma do Banco de Pedidos):",
                    show="*",
                    parent=parent,
                ) or ""
            pwd = pwd.strip()
            if not pwd:
                return

            try:
                n, errs = ensure_mysql_user_both_hosts(
                    state.conn,
                    user="arkland",
                    password=pwd,
                    database=_DB_NAME,
                )
                save_shop_connection_prefs(
                    host=state.host or "127.0.0.1",
                    port=int(state.port or 3306),
                    user="arkland",
                    password=pwd,
                    database=_DB_NAME,
                )
                if shop is not None:
                    shop.orders_db_user = "arkland"
                    shop.orders_db_password = pwd
                    shop.orders_db_host = state.host or "127.0.0.1"
                    shop.orders_db_name = _DB_NAME
                    app.config_manager.save()
                msg = f"Usuário arkland atualizado em {n} host(s) (localhost + %)."
                if errs:
                    msg += "\nAvisos:\n" + "\n".join(errs[:5])
                messagebox.showinfo("Arkland MySQL", msg, parent=parent)
            except Exception as exc:
                messagebox.showerror("Arkland MySQL", str(exc), parent=parent)

        _btn_setup.configure(command=_do_setup_db, state="disabled")
        _btn_migrate.configure(command=_do_migrate, state="disabled")
        _btn_newuser.configure(command=_do_newuser, state="disabled")
        _btn_fix_arkland.configure(command=_do_fix_arkland_user, state="disabled")
        _btn_rootpwd.configure(command=_do_rootpwd)
    
        # ── Diálogos auxiliares ────────────────────────────────────────────────
    
        def _show_msg(title: str, msg: str) -> None:
            dlg = ctk.CTkToplevel(parent)
            dlg.title(title)
            dlg.geometry("420x160")
            dlg.grab_set()
            dlg.configure(fg_color=card_bg)
            ctk.CTkLabel(dlg, text=msg, wraplength=380,
                         font=ctk.CTkFont(family="Segoe UI", size=12),
                         text_color=t_pri).pack(padx=20, pady=20)
            ctk.CTkButton(dlg, text="OK", width=80, fg_color=accent,
                          text_color="#000", command=dlg.destroy).pack(pady=(0, 16))
    
        def _show_sql_file_dialog(sql_source: str | Path, title: str = "Executar SQL") -> None:
            """Mostra SQL e oferece botão para executar."""
            if not state.is_connected():
                _show_msg("Sem conexão", "Conecte ao banco antes de executar o script.")
                return
            if isinstance(sql_source, Path):
                content = sql_source.read_text(encoding="utf-8")
            else:
                content = sql_source
            dlg = ctk.CTkToplevel(parent)
            dlg.title(title)
            dlg.geometry("680x480")
            dlg.grab_set()
            dlg.configure(fg_color=card_bg)
            dlg.grid_rowconfigure(1, weight=1)
            dlg.grid_columnconfigure(0, weight=1)
    
            ctk.CTkLabel(dlg, text=title,
                         font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"),
                         text_color=accent).grid(row=0, column=0, padx=16, pady=(14, 4), sticky="w")
    
            txt = ctk.CTkTextbox(dlg, fg_color=theme.get("input_bg", "#1e293b"),
                                 text_color=t_pri, font=ctk.CTkFont(family="Consolas", size=11))
            txt.grid(row=1, column=0, sticky="nsew", padx=16, pady=4)
            txt.insert("end", content)
    
            info_var = tk.StringVar(value="")
            ctk.CTkLabel(dlg, textvariable=info_var,
                         font=ctk.CTkFont(size=10), text_color=t_mut).grid(
                row=2, column=0, padx=16, sticky="w")
    
            btn_row = ctk.CTkFrame(dlg, fg_color="transparent")
            btn_row.grid(row=3, column=0, padx=16, pady=(4, 14), sticky="e")
    
            def _run_script() -> None:
                content = txt.get("1.0", "end").strip()
                info_var.set("Executando...")
                dlg.update()
    
                def _worker():
                    errors = []
                    executed = 0
                    statements = [s.strip() for s in content.split(";") if s.strip()]
                    for stmt in statements:
                        try:
                            _execute(state, stmt)
                            executed += 1
                        except Exception as e:
                            errors.append(str(e))
                    def _done():
                        if errors:
                            info_var.set(f"{executed} OK, {len(errors)} erro(s): {errors[0]}")
                        else:
                            info_var.set(f"✓ {executed} statement(s) executados com sucesso.")
                        _refresh_tree()
                    parent.after(0, _done)
    
                threading.Thread(target=_worker, daemon=True).start()
    
            ctk.CTkButton(btn_row, text="▶ Executar", width=110, height=32,
                          fg_color=accent, text_color="#000",
                          font=ctk.CTkFont(weight="bold"),
                          command=_run_script).grid(row=0, column=0, padx=(0, 8))
            ctk.CTkButton(btn_row, text="Fechar", width=80, height=32,
                          fg_color="transparent", text_color=t_sec,
                          border_color=sep_col, border_width=1,
                          command=dlg.destroy).grid(row=0, column=1)
    
        def _show_migrate_dialog(available_dbs: list[str]) -> None:
            dlg = ctk.CTkToplevel(parent)
            dlg.title("Migrar pontos dos jogadores")
            dlg.geometry("460x260")
            dlg.grab_set()
            dlg.configure(fg_color=card_bg)
    
            ctk.CTkLabel(dlg, text="Migrar pontos dos jogadores",
                         font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"),
                         text_color=accent).pack(padx=20, pady=(16, 4), anchor="w")
    
            ctk.CTkLabel(dlg, text="Banco de origem (banco antigo):",
                         font=ctk.CTkFont(size=11), text_color=t_sec).pack(padx=20, anchor="w")
    
            _src_var = tk.StringVar(value=available_dbs[0] if available_dbs else "")
            _src_menu = ctk.CTkOptionMenu(dlg, variable=_src_var, values=available_dbs,
                                          fg_color=theme.get("input_bg", "#1e293b"),
                                          text_color=t_pri, button_color=accent,
                                          font=ctk.CTkFont(size=11))
            _src_menu.pack(padx=20, pady=(2, 12), anchor="w", fill="x")
    
            ctk.CTkLabel(dlg,
                         text="Destino: arkland_shop.players\n"
                              "Apenas pontos > 0 serão copiados.\n"
                              "Jogadores já existentes terão o saldo máximo mantido.",
                         font=ctk.CTkFont(size=10), text_color=t_mut,
                         justify="left").pack(padx=20, anchor="w")
    
            info_var2 = tk.StringVar(value="")
            ctk.CTkLabel(dlg, textvariable=info_var2,
                         font=ctk.CTkFont(size=10), text_color=accent).pack(padx=20, pady=4, anchor="w")
    
            def _run_migrate() -> None:
                src = _src_var.get()
                if not src:
                    return
                sql = (
                    f"INSERT INTO arkland_shop.players (steam_id, points) "
                    f"SELECT steam_id, points FROM `{src}`.players WHERE points > 0 "
                    f"ON DUPLICATE KEY UPDATE points = GREATEST(arkland_shop.players.points, VALUES(points))"
                )
                info_var2.set("Migrando...")
                dlg.update()
    
                def _worker():
                    try:
                        n = _execute(state, sql)
                        parent.after(0, lambda: info_var2.set(f"✓ {n} jogador(es) migrado(s)!"))
                        parent.after(0, _refresh_tree)
                    except Exception as exc:
                        parent.after(0, lambda e=exc: info_var2.set(f"Erro: {e}"))
    
                threading.Thread(target=_worker, daemon=True).start()
    
            btn_row2 = ctk.CTkFrame(dlg, fg_color="transparent")
            btn_row2.pack(padx=20, pady=(8, 16), anchor="e")
            ctk.CTkButton(btn_row2, text="▶ Migrar agora", width=120, height=32,
                          fg_color=accent, text_color="#000",
                          font=ctk.CTkFont(weight="bold"),
                          command=_run_migrate).grid(row=0, column=0, padx=(0, 8))
            ctk.CTkButton(btn_row2, text="Fechar", width=80, height=32,
                          fg_color="transparent", text_color=t_sec,
                          border_color=sep_col, border_width=1,
                          command=dlg.destroy).grid(row=0, column=1)
    parent.after(0, _init_browser)
