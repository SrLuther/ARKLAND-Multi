"""Atalho no painel do servidor → configuração central em Clusters."""
from __future__ import annotations

import tkinter as tk
from typing import TYPE_CHECKING, Any

import customtkinter as ctk  # type: ignore[reportMissingImports]

if TYPE_CHECKING:
    from ..app import ARKServerManagerApp
    from ..asm_engine.asm_server_config import AsmServerConfig
    from ..server_config import ServerConfig


def build_server_cluster_link_asm(
    sf: Any, srv: "AsmServerConfig", vars_ref: dict, accent: str, start_row: int,
) -> int:
    """Bloco compacto no painel TEK — cluster é configurado no menu Clusters."""
    from ..asm_ui.asm_server_panel import _section_label, _str_entry

    app: ARKServerManagerApp | None = vars_ref.get("_app")
    _section_label(sf, "Cross-ARK (cluster)", start_row, accent)
    r = start_row + 1

    profiles = app.config_manager.clusters if app else []
    profile_names = ["(nenhum — configure em Clusters)"] + [p.name for p in profiles]
    profile_ids = [""] + [p.id for p in profiles]
    current_pid = getattr(srv, "cluster_profile_id", "") or ""
    current_idx = profile_ids.index(current_pid) if current_pid in profile_ids else 0

    vars_ref["cluster_profile_id"] = tk.StringVar(value=current_pid)
    prof_name_var = tk.StringVar(value=profile_names[current_idx])

    ctk.CTkLabel(
        sf,
        text="Viagem entre mapas é definida UMA vez no menu Clusters. Escolha qual perfil este mapa usa:",
        font=ctk.CTkFont(size=10), text_color="#64748b", anchor="w", wraplength=520,
    ).grid(row=r, column=0, columnspan=2, padx=8, pady=(0, 4), sticky="w")
    r += 1

    row_fr = ctk.CTkFrame(sf, fg_color="transparent")
    row_fr.grid(row=r, column=0, columnspan=2, padx=8, pady=3, sticky="w")

    def _on_pick(choice: str) -> None:
        idx = profile_names.index(choice) if choice in profile_names else 0
        vars_ref["cluster_profile_id"].set(profile_ids[idx])

    ctk.CTkOptionMenu(
        row_fr, values=profile_names, variable=prof_name_var, width=260, height=28,
        command=_on_pick,
    ).pack(side="left", padx=(0, 8))

    if app:
        ctk.CTkButton(
            row_fr, text="Abrir Clusters…", width=120, height=28,
            fg_color=accent, hover_color="#0f766e",
            command=lambda: app._show_frame("clusters"),
        ).pack(side="left", padx=(0, 8))
        if current_pid:
            ctk.CTkButton(
                row_fr, text="Editar perfil", width=100, height=28,
                fg_color="#1e293b", hover_color="#334155",
                command=lambda: (app._show_frame("clusters"), app._cluster_select(current_pid)),
            ).pack(side="left")

    r += 1
    if current_pid and app:
        prof = app.config_manager.get_cluster(current_pid)
        if prof:
            from ..cluster_paths import resolve_cluster_dir_override
            eff = resolve_cluster_dir_override(prof, install_dir=srv.install_dir or "")
            ctk.CTkLabel(
                sf,
                text=f"Perfil ativo: {prof.name}  ·  ID: {prof.cluster_id}  ·  Pasta: {eff}",
                font=ctk.CTkFont(size=10), text_color="#94a3b8", anchor="w", wraplength=560,
            ).grid(row=r, column=0, columnspan=2, padx=8, pady=(0, 4), sticky="w")
            r += 1

    _str_entry(sf, "Pasta de saves deste mapa (?AltSaveDirectoryName)", "alt_save_directory_name",
               srv, vars_ref, r, accent)
    r += 1
    ctk.CTkLabel(
        sf,
        text="Único campo local por mapa — deve ser diferente em cada servidor na mesma máquina.",
        font=ctk.CTkFont(size=10), text_color="#64748b", anchor="w",
    ).grid(row=r, column=0, columnspan=2, padx=8, pady=(0, 6), sticky="w")
    return r + 1


