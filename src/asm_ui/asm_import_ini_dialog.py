"""
TEK — Diálogo de Importação e Sincronização de INI

Permite carregar GameUserSettings.ini / Game.ini de qualquer diretório
e aplicar as configurações ao servidor atual ou sincronizar com outros.

Campos NUNCA importados: nome do servidor, portas, diretório de instalação,
mapa, save dir, cluster, branch e args extras.
"""
from __future__ import annotations

import copy
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox
from typing import TYPE_CHECKING

import customtkinter as ctk  # type: ignore[reportMissingImports]

from ..asm_engine.asm_server_config import AsmServerConfig
from ..asm_engine.asm_ini_manager import read_ini_from_paths
from ..ui_constants import get_theme

if TYPE_CHECKING:
    from ..app import ARKServerManagerApp


# ── Campos que NUNCA são importados ───────────────────────────────────────────
_EXCLUDED_FIELDS: frozenset[str] = frozenset({
    # Identificação / localização
    "id", "name", "install_dir", "server_exe",
    # Rede (portas)
    "server_port", "query_port", "rcon_port", "server_ip",
    # Nome em-jogo
    "session_name",
    # SteamCMD
    "branch_name", "branch_password",
    # Cluster
    "cross_ark_cluster_id", "cluster_dir_override",
    # Identidade do servidor
    "additional_args", "alt_save_directory_name", "server_map",
    "total_conversion_mod_id",
    # Metadados internos
    "notes", "tags",
})


