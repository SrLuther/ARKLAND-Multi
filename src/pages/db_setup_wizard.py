"""Assistente guiado — instalação MariaDB + banco arkland_shop."""
from __future__ import annotations

import threading
import tkinter as tk
from typing import TYPE_CHECKING, Callable, Optional

import customtkinter as ctk  # type: ignore[reportMissingImports]

from ..db_setup_resources import (
    _DB_NAME,
    _SHOP_USER,
    build_setup_sql,
    database_exists,
    execute_setup_sql,
    save_shop_connection_prefs,
    test_connection,
)
from ..ui_constants import get_theme
from .db_local_server import DbLocalServer

if TYPE_CHECKING:
    from .db_manager_panel import _DBState


def show_db_setup_wizard(
    parent: ctk.CTkFrame,
    local_srv: DbLocalServer,
    state: "_DBState",
    *,
    on_connected: Optional[Callable[[], None]] = None,
) -> None:
    """Abre wizard em 3 passos: servidor → root → criar arkland_shop."""
    theme = get_theme("tek")
    card_bg = theme["card_bg"]
    accent = theme["accent"]
    t_pri = theme["text_primary"]
    t_sec = theme["text_secondary"]
    t_mut = theme["text_muted"]
    sep_col = theme["separator"]

    dlg = ctk.CTkToplevel(parent)
    dlg.title("Assistente — Banco de Dados ARKLAND")
    dlg.geometry("520x520")
    dlg.resizable(False, False)
    dlg.grab_set()
    dlg.configure(fg_color=card_bg)
    dlg.grid_columnconfigure(0, weight=1)

    step_var = tk.IntVar(value=1)
    status_var = tk.StringVar(value="")
    status_color = tk.StringVar(value=t_mut)

    ctk.CTkLabel(
        dlg, text="Configuração do banco arkland_shop",
        font=ctk.CTkFont(family="Segoe UI", size=16, weight="bold"),
        text_color=accent,
    ).grid(row=0, column=0, padx=24, pady=(20, 4), sticky="w")

    step_lbl = ctk.CTkLabel(
        dlg, text="Passo 1 de 3 — Servidor MariaDB",
        font=ctk.CTkFont(family="Segoe UI", size=12),
        text_color=t_sec,
    )
    step_lbl.grid(row=1, column=0, padx=24, pady=(0, 12), sticky="w")

    body = ctk.CTkFrame(dlg, fg_color=theme.get("input_bg", "#1e293b"), corner_radius=8)
    body.grid(row=2, column=0, padx=24, sticky="ew")
    body.grid_columnconfigure(1, weight=1)

    # ── Passo 1: status servidor ─────────────────────────────────────────────
    p1 = ctk.CTkFrame(body, fg_color="transparent")
    p1.grid(row=0, column=0, columnspan=2, sticky="ew", padx=16, pady=16)
    srv_status = tk.StringVar()
    ctk.CTkLabel(p1, textvariable=srv_status, wraplength=420, justify="left",
                 font=ctk.CTkFont(size=11), text_color=t_pri).pack(anchor="w")

    # ── Passo 2: root ────────────────────────────────────────────────────────
    p2 = ctk.CTkFrame(body, fg_color="transparent")

    def _lbl(text: str, row: int) -> None:
        ctk.CTkLabel(p2, text=text, font=ctk.CTkFont(size=11),
                     text_color=t_sec).grid(row=row, column=0, padx=(0, 8), pady=6, sticky="e")

    v_root_pass = tk.StringVar(value=DbLocalServer.get_root_password())
    _lbl("Senha root", 0)
    ctk.CTkEntry(p2, textvariable=v_root_pass, width=220, show="•",
                 fg_color=card_bg, text_color=t_pri, border_color=sep_col).grid(
        row=0, column=1, pady=6, sticky="w")
    ctk.CTkLabel(
        p2,
        text="Instalação nova: deixe vazio. Se já definiu senha, informe aqui.",
        font=ctk.CTkFont(size=10), text_color=t_mut, wraplength=300, justify="left",
    ).grid(row=1, column=0, columnspan=2, pady=(0, 8), sticky="w")

    # ── Passo 3: arkland ─────────────────────────────────────────────────────
    p3 = ctk.CTkFrame(body, fg_color="transparent")
    v_shop_pass = tk.StringVar()
    v_shop_pass2 = tk.StringVar()
    _lbl3 = lambda t, r: ctk.CTkLabel(
        p3, text=t, font=ctk.CTkFont(size=11), text_color=t_sec,
    ).grid(row=r, column=0, padx=(0, 8), pady=6, sticky="e")

    _lbl3("Usuário loja", 0)
    ctk.CTkLabel(p3, text=_SHOP_USER, font=ctk.CTkFont(size=11, weight="bold"),
                 text_color=accent).grid(row=0, column=1, sticky="w", pady=6)
    _lbl3("Senha arkland", 1)
    ctk.CTkEntry(p3, textvariable=v_shop_pass, width=220, show="•",
                 fg_color=card_bg, text_color=t_pri, border_color=sep_col).grid(
        row=1, column=1, pady=6, sticky="w")
    _lbl3("Confirmar senha", 2)
    ctk.CTkEntry(p3, textvariable=v_shop_pass2, width=220, show="•",
                 fg_color=card_bg, text_color=t_pri, border_color=sep_col).grid(
        row=2, column=1, pady=6, sticky="w")
    ctk.CTkLabel(
        p3,
        text=f"Cria o banco {_DB_NAME}, usuário {_SHOP_USER} e tabelas da loja.",
        font=ctk.CTkFont(size=10), text_color=t_mut, wraplength=360, justify="left",
    ).grid(row=3, column=0, columnspan=2, pady=(4, 0), sticky="w")

    ctk.CTkLabel(dlg, textvariable=status_var,
                 font=ctk.CTkFont(size=10), text_color=t_mut).grid(
        row=3, column=0, padx=24, pady=(10, 0), sticky="w")

    btn_row = ctk.CTkFrame(dlg, fg_color="transparent")
    btn_row.grid(row=4, column=0, padx=24, pady=(16, 20), sticky="e")

    def _set_status(msg: str, *, error: bool = False) -> None:
        status_var.set(msg)
        status_color.set("#ef4444" if error else t_mut)

    def _refresh_srv_status() -> None:
        if not local_srv.is_installed():
            srv_status.set(
                "MariaDB portable não instalado.\n"
                "Feche o assistente, clique em «Instalar MariaDB» e volte aqui."
            )
        elif local_srv.is_running():
            srv_status.set("✓ MariaDB rodando em 127.0.0.1:3306")
        else:
            srv_status.set(
                "MariaDB instalado mas parado.\n"
                "Clique em «Iniciar servidor» no painel e volte ao assistente."
            )

    def _show_step(n: int) -> None:
        step_var.set(n)
        p1.grid_remove()
        p2.grid_remove()
        p3.grid_remove()
        if n == 1:
            step_lbl.configure(text="Passo 1 de 3 — Servidor MariaDB")
            p1.grid(row=0, column=0, columnspan=2, sticky="ew", padx=16, pady=16)
            _refresh_srv_status()
            btn_back.configure(state="disabled")
            btn_next.configure(text="Próximo →", state="normal")
            btn_run.grid_remove()
        elif n == 2:
            step_lbl.configure(text="Passo 2 de 3 — Conectar como root")
            p2.grid(row=0, column=0, columnspan=2, sticky="ew", padx=16, pady=16)
            btn_back.configure(state="normal")
            btn_next.configure(text="Próximo →", state="normal")
            btn_run.grid_remove()
        else:
            step_lbl.configure(text="Passo 3 de 3 — Criar banco e usuário")
            p3.grid(row=0, column=0, columnspan=2, sticky="ew", padx=16, pady=16)
            btn_back.configure(state="normal")
            btn_next.grid_remove()
            btn_run.grid(row=0, column=1, padx=(8, 0))

    def _test_root() -> bool:
        ok, msg = test_connection(
            host="127.0.0.1", port=3306, user="root",
            password=v_root_pass.get(),
        )
        if ok:
            DbLocalServer.set_root_password(v_root_pass.get())
            _set_status(msg)
            return True
        _set_status(msg, error=True)
        return False

    def _on_next() -> None:
        n = step_var.get()
        if n == 1:
            if not local_srv.is_running():
                _set_status("Inicie o MariaDB antes de continuar.", error=True)
                return
            _show_step(2)
            return
        if n == 2:
            _set_status("Testando conexão root...")
            dlg.update_idletasks()
            if not _test_root():
                return
            _show_step(3)

    def _on_run() -> None:
        pwd = v_shop_pass.get()
        pwd2 = v_shop_pass2.get()
        if not pwd:
            _set_status("Informe a senha do usuário arkland.", error=True)
            return
        if pwd != pwd2:
            _set_status("As senhas não coincidem.", error=True)
            return
        btn_run.configure(state="disabled")
        _set_status("Criando banco e tabelas...")

        def _worker() -> None:
            try:
                import pymysql  # type: ignore[import-untyped]

                conn = pymysql.connect(
                    host="127.0.0.1", port=3306, user="root",
                    password=v_root_pass.get(), connect_timeout=8,
                )
                if database_exists(conn):
                    conn.close()
                    dlg.after(0, lambda: (
                        _set_status(
                            f"Banco {_DB_NAME} já existe. Use «Migrar pts» se precisar importar dados.",
                            error=True,
                        ),
                        btn_run.configure(state="normal"),
                    ))
                    return
                executed, errors = execute_setup_sql(conn, pwd)
                conn.close()
                if errors:
                    dlg.after(0, lambda: (
                        _set_status(f"Erros: {errors[0]}", error=True),
                        btn_run.configure(state="normal"),
                    ))
                    return
                save_shop_connection_prefs(
                    host="127.0.0.1", port=3306,
                    user=_SHOP_USER, password=pwd, database=_DB_NAME,
                )

                def _done() -> None:
                    from tkinter import messagebox
                    messagebox.showinfo(
                        "Banco criado",
                        f"Banco {_DB_NAME} criado com sucesso!\n\n"
                        f"Usuário: {_SHOP_USER}\n"
                        f"Host: 127.0.0.1:3306\n\n"
                        "Configure os mesmos dados em:\n"
                        "• Loja → Web Store → Banco de Pedidos\n"
                        "• CustomShop → config.json → Database",
                        parent=dlg,
                    )
                    dlg.destroy()
                    if on_connected:
                        on_connected()

                dlg.after(0, _done)
            except Exception as exc:
                dlg.after(0, lambda: (
                    _set_status(str(exc), error=True),
                    btn_run.configure(state="normal"),
                ))

        threading.Thread(target=_worker, daemon=True).start()

    btn_back = ctk.CTkButton(btn_row, text="← Voltar", width=100, height=32,
                             fg_color="transparent", text_color=t_sec,
                             border_color=sep_col, border_width=1,
                             command=lambda: _show_step(max(1, step_var.get() - 1)))
    btn_back.grid(row=0, column=0, padx=(0, 8))

    btn_next = ctk.CTkButton(btn_row, text="Próximo →", width=120, height=32,
                             fg_color=accent, text_color="#000",
                             font=ctk.CTkFont(weight="bold"),
                             command=_on_next)
    btn_next.grid(row=0, column=1)

    btn_run = ctk.CTkButton(btn_row, text="▶ Criar banco", width=130, height=32,
                            fg_color=accent, text_color="#000",
                            font=ctk.CTkFont(weight="bold"),
                            command=_on_run)

    _show_step(1)
