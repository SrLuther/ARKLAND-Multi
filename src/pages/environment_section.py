"""Seção Configurações Globais — Ambiente ARKLAND SERVER."""
from __future__ import annotations

import os
import tkinter as tk
from tkinter import messagebox
from typing import TYPE_CHECKING

import customtkinter as ctk  # type: ignore[reportMissingImports]

from ..arkland_environment import (
    EnvironmentPaths,
    apply_cloud_backup_local_path,
    apply_cluster_dir_to_profiles,
    apply_paths_to_config,
    create_environment,
    environment_root_from_parent,
    resolve_environment,
    validate_environment,
)
from ..ui_constants import _CARD_BG, _GREEN_DARK, _GREEN_HOVER

if TYPE_CHECKING:
    from ..app import ARKServerManagerApp


def build_environment_section(app: "ARKServerManagerApp", parent, start_row: int) -> int:
    """Renderiza a seção e retorna a próxima linha livre no grid."""
    cfg = app.config_manager.config
    env = cfg.environment

    app._section_lbl(parent, start_row, "🏗  Ambiente ARKLAND SERVER")
    env_card = ctk.CTkFrame(parent, corner_radius=12, fg_color=_CARD_BG)
    env_card.grid(row=start_row + 1, column=0, padx=20, pady=(0, 14), sticky="ew")
    env_card.grid_columnconfigure(1, weight=1)

    ctk.CTkLabel(
        env_card,
        text="Pasta pai (será criada a subpasta «ARKLAND SERVER»):",
        width=200,
        anchor="w",
        text_color="gray60",
    ).grid(row=0, column=0, padx=16, pady=(14, 2), sticky="w")

    initial_parent = ""
    if env.root_path:
        root = environment_root_from_parent(env.root_path)
        initial_parent = str(root.parent)

    app._env_parent_var = tk.StringVar(value=initial_parent)
    fr_parent = ctk.CTkFrame(env_card, fg_color="transparent")
    fr_parent.grid(row=0, column=1, padx=(0, 16), pady=(14, 2), sticky="ew")
    fr_parent.grid_columnconfigure(0, weight=1)
    ctk.CTkEntry(
        fr_parent,
        textvariable=app._env_parent_var,
        height=34,
        placeholder_text="Ex: D:\\",
    ).grid(row=0, column=0, sticky="ew", padx=(0, 6))
    ctk.CTkButton(
        fr_parent,
        text="📁",
        width=34,
        height=34,
        command=lambda: app._browse_dir(app._env_parent_var),
    ).grid(row=0, column=1)

    init_paths = resolve_environment(cfg) or EnvironmentPaths(
        root=environment_root_from_parent(initial_parent or "C:\\")
    )
    app._env_preview_lbl = ctk.CTkLabel(
        env_card,
        text=init_paths.preview_tree(),
        text_color="gray55",
        font=ctk.CTkFont(family="Consolas", size=10),
        justify="left",
        anchor="w",
    )
    app._env_preview_lbl.grid(row=1, column=0, columnspan=2, padx=16, pady=(4, 6), sticky="w")

    app._env_status_lbl = ctk.CTkLabel(
        env_card,
        text="",
        text_color="gray50",
        font=ctk.CTkFont(size=11),
        justify="left",
        anchor="w",
        wraplength=680,
    )
    app._env_status_lbl.grid(row=2, column=0, columnspan=2, padx=16, pady=(0, 8), sticky="w")

    app._env_apply_paths_var = tk.BooleanVar(value=True)
    ctk.CTkCheckBox(
        env_card,
        text="Aplicar caminhos automaticamente ao criar (SteamCMD, backups, MAPAS, cluster…)",
        variable=app._env_apply_paths_var,
        checkmark_color="white",
        fg_color=_GREEN_DARK,
        hover_color=_GREEN_HOVER,
        font=ctk.CTkFont(size=11),
    ).grid(row=3, column=0, columnspan=2, padx=16, pady=(0, 6), sticky="w")

    ctk.CTkLabel(
        env_card,
        text="Servidores já configurados mantêm install_dir atual. Novos servidores usarão MAPAS/.",
        text_color="gray45",
        font=ctk.CTkFont(size=10),
        wraplength=680,
        justify="left",
    ).grid(row=4, column=0, columnspan=2, padx=16, pady=(0, 10), sticky="w")

    btn_row = ctk.CTkFrame(env_card, fg_color="transparent")
    btn_row.grid(row=5, column=0, columnspan=2, padx=16, pady=(0, 14), sticky="w")

    def _sync_preview(*_args) -> None:
        parent_path = app._env_parent_var.get().strip() or "C:\\"
        paths = EnvironmentPaths(root=environment_root_from_parent(parent_path))
        app._env_preview_lbl.configure(text=paths.preview_tree())
        _refresh_env_status(app)

    app._env_parent_var.trace_add("write", _sync_preview)

    ctk.CTkButton(
        btn_row,
        text="✨ Criar ambiente",
        height=34,
        width=140,
        fg_color=_GREEN_DARK,
        hover_color=_GREEN_HOVER,
        command=lambda: _create_environment(app),
    ).pack(side="left", padx=(0, 8))
    ctk.CTkButton(
        btn_row,
        text="🔧 Validar / Reparar",
        height=34,
        width=150,
        fg_color="#1e3a5f",
        hover_color="#2563eb",
        text_color="#7dd3fc",
        command=lambda: _repair_environment(app),
    ).pack(side="left", padx=(0, 8))
    ctk.CTkButton(
        btn_row,
        text="📂 Abrir pasta",
        height=34,
        width=120,
        fg_color="#0f172a",
        hover_color="#1e293b",
        command=lambda: _open_environment_folder(app),
    ).pack(side="left")

    _refresh_env_status(app)
    return start_row + 2


