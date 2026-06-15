"""Seção Administração → Avançado (linha de comando) — Fase 3 TEK."""
from __future__ import annotations

import customtkinter as ctk  # type: ignore[reportMissingImports]

from ..asm_engine.asm_server_config import AsmServerConfig
from .server_field_widgets import (
    CardSpec,
    build_cards_layout,
    init_panel_context,
)

_CLI_CARDS: list[CardSpec] = [
    CardSpec("Inicialização", [
        "use_battleye", "force_respawn_dinos", "use_allcores",
    ]),
    CardSpec("Rede / plataformas", [
        "crossplay", "epic_only", "public_ip_for_epic", "use_vivox",
        "use_item_dupe_check", "use_raw_sockets", "no_net_threading",
        "force_net_threading",
    ]),
    CardSpec("Segurança / anti-cheat", [
        "disable_vac", "disable_anti_speed_hack", "speed_hack_bias",
        "disable_player_move_physics_opt",
    ]),
    CardSpec("Performance / memória", [
        "use_cache", "use_old_save_format", "use_no_memory_bias",
        "stasis_keep_controllers", "use_no_hang_detection", "server_allow_ansel",
        "no_dinos", "force_dx10", "force_shader_model4", "force_low_memory",
    ], bool_grid=True),
    CardSpec("Gameplay (CLI)", [
        "allow_cave_flyers", "enable_auto_destroy_structures", "enable_no_fish_loot",
        "prevent_spawn_animations", "show_floating_damage_text", "exclusive_join",
        "no_transfer_from_filtering",
    ], bool_grid=True),
    CardSpec("Logs de admin (CLI)", [
        "enable_server_admin_logs", "server_admin_logs_include_tribe_logs",
        "server_rcon_output_tribe_logs", "notify_admin_commands_in_chat",
    ], bool_grid=True),
    CardSpec("Web Alarm", [
        "enable_web_alarm", "web_alarm_key", "web_alarm_url",
    ]),
]


def build_cli_avancado_section(
    sf: ctk.CTkScrollableFrame,
    srv: AsmServerConfig,
    vars_ref: dict,
    accent: str,
    start_row: int,
) -> int:
    """Insere cards de flags CLI em Administração. Retorna próxima linha livre."""
    ctk.CTkLabel(
        sf,
        text="Avançado — Linha de comando",
        font=ctk.CTkFont(size=13, weight="bold"),
        text_color=accent,
        anchor="w",
    ).grid(row=start_row, column=0, columnspan=2, padx=8, pady=(12, 4), sticky="w")

    area = ctk.CTkFrame(sf, fg_color="transparent")
    area.grid(row=start_row + 1, column=0, columnspan=2, sticky="ew", padx=4, pady=(0, 8))
    area.grid_columnconfigure(0, weight=1)
    area.grid_columnconfigure(1, weight=1)

    ctx = init_panel_context(
        sf, srv, vars_ref, accent, "Administração", vars_ref.get("_panel_root"),
    )
    build_cards_layout(area, ctx, _CLI_CARDS, start_row=0)
    # `area` ocupa uma única linha no grid pai; altura vem do conteúdo interno.
    return start_row + 2
