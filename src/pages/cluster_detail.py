from __future__ import annotations

import os
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

    from .cluster_helpers import iter_linkable_servers, get_linkable_server_cfg
    from ..cluster_paths import resolve_cluster_dir_override

    linkable = iter_linkable_servers(app, prof.id)

    # ── Intro ─────────────────────────────────────────────────────────────
    app._section_lbl(parent, 0, f"📋  Perfil: {prof.name}")
    intro = ctk.CTkFrame(parent, corner_radius=12, fg_color=_CARD_BG)
    intro.grid(row=1, column=0, padx=20, pady=(0, 12), sticky="ew")
    ctk.CTkLabel(
        intro,
        text=(
            "Configure o cluster UMA vez aqui e marque quais mapas recebem essa configuração.\n"
            "Máquinas diferentes: pasta UNC compartilhada, sync, ou exporte/importe o perfil (.arkcluster)."
        ),
        text_color="gray55",
        font=ctk.CTkFont(size=11),
        justify="left",
        anchor="w",
        wraplength=720,
    ).pack(anchor="w", padx=16, pady=12)

    # ── Servidores que recebem esta config ────────────────────────────────
    app._section_lbl(parent, 2, "🖥  Mapas que recebem esta configuração")
    srv_card = ctk.CTkFrame(parent, corner_radius=12, fg_color=_CARD_BG)
    srv_card.grid(row=3, column=0, padx=20, pady=(0, 12), sticky="ew")
    srv_card.grid_columnconfigure(1, weight=1)

    if not linkable:
        ctk.CTkLabel(
            srv_card,
            text="Nenhum servidor cadastrado. Adicione mapas no Dashboard primeiro.",
            text_color="gray50",
        ).grid(row=0, column=0, columnspan=3, padx=16, pady=12, sticky="w")
    else:
        hdr = ctk.CTkFrame(srv_card, fg_color="transparent")
        hdr.grid(row=0, column=0, columnspan=3, sticky="ew", padx=12, pady=(10, 4))
        ctk.CTkLabel(
            hdr,
            text="Marque os mapas do cluster. O único campo diferente por mapa é a pasta de saves.",
            text_color="gray50",
            font=ctk.CTkFont(size=10),
            anchor="w",
        ).pack(side="left")

        def _select_all(on: bool) -> None:
            for item in linkable:
                v = dw.get(item.widget_key)
                if v is not None:
                    v.set(on)

        ctk.CTkButton(
            hdr, text="Marcar todos", width=100, height=26,
            fg_color="#1e293b", hover_color="#334155",
            command=lambda: _select_all(True),
        ).pack(side="right", padx=(6, 0))
        ctk.CTkButton(
            hdr, text="Desmarcar", width=90, height=26,
            fg_color="#1e293b", hover_color="#334155",
            command=lambda: _select_all(False),
        ).pack(side="right")

        ctk.CTkLabel(
            srv_card, text="Mapa", font=ctk.CTkFont(size=10, weight="bold"),
            text_color="gray60",
        ).grid(row=1, column=0, padx=(16, 4), sticky="w")
        ctk.CTkLabel(
            srv_card, text="Pasta de saves (?AltSaveDirectoryName)",
            font=ctk.CTkFont(size=10, weight="bold"),
            text_color="gray60",
        ).grid(row=1, column=1, padx=4, sticky="w")

        for si, item in enumerate(linkable):
            row_i = si + 2
            v = tk.BooleanVar(value=item.is_linked)
            dw[item.widget_key] = v
            dw[f"alt_{item.widget_key}"] = tk.StringVar(value=item.alt_save_directory_name)

            kind_tag = "TEK" if item.kind == "asm" else "Legado"
            label = f"{item.name}  ·  {item.map_label}  ·  :{item.port}  [{kind_tag}]"
            if item.other_cluster_name:
                label += f"  ⚠ já em «{item.other_cluster_name}»"

            cb_fr = ctk.CTkFrame(srv_card, fg_color="transparent")
            cb_fr.grid(row=row_i, column=0, padx=(12, 4), pady=3, sticky="w")
            ctk.CTkCheckBox(
                cb_fr, text=label, variable=v,
                checkmark_color="white", fg_color=_BLUE, hover_color=_BLUE_HOVER,
                font=ctk.CTkFont(size=11),
            ).pack(anchor="w")

            ctk.CTkEntry(
                srv_card, textvariable=dw[f"alt_{item.widget_key}"],
                height=28, placeholder_text="ex: SaveIsland",
            ).grid(row=row_i, column=1, padx=(0, 16), pady=3, sticky="ew")

    # ── Configuração única ───────────────────────────────────────────────
    app._section_lbl(parent, 4, "⚙️  Configuração única (todos os mapas marcados)")
    card = ctk.CTkFrame(parent, corner_radius=12, fg_color=_CARD_BG)
    card.grid(row=5, column=0, padx=20, pady=(0, 12), sticky="ew")
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
    _lbl("Nome do perfil:").grid(row=r, column=0, padx=(18, 6), pady=(14, 4), sticky="w")
    dw["name"] = tk.StringVar(value=prof.name)
    ctk.CTkEntry(card, textvariable=dw["name"], height=30, width=260).grid(
        row=r, column=1, padx=(0, 18), pady=(14, 4), sticky="w")
    r += 1

    _lbl("Modo:", "Local = mesma máquina | Rede = UNC entre PCs").grid(
        row=r, column=0, padx=(18, 6), pady=4, sticky="w")
    dw["mode"] = tk.StringVar(value=prof.mode)
    ctk.CTkOptionMenu(
        card, variable=dw["mode"], width=200, height=30,
        values=["local", "network"],
        fg_color=_CARD_BG, button_color=_BLUE, button_hover_color=_BLUE_HOVER,
    ).grid(row=r, column=1, padx=(0, 18), pady=4, sticky="w")
    r += 1

    _lbl("Cluster ID (-clusterid):", "Idêntico em todos os mapas — gerado uma vez aqui.").grid(
        row=r, column=0, padx=(18, 6), pady=4, sticky="nw")
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

    _lbl(
        "Pasta de viagem (-ClusterDirOverride):",
        "Rede sem sync: UNC igual em todos (\\\\NAS\\Pasta).\n"
        "Rede + sync: UNC aqui; cada PC usa pasta local do ARK automaticamente.\n"
        "Local: ex. C:\\ARKCluster",
    ).grid(row=r, column=0, padx=(18, 6), pady=4, sticky="nw")
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

    # ── Restrições ────────────────────────────────────────────────────────
    app._section_lbl(parent, 6, "🚫  Restrições de viagem (obelisco / terminal)")
    rest_card = ctk.CTkFrame(parent, corner_radius=12, fg_color=_CARD_BG)
    rest_card.grid(row=7, column=0, padx=20, pady=(0, 12), sticky="ew")
    rest_card.grid_columnconfigure(0, weight=1)

    restriction_fields = [
        ("enable_tribute_downloads", "Permitir downloads de tributo",
         "Habilita transferências via obelisco/terminal.", True),
        ("prevent_download_survivors", "Bloquear download de sobreviventes",
         "Impede importar personagens de outros mapas.", getattr(prof, "prevent_download_survivors", False)),
        ("prevent_download_items", "Bloquear download de itens",
         "Impede trazer itens de outros mapas.", getattr(prof, "prevent_download_items", False)),
        ("prevent_download_dinos", "Bloquear download de dinos",
         "Impede trazer dinos de outros mapas.", getattr(prof, "prevent_download_dinos", False)),
        ("prevent_upload_survivors", "Bloquear upload de sobreviventes",
         "Impede enviar personagem para o cluster.", getattr(prof, "prevent_upload_survivors", False)),
        ("prevent_upload_items", "Bloquear upload de itens",
         "Impede enviar itens ao cluster.", getattr(prof, "prevent_upload_items", False)),
        ("prevent_upload_dinos", "Bloquear upload de dinos",
         "Impede enviar dinos ao cluster.", getattr(prof, "prevent_upload_dinos", False)),
        ("no_transfer_from_filtering", "Bloquear transferência por filtro",
         "Impede bypass de filtros de mapa.", getattr(prof, "no_transfer_from_filtering", False)),
        ("cross_ark_allow_foreign_dino_downloads", "Permitir dinos de outros clusters",
         "Permite baixar dinos de clusters externos.", getattr(prof, "cross_ark_allow_foreign_dino_downloads", False)),
    ]
    for rr, (field_key, label, hint, default) in enumerate(restriction_fields):
        dw[field_key] = tk.BooleanVar(value=bool(default))
        cb_fr = ctk.CTkFrame(rest_card, fg_color="transparent")
        cb_fr.grid(row=rr, column=0, padx=16, pady=(8 if rr == 0 else 2, 2), sticky="w")
        ctk.CTkCheckBox(cb_fr, text=label, variable=dw[field_key],
                        checkmark_color="white", fg_color=_GREEN_DARK,
                        hover_color=_GREEN_HOVER).pack(anchor="w")
        ctk.CTkLabel(cb_fr, text=hint, text_color="gray40",
                     font=ctk.CTkFont(size=10), anchor="w").pack(
            anchor="w", padx=(26, 0), pady=(0, 2))

    # ── Sync ──────────────────────────────────────────────────────────────
    app._section_lbl(parent, 8, "🔄  Sincronização (máquinas diferentes)")
    sync_card = ctk.CTkFrame(parent, corner_radius=12, fg_color=_CARD_BG)
    sync_card.grid(row=9, column=0, padx=20, pady=(0, 12), sticky="ew")
    sync_card.grid_columnconfigure(1, weight=1)

    ctk.CTkLabel(
        sync_card,
        text=(
            "Replica arquivos de viagem entre pasta local e UNC quando cada PC tem seu próprio ARK.\n"
            "Sem pasta de rede acessível? Use «Exportar perfil» e importe no outro PC — "
            "cada máquina mantém seus dados locais com o mesmo Cluster ID."
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
        sync_card, text="Sincronizar automaticamente com a pasta de rede",
        variable=dw["sync_enabled"],
        checkmark_color="white", fg_color=_BLUE, hover_color=_BLUE_HOVER,
    ).grid(row=sr, column=0, columnspan=2, padx=16, pady=(4, 6), sticky="w")
    sr += 1

    _slbl("Pasta local (opcional):",
          "Vazio = ShooterGame\\Saved\\clusters de cada servidor vinculado.").grid(
        row=sr, column=0, padx=(16, 6), pady=4, sticky="nw")
    dw["local_cluster_dir"] = tk.StringVar(value=getattr(prof, "local_cluster_dir", ""))
    lcd_row = ctk.CTkFrame(sync_card, fg_color="transparent")
    lcd_row.grid(row=sr, column=1, padx=(0, 16), pady=4, sticky="ew")
    lcd_row.grid_columnconfigure(0, weight=1)
    ctk.CTkEntry(lcd_row, textvariable=dw["local_cluster_dir"], height=30).grid(
        row=0, column=0, sticky="ew", padx=(0, 6))
    ctk.CTkButton(lcd_row, text="📁", width=34, height=30,
                  command=lambda: app._browse_dir(dw["local_cluster_dir"])).grid(row=0, column=1)
    sr += 1

    _slbl("Intervalo (segundos):", "").grid(row=sr, column=0, padx=(16, 6), pady=4, sticky="w")
    dw["sync_interval_var"] = tk.StringVar(value=str(getattr(prof, "sync_interval", 30)))
    ctk.CTkEntry(sync_card, textvariable=dw["sync_interval_var"], height=30, width=80).grid(
        row=sr, column=1, padx=(0, 16), pady=4, sticky="w")
    sr += 1

    _prof_id_for_sync = prof.id
    _is_running = (
        _prof_id_for_sync in app._cluster_sync_engines
        and app._cluster_sync_engines[_prof_id_for_sync].is_running
    )
    sync_ctrl_fr = ctk.CTkFrame(sync_card, fg_color="transparent")
    sync_ctrl_fr.grid(row=sr, column=0, columnspan=2, padx=16, pady=(6, 12), sticky="w")
    ctk.CTkLabel(
        sync_ctrl_fr,
        text="● Sync ativo" if _is_running else "○ Sync parado",
        text_color=_GREEN if _is_running else "gray50",
        font=ctk.CTkFont(size=11, weight="bold"),
    ).pack(side="left", padx=(0, 12))

    def _toggle_cluster_sync():
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
        sync_ctrl_fr, text="🔄 Sync agora", width=110, height=30,
        fg_color=_CARD_BG, hover_color="#252540",
        command=lambda: app._cluster_sync_once(_prof_id_for_sync),
    ).pack(side="left")

    # ── Pré-visualização ──────────────────────────────────────────────────
    app._section_lbl(parent, 10, "👁  O que será aplicado ao salvar")
    prev_card = ctk.CTkFrame(parent, corner_radius=12, fg_color=_CARD_BG)
    prev_card.grid(row=11, column=0, padx=20, pady=(0, 12), sticky="ew")

    cid = prof.cluster_id or "(defina o Cluster ID)"
    cdir = prof.cluster_dir or "(defina a pasta)"
    prev_lines = [
        f"Cluster ID (todos):  {cid}",
        f"Pasta de viagem:      {cdir}",
        "",
    ]
    linked_preview = [item for item in linkable if item.is_linked]
    if linked_preview:
        prev_lines.append("Mapas vinculados atualmente:")
        for item in linked_preview:
            cfg = get_linkable_server_cfg(app, item)
            inst = (getattr(cfg, "install_dir", "") or "") if cfg else ""
            eff = resolve_cluster_dir_override(prof, install_dir=inst) if cfg else cdir
            prev_lines.append(
                f"  • {item.name} ({item.map_label}) → pasta ARK: {eff}  |  saves: {item.alt_save_directory_name}"
            )
    else:
        prev_lines.append("Nenhum mapa vinculado ainda — marque acima e clique em Salvar.")

    ctk.CTkLabel(
        prev_card,
        text="\n".join(prev_lines),
        text_color="gray60",
        font=ctk.CTkFont(family="Consolas", size=10),
        justify="left",
        anchor="w",
    ).pack(anchor="w", padx=16, pady=12)

    # ── Diagnóstico ───────────────────────────────────────────────────────
    app._section_lbl(parent, 12, "🔍  Diagnóstico rápido")
    diag_card = ctk.CTkFrame(parent, corner_radius=12, fg_color=_CARD_BG)
    diag_card.grid(row=13, column=0, padx=20, pady=(0, 12), sticky="ew")
    _diag_row = 0
    if prof.cluster_id:
        ctk.CTkLabel(diag_card, text=f"✅ Cluster ID: {prof.cluster_id}",
                     text_color="#4caf50", font=ctk.CTkFont(size=11), anchor="w").grid(
            row=_diag_row, column=0, padx=16, pady=(10, 4), sticky="w")
        _diag_row += 1
    else:
        ctk.CTkLabel(diag_card, text="❌ Cluster ID vazio",
                     text_color="#ff9800", font=ctk.CTkFont(size=11), anchor="w").grid(
            row=_diag_row, column=0, padx=16, pady=(10, 4), sticky="w")
        _diag_row += 1

    _cl_dir = prof.cluster_dir.replace("/", "\\") if prof.cluster_dir else ""
    from ..cluster_paths import validate_network_cluster_dir, is_network_share_path

    net_warn = validate_network_cluster_dir(prof)
    if net_warn:
        ctk.CTkLabel(
            diag_card, text=f"❌ {net_warn}",
            text_color="#f44336", font=ctk.CTkFont(size=10), anchor="w", justify="left",
            wraplength=520,
        ).grid(row=_diag_row, column=0, padx=16, pady=4, sticky="w")
        _diag_row += 1
    elif prof.mode == "network" and _cl_dir and not is_network_share_path(_cl_dir):
        ctk.CTkLabel(
            diag_card,
            text=(
                "⚠ Pasta local nesta máquina — em cluster entre PCs use o mesmo UNC "
                "(ex.: \\\\192.168.1.10\\ARKCluster\\crossark) nos dois Managers."
            ),
            text_color="#ff9800", font=ctk.CTkFont(size=10), anchor="w", justify="left",
            wraplength=520,
        ).grid(row=_diag_row, column=0, padx=16, pady=4, sticky="w")
        _diag_row += 1

    if _cl_dir and os.path.isdir(_cl_dir):
        ctk.CTkLabel(diag_card, text=f"✅ Pasta acessível: {_cl_dir}",
                     text_color="#4caf50", font=ctk.CTkFont(size=11), anchor="w").grid(
            row=_diag_row, column=0, padx=16, pady=4, sticky="w")
        _diag_row += 1
    elif _cl_dir:
        ctk.CTkLabel(diag_card, text=f"⚠ Pasta não encontrada (salvar tenta criar): {_cl_dir}",
                     text_color="#ff9800", font=ctk.CTkFont(size=11), anchor="w").grid(
            row=_diag_row, column=0, padx=16, pady=4, sticky="w")
        _diag_row += 1

    from .cluster_helpers import asm_servers_in_cluster
    n = len(app.config_manager.servers_in_cluster(prof.id)) + len(asm_servers_in_cluster(app, prof.id))
    ctk.CTkLabel(
        diag_card,
        text=f"{'✅' if n >= 2 else '⚠'} {n} mapa(s) vinculado(s)" + (" (recomendado: 2+)" if n < 2 else ""),
        text_color="#4caf50" if n >= 2 else "#ff9800",
        font=ctk.CTkFont(size=11), anchor="w",
    ).grid(row=_diag_row, column=0, padx=16, pady=(4, 12), sticky="w")

    # ── Botões ────────────────────────────────────────────────────────────
    btn_row = ctk.CTkFrame(parent, fg_color="transparent")
    btn_row.grid(row=14, column=0, padx=20, pady=(4, 20), sticky="w")

    ctk.CTkButton(
        btn_row, text="📤  Exportar perfil", width=140, height=36,
        fg_color="#1e3a5f", hover_color="#2a4a6a",
        command=lambda: app._cluster_export(prof.id),
    ).pack(side="left", padx=(0, 10))

    ctk.CTkButton(
        btn_row, text="💾  Salvar e aplicar aos mapas", width=200, height=36,
        fg_color=_GREEN_DARK, hover_color=_GREEN_HOVER,
        command=lambda: app._cluster_save(prof.id),
    ).pack(side="left", padx=(0, 10))
    ctk.CTkButton(
        btn_row, text="🧪  Testar viagem", width=140, height=36,
        fg_color=_BLUE, hover_color=_BLUE_HOVER,
        command=lambda: app._cluster_travel_test(prof.id),
    ).pack(side="left", padx=(0, 10))
    ctk.CTkButton(
        btn_row, text="🗑  Excluir perfil", width=120, height=36,
        fg_color="#5a1a1a", hover_color="#8b2222",
        command=lambda: app._cluster_delete(prof.id),
    ).pack(side="left")