def _refresh_env_status(app: "ARKServerManagerApp") -> None:
    lbl = getattr(app, "_env_status_lbl", None)
    if lbl is None:
        return
    cfg = app.config_manager.config
    paths = resolve_environment(cfg)
    if paths and paths.root.is_dir():
        missing = validate_environment(paths.root)
        if missing:
            lbl.configure(
                text=f"⚠ Ambiente ativo em {paths.root} — pastas faltando: {', '.join(missing)}",
                text_color="#fbbf24",
            )
        else:
            lbl.configure(
                text=f"✅ Ambiente ativo: {paths.root}",
                text_color="#4ade80",
            )
        return
    parent = getattr(app, "_env_parent_var", tk.StringVar()).get().strip()
    if parent:
        root = environment_root_from_parent(parent)
        if root.is_dir():
            missing = validate_environment(root)
            if missing:
                lbl.configure(
                    text=f"Pasta em {root} — faltam: {', '.join(missing)} (use Reparar)",
                    text_color="#fbbf24",
                )
            else:
                lbl.configure(
                    text=f"Pasta pronta em {root} — clique em Criar para ativar no gerenciador",
                    text_color="gray55",
                )
            return
        lbl.configure(text=f"Será criado em: {root}", text_color="gray50")
        return
    lbl.configure(text="Escolha a pasta pai e clique em Criar ambiente.", text_color="gray50")


def _sync_path_vars_from_config(app: "ARKServerManagerApp") -> None:
    cfg = app.config_manager.config
    for attr, value in (
        ("_steamcmd_var", cfg.steamcmd_path),
        ("_default_dir_var", cfg.default_install_dir),
        ("_bk_dir_var", cfg.backup.backup_dir),
        ("_au_cache_dir_var", cfg.auto_update.cache_dir),
    ):
        var = getattr(app, attr, None)
        if var is not None and value:
            var.set(value)


def _resolve_parent_for_action(app: "ARKServerManagerApp") -> str:
    cfg = app.config_manager.config
    paths = resolve_environment(cfg)
    if paths:
        return str(paths.root.parent)
    return getattr(app, "_env_parent_var", tk.StringVar()).get().strip()


def _create_environment(app: "ARKServerManagerApp") -> None:
    parent = _resolve_parent_for_action(app)
    if not parent:
        messagebox.showwarning("Ambiente", "Selecione a pasta pai.", parent=app)
        return

    result = create_environment(parent)
    if result.failed:
        messagebox.showerror(
            "Ambiente",
            "Falha ao criar:\n" + "\n".join(result.failed),
            parent=app,
        )
        return

    apply_paths = getattr(app, "_env_apply_paths_var", tk.BooleanVar(value=True)).get()
    cfg = app.config_manager.config
    if apply_paths:
        apply_paths_to_config(cfg, result.paths)
        apply_cluster_dir_to_profiles(app.config_manager, result.paths)
        cloud_ok = apply_cloud_backup_local_path(result.paths)
        app.config_manager.save()
        _sync_path_vars_from_config(app)
        if hasattr(app, "mod_manager") and cfg.steamcmd_path:
            app.mod_manager.steamcmd_path = cfg.steamcmd_path
        extra = "\n• Cloud backup local → BACKUP/cloud" if cloud_ok else ""
        messagebox.showinfo(
            "Ambiente criado",
            f"Estrutura pronta em:\n{result.paths.root}\n\n"
            f"Criadas: {len(result.created)} pasta(s)\n"
            f"Já existiam: {len(result.existing)} pasta(s)\n\n"
            f"Caminhos globais atualizados.{extra}",
            parent=app,
        )
    else:
        messagebox.showinfo(
            "Ambiente criado",
            f"Pastas criadas em:\n{result.paths.root}\n\n"
            "Marque «Aplicar caminhos» e crie novamente, ou ajuste manualmente.",
            parent=app,
        )

    _refresh_env_status(app)


def _repair_environment(app: "ARKServerManagerApp") -> None:
    cfg = app.config_manager.config
    paths = resolve_environment(cfg)
    if paths:
        parent_path = str(paths.root.parent)
    else:
        parent_path = getattr(app, "_env_parent_var", tk.StringVar()).get().strip()
    if not parent_path:
        messagebox.showwarning("Ambiente", "Nenhum ambiente configurado.", parent=app)
        return

    result = create_environment(parent_path)
    if result.failed:
        messagebox.showerror("Reparar", "Falhas:\n" + "\n".join(result.failed), parent=app)
    else:
        created_msg = f"{len(result.created)} pasta(s) criada(s)." if result.created else "Tudo OK."
        messagebox.showinfo("Reparar", created_msg, parent=app)
    _refresh_env_status(app)


def _open_environment_folder(app: "ARKServerManagerApp") -> None:
    cfg = app.config_manager.config
    paths = resolve_environment(cfg)
    if paths is None:
        parent = getattr(app, "_env_parent_var", tk.StringVar()).get().strip()
        if not parent:
            messagebox.showwarning("Ambiente", "Nenhuma pasta para abrir.", parent=app)
            return
        target = environment_root_from_parent(parent)
    else:
        target = paths.root
    if not target.is_dir():
        messagebox.showwarning("Ambiente", f"Pasta não existe:\n{target}", parent=app)
        return
    os.startfile(str(target))