def build_server_cluster_link_legacy(
    app: "ARKServerManagerApp",
    parent: Any,
    srv: "ServerConfig",
    w: dict,
    *,
    make_card,
    head,
    inner_bg: str,
    label_fg: str,
    hint_fg: str,
    font_bold,
    font_hint,
    blue: str,
    blue_hover: str,
) -> None:
    """Card compacto na aba Avançado — aponta para o menu Clusters."""
    c_cl = make_card(0, 0, colspan=2)
    head(c_cl, "🌐  Cross-ARK — configurar no menu Clusters")

    profiles = app.config_manager.clusters
    profile_names = ["(nenhum)"] + [p.name for p in profiles]
    profile_ids = [""] + [p.id for p in profiles]
    current_pid = srv.cluster_profile_id or ""
    current_idx = profile_ids.index(current_pid) if current_pid in profile_ids else 0
    w["cl_profile_id_var"] = tk.StringVar(value=profile_ids[current_idx])

    fr = tk.Frame(c_cl, bg=inner_bg)
    fr.pack(fill="x", padx=10, pady=8)
    tk.Label(
        fr,
        text="Defina Cluster ID, pasta de viagem e mapas vinculados uma única vez em "
             "Clusters (menu lateral). Aqui você só escolhe qual perfil este mapa usa.",
        bg=inner_bg, fg=hint_fg, font=font_hint, anchor="w", justify="left",
        wraplength=680,
    ).pack(anchor="w", pady=(0, 8))

    btn_fr = tk.Frame(fr, bg=inner_bg)
    btn_fr.pack(fill="x")

    def _on_pick(choice: str) -> None:
        idx = profile_names.index(choice) if choice in profile_names else 0
        w["cl_profile_id_var"].set(profile_ids[idx])

    ctk.CTkOptionMenu(
        btn_fr, values=profile_names, width=240, height=32,
        fg_color=inner_bg, button_color=blue, button_hover_color=blue_hover,
        command=_on_pick,
        variable=tk.StringVar(value=profile_names[current_idx]),
    ).pack(side="left", padx=(0, 8))
    ctk.CTkButton(
        btn_fr, text="Abrir Clusters…", width=130, height=32,
        fg_color=blue, hover_color=blue_hover,
        command=lambda: app._show_frame("clusters"),
    ).pack(side="left", padx=(0, 8))
    if current_pid:
        ctk.CTkButton(
            btn_fr, text="Editar perfil", width=110, height=32,
            fg_color="#2a4a6a", hover_color="#3a5a7a",
            command=lambda: (app._show_frame("clusters"), app._cluster_select(current_pid)),
        ).pack(side="left")

    if current_pid:
        prof = app.config_manager.get_cluster(current_pid)
        if prof:
            from ..cluster_paths import resolve_cluster_dir_override
            eff = resolve_cluster_dir_override(prof, install_dir=srv.install_dir or "")
            tk.Label(
                fr, text=f"Aplicado: ID {prof.cluster_id}  ·  Pasta {eff}",
                bg=inner_bg, fg="#9090d0", font=font_hint, anchor="w",
            ).pack(anchor="w", pady=(8, 4))

    alt_fr = tk.Frame(c_cl, bg=inner_bg)
    alt_fr.pack(fill="x", padx=10, pady=(0, 10))
    tk.Label(
        alt_fr, text="Pasta de saves deste mapa (?AltSaveDirectoryName):",
        bg=inner_bg, fg=label_fg, font=font_bold, anchor="w",
    ).pack(anchor="w")
    w["cl_alt_save_dir"] = tk.StringVar(value=srv.alt_save_directory_name or "savegame")
    ctk.CTkEntry(alt_fr, textvariable=w["cl_alt_save_dir"], height=32,
                 placeholder_text="ex: SaveIsland").pack(fill="x", pady=(4, 0))
