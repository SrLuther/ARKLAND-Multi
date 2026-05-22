from __future__ import annotations

import os
import uuid
import tkinter as tk
from typing import TYPE_CHECKING

import customtkinter as ctk  # type: ignore[reportMissingImports]

from ..ui_constants import (
    _GREEN, _GREEN_DARK, _GREEN_HOVER, _BLUE, _BLUE_HOVER, _CARD_BG,
)

if TYPE_CHECKING:
    from ..app import ARKServerManagerApp


def build_cluster_detail(app: "ARKServerManagerApp", prof) -> None:
    for w in app._cluster_detail_fr.winfo_children():
        w.destroy()
    dw = app._cluster_detail_widgets
    dw.clear()
    parent = app._cluster_detail_fr

    # ── Título ────────────────────────────────────────────────────────────
    app._section_lbl(parent, 0, f"📋  Perfil: {prof.name}")

    card = ctk.CTkFrame(parent, corner_radius=12, fg_color=_CARD_BG)
    card.grid(row=1, column=0, padx=20, pady=(0, 12), sticky="ew")
    card.grid_columnconfigure(1, weight=1)

    def _lbl(text, hint=""):
        fr = ctk.CTkFrame(card, fg_color="transparent")
        ctk.CTkLabel(fr, text=text, anchor="w", text_color="gray65",
                     font=ctk.CTkFont(size=12, weight="bold")).pack(anchor="w")
        if hint:
            ctk.CTkLabel(fr, text=hint, anchor="w", text_color="gray40",
                         font=ctk.CTkFont(size=10)).pack(anchor="w")
        return fr

    r = 0
    # Nome
    _lbl("Nome do perfil:").grid(row=r, column=0, padx=(18, 6), pady=(14, 4), sticky="w")
    dw["name"] = tk.StringVar(value=prof.name)
    ctk.CTkEntry(card, textvariable=dw["name"], height=30, width=260).grid(
        row=r, column=1, padx=(0, 18), pady=(14, 4), sticky="w")
    r += 1

    # Modo
    _lbl("Modo:", "Local = mesma máquina | Rede = pasta UNC/mapeada").grid(
        row=r, column=0, padx=(18, 6), pady=4, sticky="w")
    dw["mode"] = tk.StringVar(value=prof.mode)
    mode_menu = ctk.CTkOptionMenu(
        card, variable=dw["mode"], width=200, height=30,
        values=["local", "network"],
        fg_color=_CARD_BG, button_color=_BLUE, button_hover_color=_BLUE_HOVER,
    )
    mode_menu.set(prof.mode)
    mode_menu.grid(row=r, column=1, padx=(0, 18), pady=4, sticky="w")
    r += 1

    # Cluster ID
    _lbl("Cluster ID:",
         "Mesmo ID em todos os servidores do cluster. Gerado automaticamente.").grid(
        row=r, column=0, padx=(18, 6), pady=4, sticky="w")
    dw["cluster_id"] = tk.StringVar(value=prof.cluster_id)
    cid_row = ctk.CTkFrame(card, fg_color="transparent")
    cid_row.grid(row=r, column=1, padx=(0, 18), pady=4, sticky="ew")
    cid_row.grid_columnconfigure(0, weight=1)
    ctk.CTkEntry(cid_row, textvariable=dw["cluster_id"], height=30).grid(
        row=0, column=0, sticky="ew", padx=(0, 6))
    ctk.CTkButton(cid_row, text="🔄", width=34, height=30,
                  command=lambda: dw["cluster_id"].set(
                      __import__("uuid").uuid4().hex[:20])
                  ).grid(row=0, column=1)
    r += 1

    # Pasta do cluster
    _lbl("Pasta do Cluster:",
         "Local: caminho local (ex: C:\\ARKCluster)\n"
         "Rede: caminho UNC (ex: \\\\servidor\\ARKCluster) ou drive mapeado").grid(
        row=r, column=0, padx=(18, 6), pady=4, sticky="nw")
    dw["cluster_dir"] = tk.StringVar(value=prof.cluster_dir)
    dir_row = ctk.CTkFrame(card, fg_color="transparent")
    dir_row.grid(row=r, column=1, padx=(0, 18), pady=4, sticky="ew")
    dir_row.grid_columnconfigure(0, weight=1)
    ctk.CTkEntry(dir_row, textvariable=dw["cluster_dir"], height=30,
                 placeholder_text="C:\\ARKCluster  ou  \\\\servidor\\ARKCluster").grid(
        row=0, column=0, sticky="ew", padx=(0, 6))
    ctk.CTkButton(dir_row, text="📁", width=34, height=30,
                  command=lambda: app._browse_dir(dw["cluster_dir"])).grid(row=0, column=1)
    r += 1

    # Restrições
    app._section_lbl(parent, 2, "🚫  Restrições de Transferência")
    rest_card = ctk.CTkFrame(parent, corner_radius=12, fg_color=_CARD_BG)
    rest_card.grid(row=3, column=0, padx=20, pady=(0, 12), sticky="ew")
    rest_card.grid_columnconfigure(0, weight=1)

    for rr, (field_key, label, hint) in enumerate([
        ("prevent_download_survivors", "Bloquear Download de Sobreviventes",
         "Impede jogadores de importar personagens de outros servidores."),
        ("prevent_download_items",     "Bloquear Download de Itens",
         "Impede trazer itens de outros servidores."),
        ("prevent_download_dinos",     "Bloquear Download de Dinos",
         "Impede trazer dinos domesticados de outros servidores."),
        ("no_transfer_from_filtering", "Bloquear Transferência por Filtro",
         "Impede transferências bloqueadas por restrições de filtro de mapa."),
    ]):
        dw[field_key] = tk.BooleanVar(value=getattr(prof, field_key))
        cb_fr = ctk.CTkFrame(rest_card, fg_color="transparent")
        cb_fr.grid(row=rr, column=0, padx=16, pady=(8 if rr == 0 else 2, 2), sticky="w")
        ctk.CTkCheckBox(cb_fr, text=label, variable=dw[field_key],
                        checkmark_color="white", fg_color=_GREEN_DARK,
                        hover_color=_GREEN_HOVER).pack(anchor="w")
        ctk.CTkLabel(cb_fr, text=hint, text_color="gray40",
                     font=ctk.CTkFont(size=10), anchor="w").pack(
            anchor="w", padx=(26, 0), pady=(0, 2))

    # ── Sincronização de Dados de Viagem ─────────────────────────────────
    app._section_lbl(parent, 4, "🔄  Sincronização de Dados de Viagem")
    sync_card = ctk.CTkFrame(parent, corner_radius=12, fg_color=_CARD_BG)
    sync_card.grid(row=5, column=0, padx=20, pady=(0, 12), sticky="ew")
    sync_card.grid_columnconfigure(1, weight=1)

    ctk.CTkLabel(
        sync_card,
        text=(
            "Mantém sincronizados os arquivos de personagens, itens e dinos entre a pasta local do ARK\n"
            "e a pasta compartilhada de rede. Necessário quando os servidores estão em máquinas diferentes."
        ),
        text_color="gray50", font=ctk.CTkFont(size=10), justify="left", anchor="w",
    ).grid(row=0, column=0, columnspan=2, padx=16, pady=(10, 4), sticky="w")

    def _slbl(text, hint=""):
        fr = ctk.CTkFrame(sync_card, fg_color="transparent")
        ctk.CTkLabel(fr, text=text, anchor="w", text_color="gray65",
                     font=ctk.CTkFont(size=12, weight="bold")).pack(anchor="w")
        if hint:
            ctk.CTkLabel(fr, text=hint, anchor="w", text_color="gray40",
                         font=ctk.CTkFont(size=10)).pack(anchor="w")
        return fr

    sr = 1
    dw["sync_enabled"] = tk.BooleanVar(value=getattr(prof, "sync_enabled", False))
    ctk.CTkCheckBox(
        sync_card,
        text="Sincronizar automaticamente com a pasta de rede",
        variable=dw["sync_enabled"],
        checkmark_color="white", fg_color=_BLUE, hover_color=_BLUE_HOVER,
    ).grid(row=sr, column=0, columnspan=2, padx=16, pady=(4, 6), sticky="w")
    sr += 1

    _slbl("Pasta local de dados do cluster:",
          "Onde o ARK desta máquina grava os arquivos de viagem.\n"
          "Ex: C:\\ARK\\ShooterGame\\Saved\\clusters").grid(
        row=sr, column=0, padx=(16, 6), pady=4, sticky="nw")
    dw["local_cluster_dir"] = tk.StringVar(value=getattr(prof, "local_cluster_dir", ""))
    lcd_row = ctk.CTkFrame(sync_card, fg_color="transparent")
    lcd_row.grid(row=sr, column=1, padx=(0, 16), pady=4, sticky="ew")
    lcd_row.grid_columnconfigure(0, weight=1)
    ctk.CTkEntry(lcd_row, textvariable=dw["local_cluster_dir"], height=30,
                 placeholder_text="C:\\ARK\\ShooterGame\\Saved\\clusters").grid(
        row=0, column=0, sticky="ew", padx=(0, 6))
    ctk.CTkButton(lcd_row, text="📁", width=34, height=30,
                  command=lambda: app._browse_dir(dw["local_cluster_dir"])).grid(row=0, column=1)
    sr += 1

    _slbl("Intervalo (segundos):", "Tempo entre cada ciclo de sincronização automática.").grid(
        row=sr, column=0, padx=(16, 6), pady=4, sticky="w")
    dw["sync_interval_var"] = tk.StringVar(value=str(getattr(prof, "sync_interval", 30)))
    ctk.CTkEntry(sync_card, textvariable=dw["sync_interval_var"],
                 height=30, width=80).grid(
        row=sr, column=1, padx=(0, 16), pady=4, sticky="w")
    sr += 1

    _prof_id_for_sync = prof.id
    _is_running = (_prof_id_for_sync in app._cluster_sync_engines
                   and app._cluster_sync_engines[_prof_id_for_sync].is_running)
    _sync_status_lbl = ctk.CTkLabel(
        sync_card,
        text="● Ativo" if _is_running else "○ Parado",
        text_color=_GREEN if _is_running else "gray50",
        font=ctk.CTkFont(size=12, weight="bold"),
    )
    _sync_status_lbl.grid(row=sr, column=0, padx=16, pady=(6, 12), sticky="w")
    dw["_sync_status_lbl"] = _sync_status_lbl

    sync_ctrl_fr = ctk.CTkFrame(sync_card, fg_color="transparent")
    sync_ctrl_fr.grid(row=sr, column=1, padx=(0, 16), pady=(6, 12), sticky="w")

    def _toggle_cluster_sync():
        # Salva antes de iniciar para não perder campos não salvos
        app._cluster_save(_prof_id_for_sync)
        if (_prof_id_for_sync in app._cluster_sync_engines
                and app._cluster_sync_engines[_prof_id_for_sync].is_running):
            app._cluster_sync_stop(_prof_id_for_sync)
        else:
            app._cluster_sync_start(_prof_id_for_sync)
        p2 = app.config_manager.get_cluster(_prof_id_for_sync)
        if p2:
            app._cluster_build_detail(p2)

    ctk.CTkButton(
        sync_ctrl_fr,
        text="⏹ Parar" if _is_running else "▶ Iniciar",
        width=100, height=30,
        fg_color="#5a1a1a" if _is_running else _GREEN_DARK,
        hover_color="#8b2222" if _is_running else _GREEN_HOVER,
        command=_toggle_cluster_sync,
    ).pack(side="left", padx=(0, 8))
    ctk.CTkButton(
        sync_ctrl_fr, text="🔄 Sync Agora", width=120, height=30,
        fg_color=_CARD_BG, hover_color="#252540",
        command=lambda: app._cluster_sync_once(_prof_id_for_sync),
    ).pack(side="left")

    # ── Servidores vinculados ──────────────────────────────────────────────
    app._section_lbl(parent, 6, "🖥  Servidores neste Cluster")
    srv_card = ctk.CTkFrame(parent, corner_radius=12, fg_color=_CARD_BG)
    srv_card.grid(row=7, column=0, padx=20, pady=(0, 12), sticky="ew")
    srv_card.grid_columnconfigure(0, weight=1)

    linked = app.config_manager.servers_in_cluster(prof.id)
    all_srvs = app.config_manager.servers
    if not all_srvs:
        ctk.CTkLabel(srv_card, text="Nenhum servidor cadastrado.",
                     text_color="gray50").grid(row=0, column=0, padx=16, pady=12)
    else:
        for si, srv in enumerate(all_srvs):
            is_linked = srv.id in [s.id for s in linked]
            v = tk.BooleanVar(value=is_linked)
            dw[f"srv_{srv.id}"] = v
            map_name = srv.map.replace("_P", "").replace("_", " ")
            ctk.CTkCheckBox(
                srv_card,
                text=f"{srv.name}  ({map_name}  ·  :{srv.server_port})",
                variable=v,
                checkmark_color="white", fg_color=_BLUE, hover_color=_BLUE_HOVER,
            ).grid(row=si, column=0, padx=16, pady=(8 if si == 0 else 4, 4), sticky="w")

    # ── Diagnóstico ───────────────────────────────────────────────────────
    import os as _os
    app._section_lbl(parent, 8, "🔍  Diagnóstico")
    diag_card = ctk.CTkFrame(parent, corner_radius=12, fg_color=_CARD_BG)
    diag_card.grid(row=9, column=0, padx=20, pady=(0, 12), sticky="ew")
    diag_card.grid_columnconfigure(0, weight=1)

    _diag_row = 0
    _issues: list[str] = []

    # Verifica ClusterID
    if not prof.cluster_id:
        _issues.append("⚠️  Cluster ID não definido — todos os servidores precisam do mesmo ID para se conectar.")
    else:
        ctk.CTkLabel(diag_card, text=f"✅  Cluster ID: {prof.cluster_id}",
                     text_color="#4caf50", font=ctk.CTkFont(size=11),
                     anchor="w").grid(row=_diag_row, column=0, padx=16, pady=(10, 4), sticky="w")
        _diag_row += 1

    # Verifica pasta do cluster
    _cl_dir = prof.cluster_dir.replace("/", "\\") if prof.cluster_dir else ""
    if not _cl_dir:
        _issues.append("⚠️  Pasta do Cluster não configurada — obrigatória para CrossARK funcionar.")
    elif not _os.path.isdir(_cl_dir):
        _issues.append(f"⚠️  Pasta do Cluster não existe: {_cl_dir}\n    Salve o perfil para criá-la automaticamente.")
    else:
        ctk.CTkLabel(diag_card, text=f"✅  Pasta do Cluster existe: {_cl_dir}",
                     text_color="#4caf50", font=ctk.CTkFont(size=11),
                     anchor="w").grid(row=_diag_row, column=0, padx=16, pady=(10 if _diag_row == 0 else 4, 4), sticky="w")
        _diag_row += 1

    # Exibe problemas encontrados
    for _issue_txt in _issues:
        ctk.CTkLabel(diag_card, text=_issue_txt, text_color="#ff9800",
                     font=ctk.CTkFont(size=11), anchor="w", justify="left").grid(
            row=_diag_row, column=0, padx=16, pady=(10 if _diag_row == 0 else 4, 4), sticky="w")
        _diag_row += 1

    # Servidores vinculados vs. não vinculados
    _linked = app.config_manager.servers_in_cluster(prof.id)
    _linked_ids = {s.id for s in _linked}
    _all = app.config_manager.servers
    _unlinked = [s for s in _all if s.id not in _linked_ids]
    if _linked:
        ctk.CTkLabel(diag_card,
                     text=f"✅  {len(_linked)} servidor(es) vinculado(s) a este cluster",
                     text_color="#4caf50", font=ctk.CTkFont(size=11), anchor="w").grid(
            row=_diag_row, column=0, padx=16, pady=4, sticky="w")
        _diag_row += 1
    else:
        ctk.CTkLabel(diag_card,
                     text="⚠️  Nenhum servidor vinculado — marque os servidores acima e salve.",
                     text_color="#ff9800", font=ctk.CTkFont(size=11), anchor="w").grid(
            row=_diag_row, column=0, padx=16, pady=4, sticky="w")
        _diag_row += 1

    if _diag_row == 0:
        ctk.CTkLabel(diag_card, text="Sem problemas detectados.",
                     text_color="gray50").grid(row=0, column=0, padx=16, pady=12)

    # padding final
    ctk.CTkFrame(diag_card, height=6, fg_color="transparent").grid(
        row=_diag_row, column=0)

    # ── Botões ────────────────────────────────────────────────────────────
    btn_row = ctk.CTkFrame(parent, fg_color="transparent")
    btn_row.grid(row=10, column=0, padx=20, pady=(4, 20), sticky="w")

    ctk.CTkButton(
        btn_row, text="💾  Salvar", width=130, height=36,
        fg_color=_GREEN_DARK, hover_color=_GREEN_HOVER,
        command=lambda: app._cluster_save(prof.id),
    ).pack(side="left", padx=(0, 10))

    ctk.CTkButton(
        btn_row, text="🗑  Excluir", width=110, height=36,
        fg_color="#5a1a1a", hover_color="#8b2222",
        command=lambda: app._cluster_delete(prof.id),
    ).pack(side="left")

