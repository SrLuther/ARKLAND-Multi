"""Builders das seções de editores agregados ASM — Fase 4 TEK."""
from __future__ import annotations

import customtkinter as ctk  # type: ignore[reportMissingImports]

from ..asm_engine.asm_server_config import AsmServerConfig
from .tek_list_editor import (
    build_class_multiplier_editor,
    build_class_name_list_editor,
    build_spawn_weight_editor,
)


def build_harvest_resource_section(
    sf: ctk.CTkScrollableFrame,
    srv: AsmServerConfig,
    vars_ref: dict,
    accent: str,
) -> None:
    wrap = ctk.CTkFrame(sf, fg_color="transparent")
    wrap.grid(row=0, column=0, columnspan=2, sticky="ew", padx=8, pady=8)
    wrap.grid_columnconfigure(0, weight=1)

    ctk.CTkLabel(
        wrap,
        text="Multiplicadores de coleta por tipo de recurso (Game.ini)",
        font=ctk.CTkFont(size=11),
        text_color="#7ab8c8", anchor="w",
    ).pack(fill="x", pady=(0, 8))

    build_class_multiplier_editor(
        wrap, vars_ref, "_list_harvest",
        "HarvestResourceItemAmountClassMultipliers",
        "Multiplica a quantidade coletada por recurso. Empilha com HarvestAmountMultiplier global.",
        srv.harvest_resource_multipliers, accent,
        class_label="Recurso",
        class_placeholder="PrimalItemResource_Stone_C",
    )


def build_dino_class_multipliers_section(
    sf: ctk.CTkScrollableFrame,
    srv: AsmServerConfig,
    vars_ref: dict,
    accent: str,
) -> None:
    wrap = ctk.CTkFrame(sf, fg_color="transparent")
    wrap.grid(row=0, column=0, columnspan=2, sticky="ew", padx=8, pady=8)
    wrap.grid_columnconfigure(0, weight=1)

    ctk.CTkLabel(
        wrap,
        text="Dano e resistência por classe de dino (Game.ini)",
        font=ctk.CTkFont(size=11),
        text_color="#7ab8c8", anchor="w",
    ).pack(fill="x", pady=(0, 8))

    build_class_multiplier_editor(
        wrap, vars_ref, "_list_dino_res",
        "Resistência — selvagens (DinoClassResistanceMultipliers)",
        "2.0 = metade do dano recebido; 0.5 = dobro do dano.",
        srv.dino_class_resistance_multipliers, accent,
        class_placeholder="Rex_Character_BP_C",
    )
    build_class_multiplier_editor(
        wrap, vars_ref, "_list_dino_dmg",
        "Dano — selvagens (DinoClassDamageMultipliers)",
        "2.0 = dobro do dano causado; 0.5 = metade.",
        srv.dino_class_damage_multipliers, accent,
        class_placeholder="Rex_Character_BP_C",
    )
    build_class_multiplier_editor(
        wrap, vars_ref, "_list_tamed_dino_res",
        "Resistência — domados (TamedDinoClassResistanceMultipliers)",
        "Aplica-se a dinos domesticados.",
        srv.tamed_dino_class_resistance_multipliers, accent,
        class_placeholder="Rex_Character_BP_C",
    )
    build_class_multiplier_editor(
        wrap, vars_ref, "_list_tamed_dino_dmg",
        "Dano — domados (TamedDinoClassDamageMultipliers)",
        "Aplica-se a dinos domesticados.",
        srv.tamed_dino_class_damage_multipliers, accent,
        class_placeholder="Rex_Character_BP_C",
    )


def build_spawn_tame_section(
    sf: ctk.CTkScrollableFrame,
    srv: AsmServerConfig,
    vars_ref: dict,
    accent: str,
) -> None:
    wrap = ctk.CTkFrame(sf, fg_color="transparent")
    wrap.grid(row=0, column=0, columnspan=2, sticky="ew", padx=8, pady=8)
    wrap.grid_columnconfigure(0, weight=1)

    build_spawn_weight_editor(
        wrap, vars_ref, "_list_spawn_weight",
        "Peso de spawn (DinoSpawnWeightMultipliers)",
        "Ajusta frequência e limite de população por espécie no mapa.",
        srv.dino_spawn_weight_multipliers, accent,
    )
    build_class_name_list_editor(
        wrap, vars_ref, "_list_prevent_tame",
        "Impedir domesticação (PreventDinoTameClassNames)",
        "Classes listadas não podem ser domesticadas.",
        srv.prevent_dino_tame_class_names, accent,
    )
