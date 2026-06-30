"""Seção Extensões SM — Fase 5 TEK."""
from __future__ import annotations

from ..asm_engine.asm_server_config import AsmServerConfig
from .server_field_widgets import CardSpec, begin_tek_section, build_cards_layout, add_collapsible_help


def build_sm_extensions_section(
    sf,
    srv: AsmServerConfig,
    vars_ref: dict,
    accent: str,
) -> None:
    ctx = begin_tek_section(sf, srv, vars_ref, accent, "Extensões SM", "Extensões SM")
    row = build_cards_layout(sf, ctx, [
        CardSpec("Pilhas e itens (GUS)", [
            "item_stack_size_multiplier",
            "spoiling_time_multiplier",
            "item_decomposition_time_multiplier",
        ]),
        CardSpec("Terminal de tributo (GUS)", [
            "max_tribute_dinos",
            "max_tribute_items",
            "tribute_dino_expiration_seconds",
            "tribute_item_expiration_seconds",
        ]),
        CardSpec("Reprodução / criativo (Game.ini)", [
            "baby_imprint_amount_multiplier",
            "enable_creative_mode",
        ], bool_grid=False),
    ])
    add_collapsible_help(sf, [
        ("ItemStackSizeMultiplier", "Multiplica o tamanho global de pilhas. Empilha com overrides por item."),
        ("SpoilingTimeMultiplier", "Legado GUS; use também GlobalSpoilingTimeMultiplier em Meio Ambiente."),
        ("MaxTributeDinos/Items", "Slots no obelisco/terminal. Valores altos podem corromper perfis de cluster."),
        ("BabyImprintAmountMultiplier", "Multiplica o % ganho por cada carinho de imprint (patch 312.35)."),
        ("Platform saddle / Stryder", "Configurações de platform saddle ficam em Estruturas → Platform saddle / Tek Strider."),
        ("bShowCreativeMode", "Habilita modo criativo no menu ESC (requer admin)."),
        ("Crossplay / Vivox", "Configurados em Administração → Avançado — Linha de comando."),
    ], row)
