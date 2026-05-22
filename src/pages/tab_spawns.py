from __future__ import annotations

import os
from pathlib import Path
import tkinter as tk
from typing import TYPE_CHECKING

import customtkinter as ctk  # type: ignore[reportMissingImports]

from ..ui_constants import _GREEN_DARK, _GREEN_HOVER, _BLUE, _CARD_BG

if TYPE_CHECKING:
    from ..app import ARKServerManagerApp
    from ..server_config import ServerConfig


def build_tab_spawns(app: "ARKServerManagerApp", parent, srv: "ServerConfig") -> None:  # noqa: C901
    """Constrói a aba de configuração de Spawn de Dinos Customizados."""
    adv = srv.advanced_settings
    w   = app._server_widgets[srv.id]

    outer_scroll = ctk.CTkScrollableFrame(parent, fg_color="transparent")
    outer_scroll.pack(fill="both", expand=True, padx=4, pady=4)
    outer_scroll.grid_columnconfigure(0, weight=1)

    # ── Cabeçalho explicativo ─────────────────────────────────────────────
    r = 0
    info_card = ctk.CTkFrame(outer_scroll, corner_radius=10, fg_color=_CARD_BG)
    info_card.grid(row=r, column=0, padx=12, pady=(8, 6), sticky="ew")
    info_card.grid_columnconfigure(0, weight=1)
    ctk.CTkLabel(
        info_card,
        text="🦖  Spawn de Dinos Customizados",
        font=ctk.CTkFont(size=14, weight="bold"),
        anchor="w",
    ).grid(row=0, column=0, padx=14, pady=(10, 2), sticky="w")
    fields_info = (
        "📦 Container de Spawn — a \"zona\" do mapa onde os dinos aparecem (ex: DinoSpawnEntriesBeach_C = praia da Island). "
        "Cada mapa tem seus próprios containers; escolha o da região que deseja modificar.\n"
        "\n"
        "📋 Entry (Registro) — um \"slot\" dentro do container representando um tipo de dino. "
        "Um container pode ter vários entries; o ARK escolhe qual spawnar baseado no peso de cada um.\n"
        "\n"
        "🏷  Nome (AnEntryName) — identificador textual da entry, apenas para referência/debug. "
        "Pode ser qualquer texto sem espaços, ex: \"MeuRex\".\n"
        "\n"
        "⚖  Peso (EntryWeight) — chance relativa de spawn. Peso 2.0 aparece o dobro de vezes que peso 1.0. "
        "Se houver vários entries, o ARK sorteará proporcionalmente (ex: 1.0 + 1.0 + 2.0 = 25 % / 25 % / 50 %).\n"
        "\n"
        "🧬 Blueprint Path — caminho do arquivo do dino no jogo, deve começar com Blueprint' e terminar com '. "
        "Um por linha; com múltiplos paths o ARK escolhe aleatoriamente. "
        "Ex: Blueprint'/Game/PrimalEarth/Dinos/Rex/Rex_Character_BP.Rex_Character_BP'\n"
        "\n"
        "🔢 Max Inimigos Mult. (apenas Substituir) — multiplica a quantidade máxima de dinos dessa zona. "
        "1.0 = padrão; 2.0 = dobro de dinos na área; 0.5 = metade."
    )
    ctk.CTkLabel(
        info_card,
        text=fields_info,
        text_color="gray55",
        font=ctk.CTkFont(size=10),
        justify="left",
        anchor="w",
        wraplength=860,
    ).grid(row=1, column=0, padx=14, pady=(0, 12), sticky="w")
    r += 1

    # ── Fábrica de seção (Add / Override) ────────────────────────────────
    def _build_spawn_section(
        parent_frame,
        section_label: str,
        section_hint: str,
        is_override: bool,
        initial_containers: list,
        container_store_key: str,
    ) -> None:
        """Constrói uma seção (Adicionar ou Substituir) de spawn containers."""
        sec_frame = ctk.CTkFrame(parent_frame, corner_radius=10, fg_color=_CARD_BG)
        sec_frame.pack(fill="x", padx=0, pady=(0, 10))
        sec_frame.grid_columnconfigure(0, weight=1)

        hdr = ctk.CTkFrame(sec_frame, fg_color="transparent")
        hdr.grid(row=0, column=0, padx=12, pady=(10, 4), sticky="ew")
        hdr.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            hdr, text=section_label,
            font=ctk.CTkFont(size=13, weight="bold"), anchor="w",
        ).grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(
            hdr, text=section_hint,
            text_color="gray50", font=ctk.CTkFont(size=10), anchor="w",
        ).grid(row=1, column=0, sticky="w")

        containers_frame = ctk.CTkFrame(sec_frame, fg_color="transparent")
        containers_frame.grid(row=1, column=0, padx=8, pady=(0, 4), sticky="ew")
        containers_frame.grid_columnconfigure(0, weight=1)

        w[container_store_key] = []  # List[dict]

        def _add_container(initial: dict | None = None) -> None:
            idx = len(w[container_store_key])
            container_data: dict = {}
            w[container_store_key].append(container_data)

            card = ctk.CTkFrame(containers_frame, corner_radius=8,
                                fg_color="#252535", border_width=1,
                                border_color="#3a3a55")
            card.grid(row=idx, column=0, padx=0, pady=(0, 8), sticky="ew")
            card.grid_columnconfigure(1, weight=1)
            container_data["_card"] = card

            ci = 0

            # Linha: container class
            lbl_cont_fr = ctk.CTkFrame(card, fg_color="transparent")
            lbl_cont_fr.grid(row=ci, column=0, padx=(10, 4), pady=(8, 2), sticky="w")
            ctk.CTkLabel(lbl_cont_fr, text="Container:", anchor="w",
                         text_color="gray65",
                         font=ctk.CTkFont(size=11, weight="bold")).pack(anchor="w")
            ctk.CTkLabel(lbl_cont_fr,
                         text="Zona do mapa a modificar",
                         anchor="w", text_color="gray40",
                         font=ctk.CTkFont(size=9)).pack(anchor="w")
            container_var = tk.StringVar(
                value=initial.get("container", "") if initial else "")
            container_data["container_var"] = container_var
            cont_combo = ctk.CTkComboBox(
                card, variable=container_var,
                values=app._SPAWN_CONTAINERS,
                width=420, height=30,
            )
            cont_combo.grid(row=ci, column=1, padx=(0, 4), pady=(8, 2), sticky="w")

            def _remove_this(_card=card, _data=container_data,
                              _store_key=container_store_key):
                if _data in w[_store_key]:
                    w[_store_key].remove(_data)
                _card.destroy()

            ctk.CTkButton(card, text="✖", width=28, height=28,
                          fg_color="#5a2020", hover_color="#7a2020",
                          command=_remove_this).grid(
                row=ci, column=2, padx=(4, 10), pady=(8, 2))
            ci += 1

            # Linha: MaxDesiredNumEnemiesMultiplier (só Override)
            if is_override:
                lbl_mult_fr = ctk.CTkFrame(card, fg_color="transparent")
                lbl_mult_fr.grid(row=ci, column=0, padx=(10, 4), pady=(4, 2), sticky="w")
                ctk.CTkLabel(lbl_mult_fr, text="Max Inimigos Mult.:", anchor="w",
                             text_color="gray65",
                             font=ctk.CTkFont(size=11)).pack(anchor="w")
                ctk.CTkLabel(lbl_mult_fr,
                             text="Qtd. máx. de dinos na zona\n(1.0=padrão, 2.0=dobro)",
                             anchor="w", text_color="gray40",
                             font=ctk.CTkFont(size=9)).pack(anchor="w")
                mult_var = tk.StringVar(
                    value=str(initial.get("max_enemies_multiplier", 1.0)) if initial else "1.0")
                container_data["max_mult_var"] = mult_var
                ctk.CTkEntry(card, textvariable=mult_var, width=100, height=28).grid(
                    row=ci, column=1, padx=(0, 4), pady=(4, 2), sticky="w")
                ci += 1

            # Sub-frame de entries
            entries_outer = ctk.CTkFrame(card, fg_color="transparent")
            entries_outer.grid(row=ci, column=0, columnspan=3,
                               padx=8, pady=(4, 0), sticky="ew")
            entries_outer.grid_columnconfigure(0, weight=1)
            ci += 1

            # Linha de cabeçalhos das entries
            hdr_row = ctk.CTkFrame(entries_outer, fg_color="transparent")
            hdr_row.grid(row=0, column=0, sticky="ew", pady=(0, 2))
            hdr_row.grid_columnconfigure(1, weight=1)
            ctk.CTkLabel(hdr_row,
                         text="Nome  (AnEntryName)",
                         width=130, anchor="w",
                         text_color="gray50",
                         font=ctk.CTkFont(size=10)).grid(row=0, column=0, padx=(2, 4))
            ctk.CTkLabel(hdr_row,
                         text="Peso  (EntryWeight)",
                         width=55, anchor="w",
                         text_color="gray50",
                         font=ctk.CTkFont(size=10)).grid(row=0, column=1, padx=(0, 4))
            ctk.CTkLabel(hdr_row,
                         text="Blueprint Path(s) — um por linha  "
                              "(Blueprint'/Game/…/NomeDino_Character_BP.NomeDino_Character_BP')",
                         anchor="w", text_color="gray50",
                         font=ctk.CTkFont(size=10)).grid(
                row=0, column=2, padx=(0, 4), sticky="w")

            entries_frame = ctk.CTkFrame(entries_outer, fg_color="transparent")
            entries_frame.grid(row=1, column=0, sticky="ew")
            entries_frame.grid_columnconfigure(2, weight=1)

            container_data["entries"] = []

            def _add_entry(initial_entry: dict | None = None,
                            _ef=entries_frame,
                            _cd=container_data):
                ei = len(_cd["entries"])
                entry_data: dict = {}
                _cd["entries"].append(entry_data)

                name_var   = tk.StringVar(
                    value=initial_entry.get("name", "") if initial_entry else "")
                weight_var = tk.StringVar(
                    value=str(initial_entry.get("weight", 1.0)) if initial_entry else "1.0")
                bp_var     = tk.StringVar(
                    value="\n".join(initial_entry.get("blueprints", []))
                    if initial_entry else "")
                entry_data["name_var"]   = name_var
                entry_data["weight_var"] = weight_var
                entry_data["bp_var"]     = bp_var

                row_fr = ctk.CTkFrame(_ef, fg_color="transparent")
                row_fr.grid(row=ei, column=0, columnspan=4,
                            padx=0, pady=(0, 4), sticky="ew")
                row_fr.grid_columnconfigure(2, weight=1)

                ctk.CTkEntry(row_fr, textvariable=name_var,
                             width=130, height=28,
                             placeholder_text="Nome").grid(
                    row=0, column=0, padx=(0, 4))
                ctk.CTkEntry(row_fr, textvariable=weight_var,
                             width=55, height=28,
                             placeholder_text="1.0").grid(
                    row=0, column=1, padx=(0, 4))

                bp_box = ctk.CTkTextbox(row_fr, height=52, wrap="none")
                bp_box.grid(row=0, column=2, padx=(0, 4), sticky="ew")
                bp_box.insert("1.0", "\n".join(
                    initial_entry.get("blueprints", [])) if initial_entry else "")
                entry_data["bp_box"] = bp_box

                def _remove_entry(_rd=row_fr, _ed=entry_data, _cd2=_cd):
                    if _ed in _cd2["entries"]:
                        _cd2["entries"].remove(_ed)
                    _rd.destroy()

                ctk.CTkButton(row_fr, text="✖", width=26, height=28,
                              fg_color="#5a2020", hover_color="#7a2020",
                              command=_remove_entry).grid(row=0, column=3)

            # Carrega entries iniciais ou cria uma em branco
            if initial and initial.get("entries"):
                for ie in initial["entries"]:
                    _add_entry(ie)
            else:
                _add_entry()

            # Botão "Adicionar Entry"
            add_entry_row = ctk.CTkFrame(card, fg_color="transparent")
            add_entry_row.grid(row=ci, column=0, columnspan=3,
                               padx=8, pady=(2, 8), sticky="w")
            container_data["_add_entry_fn"] = _add_entry
            ctk.CTkButton(
                add_entry_row, text="➕ Adicionar Entry",
                width=160, height=28,
                fg_color=_GREEN_DARK, hover_color=_GREEN_HOVER,
                command=_add_entry,
            ).pack(side="left")

        # Carrega containers iniciais
        for init_c in initial_containers:
            _add_container(init_c)

        # Botão "Adicionar Container"
        add_cont_row = ctk.CTkFrame(sec_frame, fg_color="transparent")
        add_cont_row.grid(row=2, column=0, padx=12, pady=(0, 12), sticky="w")
        ctk.CTkButton(
            add_cont_row, text="➕ Adicionar Container de Spawn",
            width=230, height=30,
            fg_color=_BLUE, hover_color="#253a6a",
            command=_add_container,
        ).pack(side="left")

    # ── Coloca as duas seções no scroll ───────────────────────────────────
    sections_frame = ctk.CTkFrame(outer_scroll, fg_color="transparent")
    sections_frame.grid(row=r, column=0, sticky="ew", padx=4)
    sections_frame.grid_columnconfigure(0, weight=1)
    r += 1

    _build_spawn_section(
        sections_frame,
        "➕  Adicionar Spawns",
        "Adiciona entradas a containers existentes sem remover os spawns padrão.",
        is_override=False,
        initial_containers=adv.npc_spawn_entries_add,
        container_store_key="spawn_add_list",
    )
    _build_spawn_section(
        sections_frame,
        "🔄  Substituir Spawns",
        "Substitui completamente os spawns de um container (remove os padrões).",
        is_override=True,
        initial_containers=adv.npc_spawn_entries_override,
        container_store_key="spawn_override_list",
    )

    # ── Multiplicadores por Classe de Dino ────────────────────────────────
    def _build_dino_mult_section(
        parent_frame,
        title: str,
        hint: str,
        store_key: str,
        initial_data: list,
    ) -> None:
        sec = ctk.CTkFrame(parent_frame, fg_color=_CARD_BG, corner_radius=10)
        sec.grid(row=sec.master.grid_size()[1], column=0, sticky="ew", padx=0, pady=(10, 0))
        sec.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(sec, text=title, font=ctk.CTkFont(size=13, weight="bold")
                     ).grid(row=0, column=0, padx=14, pady=(10, 2), sticky="w")
        ctk.CTkLabel(sec, text=hint, text_color="gray60", wraplength=640, justify="left"
                     ).grid(row=1, column=0, padx=14, pady=(0, 6), sticky="w")

        rows_frame = ctk.CTkFrame(sec, fg_color="transparent")
        rows_frame.grid(row=2, column=0, sticky="ew", padx=14, pady=(0, 4))
        rows_frame.grid_columnconfigure(1, weight=1)

        row_list: list[dict] = []
        w[store_key] = row_list

        def _add_row(class_name: str = "", mult: float = 1.0) -> None:
            idx = len(row_list)
            rf = ctk.CTkFrame(rows_frame, fg_color="#1e2a3a", corner_radius=6)
            rf.grid(row=idx, column=0, columnspan=3, sticky="ew", pady=2)
            rf.grid_columnconfigure(1, weight=1)

            ctk.CTkLabel(rf, text="Classe:", text_color="gray60", width=50
                         ).grid(row=0, column=0, padx=(8, 4), pady=4)
            cn_var = tk.StringVar(value=class_name)
            ctk.CTkEntry(rf, textvariable=cn_var, width=280, height=28,
                         placeholder_text="Ex: Rex_Character_BP_C"
                         ).grid(row=0, column=1, padx=4, pady=4, sticky="ew")
            ctk.CTkLabel(rf, text="Mult:", text_color="gray60", width=36
                         ).grid(row=0, column=2, padx=(6, 2), pady=4)
            mt_var = tk.StringVar(value=str(mult))
            ctk.CTkEntry(rf, textvariable=mt_var, width=70, height=28
                         ).grid(row=0, column=3, padx=(0, 4), pady=4)

            rd = {"class_name_var": cn_var, "mult_var": mt_var, "_frame": rf}
            row_list.append(rd)

            def _remove(r=rd, f=rf):
                row_list.remove(r)
                f.destroy()

            ctk.CTkButton(rf, text="✖", width=28, height=28,
                          fg_color="#5a1f1f", hover_color="#8a2a2a",
                          command=_remove).grid(row=0, column=4, padx=(4, 8), pady=4)

        for item in initial_data:
            _add_row(item.get("class_name", ""), item.get("multiplier", 1.0))

        add_row_frame = ctk.CTkFrame(sec, fg_color="transparent")
        add_row_frame.grid(row=3, column=0, padx=14, pady=(0, 10), sticky="w")
        ctk.CTkButton(
            add_row_frame, text="➕ Adicionar Classe",
            width=180, height=28,
            fg_color=_BLUE, hover_color="#253a6a",
            command=_add_row,
        ).pack(side="left")

    dino_mult_frame = ctk.CTkFrame(outer_scroll, fg_color="transparent")
    dino_mult_frame.grid(row=r, column=0, sticky="ew", padx=4)
    dino_mult_frame.grid_columnconfigure(0, weight=1)
    r += 1

    _build_dino_mult_section(
        dino_mult_frame,
        "🛡️  Resistência por Classe de Dino (DinoClassResistanceMultipliers)",
        "Multiplica a resistência a dano de dinos selvagens por classe.  "
        "2.0 = recebe metade do dano;  0.5 = recebe o dobro do dano.",
        "dino_res_mult_list",
        adv.dino_class_resistance_multipliers,
    )
    _build_dino_mult_section(
        dino_mult_frame,
        "⚔️  Dano por Classe de Dino (DinoClassDamageMultipliers)",
        "Multiplica o dano causado por dinos selvagens por classe.  "
        "2.0 = causa o dobro de dano;  0.5 = causa metade do dano.",
        "dino_dmg_mult_list",
        adv.dino_class_damage_multipliers,
    )
    _build_dino_mult_section(
        dino_mult_frame,
        "🛡️  Resistência — Domados (TamedDinoClassResistanceMultipliers)",
        "Igual ao anterior, mas aplica-se a dinos domados.",
        "tamed_dino_res_mult_list",
        adv.tamed_dino_class_resistance_multipliers,
    )
    _build_dino_mult_section(
        dino_mult_frame,
        "⚔️  Dano — Domados (TamedDinoClassDamageMultipliers)",
        "Igual ao anterior, mas aplica-se a dinos domados.",
        "tamed_dino_dmg_mult_list",
        adv.tamed_dino_class_damage_multipliers,
    )

    app._save_btn_row(outer_scroll, r, srv.id)