# ── Categorias de configuração ─────────────────────────────────────────────────
_CATEGORIES: list[tuple[str, list[str]]] = [
    ("Senhas e Mods", [
        "server_password", "admin_password", "spectator_password",
        "rcon_enabled", "rcon_log_buffer", "admin_logging",
        "active_mods", "auto_save_period",
        "kick_idle_players", "enable_kick_idle_players",
        "enable_ban_list_url", "ban_list_url",
        "motd", "motd_duration",
        "max_tribe_logs", "tribe_log_destroyed_enemy_structures",
        "allow_hide_damage_source",
    ]),
    ("Regras", [
        "enable_hardcore", "enable_pvp", "allow_cave_building_pve",
        "disable_friendly_fire_pvp", "disable_friendly_fire_pve",
        "disable_loot_crates", "enable_difficulty_override",
        "override_official_difficulty", "difficulty_offset",
        "max_tribe_size", "allow_pvp_gamma", "allow_pve_gamma",
        "allow_tribe_alliances", "allow_custom_recipes",
        "enable_diseases", "non_permanent_diseases",
        "prevent_pvp_offline", "prevent_pvp_offline_interval",
        "prevent_pvp_offline_invincible_interval",
        "auto_pve_timer", "auto_pve_use_system_time",
        "auto_pve_start_time", "auto_pve_stop_time",
        "allow_tribe_war_pve", "allow_tribe_war_cancel_pve",
        "enable_extra_structure_prevention_volumes",
        "oxygen_swim_speed_stat_multiplier",
        "supply_crate_loot_quality_multiplier",
        "fishing_loot_quality_multiplier",
        "use_corpse_life_span_multiplier",
        "global_powered_battery_durability_decrease",
        "tribe_name_change_cooldown", "random_supply_crate_points",
        "increase_pvp_respawn_interval", "pvp_respawn_check_period",
        "pvp_respawn_multiplier", "pvp_respawn_base_amount",
        "custom_recipe_effectiveness_multiplier",
        "custom_recipe_skill_multiplier",
        "override_npc_stasis_range_scale",
        "npc_stasis_range_scale_start", "npc_stasis_range_scale_end",
        "npc_stasis_range_scale_percent_end",
        "use_corpse_locator", "prevent_spawn_animations",
        "allow_unlimited_respecs", "allow_platform_saddle_multi_floors",
        "max_alliances_per_tribe", "max_tribes_per_alliance",
    ]),
    ("Transferências / Tributo", [
        "enable_tribute_downloads",
        "prevent_download_survivors", "prevent_download_items", "prevent_download_dinos",
        "prevent_upload_survivors", "prevent_upload_items", "prevent_upload_dinos",
        "cross_ark_allow_foreign_dino_downloads",
        "save_tribute_char_expiration", "tribute_char_expiration_seconds",
        "save_tribute_item_expiration", "tribute_item_expiration_seconds",
        "save_tribute_dino_expiration", "tribute_dino_expiration_seconds",
        "save_min_dino_reupload_interval", "min_dino_reupload_interval",
    ]),
    ("Chat e Notificações", [
        "global_voice_chat", "proximity_chat",
        "player_leave_notifications", "player_joined_notifications",
    ]),
    ("HUD e Visuais", [
        "allow_crosshair", "allow_hud", "allow_third_person_view",
        "show_map_player_location", "show_floating_damage_text", "allow_hit_markers",
    ]),
    ("Jogadores", [
        "xp_multiplier", "player_damage_multiplier", "player_resistance_multiplier",
        "player_water_drain_multiplier", "player_food_drain_multiplier",
        "player_stamina_drain_multiplier", "player_health_recovery_multiplier",
        "player_harvesting_damage_multiplier", "crafting_skill_bonus_multiplier",
        "enable_flyer_carry", "override_max_xp_player",
    ]),
    ("Dinos", [
        "dino_damage_multiplier", "tamed_dino_damage_multiplier",
        "dino_resistance_multiplier", "tamed_dino_resistance_multiplier",
        "max_tamed_dinos", "dino_count_multiplier", "taming_speed_multiplier",
        "disable_imprint_buff", "allow_anyone_baby_imprint",
        "disable_dino_riding", "disable_dino_taming",
        "passive_tame_interval_multiplier", "dino_harvesting_damage_multiplier",
        "disable_dino_decay_pve", "pvp_dino_decay",
        "dino_char_food_drain_multiplier", "dino_char_stamina_drain_multiplier",
        "dino_char_health_recovery_multiplier",
        "allow_raid_dino_feeding", "raid_dino_food_drain_multiplier",
        "allow_flying_stamina_recovery", "prevent_mate_boost",
        "auto_destroy_decayed_dinos", "pve_dino_decay_period_multiplier",
        "allow_multiple_attached_c4", "max_personal_tamed_dinos",
        "personal_tamed_dinos_saddle_structure_cost",
        "use_tame_limit_for_structures_only",
        "wild_dino_char_food_drain_multiplier", "tamed_dino_char_food_drain_multiplier",
        "wild_dino_torpor_drain_multiplier", "tamed_dino_torpor_drain_multiplier",
        "override_max_xp_dino", "dino_turret_damage_multiplier",
    ]),
    ("Reprodução", [
        "mating_interval_multiplier", "egg_hatch_speed_multiplier",
        "baby_mature_speed_multiplier", "baby_food_consumption_multiplier",
        "baby_cuddle_interval_multiplier", "baby_imprinting_stat_scale",
        "baby_cuddle_grace_period_multiplier",
        "baby_cuddle_lose_imprint_quality_speed_multiplier",
    ]),
    ("Meio Ambiente", [
        "harvest_amount_multiplier", "harvest_health_multiplier",
        "resources_respawn_multiplier",
        "day_cycle_speed_scale", "day_time_speed_scale", "night_time_speed_scale",
        "global_spoiling_time_multiplier",
        "global_item_decomposition_multiplier",
        "global_corpse_decomposition_multiplier",
        "crop_decay_speed_multiplier", "crop_growth_speed_multiplier",
        "hair_growth_speed_multiplier", "base_temperature_multiplier",
        "disable_weather_fog",
        "craft_xp_multiplier", "generic_xp_multiplier",
        "harvest_xp_multiplier", "kill_xp_multiplier", "special_xp_multiplier",
        "lay_egg_interval_multiplier", "poop_interval_multiplier",
        "resource_no_replenish_radius_players",
        "resource_no_replenish_radius_structures",
        "use_optimized_harvesting_health",
        "clamp_resource_harvest_damage", "clamp_item_spoiling_times",
    ]),
    ("Estruturas", [
        "structure_resistance_multiplier", "structure_damage_multiplier",
        "max_structures_in_range", "per_platform_max_structures_multiplier",
        "max_platform_saddle_structures",
        "enable_structure_decay_pve", "pve_structure_decay_period_multiplier",
        "pve_structure_decay_destruction_period",
        "auto_destroy_old_structures_multiplier", "force_all_structure_locking",
        "disable_structure_placement_collision",
        "limit_turrets_in_range", "limit_turrets_range", "limit_turrets_num",
        "pvp_structure_decay", "pvp_zone_structure_damage_multiplier",
        "structure_damage_repair_cooldown",
        "override_structure_platform_prevention",
        "flyer_platform_allow_unaligned_dino_basing",
        "pve_allow_structures_at_supply_drops",
        "only_auto_destroy_core_structures", "only_decay_unsnapped_core_structures",
        "fast_decay_unsnapped_core_structures", "destroy_unconnected_water_pipes",
        "enable_fast_decay_interval", "fast_decay_interval",
        "hard_limit_turrets_in_range", "passive_defenses_damage_riderless_dinos",
    ]),
    ("Extinção e Wilds", [
        "enable_extinction_event", "extinction_event_interval", "extinction_event_utc",
        "enable_auto_respawn_wild_dinos", "auto_respawn_wild_dinos_interval",
    ]),
    ("Engramas", [
        "only_allow_specified_engrams", "auto_unlock_all_engrams",
        "engram_entries_raw",
    ]),
    ("Progressões de Nível", [
        "per_level_player", "per_level_dino_wild", "per_level_dino_tamed",
        "per_level_dino_tamed_add", "per_level_dino_tamed_affinity",
        "player_level_stats_raw", "dino_level_stats_raw",
    ]),
    ("Subs. de Crafting", ["crafting_overrides_raw"]),
    ("Subs. de Stack", ["stack_size_overrides_raw"]),
    ("Subs. de Spawner", ["npc_spawn_overrides_raw"]),
    ("Supply Crates", ["supply_crate_overrides_raw"]),
    ("Impedir Transferências", ["prevent_transfer_raw"]),
    ("Custom GUS INI", ["custom_gus_ini_raw", "custom_ini_sections"]),
    ("Custom Game.ini", ["custom_game_ini_raw"]),
    ("Custom Engine.ini", ["custom_engine_ini_raw"]),
    ("PGM", ["pgm_enabled", "pgm_name", "pgm_terrain_string"]),
]


