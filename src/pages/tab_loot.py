from __future__ import annotations

import tkinter as tk
from typing import TYPE_CHECKING

import customtkinter as ctk  # type: ignore[reportMissingImports]

from ..ui_constants import _GREEN_DARK, _GREEN_HOVER, _BLUE, _CARD_BG

if TYPE_CHECKING:
    from ..app import ARKServerManagerApp
    from ..server_config import ServerConfig


def build_tab_loot(app: "ARKServerManagerApp", parent, srv: "ServerConfig") -> None:  # noqa: C901
    parent.grid_columnconfigure(0, weight=1)
    parent.grid_rowconfigure(0, weight=1)

    w = app._server_widgets[srv.id]
    adv = srv.advanced_settings
    w["loot_crate_list"] = []

    outer_scroll = ctk.CTkScrollableFrame(parent, fg_color="transparent")
    outer_scroll.grid(row=0, column=0, sticky="nsew")
    outer_scroll.grid_columnconfigure(0, weight=1)

    # ── Cabeçalho ─────────────────────────────────────────────────────────
    hdr = ctk.CTkFrame(outer_scroll, fg_color=_CARD_BG, corner_radius=10)
    hdr.grid(row=0, column=0, padx=12, pady=(12, 4), sticky="ew")
    hdr.grid_columnconfigure(0, weight=1)
    ctk.CTkLabel(hdr, text="📦  Substituição de Itens de Supply Crates",
                 font=ctk.CTkFont(size=14, weight="bold")
                 ).grid(row=0, column=0, padx=16, pady=(12, 4), sticky="w")
    ctk.CTkLabel(
        hdr,
        text=(
            "ConfigOverrideSupplyCrateItems — substitui completamente os itens de um tipo de crate.\n"
            "Cada override define sets de itens; cada set define entries com as classes dos itens possíveis."
        ),
        text_color="gray60", wraplength=660, justify="left",
    ).grid(row=1, column=0, padx=16, pady=(0, 12), sticky="w")

    # ── Container de crates ───────────────────────────────────────────────
    crates_frame = ctk.CTkFrame(outer_scroll, fg_color="transparent")
    crates_frame.grid(row=1, column=0, sticky="ew", padx=4)
    crates_frame.grid_columnconfigure(0, weight=1)

    _KNOWN_CRATES = [
        "SupplyCrate_Level03_C",
        "SupplyCrate_Level06_C",
        "SupplyCrate_Level12_C",
        "SupplyCrate_Level25_C",
        "SupplyCrate_Level35_C",
        "SupplyCrate_Level50_C",
        "SupplyCrate_Cave_C",
        "SupplyCrate_OceanCage_C",
    ]

    def _add_entry_row(entries_frame, entry_list, items="", weight=1.0,
                       min_qty=1.0, max_qty=1.0,
                       min_ql=1.0, max_ql=1.0,
                       force_bp=False, bp_chance=0.0):
        idx = len(entry_list)
        ef = ctk.CTkFrame(entries_frame, fg_color="#1a2535", corner_radius=6)
        ef.grid(row=idx, column=0, sticky="ew", pady=2)
        ef.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(ef, text="Peso:", text_color="gray60", width=42
                     ).grid(row=0, column=0, padx=(8, 2), pady=(6, 2))
        wt_var = tk.StringVar(value=str(weight))
        ctk.CTkEntry(ef, textvariable=wt_var, width=56, height=26
                     ).grid(row=0, column=1, padx=2, pady=(6, 2), sticky="w")

        # Remove button
        def _rem_entry(ed=None, fr=ef):
            if ed in entry_list:
                entry_list.remove(ed)
            fr.destroy()

        # We'll set up the dict after creating all widgets
        ctk.CTkLabel(ef, text="Classes de Item (uma por linha):",
                     text_color="gray60").grid(row=1, column=0, columnspan=2,
                                                padx=8, pady=(4, 0), sticky="w")
        items_box = ctk.CTkTextbox(ef, height=60, width=380)
        items_box.grid(row=2, column=0, columnspan=5, padx=8, pady=(0, 4), sticky="ew")
        if items:
            items_box.insert("1.0", items)

        num_frame = ctk.CTkFrame(ef, fg_color="transparent")
        num_frame.grid(row=3, column=0, columnspan=5, padx=8, pady=(0, 6), sticky="w")

        def _lbl(txt): return ctk.CTkLabel(num_frame, text=txt, text_color="gray60")
        def _ent(var, w=64): return ctk.CTkEntry(num_frame, textvariable=var, width=w, height=26)

        min_qty_var = tk.StringVar(value=str(min_qty))
        max_qty_var = tk.StringVar(value=str(max_qty))
        min_ql_var  = tk.StringVar(value=str(min_ql))
        max_ql_var  = tk.StringVar(value=str(max_ql))
        bp_chance_var = tk.StringVar(value=str(bp_chance))
        force_bp_var  = tk.BooleanVar(value=force_bp)

        c = 0
        for lbl, var in (
            ("Qtd Min:", min_qty_var), ("Qtd Máx:", max_qty_var),
            ("Qual Min:", min_ql_var), ("Qual Máx:", max_ql_var),
            ("% Blueprint:", bp_chance_var),
        ):
            _lbl(lbl).grid(row=0, column=c, padx=(4, 1))
            _ent(var).grid(row=0, column=c + 1, padx=(0, 8))
            c += 2
        ctk.CTkLabel(num_frame, text="Forçar BP:", text_color="gray60"
                     ).grid(row=0, column=c, padx=(4, 1))
        ctk.CTkCheckBox(num_frame, text="", variable=force_bp_var, width=24
                        ).grid(row=0, column=c + 1, padx=(0, 8))

        ed = {
            "weight_var": wt_var, "items_box": items_box,
            "min_qty_var": min_qty_var, "max_qty_var": max_qty_var,
            "min_ql_var": min_ql_var, "max_ql_var": max_ql_var,
            "force_bp_var": force_bp_var, "bp_chance_var": bp_chance_var,
            "_frame": ef,
        }
        entry_list.append(ed)

        ctk.CTkButton(ef, text="✖", width=28, height=26,
                      fg_color="#5a1f1f", hover_color="#8a2a2a",
                      command=lambda: _rem_entry(ed)).grid(
            row=0, column=4, padx=(4, 8), pady=(6, 2))

    def _add_item_set_row(sets_frame, set_list, set_data=None):
        if set_data is None:
            set_data = {}
        idx = len(set_list)
        sf = ctk.CTkFrame(sets_frame, fg_color="#17202f", corner_radius=8)
        sf.grid(row=idx, column=0, sticky="ew", pady=4)
        sf.grid_columnconfigure(0, weight=1)

        hf = ctk.CTkFrame(sf, fg_color="transparent")
        hf.grid(row=0, column=0, sticky="ew", padx=10, pady=(8, 4))

        def _lbl(p, txt): return ctk.CTkLabel(p, text=txt, text_color="gray60")
        def _ent(p, var, w=64): return ctk.CTkEntry(p, textvariable=var, width=w, height=26)

        sw_var   = tk.StringVar(value=str(set_data.get("set_weight", 1.0)))
        min_var  = tk.StringVar(value=str(set_data.get("min_items", 1)))
        max_var  = tk.StringVar(value=str(set_data.get("max_items", 2)))
        pow_var  = tk.StringVar(value=str(set_data.get("num_items_power", 1.0)))
        repl_var = tk.BooleanVar(value=set_data.get("items_no_replacement", True))

        c = 0
        for lbl_txt, var, w_px in (
            ("Peso:", sw_var, 64), ("Min Itens:", min_var, 52),
            ("Max Itens:", max_var, 52), ("Power:", pow_var, 56),
        ):
            _lbl(hf, lbl_txt).grid(row=0, column=c, padx=(0 if c == 0 else 4, 2))
            _ent(hf, var, w_px).grid(row=0, column=c + 1, padx=(0, 6))
            c += 2
        _lbl(hf, "Sem Repet.:").grid(row=0, column=c, padx=(4, 2))
        ctk.CTkCheckBox(hf, text="", variable=repl_var, width=24
                        ).grid(row=0, column=c + 1, padx=(0, 4))

        ctk.CTkLabel(sf, text="Entries de Itens:", text_color="gray60",
                     font=ctk.CTkFont(size=11)
                     ).grid(row=1, column=0, padx=14, pady=(4, 0), sticky="w")

        entries_container = ctk.CTkFrame(sf, fg_color="transparent")
        entries_container.grid(row=2, column=0, sticky="ew", padx=14)
        entries_container.grid_columnconfigure(0, weight=1)
        entry_list: list[dict] = []

        for edata in set_data.get("entries", []):
            _add_entry_row(
                entries_container, entry_list,
                items="\n".join(edata.get("items", [])),
                weight=edata.get("weight", 1.0),
                min_qty=edata.get("min_qty", 1.0),
                max_qty=edata.get("max_qty", 1.0),
                min_ql=edata.get("min_quality", 1.0),
                max_ql=edata.get("max_quality", 1.0),
                force_bp=edata.get("force_blueprint", False),
                bp_chance=edata.get("blueprint_chance", 0.0),
            )

        add_e_row = ctk.CTkFrame(sf, fg_color="transparent")
        add_e_row.grid(row=3, column=0, padx=14, pady=(4, 8), sticky="w")
        ctk.CTkButton(
            add_e_row, text="➕ Adicionar Entry", width=160, height=26,
            fg_color=_BLUE, hover_color="#253a6a",
            command=lambda ec=entries_container, el=entry_list: _add_entry_row(ec, el),
        ).pack(side="left")

        sd = {
            "set_weight_var": sw_var, "min_items_var": min_var,
            "max_items_var": max_var, "num_items_power_var": pow_var,
            "items_no_repl_var": repl_var, "entries": entry_list, "_frame": sf,
        }
        set_list.append(sd)

        def _rem_set(sdd=sd, fr=sf):
            if sdd in set_list:
                set_list.remove(sdd)
            fr.destroy()

        ctk.CTkButton(
            hf, text="✖ Set", width=56, height=26,
            fg_color="#5a1f1f", hover_color="#8a2a2a",
            command=_rem_set,
        ).grid(row=0, column=c + 2, padx=(12, 0))

    def _add_crate_card(crate_data=None):
        if crate_data is None:
            crate_data = {}
        idx = len(w["loot_crate_list"])
        card = ctk.CTkFrame(crates_frame, fg_color=_CARD_BG, corner_radius=10)
        card.grid(row=idx, column=0, sticky="ew", padx=0, pady=(0, 8))
        card.grid_columnconfigure(0, weight=1)

        # Header row
        top_row = ctk.CTkFrame(card, fg_color="transparent")
        top_row.grid(row=0, column=0, sticky="ew", padx=12, pady=(10, 4))
        top_row.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(top_row, text="Classe do Crate:", text_color="gray60"
                     ).grid(row=0, column=0, padx=(0, 4))

        crate_class_var = tk.StringVar(value=crate_data.get("crate_class", ""))
        combo = ctk.CTkComboBox(
            top_row, variable=crate_class_var, values=_KNOWN_CRATES,
            width=260, height=28,
        )
        combo.grid(row=0, column=1, padx=(0, 8), sticky="ew")

        def _lbl(p, txt): return ctk.CTkLabel(p, text=txt, text_color="gray60")
        def _ent(p, var, ww=64): return ctk.CTkEntry(p, textvariable=var, width=ww, height=26)

        num_row = ctk.CTkFrame(card, fg_color="transparent")
        num_row.grid(row=1, column=0, sticky="w", padx=12, pady=(0, 4))

        min_sets_var  = tk.StringVar(value=str(crate_data.get("min_sets", 1)))
        max_sets_var  = tk.StringVar(value=str(crate_data.get("max_sets", 1)))
        pow_sets_var  = tk.StringVar(value=str(crate_data.get("num_sets_power", 1.0)))
        repl_sets_var = tk.BooleanVar(value=crate_data.get("sets_no_replacement", True))

        c = 0
        for lbl_txt, var, wpx in (
            ("Min Sets:", min_sets_var, 52),
            ("Max Sets:", max_sets_var, 52),
            ("NumSetsPower:", pow_sets_var, 64),
        ):
            _lbl(num_row, lbl_txt).grid(row=0, column=c, padx=(0 if c == 0 else 4, 2))
            _ent(num_row, var, wpx).grid(row=0, column=c + 1, padx=(0, 8))
            c += 2
        _lbl(num_row, "Sets Sem Repet.:").grid(row=0, column=c, padx=(4, 2))
        ctk.CTkCheckBox(num_row, text="", variable=repl_sets_var, width=24
                        ).grid(row=0, column=c + 1, padx=(0, 4))

        ctk.CTkLabel(card, text="Item Sets:", text_color="gray60",
                     font=ctk.CTkFont(size=11, weight="bold")
                     ).grid(row=2, column=0, padx=14, pady=(4, 0), sticky="w")

        sets_container = ctk.CTkFrame(card, fg_color="transparent")
        sets_container.grid(row=3, column=0, sticky="ew", padx=12)
        sets_container.grid_columnconfigure(0, weight=1)
        set_list: list[dict] = []

        for sdata in crate_data.get("item_sets", []):
            _add_item_set_row(sets_container, set_list, sdata)

        add_set_row = ctk.CTkFrame(card, fg_color="transparent")
        add_set_row.grid(row=4, column=0, padx=14, pady=(6, 10), sticky="w")
        ctk.CTkButton(
            add_set_row, text="➕ Adicionar Item Set", width=180, height=28,
            fg_color=_BLUE, hover_color="#253a6a",
            command=lambda sc=sets_container, sl=set_list: _add_item_set_row(sc, sl),
        ).pack(side="left")

        cd = {
            "crate_class_var": crate_class_var,
            "min_sets_var": min_sets_var, "max_sets_var": max_sets_var,
            "num_sets_power_var": pow_sets_var, "sets_no_repl_var": repl_sets_var,
            "item_sets": set_list, "_card": card,
        }
        w["loot_crate_list"].append(cd)

        def _rem_crate(cdd=cd, fr=card):
            if cdd in w["loot_crate_list"]:
                w["loot_crate_list"].remove(cdd)
            fr.destroy()

        ctk.CTkButton(
            top_row, text="✖ Remover Crate", width=120, height=28,
            fg_color="#5a1f1f", hover_color="#8a2a2a",
            command=_rem_crate,
        ).grid(row=0, column=2, padx=(8, 0))

    # Carrega dados existentes
    for cd in adv.supply_crate_overrides:
        _add_crate_card(cd)

    add_crate_row = ctk.CTkFrame(outer_scroll, fg_color="transparent")
    add_crate_row.grid(row=2, column=0, padx=16, pady=(4, 6), sticky="w")
    ctk.CTkButton(
        add_crate_row, text="➕ Adicionar Override de Crate",
        width=220, height=30,
        fg_color=_GREEN_DARK, hover_color=_GREEN_HOVER,
        command=_add_crate_card,
    ).pack(side="left")

    app._save_btn_row(outer_scroll, 3, srv.id)

