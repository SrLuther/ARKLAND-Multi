from __future__ import annotations

import json
import os
import threading
import tkinter as tk
import webbrowser
from typing import TYPE_CHECKING

import customtkinter as ctk  # type: ignore[reportMissingImports]
from tkinter import filedialog
from tkinter import messagebox
from tkinter import ttk

from ..ui_constants import (
    _GREEN, _GREEN_DARK, _GREEN_HOVER,
    _RED_DARK, _RED_HOVER,
    _BLUE, _BLUE_HOVER,
    _CARD_BG,
)
from ..plugin_manager import PluginManager

if TYPE_CHECKING:
    from ..app import ARKServerManagerApp
    from ..server_config import ServerConfig


def build_tab_plugins(app: "ARKServerManagerApp", parent, srv: "ServerConfig") -> None:  # noqa: C901
    """Constrói a aba de gerenciamento do plugin CustomShop."""
    parent.grid_columnconfigure(0, weight=1)
    parent.grid_rowconfigure(1, weight=1)  # sub-tabview expande

    # ── estado compartilhado ──────────────────────────────────────────────
    _state: dict = {
        "timed_groups": [],
        "raw_cfg":     {},   # config bruta carregada do disco
        "tabs_built":  set(),
        "raw_items":   [],   # list[tuple[str, dict]] — TODOS os itens
        "raw_kits":    [],   # list[tuple[str, dict]] — TODOS os kits
    }

    # ══ STATUS CARD (fixo no topo, row=0) ════════════════════════════════
    status_card = ctk.CTkFrame(parent, corner_radius=10, fg_color=_CARD_BG)
    status_card.grid(row=0, column=0, padx=12, pady=(12, 4), sticky="ew")
    status_card.grid_columnconfigure(0, weight=1)

    ctk.CTkLabel(
        status_card, text="🔌  Plugin CustomShop",
        font=ctk.CTkFont(size=14, weight="bold"), anchor="w",
    ).grid(row=0, column=0, padx=16, pady=(12, 4), sticky="w")

    arkapi_lbl = ctk.CTkLabel(status_card, text="", anchor="w")
    arkapi_lbl.grid(row=1, column=0, padx=20, pady=(0, 2), sticky="w")
    plugin_lbl = ctk.CTkLabel(status_card, text="", anchor="w")
    plugin_lbl.grid(row=2, column=0, padx=20, pady=(0, 2), sticky="w")
    perms_lbl = ctk.CTkLabel(status_card, text="", anchor="w")
    perms_lbl.grid(row=3, column=0, padx=20, pady=(0, 6), sticky="w")

    btn_row = ctk.CTkFrame(status_card, fg_color="transparent")
    btn_row.grid(row=4, column=0, padx=12, pady=(0, 12), sticky="w")

    # ══ INNER TABVIEW (row=1, expande para preencher o espaço restante) ══
    inner_tabs = ctk.CTkTabview(parent, fg_color="transparent")
    inner_tabs.grid(row=1, column=0, padx=8, pady=(0, 8), sticky="nsew")
    for _t in ("⚙️ Config", "🛒 Itens", "🎁 Kits", "⏱ Pontos", "🗃️ BD"):
        inner_tabs.add(_t)
        inner_tabs.tab(_t).grid_columnconfigure(0, weight=1)
        inner_tabs.tab(_t).grid_rowconfigure(0, weight=1)
    inner_tabs.grid_remove()  # oculto até plugin instalado

    # ══ ABA CONFIG — conteúdo fixo, construído uma única vez ═════════════
    _tab_cfg = inner_tabs.tab("⚙️ Config")
    _tab_cfg.grid_rowconfigure(0, weight=1)
    cfg_scroll = ctk.CTkScrollableFrame(_tab_cfg, fg_color="transparent")
    cfg_scroll.grid(row=0, column=0, sticky="nsew")
    cfg_scroll.grid_columnconfigure(0, weight=1)

    # ══ SETTINGS CARD ═════════════════════════════════════════════════════
    settings_card = ctk.CTkFrame(cfg_scroll, corner_radius=10, fg_color=_CARD_BG)
    settings_card.grid(row=0, column=0, padx=4, pady=(4, 6), sticky="ew")
    settings_card.grid_columnconfigure(1, weight=1)
    settings_card.grid_columnconfigure(3, weight=1)

    ctk.CTkLabel(
        settings_card, text="⚙️  Configurações Gerais",
        font=ctk.CTkFont(size=13, weight="bold"), anchor="w",
    ).grid(row=0, column=0, columnspan=4, padx=16, pady=(12, 8), sticky="w")

    def _cfg_lbl(text: str) -> ctk.CTkLabel:
        return ctk.CTkLabel(settings_card, text=text, text_color="gray60",
                            anchor="w", width=155)

    def _sec_sep(text: str, row: int) -> None:
        ctk.CTkLabel(settings_card, text=f"  {text}",
                     text_color="gray45", font=ctk.CTkFont(size=10),
                     fg_color="#1c1c2a", corner_radius=3, anchor="w",
                     ).grid(row=row, column=0, columnspan=4,
                            padx=10, pady=(8, 2), sticky="ew")

    sv_shop_name      = tk.StringVar()
    sv_ui_key         = tk.StringVar()
    sv_start_pts      = tk.StringVar()
    sv_items_per_page = tk.StringVar()
    sv_display_time   = tk.StringVar()
    sv_text_size      = tk.StringVar()
    sv_default_kit    = tk.StringVar()
    sv_db_path        = tk.StringVar()
    bv_no_sell        = tk.BooleanVar()
    bv_no_trade       = tk.BooleanVar()
    bv_orig_trade     = tk.BooleanVar()
    bv_dinos_cryo     = tk.BooleanVar()
    bv_soul_traps     = tk.BooleanVar()
    bv_cryo_limited   = tk.BooleanVar()
    bv_no_noglin      = tk.BooleanVar()
    bv_no_unconscious = tk.BooleanVar()
    bv_no_handcuffed  = tk.BooleanVar()
    bv_no_carried     = tk.BooleanVar()

    # ── Loja ─────────────────────────────────────────────────────────────
    _sec_sep("Loja", 1)
    _cfg_lbl("Nome da loja:").grid(row=2, column=0, padx=(16, 4), pady=3, sticky="w")
    ctk.CTkEntry(settings_card, textvariable=sv_shop_name, height=28, width=200
                 ).grid(row=2, column=1, padx=(0, 10), pady=3, sticky="w")
    _cfg_lbl("Tecla de abrir (UiKey):").grid(row=2, column=2, padx=(10, 4), pady=3, sticky="w")
    ctk.CTkEntry(settings_card, textvariable=sv_ui_key, height=28, width=70
                 ).grid(row=2, column=3, padx=(0, 16), pady=3, sticky="w")

    _cfg_lbl("Pontos iniciais:").grid(row=3, column=0, padx=(16, 4), pady=3, sticky="w")
    ctk.CTkEntry(settings_card, textvariable=sv_start_pts, height=28, width=70
                 ).grid(row=3, column=1, padx=(0, 10), pady=3, sticky="w")
    _cfg_lbl("Itens por página:").grid(row=3, column=2, padx=(10, 4), pady=3, sticky="w")
    ctk.CTkEntry(settings_card, textvariable=sv_items_per_page, height=28, width=70
                 ).grid(row=3, column=3, padx=(0, 16), pady=3, sticky="w")

    _cfg_lbl("Tempo exibição (s):").grid(row=4, column=0, padx=(16, 4), pady=3, sticky="w")
    ctk.CTkEntry(settings_card, textvariable=sv_display_time, height=28, width=70
                 ).grid(row=4, column=1, padx=(0, 10), pady=3, sticky="w")
    _cfg_lbl("Tamanho do texto:").grid(row=4, column=2, padx=(10, 4), pady=3, sticky="w")
    ctk.CTkEntry(settings_card, textvariable=sv_text_size, height=28, width=70
                 ).grid(row=4, column=3, padx=(0, 16), pady=3, sticky="w")

    _cfg_lbl("Kit padrão:").grid(row=5, column=0, padx=(16, 4), pady=3, sticky="w")
    ctk.CTkEntry(settings_card, textvariable=sv_default_kit, height=28, width=140
                 ).grid(row=5, column=1, padx=(0, 10), pady=3, sticky="w")

    _cfg_lbl("Caminho BD (override):").grid(row=6, column=0, padx=(16, 4), pady=3, sticky="w")
    ctk.CTkEntry(settings_card, textvariable=sv_db_path, height=28,
                 placeholder_text="Deixe vazio para usar o padrão"
                 ).grid(row=6, column=1, columnspan=3, padx=(0, 16), pady=3, sticky="ew")

    # ── Botões ───────────────────────────────────────────────────────────
    _sec_sep("Botões", 7)
    _cfg_lbl("Desativar botão Vender:").grid(row=8, column=0, padx=(16, 4), pady=3, sticky="w")
    ctk.CTkSwitch(settings_card, text="", variable=bv_no_sell, width=48
                  ).grid(row=8, column=1, padx=(0, 10), pady=3, sticky="w")
    _cfg_lbl("Desativar botão Trocar:").grid(row=8, column=2, padx=(10, 4), pady=3, sticky="w")
    ctk.CTkSwitch(settings_card, text="", variable=bv_no_trade, width=48
                  ).grid(row=8, column=3, padx=(0, 16), pady=3, sticky="w")

    _cfg_lbl("Troca original com UI:").grid(row=9, column=0, padx=(16, 4), pady=3, sticky="w")
    ctk.CTkSwitch(settings_card, text="", variable=bv_orig_trade, width=48
                  ).grid(row=9, column=1, padx=(0, 10), pady=3, sticky="w")

    # ── Criaturas / Cryo ─────────────────────────────────────────────────
    _sec_sep("Criaturas / Cryo", 10)
    _cfg_lbl("Dinos em Cryopods:").grid(row=11, column=0, padx=(16, 4), pady=3, sticky="w")
    ctk.CTkSwitch(settings_card, text="", variable=bv_dinos_cryo, width=48
                  ).grid(row=11, column=1, padx=(0, 10), pady=3, sticky="w")
    _cfg_lbl("Soul Traps:").grid(row=11, column=2, padx=(10, 4), pady=3, sticky="w")
    ctk.CTkSwitch(settings_card, text="", variable=bv_soul_traps, width=48
                  ).grid(row=11, column=3, padx=(0, 16), pady=3, sticky="w")

    _cfg_lbl("Cryo tempo limitado:").grid(row=12, column=0, padx=(16, 4), pady=3, sticky="w")
    ctk.CTkSwitch(settings_card, text="", variable=bv_cryo_limited, width=48
                  ).grid(row=12, column=1, padx=(0, 10), pady=3, sticky="w")

    # ── Restrições de uso ─────────────────────────────────────────────────
    _sec_sep("Restrições de uso", 13)
    _cfg_lbl("Bloquear com Noglin:").grid(row=14, column=0, padx=(16, 4), pady=3, sticky="w")
    ctk.CTkSwitch(settings_card, text="", variable=bv_no_noglin, width=48
                  ).grid(row=14, column=1, padx=(0, 10), pady=3, sticky="w")
    _cfg_lbl("Bloquear inconsciente:").grid(row=14, column=2, padx=(10, 4), pady=3, sticky="w")
    ctk.CTkSwitch(settings_card, text="", variable=bv_no_unconscious, width=48
                  ).grid(row=14, column=3, padx=(0, 16), pady=3, sticky="w")

    _cfg_lbl("Bloquear algemado:").grid(row=15, column=0, padx=(16, 4), pady=3, sticky="w")
    ctk.CTkSwitch(settings_card, text="", variable=bv_no_handcuffed, width=48
                  ).grid(row=15, column=1, padx=(0, 10), pady=3, sticky="w")
    _cfg_lbl("Bloquear sendo carregado:").grid(row=15, column=2, padx=(10, 4), pady=3, sticky="w")
    ctk.CTkSwitch(settings_card, text="", variable=bv_no_carried, width=48
                  ).grid(row=15, column=3, padx=(0, 16), pady=(3, 12), sticky="w")

    # ── Botões de ação (sub-aba Config) ───────────────────────────────────
    save_row = ctk.CTkFrame(cfg_scroll, fg_color="transparent")
    save_row.grid(row=1, column=0, padx=4, pady=(0, 8), sticky="w")

    # ══ ABA ITENS — Treeview + painel de edição único ════════════════════
    _tab_items = inner_tabs.tab("🛒 Itens")
    _tab_items.grid_rowconfigure(1, weight=1)
    _tab_items.grid_rowconfigure(3, weight=0)
    _tab_items.grid_columnconfigure(0, weight=1)

    # ── Cabeçalho
    items_hdr = ctk.CTkFrame(_tab_items, fg_color="transparent")
    items_hdr.grid(row=0, column=0, padx=4, pady=(6, 2), sticky="ew")
    items_hdr.grid_columnconfigure(1, weight=1)
    ctk.CTkLabel(items_hdr, text="🛒  Itens da Loja",
                 font=ctk.CTkFont(size=13, weight="bold"), anchor="w"
                 ).grid(row=0, column=0, padx=(0, 8), sticky="w")
    sv_items_search = tk.StringVar()
    ctk.CTkEntry(items_hdr, textvariable=sv_items_search, height=28, width=180,
                 placeholder_text="🔍 Buscar por ID..."
                 ).grid(row=0, column=1, sticky="w")
    ctk.CTkButton(
        items_hdr, text="+ Item", height=28, width=80,
        fg_color="#3a3a5a", hover_color="#252540",
        command=lambda: _add_new_item(),
    ).grid(row=0, column=2, padx=(8, 0), sticky="e")
    ctk.CTkButton(
        items_hdr, text="🗑 Excluir", height=28, width=90,
        fg_color=_RED_DARK, hover_color=_RED_HOVER,
        command=lambda: _delete_selected_item(),
    ).grid(row=0, column=3, padx=(4, 0), sticky="e")

    # ── Treeview de itens (C nativo, sem Canvas CTk)
    _tv_items_container = tk.Frame(_tab_items, bg="#1e1e2e")
    _tv_items_container.grid(row=1, column=0, padx=4, pady=(0, 2), sticky="nsew")
    _tv_items_container.grid_columnconfigure(0, weight=1)
    _tv_items_container.grid_rowconfigure(0, weight=1)

    _items_tv_style = ttk.Style()
    _items_tv_style.theme_use("default")
    _items_tv_style.configure("Items.Treeview",
        background="#252535", foreground="#dddddd",
        fieldbackground="#252535", rowheight=26, borderwidth=0,
        font=("Segoe UI", 11))
    _items_tv_style.configure("Items.Treeview.Heading",
        background="#1a1a2e", foreground="#9090bb",
        relief="flat", font=("Segoe UI", 11, "bold"))
    _items_tv_style.map("Items.Treeview",
        background=[("selected", "#3a3a6e")],
        foreground=[("selected", "white")])

    items_tv = ttk.Treeview(
        _tv_items_container, style="Items.Treeview",
        columns=("type", "price"), show="tree headings",
        selectmode="browse")
    items_tv.heading("#0", text="ID")
    items_tv.heading("type", text="Tipo")
    items_tv.heading("price", text="Preço")
    items_tv.column("#0", width=220, minwidth=100)
    items_tv.column("type", width=90, minwidth=60)
    items_tv.column("price", width=80, minwidth=50)
    _tv_items_vsb = ttk.Scrollbar(_tv_items_container, orient="vertical",
                                  command=items_tv.yview)
    items_tv.configure(yscrollcommand=_tv_items_vsb.set)
    items_tv.grid(row=0, column=0, sticky="nsew")
    _tv_items_vsb.grid(row=0, column=1, sticky="ns")

    # ── Separador de painel de edição
    _items_edit_lbl = ctk.CTkLabel(_tab_items,
        text="─── Editar Item Selecionado ───",
        text_color="gray50", font=ctk.CTkFont(size=11))
    _items_edit_lbl.grid(row=2, column=0, padx=4, pady=(2, 0), sticky="w")

    # ── Painel de edição único (CTkScrollableFrame, altura fixa)
    items_edit_scroll = ctk.CTkScrollableFrame(_tab_items, fg_color="transparent",
                                               height=260)
    items_edit_scroll.grid(row=3, column=0, padx=4, pady=(0, 4), sticky="ew")
    items_edit_scroll.grid_columnconfigure(0, weight=1)

    # Vars do painel de edição de itens
    _sv_ei_id           = tk.StringVar()
    _sv_ei_price        = tk.StringVar(value="0")
    _sv_ei_type         = tk.StringVar(value="item")
    _sv_ei_desc         = tk.StringVar()
    _sv_ei_bp           = tk.StringVar()
    _sv_ei_qty          = tk.StringVar(value="1")
    _sv_ei_qual         = tk.StringVar(value="0.0")
    _bv_ei_force_bp     = tk.BooleanVar(value=False)
    _sv_ei_dino_level   = tk.StringVar(value="1")
    _sv_ei_dino_gender  = tk.StringVar(value="Random")
    _bv_ei_dino_neutered = tk.BooleanVar(value=False)
    _edit_item_idx      = [-1]   # [0] = índice em raw_items, -1 = nenhum

    # Linha 0: ID | Tipo | Preço
    _ei_row0 = ctk.CTkFrame(items_edit_scroll, fg_color="transparent")
    _ei_row0.grid(row=0, column=0, padx=4, pady=(8, 2), sticky="ew")
    _ei_row0.grid_columnconfigure(1, weight=1)
    ctk.CTkLabel(_ei_row0, text="ID:", text_color="gray55", width=28
                 ).grid(row=0, column=0, padx=(0, 2))
    ctk.CTkEntry(_ei_row0, textvariable=_sv_ei_id, height=28
                 ).grid(row=0, column=1, padx=(0, 8), sticky="ew")
    ctk.CTkLabel(_ei_row0, text="Tipo:", text_color="gray55", width=38
                 ).grid(row=0, column=2, padx=(0, 2))
    _ei_type_om = ctk.CTkOptionMenu(_ei_row0, values=["item", "command", "dino"],
                                    variable=_sv_ei_type, width=110, height=28)
    _ei_type_om.grid(row=0, column=3, padx=(0, 8))
    ctk.CTkLabel(_ei_row0, text="Preço:", text_color="gray55", width=44
                 ).grid(row=0, column=4, padx=(0, 2))
    ctk.CTkEntry(_ei_row0, textvariable=_sv_ei_price, height=28, width=80
                 ).grid(row=0, column=5)

    # Linha 1: Descrição
    _ei_row1 = ctk.CTkFrame(items_edit_scroll, fg_color="transparent")
    _ei_row1.grid(row=1, column=0, padx=4, pady=2, sticky="ew")
    _ei_row1.grid_columnconfigure(1, weight=1)
    ctk.CTkLabel(_ei_row1, text="Desc:", text_color="gray55", width=36
                 ).grid(row=0, column=0, padx=(0, 2))
    ctk.CTkEntry(_ei_row1, textvariable=_sv_ei_desc, height=28,
                 placeholder_text="Descrição exibida na loja"
                 ).grid(row=0, column=1, sticky="ew")

    # ── Seção ITEM (bp/qty/qual/force_bp)
    _ei_item_frame = ctk.CTkFrame(items_edit_scroll, fg_color="transparent")
    _ei_item_frame.grid(row=2, column=0, padx=4, pady=2, sticky="ew")
    _ei_item_frame.grid_columnconfigure(1, weight=1)
    ctk.CTkLabel(_ei_item_frame, text="BP:", text_color="gray55", width=28
                 ).grid(row=0, column=0, padx=(0, 2))
    ctk.CTkEntry(_ei_item_frame, textvariable=_sv_ei_bp, height=28,
                 placeholder_text="/Game/PrimalEarth/..."
                 ).grid(row=0, column=1, columnspan=5, padx=(0, 0), sticky="ew")
    _ei_qty_row = ctk.CTkFrame(_ei_item_frame, fg_color="transparent")
    _ei_qty_row.grid(row=1, column=0, columnspan=6, sticky="ew")
    ctk.CTkLabel(_ei_qty_row, text="Qtd:", text_color="gray55", width=32
                 ).pack(side="left", padx=(0, 2))
    ctk.CTkEntry(_ei_qty_row, textvariable=_sv_ei_qty, height=28, width=70
                 ).pack(side="left", padx=(0, 12))
    ctk.CTkLabel(_ei_qty_row, text="Qual:", text_color="gray55", width=38
                 ).pack(side="left", padx=(0, 2))
    ctk.CTkEntry(_ei_qty_row, textvariable=_sv_ei_qual, height=28, width=70
                 ).pack(side="left", padx=(0, 12))
    ctk.CTkCheckBox(_ei_qty_row, text="Forçar BP", variable=_bv_ei_force_bp,
                    text_color="gray60", height=28
                    ).pack(side="left")

    # ── Seção DINO (blueprint + nível/gênero/castrado)
    _ei_dino_frame = ctk.CTkFrame(items_edit_scroll, fg_color="transparent")
    _ei_dino_frame.grid(row=3, column=0, padx=4, pady=2, sticky="ew")
    _ei_dino_frame.grid_columnconfigure(1, weight=1)
    _ei_dino_frame.grid_remove()

    ctk.CTkLabel(_ei_dino_frame, text="BP:", text_color="gray55", width=28
                 ).grid(row=0, column=0, padx=(0, 2))
    ctk.CTkEntry(_ei_dino_frame, textvariable=_sv_ei_bp, height=28,
                 placeholder_text="/Game/PrimalEarth/Dinos/Rex/Rex_Character_BP.Rex_Character_BP_C"
                 ).grid(row=0, column=1, columnspan=5, sticky="ew")

    _ei_dino_row1 = ctk.CTkFrame(_ei_dino_frame, fg_color="transparent")
    _ei_dino_row1.grid(row=1, column=0, columnspan=6, sticky="ew", pady=(4, 0))
    ctk.CTkLabel(_ei_dino_row1, text="Nível:", text_color="gray55", width=44
                 ).pack(side="left", padx=(0, 2))
    ctk.CTkEntry(_ei_dino_row1, textvariable=_sv_ei_dino_level, height=28, width=70
                 ).pack(side="left", padx=(0, 14))
    ctk.CTkLabel(_ei_dino_row1, text="Gênero:", text_color="gray55", width=56
                 ).pack(side="left", padx=(0, 2))
    ctk.CTkOptionMenu(_ei_dino_row1,
                      values=["Random", "Male", "Female"],
                      variable=_sv_ei_dino_gender, width=110, height=28
                      ).pack(side="left", padx=(0, 14))
    ctk.CTkCheckBox(_ei_dino_row1, text="Castrado", variable=_bv_ei_dino_neutered,
                    text_color="gray60", height=28
                    ).pack(side="left")

    # ── Seção COMMAND
    _ei_cmd_frame = ctk.CTkFrame(items_edit_scroll, fg_color="transparent")
    _ei_cmd_frame.grid(row=4, column=0, padx=4, pady=2, sticky="ew")
    _ei_cmd_frame.grid_columnconfigure(0, weight=1)
    _ei_cmd_frame.grid_remove()

    ctk.CTkLabel(_ei_cmd_frame, text="Comandos:", text_color="gray55",
                 font=ctk.CTkFont(size=11), anchor="w"
                 ).grid(row=0, column=0, pady=(4, 2), sticky="w")
    _ei_cmd_list = ctk.CTkFrame(_ei_cmd_frame, fg_color="transparent")
    _ei_cmd_list.grid(row=1, column=0, sticky="ew")
    _ei_cmd_list.grid_columnconfigure(0, weight=1)
    _ei_cmd_rows: list = []

    def _add_ei_cmd_row(command: str = "", display_as: str = "",
                        exec_admin: bool = True) -> None:
        cr: dict = {}
        _ei_cmd_rows.append(cr)
        cidx = len(_ei_cmd_rows) - 1
        cf = ctk.CTkFrame(_ei_cmd_list, fg_color="#1e1e2e", corner_radius=4)
        cf.grid(row=cidx, column=0, pady=1, sticky="ew")
        cf.grid_columnconfigure(1, weight=1)
        cf.grid_columnconfigure(3, weight=1)
        cr["_frame"] = cf

        def _del_cr(c=cr, f=cf):
            if c in _ei_cmd_rows:
                _ei_cmd_rows.remove(c)
            f.destroy()

        ctk.CTkLabel(cf, text="Cmd:", text_color="gray55", width=36
                     ).grid(row=0, column=0, padx=(6, 2), pady=3)
        cr["command"] = tk.StringVar(value=command)
        ctk.CTkEntry(cf, textvariable=cr["command"], height=26,
                     placeholder_text="Permissions.AddTimed {steamid} grupo 720"
                     ).grid(row=0, column=1, padx=(0, 6), pady=3, sticky="ew")
        ctk.CTkLabel(cf, text="Exibir:", text_color="gray55", width=50
                     ).grid(row=0, column=2, padx=(4, 2), pady=3)
        cr["display_as"] = tk.StringVar(value=display_as)
        ctk.CTkEntry(cf, textvariable=cr["display_as"], height=26, width=140
                     ).grid(row=0, column=3, padx=(0, 6), pady=3, sticky="ew")
        cr["exec_as_admin"] = tk.BooleanVar(value=exec_admin)
        ctk.CTkCheckBox(cf, text="Admin", variable=cr["exec_as_admin"],
                        text_color="gray60", height=24, width=64
                        ).grid(row=0, column=4, padx=4, pady=3)
        ctk.CTkButton(cf, text="✕", width=24, height=24,
                      fg_color=_RED_DARK, hover_color=_RED_HOVER,
                      command=_del_cr).grid(row=0, column=5, padx=(2, 6), pady=3)

    ctk.CTkButton(
        _ei_cmd_frame, text="+ Comando", height=26, width=120,
        fg_color="#3a3a5a", hover_color="#252540",
        command=lambda: _add_ei_cmd_row(),
    ).grid(row=2, column=0, pady=(2, 4), sticky="w")

    # Toggle item/command/dino seção ao mudar tipo
    def _on_ei_type_change(v: str) -> None:
        _ei_item_frame.grid_remove()
        _ei_cmd_frame.grid_remove()
        _ei_dino_frame.grid_remove()
        if v == "command":
            _ei_cmd_frame.grid()
        elif v == "dino":
            _ei_dino_frame.grid()
        else:
            _ei_item_frame.grid()
    _sv_ei_type.trace_add("write", lambda *_: _on_ei_type_change(_sv_ei_type.get()))

    # ══ ABA KITS — Treeview + painel de edição único ══════════════════════
    _tab_kits = inner_tabs.tab("🎁 Kits")
    _tab_kits.grid_rowconfigure(1, weight=1)
    _tab_kits.grid_rowconfigure(3, weight=0)
    _tab_kits.grid_columnconfigure(0, weight=1)

    # ── Cabeçalho kits
    kits_hdr = ctk.CTkFrame(_tab_kits, fg_color="transparent")
    kits_hdr.grid(row=0, column=0, padx=4, pady=(6, 2), sticky="ew")
    kits_hdr.grid_columnconfigure(1, weight=1)
    ctk.CTkLabel(kits_hdr, text="🎁  Kits",
                 font=ctk.CTkFont(size=13, weight="bold"), anchor="w"
                 ).grid(row=0, column=0, padx=(0, 8), sticky="w")
    sv_kits_search = tk.StringVar()
    ctk.CTkEntry(kits_hdr, textvariable=sv_kits_search, height=28, width=180,
                 placeholder_text="🔍 Buscar por ID..."
                 ).grid(row=0, column=1, sticky="w")
    ctk.CTkButton(
        kits_hdr, text="+ Kit", height=28, width=80,
        fg_color="#3a3a5a", hover_color="#252540",
        command=lambda: _add_new_kit(),
    ).grid(row=0, column=2, padx=(8, 0), sticky="e")
    ctk.CTkButton(
        kits_hdr, text="🗑 Excluir", height=28, width=90,
        fg_color=_RED_DARK, hover_color=_RED_HOVER,
        command=lambda: _delete_selected_kit(),
    ).grid(row=0, column=3, padx=(4, 0), sticky="e")

    # ── Treeview de kits
    _tv_kits_container = tk.Frame(_tab_kits, bg="#1e1e2e")
    _tv_kits_container.grid(row=1, column=0, padx=4, pady=(0, 2), sticky="nsew")
    _tv_kits_container.grid_columnconfigure(0, weight=1)
    _tv_kits_container.grid_rowconfigure(0, weight=1)

    _kits_tv_style = ttk.Style()
    _kits_tv_style.configure("Kits.Treeview",
        background="#252535", foreground="#dddddd",
        fieldbackground="#252535", rowheight=26, borderwidth=0,
        font=("Segoe UI", 11))
    _kits_tv_style.configure("Kits.Treeview.Heading",
        background="#1a1a2e", foreground="#9090bb",
        relief="flat", font=("Segoe UI", 11, "bold"))
    _kits_tv_style.map("Kits.Treeview",
        background=[("selected", "#3a3a6e")],
        foreground=[("selected", "white")])

    kits_tv = ttk.Treeview(
        _tv_kits_container, style="Kits.Treeview",
        columns=("price", "uses"), show="tree headings",
        selectmode="browse")
    kits_tv.heading("#0", text="ID")
    kits_tv.heading("price", text="Preço")
    kits_tv.heading("uses", text="Usos")
    kits_tv.column("#0", width=220, minwidth=100)
    kits_tv.column("price", width=80, minwidth=50)
    kits_tv.column("uses", width=70, minwidth=40)
    _tv_kits_vsb = ttk.Scrollbar(_tv_kits_container, orient="vertical",
                                 command=kits_tv.yview)
    kits_tv.configure(yscrollcommand=_tv_kits_vsb.set)
    kits_tv.grid(row=0, column=0, sticky="nsew")
    _tv_kits_vsb.grid(row=0, column=1, sticky="ns")

    # ── Separador de edição
    ctk.CTkLabel(_tab_kits,
        text="─── Editar Kit Selecionado ───",
        text_color="gray50", font=ctk.CTkFont(size=11)
        ).grid(row=2, column=0, padx=4, pady=(2, 0), sticky="w")

    # ── Painel de edição único de kits
    kits_edit_scroll = ctk.CTkScrollableFrame(_tab_kits, fg_color="transparent",
                                               height=300)
    kits_edit_scroll.grid(row=3, column=0, padx=4, pady=(0, 4), sticky="ew")
    kits_edit_scroll.grid_columnconfigure(0, weight=1)

    # Vars do painel de edição de kits
    _sv_ek_id    = tk.StringVar()
    _sv_ek_price = tk.StringVar(value="0")
    _sv_ek_amount = tk.StringVar(value="1")
    _sv_ek_desc  = tk.StringVar()
    _sv_ek_perms = tk.StringVar()
    _edit_kit_idx = [-1]

    # Linha 0: ID | Preço | Usos
    _ek_row0 = ctk.CTkFrame(kits_edit_scroll, fg_color="transparent")
    _ek_row0.grid(row=0, column=0, padx=4, pady=(8, 2), sticky="ew")
    _ek_row0.grid_columnconfigure(1, weight=1)
    ctk.CTkLabel(_ek_row0, text="ID:", text_color="gray55", width=28
                 ).grid(row=0, column=0, padx=(0, 2))
    ctk.CTkEntry(_ek_row0, textvariable=_sv_ek_id, height=28
                 ).grid(row=0, column=1, padx=(0, 8), sticky="ew")
    ctk.CTkLabel(_ek_row0, text="Preço:", text_color="gray55", width=46
                 ).grid(row=0, column=2, padx=(0, 2))
    ctk.CTkEntry(_ek_row0, textvariable=_sv_ek_price, height=28, width=80
                 ).grid(row=0, column=3, padx=(0, 8))
    ctk.CTkLabel(_ek_row0, text="Usos:", text_color="gray55", width=38
                 ).grid(row=0, column=4, padx=(0, 2))
    ctk.CTkEntry(_ek_row0, textvariable=_sv_ek_amount, height=28, width=70
                 ).grid(row=0, column=5)

    # Linha 1: Descrição
    _ek_row1 = ctk.CTkFrame(kits_edit_scroll, fg_color="transparent")
    _ek_row1.grid(row=1, column=0, padx=4, pady=2, sticky="ew")
    _ek_row1.grid_columnconfigure(1, weight=1)
    ctk.CTkLabel(_ek_row1, text="Desc:", text_color="gray55", width=36
                 ).grid(row=0, column=0, padx=(0, 2))
    ctk.CTkEntry(_ek_row1, textvariable=_sv_ek_desc, height=28,
                 placeholder_text="Descrição exibida na loja"
                 ).grid(row=0, column=1, sticky="ew")

    # Linha 2: Permissões
    _ek_row2 = ctk.CTkFrame(kits_edit_scroll, fg_color="transparent")
    _ek_row2.grid(row=2, column=0, padx=4, pady=2, sticky="ew")
    _ek_row2.grid_columnconfigure(1, weight=1)
    ctk.CTkLabel(_ek_row2, text="Perms:", text_color="gray55", width=46
                 ).grid(row=0, column=0, padx=(0, 2))
    ctk.CTkEntry(_ek_row2, textvariable=_sv_ek_perms, height=28,
                 placeholder_text="VIPOuro, Staff (vírgula)"
                 ).grid(row=0, column=1, sticky="ew")

    # Itens do kit
    ctk.CTkLabel(kits_edit_scroll, text="Itens do Kit:",
                 text_color="gray55", font=ctk.CTkFont(size=11), anchor="w"
                 ).grid(row=3, column=0, padx=4, pady=(6, 2), sticky="w")
    _ek_kit_items_frame = ctk.CTkFrame(kits_edit_scroll, fg_color="transparent")
    _ek_kit_items_frame.grid(row=4, column=0, padx=4, pady=(0, 2), sticky="ew")
    _ek_kit_items_frame.grid_columnconfigure(0, weight=1)
    _ek_kit_item_rows: list = []

    def _add_ek_kit_item(ki_type="item", bp="", qty=1, qual=0.0, force_bp=False,
                         level=1, gender="Random", neutered=False) -> None:
        ki: dict = {}
        _ek_kit_item_rows.append(ki)
        kidx = len(_ek_kit_item_rows) - 1
        kif = ctk.CTkFrame(_ek_kit_items_frame, fg_color="#1e1e2e", corner_radius=4)
        kif.grid(row=kidx, column=0, pady=1, sticky="ew")
        kif.grid_columnconfigure(2, weight=1)
        ki["_frame"] = kif

        def _del_ki(k=ki, f=kif):
            if k in _ek_kit_item_rows:
                _ek_kit_item_rows.remove(k)
            f.destroy()

        # Tipo (item | dino)
        ki["type"] = tk.StringVar(value=ki_type)
        ctk.CTkLabel(kif, text="Tipo:", text_color="gray55", width=36
                     ).grid(row=0, column=0, padx=(6, 2), pady=(4, 2))
        _ki_type_om = ctk.CTkOptionMenu(
            kif, values=["item", "dino"],
            variable=ki["type"], width=80, height=24,
        )
        _ki_type_om.grid(row=0, column=1, padx=(0, 6), pady=(4, 2))

        # Blueprint (compartilhado)
        ctk.CTkLabel(kif, text="BP:", text_color="gray55", width=28
                     ).grid(row=0, column=2, padx=(0, 2), pady=(4, 2))
        ki["bp"] = tk.StringVar(value=bp)
        ctk.CTkEntry(kif, textvariable=ki["bp"], height=24,
                     placeholder_text="/Game/..."
                     ).grid(row=0, column=3, padx=(0, 4), pady=(4, 2), sticky="ew")
        ctk.CTkButton(kif, text="✕", width=24, height=24,
                      fg_color=_RED_DARK, hover_color=_RED_HOVER,
                      command=_del_ki).grid(row=0, column=4, padx=(0, 6), pady=(4, 2))

        # ── sub-frame ITEM (qty/qual/force_bp)
        ki_item_sub = ctk.CTkFrame(kif, fg_color="transparent")
        ki_item_sub.grid(row=1, column=0, columnspan=5, padx=6, pady=(0, 4), sticky="w")
        ki["qty"] = tk.StringVar(value=str(qty))
        ki["qual"] = tk.StringVar(value=str(qual))
        ki["force_bp"] = tk.BooleanVar(value=force_bp)
        ctk.CTkLabel(ki_item_sub, text="Qtd:", text_color="gray55", width=30
                     ).pack(side="left", padx=(0, 2))
        ctk.CTkEntry(ki_item_sub, textvariable=ki["qty"], height=24, width=54
                     ).pack(side="left", padx=(0, 10))
        ctk.CTkLabel(ki_item_sub, text="Qual:", text_color="gray55", width=34
                     ).pack(side="left", padx=(0, 2))
        ctk.CTkEntry(ki_item_sub, textvariable=ki["qual"], height=24, width=54
                     ).pack(side="left", padx=(0, 10))
        ctk.CTkCheckBox(ki_item_sub, text="Forçar BP", variable=ki["force_bp"],
                        text_color="gray60", height=24
                        ).pack(side="left")

        # ── sub-frame DINO (level/gender/neutered)
        ki_dino_sub = ctk.CTkFrame(kif, fg_color="transparent")
        ki_dino_sub.grid(row=1, column=0, columnspan=5, padx=6, pady=(0, 4), sticky="w")
        ki["level"] = tk.StringVar(value=str(level))
        ki["gender"] = tk.StringVar(value=gender)
        ki["neutered"] = tk.BooleanVar(value=neutered)
        ctk.CTkLabel(ki_dino_sub, text="Nível:", text_color="gray55", width=40
                     ).pack(side="left", padx=(0, 2))
        ctk.CTkEntry(ki_dino_sub, textvariable=ki["level"], height=24, width=60
                     ).pack(side="left", padx=(0, 10))
        ctk.CTkLabel(ki_dino_sub, text="Gênero:", text_color="gray55", width=54
                     ).pack(side="left", padx=(0, 2))
        ctk.CTkOptionMenu(ki_dino_sub, values=["Random", "Male", "Female"],
                          variable=ki["gender"], width=100, height=24
                          ).pack(side="left", padx=(0, 10))
        ctk.CTkCheckBox(ki_dino_sub, text="Castrado", variable=ki["neutered"],
                        text_color="gray60", height=24
                        ).pack(side="left")

        def _toggle_ki_type(v: str, isub=ki_item_sub, dsub=ki_dino_sub) -> None:
            if v == "dino":
                isub.grid_remove()
                dsub.grid()
            else:
                dsub.grid_remove()
                isub.grid()

        ki["type"].trace_add("write", lambda *_, t=ki["type"]: _toggle_ki_type(t.get()))
        _toggle_ki_type(ki_type)  # estado inicial

    ctk.CTkButton(
        kits_edit_scroll, text="+ Item no Kit", height=26, width=130,
        fg_color="#3a3a5a", hover_color="#252540",
        command=lambda: _add_ek_kit_item(),
    ).grid(row=5, column=0, padx=4, pady=(2, 4), sticky="w")

    # Comandos do kit
    ctk.CTkLabel(kits_edit_scroll, text="Comandos (um por linha):",
                 text_color="gray55", font=ctk.CTkFont(size=11), anchor="w"
                 ).grid(row=6, column=0, padx=4, pady=(4, 2), sticky="w")
    _ek_commands_tb = ctk.CTkTextbox(kits_edit_scroll, height=56)
    _ek_commands_tb.grid(row=7, column=0, padx=4, pady=(0, 8), sticky="ew")

    # ══ ABA PONTOS ════════════════════════════════════════════════════════
    _tab_pontos = inner_tabs.tab("⏱ Pontos")
    _tab_pontos.grid_rowconfigure(2, weight=1)

    timed_settings_frame = ctk.CTkFrame(_tab_pontos, fg_color=_CARD_BG, corner_radius=10)
    timed_settings_frame.grid(row=0, column=0, padx=4, pady=(4, 4), sticky="ew")

    ctk.CTkLabel(timed_settings_frame, text="⏱  Pontos por Tempo",
                 font=ctk.CTkFont(size=13, weight="bold"), anchor="w",
                 ).grid(row=0, column=0, columnspan=6, padx=16, pady=(10, 6), sticky="w")

    bv_timed_enabled  = tk.BooleanVar(value=True)
    sv_timed_interval = tk.StringVar(value="30")
    bv_timed_stack    = tk.BooleanVar(value=True)

    ctk.CTkLabel(timed_settings_frame, text="Ativar:", text_color="gray60",
                 width=50, anchor="w").grid(row=1, column=0, padx=(16, 4), pady=(0, 8), sticky="w")
    ctk.CTkSwitch(timed_settings_frame, text="", variable=bv_timed_enabled, width=48
                  ).grid(row=1, column=1, padx=(0, 20), pady=(0, 8), sticky="w")

    ctk.CTkLabel(timed_settings_frame, text="Intervalo (s):", text_color="gray60",
                 width=90, anchor="w").grid(row=1, column=2, padx=(0, 4), pady=(0, 8), sticky="w")
    ctk.CTkEntry(timed_settings_frame, textvariable=sv_timed_interval, height=28, width=70
                 ).grid(row=1, column=3, padx=(0, 20), pady=(0, 8), sticky="w")

    ctk.CTkLabel(timed_settings_frame, text="Acumular:", text_color="gray60",
                 width=70, anchor="w").grid(row=1, column=4, padx=(0, 4), pady=(0, 8), sticky="w")
    ctk.CTkSwitch(timed_settings_frame, text="", variable=bv_timed_stack, width=48
                  ).grid(row=1, column=5, pady=(0, 8), sticky="w")

    timed_groups_hdr = ctk.CTkFrame(_tab_pontos, fg_color="transparent")
    timed_groups_hdr.grid(row=1, column=0, padx=4, pady=(0, 2), sticky="ew")
    timed_groups_hdr.grid_columnconfigure(0, weight=1)
    ctk.CTkLabel(timed_groups_hdr, text="Grupos (pontos recebidos por grupo):",
                 text_color="gray60", font=ctk.CTkFont(size=11), anchor="w"
                 ).grid(row=0, column=0, sticky="w")
    ctk.CTkButton(
        timed_groups_hdr, text="+ Grupo", height=24, width=80,
        fg_color="#3a3a5a", hover_color="#252540",
        command=lambda: _add_timed_group(),
    ).grid(row=0, column=1, sticky="e")

    groups_scroll = ctk.CTkScrollableFrame(_tab_pontos, fg_color="transparent")
    groups_scroll.grid(row=2, column=0, padx=4, pady=(0, 4), sticky="nsew")
    groups_scroll.grid_columnconfigure(0, weight=1)

    # ══ ABA BD ════════════════════════════════════════════════════════════
    _tab_bd = inner_tabs.tab("🗃️ BD")

    db_card = ctk.CTkFrame(_tab_bd, corner_radius=10, fg_color=_CARD_BG)
    db_card.grid(row=0, column=0, padx=4, pady=4, sticky="ew")
    db_card.grid_columnconfigure(1, weight=1)
    db_card.grid_columnconfigure(3, weight=1)

    ctk.CTkLabel(
        db_card, text="🗃️  Banco de Dados (MySQL)",
        font=ctk.CTkFont(size=13, weight="bold"), anchor="w",
    ).grid(row=0, column=0, columnspan=4, padx=16, pady=(12, 8), sticky="w")

    ctk.CTkLabel(
        db_card,
        text="💡 Requer libmysql.dll na mesma pasta do CustomShop.dll",
        text_color="gray55", font=ctk.CTkFont(size=10), anchor="w",
    ).grid(row=0, column=0, columnspan=4, padx=16, pady=(0, 0), sticky="se")

    def _db_lbl(text: str) -> ctk.CTkLabel:
        return ctk.CTkLabel(db_card, text=text, text_color="gray60", anchor="w", width=90)

    sv_db_host = tk.StringVar()
    sv_db_port = tk.StringVar()
    sv_db_user = tk.StringVar()
    sv_db_pass = tk.StringVar()
    sv_db_name = tk.StringVar()

    _db_lbl("Host:").grid(row=1, column=0, padx=(16, 4), pady=3, sticky="w")
    ctk.CTkEntry(db_card, textvariable=sv_db_host, height=28, width=180
                 ).grid(row=1, column=1, padx=(0, 10), pady=3, sticky="w")
    _db_lbl("Porta:").grid(row=1, column=2, padx=(10, 4), pady=3, sticky="w")
    ctk.CTkEntry(db_card, textvariable=sv_db_port, height=28, width=70
                 ).grid(row=1, column=3, padx=(0, 16), pady=3, sticky="w")

    _db_lbl("Usuário:").grid(row=2, column=0, padx=(16, 4), pady=3, sticky="w")
    ctk.CTkEntry(db_card, textvariable=sv_db_user, height=28, width=180
                 ).grid(row=2, column=1, padx=(0, 10), pady=3, sticky="w")
    _db_lbl("Senha:").grid(row=2, column=2, padx=(10, 4), pady=3, sticky="w")
    ctk.CTkEntry(db_card, textvariable=sv_db_pass, height=28, width=180, show="•"
                 ).grid(row=2, column=3, padx=(0, 16), pady=3, sticky="w")

    _db_lbl("Banco:").grid(row=3, column=0, padx=(16, 4), pady=(3, 12), sticky="w")
    ctk.CTkEntry(db_card, textvariable=sv_db_name, height=28, width=180
                 ).grid(row=3, column=1, padx=(0, 10), pady=(3, 12), sticky="w")

    # ── paginação: helpers de coleta ──────────────────────────────────────
    # ── Helpers: items (Treeview + painel único) ─────────────────────────

    def _collect_edit_item() -> tuple[str, dict]:
        """Lê o painel de edição de item e retorna (id, data)."""
        iid = _sv_ei_id.get().strip()
        try:
            price = int(_sv_ei_price.get())
        except ValueError:
            price = 0
        item_type = _sv_ei_type.get()
        desc = _sv_ei_desc.get().strip()
        if item_type == "command":
            cmd_items = []
            for cr in _ei_cmd_rows:
                cmd = cr["command"].get().strip()
                if cmd:
                    cmd_items.append({
                        "Command":        cmd,
                        "DisplayAs":      cr["display_as"].get().strip(),
                        "ExecuteAsAdmin": cr["exec_as_admin"].get(),
                    })
            return iid, {"Type": "command", "Price": price,
                          "Description": desc, "Items": cmd_items}
        elif item_type == "dino":
            try:
                level = int(_sv_ei_dino_level.get())
            except ValueError:
                level = 1
            return iid, {"Type": "dino", "Price": price, "Description": desc,
                          "Blueprint": _sv_ei_bp.get().strip(),
                          "Level": level,
                          "Gender": _sv_ei_dino_gender.get(),
                          "Neutered": _bv_ei_dino_neutered.get()}
        else:
            try:
                qty = int(_sv_ei_qty.get())
            except ValueError:
                qty = 1
            try:
                qual = float(_sv_ei_qual.get())
            except ValueError:
                qual = 0.0
            return iid, {"Type": "item", "Price": price, "Description": desc,
                          "Blueprint": _sv_ei_bp.get().strip(), "Quantity": qty,
                          "Quality": qual, "ForceBlueprint": _bv_ei_force_bp.get()}

    def _save_item_edit() -> None:
        """Salva edição atual em raw_items (sem interação com widgets de lista)."""
        idx = _edit_item_idx[0]
        if 0 <= idx < len(_state["raw_items"]):
            _state["raw_items"][idx] = _collect_edit_item()

    def _load_item_edit(idx: int) -> None:
        """Carrega item do raw_items no painel de edição."""
        _save_item_edit()
        _edit_item_idx[0] = idx
        if idx < 0 or idx >= len(_state["raw_items"]):
            return
        item_id, data = _state["raw_items"][idx]
        _sv_ei_id.set(str(item_id))
        _sv_ei_price.set(str(data.get("Price", 0)))
        item_type = data.get("Type", "item")
        _sv_ei_type.set(item_type)
        _sv_ei_desc.set(data.get("Description", ""))
        _sv_ei_bp.set(data.get("Blueprint", ""))
        _sv_ei_qty.set(str(data.get("Quantity", 1)))
        _sv_ei_qual.set(str(data.get("Quality", 0.0)))
        _bv_ei_force_bp.set(bool(data.get("ForceBlueprint", False)))
        _sv_ei_dino_level.set(str(data.get("Level", 1)))
        _sv_ei_dino_gender.set(data.get("Gender", "Random"))
        _bv_ei_dino_neutered.set(bool(data.get("Neutered", False)))
        _on_ei_type_change(item_type)
        # Rebuild cmd rows
        for cr in list(_ei_cmd_rows):
            cr["_frame"].destroy()
        _ei_cmd_rows.clear()
        if item_type == "command":
            for ci in data.get("Items", []):
                if isinstance(ci, dict) and "Command" in ci:
                    _add_ei_cmd_row(ci.get("Command", ""),
                                    ci.get("DisplayAs", ""),
                                    bool(ci.get("ExecuteAsAdmin", True)))

    def _populate_items_tv() -> None:
        """Popula o Treeview de itens aplicando filtro de busca."""
        for row in items_tv.get_children():
            items_tv.delete(row)
        query = sv_items_search.get().strip().lower()
        for idx, (item_id, data) in enumerate(_state["raw_items"]):
            if query and query not in str(item_id).lower():
                continue
            items_tv.insert("", "end", iid=str(idx),
                            text=str(item_id),
                            values=(data.get("Type", "item"),
                                    data.get("Price", 0)))

    def _on_items_tv_select(event=None) -> None:
        sel = items_tv.selection()
        if not sel:
            return
        try:
            _load_item_edit(int(sel[0]))
        except (ValueError, IndexError):
            pass

    items_tv.bind("<<TreeviewSelect>>", _on_items_tv_select)
    items_tv.bind("<Delete>", lambda e: _delete_selected_item())
    sv_items_search.trace_add("write", lambda *_: _populate_items_tv())

    def _add_new_item() -> None:
        _save_item_edit()
        _state["raw_items"].append(("", {}))
        new_idx = len(_state["raw_items"]) - 1
        _populate_items_tv()
        items_tv.selection_set(str(new_idx))
        items_tv.see(str(new_idx))
        _load_item_edit(new_idx)

    def _delete_selected_item() -> None:
        sel = items_tv.selection()
        if not sel:
            return
        try:
            idx = int(sel[0])
        except ValueError:
            return
        if 0 <= idx < len(_state["raw_items"]):
            _state["raw_items"].pop(idx)
        _edit_item_idx[0] = -1
        _populate_items_tv()
        total = len(_state["raw_items"])
        if total > 0:
            new_idx = min(idx, total - 1)
            items_tv.selection_set(str(new_idx))
            _load_item_edit(new_idx)

    def _collect_items_page() -> None:
        """Salva a edição atual do painel de itens em raw_items."""
        _save_item_edit()

    # ── Helpers: kits (Treeview + painel único) ───────────────────────────

    def _collect_edit_kit() -> tuple[str, dict]:
        """Lê o painel de edição de kit e retorna (id, data)."""
        kid = _sv_ek_id.get().strip()
        try:
            price = int(_sv_ek_price.get())
        except ValueError:
            price = 0
        try:
            amount = int(_sv_ek_amount.get())
        except ValueError:
            amount = 1
        desc = _sv_ek_desc.get().strip()
        perms_raw = _sv_ek_perms.get().strip()
        perms = [p.strip() for p in perms_raw.split(",") if p.strip()]
        cmds_raw = _ek_commands_tb.get("1.0", "end").strip()
        cmds = [c for c in cmds_raw.splitlines() if c.strip()]
        kit_items = []
        for ki in _ek_kit_item_rows:
            ki_type = ki["type"].get()
            if ki_type == "dino":
                try:
                    ki_lvl = int(ki["level"].get())
                except ValueError:
                    ki_lvl = 1
                kit_items.append({
                    "Type":      "dino",
                    "Blueprint": ki["bp"].get().strip(),
                    "Level":     ki_lvl,
                    "Gender":    ki["gender"].get(),
                    "Neutered":  ki["neutered"].get(),
                })
            else:
                try:
                    ki_qty = int(ki["qty"].get())
                except ValueError:
                    ki_qty = 1
                try:
                    ki_qual = float(ki["qual"].get())
                except ValueError:
                    ki_qual = 0.0
                kit_items.append({
                    "Blueprint":      ki["bp"].get().strip(),
                    "Quantity":       ki_qty,
                    "Quality":        ki_qual,
                    "ForceBlueprint": ki["force_bp"].get(),
                })
        data: dict = {
            "Price":         price,
            "Description":   desc,
            "DefaultAmount": amount,
            "Items":         kit_items,
            "Commands":      cmds,
        }
        if perms:
            data["Permissions"] = perms
        return kid, data

    def _save_kit_edit() -> None:
        idx = _edit_kit_idx[0]
        if 0 <= idx < len(_state["raw_kits"]):
            _state["raw_kits"][idx] = _collect_edit_kit()

    def _load_kit_edit(idx: int) -> None:
        _save_kit_edit()
        _edit_kit_idx[0] = idx
        if idx < 0 or idx >= len(_state["raw_kits"]):
            return
        kit_id, data = _state["raw_kits"][idx]
        _sv_ek_id.set(str(kit_id))
        _sv_ek_price.set(str(data.get("Price", 0)))
        _sv_ek_amount.set(str(data.get("DefaultAmount", 1)))
        _sv_ek_desc.set(data.get("Description", ""))
        perms = data.get("Permissions", [])
        _sv_ek_perms.set(perms if isinstance(perms, str) else ", ".join(perms))
        _ek_commands_tb.delete("1.0", "end")
        for cmd in data.get("Commands", []):
            _ek_commands_tb.insert("end", cmd + "\n")
        # Rebuild kit item rows
        for ki in list(_ek_kit_item_rows):
            ki["_frame"].destroy()
        _ek_kit_item_rows.clear()
        for ki_data in data.get("Items", []):
            if ki_data.get("Type") == "dino":
                _add_ek_kit_item(
                    ki_type="dino",
                    bp=ki_data.get("Blueprint", ""),
                    level=ki_data.get("Level", 1),
                    gender=ki_data.get("Gender", "Random"),
                    neutered=bool(ki_data.get("Neutered", False)),
                )
            else:
                _add_ek_kit_item(
                    ki_type="item",
                    bp=ki_data.get("Blueprint", ""),
                    qty=ki_data.get("Quantity", 1),
                    qual=ki_data.get("Quality", 0.0),
                    force_bp=bool(ki_data.get("ForceBlueprint", False)),
                )

    def _populate_kits_tv() -> None:
        for row in kits_tv.get_children():
            kits_tv.delete(row)
        query = sv_kits_search.get().strip().lower()
        for idx, (kit_id, data) in enumerate(_state["raw_kits"]):
            if query and query not in str(kit_id).lower():
                continue
            kits_tv.insert("", "end", iid=str(idx),
                           text=str(kit_id),
                           values=(data.get("Price", 0),
                                   data.get("DefaultAmount", 1)))

    def _on_kits_tv_select(event=None) -> None:
        sel = kits_tv.selection()
        if not sel:
            return
        try:
            _load_kit_edit(int(sel[0]))
        except (ValueError, IndexError):
            pass

    kits_tv.bind("<<TreeviewSelect>>", _on_kits_tv_select)
    kits_tv.bind("<Delete>", lambda e: _delete_selected_kit())
    sv_kits_search.trace_add("write", lambda *_: _populate_kits_tv())

    def _add_new_kit() -> None:
        _save_kit_edit()
        _state["raw_kits"].append(("", {}))
        new_idx = len(_state["raw_kits"]) - 1
        _populate_kits_tv()
        kits_tv.selection_set(str(new_idx))
        kits_tv.see(str(new_idx))
        _load_kit_edit(new_idx)

    def _delete_selected_kit() -> None:
        sel = kits_tv.selection()
        if not sel:
            return
        try:
            idx = int(sel[0])
        except ValueError:
            return
        if 0 <= idx < len(_state["raw_kits"]):
            _state["raw_kits"].pop(idx)
        _edit_kit_idx[0] = -1
        _populate_kits_tv()
        total = len(_state["raw_kits"])
        if total > 0:
            new_idx = min(idx, total - 1)
            kits_tv.selection_set(str(new_idx))
            _load_kit_edit(new_idx)

    def _collect_kits_page() -> None:
        """Salva a edição atual do painel de kits em raw_kits."""
        _save_kit_edit()

    # ── helper de grupo de pontos por tempo ───────────────────────────────
    def _add_timed_group(name: str = "", amount: int = 0) -> None:
        row: dict = {}
        _state["timed_groups"].append(row)
        idx = len(_state["timed_groups"]) - 1

        fr = ctk.CTkFrame(groups_scroll, fg_color="#252535", corner_radius=4,
                          border_width=1, border_color="#3a3a55")
        fr.grid(row=idx, column=0, padx=2, pady=1, sticky="ew")
        fr.grid_columnconfigure(1, weight=1)
        row["_frame"] = fr

        def _del(r=row, f=fr):
            if r in _state["timed_groups"]:
                _state["timed_groups"].remove(r)
            f.destroy()

        ctk.CTkLabel(fr, text="Grupo:", text_color="gray55", width=46
                     ).grid(row=0, column=0, padx=(8, 2), pady=5)
        row["name"] = tk.StringVar(value=name)
        ctk.CTkEntry(fr, textvariable=row["name"], height=26, width=140,
                     placeholder_text="Ex: VIPOuro"
                     ).grid(row=0, column=1, padx=(0, 8), pady=5, sticky="w")

        ctk.CTkLabel(fr, text="Pontos:", text_color="gray55", width=54
                     ).grid(row=0, column=2, padx=(4, 2), pady=5)
        row["amount"] = tk.StringVar(value=str(amount))
        ctk.CTkEntry(fr, textvariable=row["amount"], height=26, width=70
                     ).grid(row=0, column=3, padx=(0, 8), pady=5, sticky="w")

        ctk.CTkButton(fr, text="🗑", width=28, height=24,
                      fg_color=_RED_DARK, hover_color=_RED_HOVER,
                      command=_del).grid(row=0, column=4, padx=(2, 8), pady=5)

    # ── função de carregamento ─────────────────────────────────────────────
    # ── funções de populate por seção ─────────────────────────────────────
    def _populate_settings(cfg: dict) -> None:
        settings = cfg.get("Settings", {})
        sv_shop_name.set(settings.get("ShopName", "ARKLAND Shop"))
        sv_ui_key.set(settings.get("UiKey", "F3"))
        sv_start_pts.set(str(settings.get("StartingPoints", 100)))
        sv_items_per_page.set(str(settings.get("ItemsPerPage", 15)))
        sv_display_time.set(str(settings.get("ShopDisplayTime", 15.0)))
        sv_text_size.set(str(settings.get("ShopTextSize", 1.3)))
        sv_default_kit.set(settings.get("DefaultKit", ""))
        sv_db_path.set(settings.get("DbPathOverride", ""))
        bv_no_sell.set(bool(settings.get("DisableSellButton", True)))
        bv_no_trade.set(bool(settings.get("DisableTradeButton", True)))
        bv_orig_trade.set(bool(settings.get("UseOriginalTradeCommandWithUI", False)))
        bv_dinos_cryo.set(bool(settings.get("GiveDinosInCryopods", True)))
        bv_soul_traps.set(bool(settings.get("UseSoulTraps", True)))
        bv_cryo_limited.set(bool(settings.get("CryoLimitedTime", False)))
        bv_no_noglin.set(bool(settings.get("PreventUseNoglin", True)))
        bv_no_unconscious.set(bool(settings.get("PreventUseUnconscious", True)))
        bv_no_handcuffed.set(bool(settings.get("PreventUseHandcuffed", True)))
        bv_no_carried.set(bool(settings.get("PreventUseCarried", True)))

    def _populate_db(cfg: dict) -> None:
        db = cfg.get("Database", {})
        sv_db_host.set(db.get("Host", "127.0.0.1"))
        sv_db_port.set(str(db.get("Port", 3306)))
        sv_db_user.set(db.get("User", "arkland"))
        sv_db_pass.set(db.get("Password", ""))
        sv_db_name.set(db.get("Database", "arkland_shop"))

    def _populate_items(cfg: dict) -> None:
        _state["raw_items"] = list(cfg.get("Items", {}).items())
        _edit_item_idx[0] = -1
        _populate_items_tv()
        if _state["raw_items"]:
            items_tv.selection_set("0")
            _load_item_edit(0)

    def _populate_kits(cfg: dict) -> None:
        _state["raw_kits"] = list(cfg.get("Kits", {}).items())
        _edit_kit_idx[0] = -1
        _populate_kits_tv()
        if _state["raw_kits"]:
            kits_tv.selection_set("0")
            _load_kit_edit(0)

    def _populate_timed(cfg: dict) -> None:
        tp = cfg.get("TimedPointsReward", {})
        bv_timed_enabled.set(bool(tp.get("Enabled", True)))
        sv_timed_interval.set(str(tp.get("Interval", 30)))
        bv_timed_stack.set(bool(tp.get("StackRewards", True)))
        _state["timed_groups"].clear()
        for w in groups_scroll.winfo_children():
            w.destroy()
        for grp_name, grp_data in tp.get("Groups", {}).items():
            _add_timed_group(grp_name, grp_data.get("Amount", 0))

    def _populate_fields(cfg: dict) -> None:
        """Popula todas as seções de uma vez (usado após importar config)."""
        _state["raw_cfg"] = cfg
        _state["tabs_built"] = {"⚙️ Config", "🛒 Itens", "🎁 Kits", "⏱ Pontos", "🗃️ BD"}
        _populate_settings(cfg)
        _populate_db(cfg)
        _populate_items(cfg)
        _populate_kits(cfg)
        _populate_timed(cfg)

    def _on_tab_selected() -> None:
        """Carrega o conteúdo de uma sub-aba apenas quando selecionada pela primeira vez."""
        t = inner_tabs.get()
        if t in _state["tabs_built"]:
            return
        _state["tabs_built"].add(t)
        cfg = _state["raw_cfg"]
        if t == "🛒 Itens":
            _populate_items(cfg)
        elif t == "🎁 Kits":
            _populate_kits(cfg)
        elif t == "⏱ Pontos":
            _populate_timed(cfg)
        elif t == "🗃️ BD":
            _populate_db(cfg)

    inner_tabs.configure(command=_on_tab_selected)

    def _load_config() -> None:
        if not srv.install_dir:
            return
        cfg = PluginManager.load_config(srv.install_dir)
        _state["raw_cfg"] = cfg
        # Marca todas as abas como não construídas (forçar rebuild na próxima abertura)
        _state["tabs_built"] = {"⚙️ Config"}
        _populate_settings(cfg)
        # Se a aba atual já estiver em "🛒 Itens" etc., popula imediatamente
        current = inner_tabs.get()
        if current and current not in _state["tabs_built"]:
            _on_tab_selected()

    def _convert_arkshop(raw: dict) -> dict:
        """Converte o formato legado ArkShop para o formato CustomShop."""
        general = raw.get("General", {})
        mysql   = raw.get("Mysql", {})

        settings = {
            "ShopName":                      general.get("ShopName", "ARKLAND Shop"),
            "UiKey":                         general.get("UiKey", "F3"),
            "StartingPoints":                general.get("StartingPoints", 100),
            "ItemsPerPage":                  general.get("ItemsPerPage", 15),
            "ShopDisplayTime":               general.get("ShopDisplayTime", 15.0),
            "ShopTextSize":                  general.get("ShopTextSize", 1.3),
            "DefaultKit":                    general.get("DefaultKit", ""),
            "DbPathOverride":                general.get("DbPathOverride", ""),
            "DisableSellButton":             general.get("DisableSellButton", True),
            "DisableTradeButton":            general.get("DisableTradeButton", True),
            "UseOriginalTradeCommandWithUI": general.get("UseOriginalTradeCommandWithUI", False),
            "GiveDinosInCryopods":           general.get("GiveDinosInCryopods", True),
            "UseSoulTraps":                  general.get("UseSoulTraps", True),
            "CryoLimitedTime":               general.get("CryoLimitedTime", False),
            "PreventUseNoglin":              general.get("PreventUseNoglin", True),
            "PreventUseUnconscious":         general.get("PreventUseUnconscious", True),
            "PreventUseHandcuffed":          general.get("PreventUseHandcuffed", True),
            "PreventUseCarried":             general.get("PreventUseCarried", True),
        }
        database = {
            "Host":     mysql.get("MysqlHost", "127.0.0.1"),
            "Port":     mysql.get("MysqlPort", 3306),
            "User":     mysql.get("MysqlUser", "arkland"),
            "Password": mysql.get("MysqlPass", ""),
            "Database": mysql.get("MysqlDB", "arkland_shop"),
        }
        # Kits: Amount → Quantity nos itens do kit
        kits: dict = {}
        for kid, kdata in raw.get("Kits", {}).items():
            kit = dict(kdata)
            if "Items" in kit:
                converted = []
                for it in kit["Items"]:
                    it2 = dict(it)
                    if "Amount" in it2 and "Quantity" not in it2:
                        it2["Quantity"] = it2.pop("Amount")
                    converted.append(it2)
                kit["Items"] = converted
            kits[kid] = kit
        # ShopItems → Items (itens simples apenas; bundles são ignorados)
        items: dict = {}
        for iid, idata in raw.get("ShopItems", {}).items():
            tipo = idata.get("Type", "item")
            if tipo == "command":
                items[iid] = {
                    "Type":        "command",
                    "Price":       idata.get("Price", 0),
                    "Description": idata.get("Description", ""),
                    "Items":       idata.get("Items", []),
                }
            else:
                sub = [i for i in idata.get("Items", []) if "Blueprint" in i]
                if len(sub) == 1:
                    entry = dict(sub[0])
                    if "Amount" in entry and "Quantity" not in entry:
                        entry["Quantity"] = entry.pop("Amount")
                    items[iid] = {
                        "Type":           "item",
                        "Price":          idata.get("Price", 0),
                        "Description":    idata.get("Description", ""),
                        "Blueprint":      entry.get("Blueprint", ""),
                        "Quantity":       entry.get("Quantity", 1),
                        "Quality":        entry.get("Quality", 0.0),
                        "ForceBlueprint": entry.get("ForceBlueprint", False),
                    }
        timed_raw = general.get("TimedPointsReward", raw.get("TimedPointsReward", {}))
        # Converte Groups: ArkShop usa int direto ("Default": 25),
        # CustomShop usa dict ("Default": {"Amount": 25})
        groups_raw = timed_raw.get("Groups", {})
        groups = {
            name: (val if isinstance(val, dict) else {"Amount": val})
            for name, val in groups_raw.items()
        }
        timed = {
            "Enabled":      timed_raw.get("Enabled", True),
            "Interval":     timed_raw.get("Interval", 30),
            "StackRewards": timed_raw.get("StackRewards", True),
            "Groups":       groups,
        }
        return {
            "Settings":          settings,
            "Database":          database,
            "Kits":              kits,
            "Items":             items,
            "TimedPointsReward": timed,
        }

    def _import_config() -> None:
        path = filedialog.askopenfilename(
            title="Importar config.json da loja",
            filetypes=[("JSON", "*.json"), ("Todos os arquivos", "*.*")],
            parent=app,
        )
        if not path:
            return
        try:
            with open(path, encoding="utf-8") as f:
                raw = json.load(f)
        except Exception as exc:
            messagebox.showerror("Erro ao abrir arquivo", str(exc), parent=app)
            return
        is_arkshop = "Mysql" in raw or ("General" in raw and "Items" not in raw)
        try:
            cfg = _convert_arkshop(raw) if is_arkshop else raw
        except Exception as exc:
            messagebox.showerror("Erro ao converter", str(exc), parent=app)
            return
        _populate_fields(cfg)
        n_items = len(cfg.get("Items", {}))
        n_kits  = len(cfg.get("Kits",  {}))
        fmt = "ArkShop (convertido)" if is_arkshop else "CustomShop"
        messagebox.showinfo(
            "Importado",
            f"Formato: {fmt}\n{n_items} item(s), {n_kits} kit(s) carregados.\n\n"
            "Revise os dados e clique em 💾 Salvar config.json.",
            parent=app,
        )

    # ── função de coleta e salvamento ─────────────────────────────────────
    def _save_config() -> None:
        if not srv.install_dir:
            messagebox.showwarning("Sem diretório",
                "Configure o diretório de instalação do servidor primeiro.", parent=app)
            return

        try:
            start_pts = int(sv_start_pts.get())
        except ValueError:
            start_pts = 100
        try:
            items_per_page = int(sv_items_per_page.get())
        except ValueError:
            items_per_page = 15
        try:
            display_time = float(sv_display_time.get())
        except ValueError:
            display_time = 15.0
        try:
            text_size = float(sv_text_size.get())
        except ValueError:
            text_size = 1.3

        # Itens: coleta dos widgets se a aba foi aberta, senão usa raw_cfg
        if "🛒 Itens" in _state["tabs_built"]:
            _collect_items_page()
            items_dict: dict = {}
            for item_id, item_data in _state["raw_items"]:
                iid = str(item_id).strip() if item_id else ""
                if iid:
                    items_dict[iid] = item_data
        else:
            items_dict = _state["raw_cfg"].get("Items", {})

        # Kits: coleta dos widgets se a aba foi aberta, senão usa raw_cfg
        if "🎁 Kits" in _state["tabs_built"]:
            _collect_kits_page()
            kits_dict: dict = {}
            for kit_id, kit_data in _state["raw_kits"]:
                kid = str(kit_id).strip() if kit_id else ""
                if kid:
                    kits_dict[kid] = kit_data
        else:
            kits_dict = _state["raw_cfg"].get("Kits", {})

        # Timed: coleta dos widgets se a aba foi aberta, senão usa raw_cfg
        if "⏱ Pontos" in _state["tabs_built"]:
            timed_groups_dict: dict = {}
            for tg_row in _state["timed_groups"]:
                grp = tg_row["name"].get().strip()
                if not grp:
                    continue
                try:
                    amt = int(tg_row["amount"].get())
                except ValueError:
                    amt = 0
                timed_groups_dict[grp] = {"Amount": amt}
            try:
                timed_interval = int(sv_timed_interval.get())
            except ValueError:
                timed_interval = 30
            timed_section: dict = {
                **_state["raw_cfg"].get("TimedPointsReward", {}),
                "Enabled":      bv_timed_enabled.get(),
                "Interval":     timed_interval,
                "StackRewards": bv_timed_stack.get(),
                "Groups":       timed_groups_dict,
            }
        else:
            timed_section = _state["raw_cfg"].get("TimedPointsReward", {})

        # BD: coleta dos widgets se a aba foi aberta, senão usa raw_cfg
        if "🗃️ BD" in _state["tabs_built"]:
            db_section: dict = {
                **_state["raw_cfg"].get("Database", {}),
                "Host":     sv_db_host.get().strip(),
                "Port":     int(sv_db_port.get()) if sv_db_port.get().isdigit() else 3306,
                "User":     sv_db_user.get().strip(),
                "Password": sv_db_pass.get(),
                "Database": sv_db_name.get().strip(),
            }
        else:
            db_section = _state["raw_cfg"].get("Database", {})

        existing = _state["raw_cfg"]
        data = {
            **existing,
            "Settings": {
                **existing.get("Settings", {}),
                "ShopName":                      sv_shop_name.get().strip(),
                "UiKey":                         sv_ui_key.get().strip(),
                "StartingPoints":                start_pts,
                "ItemsPerPage":                  items_per_page,
                "ShopDisplayTime":               display_time,
                "ShopTextSize":                  text_size,
                "DefaultKit":                    sv_default_kit.get().strip(),
                "DbPathOverride":                sv_db_path.get().strip(),
                "DisableSellButton":             bv_no_sell.get(),
                "DisableTradeButton":            bv_no_trade.get(),
                "UseOriginalTradeCommandWithUI": bv_orig_trade.get(),
                "GiveDinosInCryopods":           bv_dinos_cryo.get(),
                "UseSoulTraps":                  bv_soul_traps.get(),
                "CryoLimitedTime":               bv_cryo_limited.get(),
                "PreventUseNoglin":              bv_no_noglin.get(),
                "PreventUseUnconscious":         bv_no_unconscious.get(),
                "PreventUseHandcuffed":          bv_no_handcuffed.get(),
                "PreventUseCarried":             bv_no_carried.get(),
            },
            "Items":             items_dict,
            "Kits":              kits_dict,
            "TimedPointsReward": timed_section,
            "Database":          db_section,
        }
        try:
            PluginManager.save_config(srv.install_dir, data)
            saved_path = PluginManager.config_path(srv.install_dir)
            messagebox.showinfo("Configuração salva",
                f"config.json do CustomShop salvo com sucesso!\n\n{saved_path}", parent=app)
        except Exception as exc:
            messagebox.showerror("Erro ao salvar", str(exc), parent=app)

    # ── função de status / install / uninstall ────────────────────────────
    def _refresh_status() -> None:
        for w in btn_row.winfo_children():
            w.destroy()

        if not srv.install_dir:
            arkapi_lbl.configure(
                text="⚠️  Diretório de instalação não configurado na aba Geral.",
                text_color="orange")
            plugin_lbl.configure(text="")
            inner_tabs.grid_remove()
            return

        # Mostra estado de carregamento imediatamente, sem bloquear a UI
        arkapi_lbl.configure(text="⏳  Verificando...", text_color="gray55")
        plugin_lbl.configure(text="⏳  Verificando...", text_color="gray55")
        perms_lbl.configure(text="", text_color="gray55")

        def _apply_status(arkapi_ok: bool, plugin_ok: bool, perms_ok: bool) -> None:
            """Executa no UI thread com os resultados das verificações de I/O."""
            try:
                if not arkapi_lbl.winfo_exists():
                    return
            except Exception:
                return

            arkapi_lbl.configure(
                text=("✅  ArkApi detectado" if arkapi_ok
                      else "❌  ArkApi não encontrado — instale o ArkApi no servidor primeiro"),
                text_color=(_GREEN if arkapi_ok else "#ff6666"),
            )
            plugin_lbl.configure(
                text=("✅  CustomShop instalado" if plugin_ok else "❌  CustomShop não instalado"),
                text_color=(_GREEN if plugin_ok else "#ff6666"),
            )
            perms_lbl.configure(
                text=("✅  ASE Permissions instalado" if perms_ok
                      else "⚠️  ASE Permissions não encontrado — dependência obrigatória do CustomShop"),
                text_color=(_GREEN if perms_ok else "orange"),
            )

            ctk.CTkButton(
                btn_row, text="🔄 Verificar", height=32, width=110,
                fg_color="#3a3a5a", hover_color="#252540",
                command=_refresh_status,
            ).pack(side="left", padx=(0, 8))

            if not perms_ok:
                ctk.CTkButton(
                    btn_row, text="⬇ Instalar Permissions", height=32, width=185,
                    fg_color="#5a4a20", hover_color="#3a3010",
                    command=lambda: webbrowser.open(
                        "https://ark-server-api.com/resources/ase-permissions.35/"),
                ).pack(side="left", padx=(0, 8))

            if not plugin_ok:
                def _install():
                    dll = PluginManager.dll_source()
                    dll_path: str | None = None
                    if dll is None:
                        p = filedialog.askopenfilename(
                            title="Selecione CustomShop.dll",
                            filetypes=[("DLL", "*.dll")],
                            parent=app,
                        )
                        if not p:
                            return
                        dll_path = p
                    try:
                        PluginManager.install(srv.install_dir, dll_path)
                        _refresh_status()
                    except Exception as exc:
                        messagebox.showerror("Erro ao instalar", str(exc), parent=app)

                ctk.CTkButton(
                    btn_row, text="📦 Instalar", height=32, width=120,
                    fg_color=_GREEN_DARK, hover_color=_GREEN_HOVER,
                    command=_install,
                ).pack(side="left", padx=(0, 8))
            else:
                def _uninstall():
                    if not messagebox.askyesno(
                        "Confirmar",
                        "Remover o plugin CustomShop do servidor?\n"
                        "O diretório do plugin será excluído.",
                        parent=app,
                    ):
                        return
                    try:
                        PluginManager.uninstall(srv.install_dir)
                        _refresh_status()
                    except Exception as exc:
                        messagebox.showerror("Erro ao remover", str(exc), parent=app)

                ctk.CTkButton(
                    btn_row, text="🗑 Desinstalar", height=32, width=120,
                    fg_color=_RED_DARK, hover_color=_RED_HOVER,
                    command=_uninstall,
                ).pack(side="left", padx=(0, 8))

            if plugin_ok:
                inner_tabs.grid(row=1, column=0, padx=8, pady=(0, 8), sticky="nsew")
                _load_config()

                # Botões de ação na save_row (sub-aba Config)
                for w in save_row.winfo_children():
                    w.destroy()

                ctk.CTkButton(
                    save_row, text="📂 Importar", height=32, width=110,
                    fg_color="#3a4a5a", hover_color="#253040",
                    command=_import_config,
                ).pack(side="left", padx=(0, 16))
                ctk.CTkButton(
                    save_row, text="💾 Salvar config.json", height=32, width=190,
                    fg_color=_GREEN_DARK, hover_color=_GREEN_HOVER,
                    command=_save_config,
                ).pack(side="left", padx=(0, 8))
                ctk.CTkButton(
                    save_row, text="⚡ Recarregar via RCON", height=32, width=190,
                    fg_color=_BLUE, hover_color=_BLUE_HOVER,
                    command=lambda: app._rcon_exec(srv.id, "shop.reload"),
                ).pack(side="left")
            else:
                inner_tabs.grid_remove()

        def _io_check() -> None:
            """Executa em background thread — apenas I/O de filesystem."""
            a = PluginManager.is_arkapi_installed(srv.install_dir)
            p = PluginManager.is_plugin_installed(srv.install_dir)
            r = PluginManager.is_permissions_installed(srv.install_dir)
            try:
                app.after(0, lambda: _apply_status(a, p, r))
            except Exception:
                pass

        threading.Thread(target=_io_check, daemon=True, name="PluginStatusCheck").start()

    _refresh_status()