# ── Diálogo ────────────────────────────────────────────────────────────────────

class _ImportIniDialog(ctk.CTkToplevel):
    """Modal de importação e sincronização de configurações INI."""

    def __init__(self, parent: ctk.CTk, app: "ARKServerManagerApp", srv: AsmServerConfig):
        super().__init__(parent)
        self._app  = app
        self._srv  = srv
        self._tmp_cfg: AsmServerConfig | None = None
        self._theme = get_theme("tek")

        self.title("Importar / Sincronizar INI")
        self.geometry("880x680")
        self.minsize(700, 500)
        self.resizable(True, True)
        self.transient(parent)
        self.configure(fg_color=self._theme["bg"])

        # Variáveis de caminhos de arquivo
        self._gus_var  = tk.StringVar()
        self._game_var = tk.StringVar()

        # Pré-preenche com o diretório de instalação do servidor, se disponível
        if srv.install_dir:
            base = (
                Path(srv.install_dir)
                / "ShooterGame" / "Saved" / "Config" / "WindowsServer"
            )
            gus  = base / "GameUserSettings.ini"
            game = base / "Game.ini"
            if gus.exists():
                self._gus_var.set(str(gus))
            if game.exists():
                self._game_var.set(str(game))

        self._status_var = tk.StringVar(value="Aguardando arquivos…")
        self._cat_vars:  dict[str, tk.BooleanVar] = {}
        self._srv_vars:  dict[str, tk.BooleanVar] = {}
        self._sel_all_var = tk.BooleanVar(value=True)

        self._build_ui()

        self.after(100, self.lift)
        self.after(150, self.focus_force)

        # Auto-carrega se os arquivos já existem
        if self._gus_var.get() or self._game_var.get():
            self.after(300, self._load_files)

    # ── Construção da UI ──────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        th = self._theme
        sep = th["separator"]

        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # Barra de título
        self._build_titlebar()

        # Separador
        ctk.CTkFrame(self, height=1, fg_color=sep).grid(
            row=0, column=0, sticky="ews")

        # Área de conteúdo rolável
        scroll = ctk.CTkScrollableFrame(
            self, fg_color=th["bg"], corner_radius=0,
            scrollbar_button_color=sep,
        )
        scroll.grid(row=1, column=0, sticky="nsew")
        scroll.grid_columnconfigure(0, weight=1)

        r = 0
        r = self._build_file_section(scroll, r)
        r = self._build_categories_section(scroll, r)
        r = self._build_apply_section(scroll, r)
        r = self._build_sync_section(scroll, r)
        ctk.CTkFrame(scroll, height=24, fg_color="transparent").grid(
            row=r, column=0, sticky="ew")

    def _build_titlebar(self) -> None:
        th = self._theme
        tb = ctk.CTkFrame(self, fg_color=th["card_bg"], corner_radius=0, height=54)
        tb.grid(row=0, column=0, sticky="ew")
        tb.grid_propagate(False)
        tb.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            tb, text="📥  Importar / Sincronizar INI",
            font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"),
            text_color=th["accent"],
        ).grid(row=0, column=0, padx=16, pady=14, sticky="w")

        ctk.CTkLabel(
            tb, text=f"Servidor: {self._srv.name}",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=th["text_secondary"],
        ).grid(row=0, column=1, padx=0, pady=0, sticky="w")

        ctk.CTkButton(
            tb, text="✕", width=36, height=36, corner_radius=6,
            fg_color="transparent", hover_color=th["accent_muted_bg"],
            text_color=th["text_secondary"],
            command=self.destroy,
        ).grid(row=0, column=2, padx=12, pady=0, sticky="e")

    def _section_header(self, parent: ctk.CTkScrollableFrame,
                        row: int, text: str) -> int:
        th = self._theme
        f = ctk.CTkFrame(parent, fg_color=th["card_bg"], corner_radius=8)
        f.grid(row=row, column=0, sticky="ew", padx=16, pady=(12, 4))
        ctk.CTkLabel(
            f, text=text,
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            text_color=th["accent"],
        ).grid(row=0, column=0, padx=12, pady=8, sticky="w")
        return row + 1

    # ── Seção: Arquivos INI ───────────────────────────────────────────────────

    def _build_file_section(self, parent: ctk.CTkScrollableFrame, row: int) -> int:
        th = self._theme
        row = self._section_header(parent, row, "📁  Arquivos INI")

        card = ctk.CTkFrame(parent, fg_color=th["card_bg"], corner_radius=8)
        card.grid(row=row, column=0, sticky="ew", padx=16, pady=(0, 4))
        card.grid_columnconfigure(1, weight=1)
        row += 1

        font_lbl  = ctk.CTkFont(family="Segoe UI", size=11)
        font_mono = ctk.CTkFont(family="Consolas", size=10)

        for i, (lbl_text, path_var) in enumerate([
            ("GameUserSettings.ini", self._gus_var),
            ("Game.ini",             self._game_var),
        ]):
            ctk.CTkLabel(
                card, text=lbl_text, width=175, anchor="e",
                font=font_lbl, text_color=th["text_secondary"],
            ).grid(row=i, column=0, padx=(12, 6), pady=(8, 4), sticky="e")

            ctk.CTkEntry(
                card, textvariable=path_var,
                font=font_mono, height=30,
                fg_color=th["bg"],
                border_color=th["separator"],
                text_color=th["text_primary"],
            ).grid(row=i, column=1, padx=(0, 4), pady=(8, 4), sticky="ew")

            _var = path_var
            ctk.CTkButton(
                card, text="📂", width=34, height=30,
                fg_color=th["accent_muted_bg"], hover_color=th["accent_dark"],
                text_color=th["accent"], corner_radius=6,
                command=lambda v=_var, t=lbl_text: self._browse(v, t),
            ).grid(row=i, column=2, padx=(0, 12), pady=(8, 4))

        # Linha de botão + status
        btn_row = ctk.CTkFrame(card, fg_color="transparent")
        btn_row.grid(row=2, column=0, columnspan=3, sticky="ew", padx=12, pady=(4, 10))
        btn_row.grid_columnconfigure(0, weight=1)

        self._status_lbl = ctk.CTkLabel(
            btn_row, textvariable=self._status_var,
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=th["text_secondary"],
        )
        self._status_lbl.grid(row=0, column=0, sticky="w")

        ctk.CTkButton(
            btn_row, text="📂  Carregar", width=130, height=32,
            fg_color=th["accent_muted_bg"], hover_color=th["accent_dark"],
            text_color=th["accent"], corner_radius=6,
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            command=self._load_files,
        ).grid(row=0, column=1, sticky="e")

        return row

    # ── Seção: Categorias ─────────────────────────────────────────────────────

    def _build_categories_section(self, parent: ctk.CTkScrollableFrame,
                                   row: int) -> int:
        th = self._theme
        row = self._section_header(parent, row, "⚙️  Categorias a Importar / Sincronizar")

        card = ctk.CTkFrame(parent, fg_color=th["card_bg"], corner_radius=8)
        card.grid(row=row, column=0, sticky="ew", padx=16, pady=(0, 4))
        card.grid_columnconfigure(0, weight=1)
        card.grid_columnconfigure(1, weight=1)
        row += 1

        font_check = ctk.CTkFont(family="Segoe UI", size=11)

        # Linha "Selecionar Tudo" + contador
        sel_row = ctk.CTkFrame(card, fg_color="transparent")
        sel_row.grid(row=0, column=0, columnspan=2, sticky="ew", padx=12, pady=(8, 4))

        ctk.CTkCheckBox(
            sel_row, text="Selecionar Tudo",
            variable=self._sel_all_var,
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color=th["text_primary"],
            fg_color=th["accent"], hover_color=th["accent_hover"],
            border_color=th["separator"],
            command=self._on_select_all,
        ).pack(side="left")

        self._field_count_lbl = ctk.CTkLabel(
            sel_row, text="",
            font=ctk.CTkFont(family="Segoe UI", size=10),
            text_color=th["text_muted"],
        )
        self._field_count_lbl.pack(side="right", padx=8)

        # Checkboxes em 2 colunas
        for i, (cat_label, _) in enumerate(_CATEGORIES):
            var = tk.BooleanVar(value=True)
            self._cat_vars[cat_label] = var

            col = i % 2
            r   = (i // 2) + 1

            ctk.CTkCheckBox(
                card, text=cat_label, variable=var,
                font=font_check,
                text_color=th["text_primary"],
                fg_color=th["accent"], hover_color=th["accent_hover"],
                border_color=th["separator"],
                command=self._on_cat_changed,
            ).grid(row=r, column=col, sticky="w", padx=(16, 8), pady=2)

        # Padding inferior
        ctk.CTkFrame(card, height=8, fg_color="transparent").grid(
            row=(len(_CATEGORIES) // 2) + 2, column=0, columnspan=2, sticky="ew")

        return row

    # ── Seção: Aplicar ao servidor atual ──────────────────────────────────────

    def _build_apply_section(self, parent: ctk.CTkScrollableFrame,
                              row: int) -> int:
        th = self._theme
        row = self._section_header(parent, row, "✅  Aplicar neste servidor")

        card = ctk.CTkFrame(parent, fg_color=th["card_bg"], corner_radius=8)
        card.grid(row=row, column=0, sticky="ew", padx=16, pady=(0, 4))
        card.grid_columnconfigure(0, weight=1)
        row += 1

        ctk.CTkLabel(
            card,
            text=(
                f"Aplica as categorias selecionadas ao servidor \"{self._srv.name}\". "
                "Nome, portas, mapa e diretório de instalação são sempre preservados."
            ),
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=th["text_secondary"],
            wraplength=700, justify="left",
        ).grid(row=0, column=0, padx=12, pady=(10, 4), sticky="w")

        self._apply_btn = ctk.CTkButton(
            card, text="✅  Aplicar neste servidor",
            width=210, height=36,
            fg_color=th["accent_muted_bg"], hover_color=th["accent_dark"],
            text_color=th["accent"],
            border_width=1, border_color=th["accent_dark"],
            corner_radius=8,
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            state="disabled",
            command=self._apply_to_current,
        )
        self._apply_btn.grid(row=1, column=0, padx=12, pady=(4, 12), sticky="e")

        return row

    # ── Seção: Sincronizar para outros servidores ──────────────────────────────

    def _build_sync_section(self, parent: ctk.CTkScrollableFrame,
                             row: int) -> int:
        th = self._theme
        row = self._section_header(parent, row, "🔄  Sincronizar para outros servidores")

        card = ctk.CTkFrame(parent, fg_color=th["card_bg"], corner_radius=8)
        card.grid(row=row, column=0, sticky="ew", padx=16, pady=(0, 4))
        card.grid_columnconfigure(0, weight=1)
        row += 1

        other_servers = [
            s for s in self._app.asm_config_manager.servers
            if s.id != self._srv.id
        ]

        if not other_servers:
            ctk.CTkLabel(
                card,
                text="Nenhum outro servidor gerenciado. Adicione servidores no Dashboard.",
                font=ctk.CTkFont(family="Segoe UI", size=11),
                text_color=th["text_muted"],
            ).grid(row=0, column=0, padx=12, pady=12, sticky="w")
        else:
            ctk.CTkLabel(
                card,
                text=(
                    "Selecione os servidores destino. "
                    "As categorias marcadas acima sobrescreverão os campos correspondentes."
                ),
                font=ctk.CTkFont(family="Segoe UI", size=11),
                text_color=th["text_secondary"],
                wraplength=700, justify="left",
            ).grid(row=0, column=0, padx=12, pady=(10, 4), sticky="w")

            srv_grid = ctk.CTkFrame(card, fg_color="transparent")
            srv_grid.grid(row=1, column=0, sticky="ew", padx=12, pady=4)
            for i, s in enumerate(other_servers):
                var = tk.BooleanVar(value=False)
                self._srv_vars[s.id] = var
                col = i % 3
                r   = i // 3
                ctk.CTkCheckBox(
                    srv_grid, text=s.name, variable=var,
                    font=ctk.CTkFont(family="Segoe UI", size=11),
                    text_color=th["text_primary"],
                    fg_color=th["accent"], hover_color=th["accent_hover"],
                    border_color=th["separator"],
                ).grid(row=r, column=col, sticky="w", padx=(0, 24), pady=2)

        self._sync_btn = ctk.CTkButton(
            card, text="🔄  Sincronizar selecionados",
            width=230, height=36,
            fg_color=th["accent_muted_bg"], hover_color=th["accent_dark"],
            text_color=th["accent"],
            border_width=1, border_color=th["accent_dark"],
            corner_radius=8,
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            state="disabled",
            command=self._sync_to_destinations,
        )
        self._sync_btn.grid(row=99, column=0, padx=12, pady=(4, 12), sticky="e")

        return row

    # ── Ações ─────────────────────────────────────────────────────────────────

    def _browse(self, var: tk.StringVar, title: str) -> None:
        path = filedialog.askopenfilename(
            parent=self,
            title=f"Selecionar {title}",
            filetypes=[("INI files", "*.ini"), ("All files", "*.*")],
        )
        if path:
            var.set(path)

    def _load_files(self) -> None:
        gus  = self._gus_var.get().strip()
        game = self._game_var.get().strip()

        if not gus and not game:
            self._status_var.set("⚠  Selecione pelo menos um arquivo .ini")
            self._status_lbl.configure(text_color="#f59e0b")
            return

        # Cria config temporária como cópia do servidor atual
        tmp = copy.deepcopy(self._srv)

        try:
            read_ini_from_paths(
                tmp,
                gus_path=gus  or None,
                game_path=game or None,
            )
            self._tmp_cfg = tmp

            count = self._count_importable_fields()
            self._status_var.set(f"✅  Arquivos carregados — {count} campos disponíveis")
            self._status_lbl.configure(text_color=self._theme["accent"])
            self._field_count_lbl.configure(text=f"{count} campos")

            # Habilita botões de ação
            self._apply_btn.configure(state="normal")
            self._sync_btn.configure(state="normal")

        except Exception as exc:
            self._status_var.set(f"❌  Erro: {exc}")
            self._status_lbl.configure(text_color="#ef4444")

    def _count_importable_fields(self) -> int:
        """Conta campos importáveis (todos os campos das categorias, excluindo excluídos)."""
        seen: set[str] = set()
        for _, fields in _CATEGORIES:
            for f in fields:
                if f not in _EXCLUDED_FIELDS:
                    seen.add(f)
        return len(seen)

    def _on_select_all(self) -> None:
        val = self._sel_all_var.get()
        for var in self._cat_vars.values():
            var.set(val)

    def _on_cat_changed(self) -> None:
        all_checked = all(v.get() for v in self._cat_vars.values())
        self._sel_all_var.set(all_checked)

    def _get_selected_categories(self) -> list[str]:
        return [cat for cat, var in self._cat_vars.items() if var.get()]

    def _apply_categories_to(
        self,
        source: AsmServerConfig,
        target: AsmServerConfig,
        selected_cats: list[str],
    ) -> int:
        """Copia campos das categorias selecionadas de source para target.
        Retorna a contagem de campos copiados.
        """
        count = 0
        for cat_label, fields in _CATEGORIES:
            if cat_label not in selected_cats:
                continue
            for field_name in fields:
                if field_name in _EXCLUDED_FIELDS:
                    continue
                if not hasattr(source, field_name) or not hasattr(target, field_name):
                    continue
                val = getattr(source, field_name)
                if isinstance(val, list):
                    val = copy.deepcopy(val)
                setattr(target, field_name, val)
                count += 1
        return count

    def _apply_to_current(self) -> None:
        if self._tmp_cfg is None:
            return
        selected = self._get_selected_categories()
        if not selected:
            messagebox.showwarning(
                "Aviso", "Selecione pelo menos uma categoria.", parent=self)
            return

        count = self._apply_categories_to(self._tmp_cfg, self._srv, selected)
        self._app.asm_config_manager.update_server(self._srv)
        self.destroy()
        self._app._asm_open_server_panel(self._srv.id)
        messagebox.showinfo(
            "Importação concluída",
            f"✅  {count} campos aplicados ao servidor \"{self._srv.name}\".\n\n"
            "O painel foi atualizado com as novas configurações.\n"
            "Verifique e salve para gravar nos arquivos .ini do servidor.",
            parent=self._app,
        )

    def _sync_to_destinations(self) -> None:
        if self._tmp_cfg is None:
            return
        selected_cats = self._get_selected_categories()
        if not selected_cats:
            messagebox.showwarning(
                "Aviso", "Selecione pelo menos uma categoria.", parent=self)
            return

        dest_ids = [sid for sid, var in self._srv_vars.items() if var.get()]
        if not dest_ids:
            messagebox.showwarning(
                "Aviso", "Selecione pelo menos um servidor destino.", parent=self)
            return

        srv_map = {s.id: s for s in self._app.asm_config_manager.servers}
        total   = 0
        synced: list[str] = []

        for sid in dest_ids:
            target = srv_map.get(sid)
            if target:
                n = self._apply_categories_to(self._tmp_cfg, target, selected_cats)
                total  += n
                synced.append(target.name)
                self._app.asm_config_manager.update_server(target)

        if synced:
            self.destroy()
            messagebox.showinfo(
                "Sincronização concluída",
                f"✅  {total} campos sincronizados para {len(synced)} servidor(es):\n\n"
                + "\n".join(f"  • {n}" for n in synced)
                + "\n\nAcesse cada servidor e salve para gravar nos arquivos .ini.",
                parent=self._app,
            )


# ── Ponto de entrada (singleton por servidor) ──────────────────────────────────

def open_asm_import_ini_dialog(
    app: "ARKServerManagerApp",
    srv: AsmServerConfig,
) -> None:
    """Abre o diálogo de importação/sincronização de INI (singleton por servidor)."""
    key = f"_asm_import_ini_{srv.id}"
    win: _ImportIniDialog | None = getattr(app, key, None)
    if win and win.winfo_exists():
        win.lift()
        win.focus_force()
        return

    win = _ImportIniDialog(app, app, srv)
    setattr(app, key, win)
    win.protocol("WM_DELETE_WINDOW", lambda: (win.destroy(), setattr(app, key, None)))
