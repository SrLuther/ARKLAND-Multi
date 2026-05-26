"""
TEK — Painel de configuração de um servidor ASM.
Container das abas (Administration, Rules, Players, Dinos, etc.)
"""
from __future__ import annotations

import tkinter as tk
from typing import TYPE_CHECKING
import customtkinter as ctk  # type: ignore[reportMissingImports]

from ..asm_engine.asm_server_config import AsmServerConfig
from ..ui_constants import get_theme

if TYPE_CHECKING:
    from ..app import ARKServerManagerApp


def build_asm_server_panel(app: "ARKServerManagerApp",
                           parent: ctk.CTkFrame,
                           srv: AsmServerConfig) -> None:
    """Constrói o painel de configuração TEK dentro de `parent`."""
    theme = get_theme("tek")
    accent  = theme["accent"]
    bg      = theme["bg"]
    card_bg = theme["card_bg"]
    tab_bg  = theme["tab_bar_bg"]

    parent.grid_columnconfigure(0, weight=1)
    parent.grid_rowconfigure(0, weight=0)   # header
    parent.grid_rowconfigure(1, weight=1)   # tabview

    # ── Header ────────────────────────────────────────────────────────────────
    hdr = ctk.CTkFrame(parent, fg_color=card_bg, corner_radius=0, height=52)
    hdr.grid(row=0, column=0, sticky="ew")
    hdr.grid_propagate(False)
    hdr.grid_columnconfigure(1, weight=1)

    ctk.CTkButton(hdr, text="◀ Dashboard", width=110, height=30,
                  fg_color="transparent", hover_color=tab_bg,
                  text_color=accent,
                  command=lambda: app._show_frame("dashboard")).grid(
        row=0, column=0, padx=(12, 0), pady=10, sticky="w")

    ctk.CTkLabel(hdr, text=srv.name,
                 font=ctk.CTkFont(size=14, weight="bold"),
                 text_color="#e0f4f8").grid(row=0, column=1, padx=8, pady=10, sticky="w")

    ctk.CTkButton(hdr, text="💾 Salvar", width=100, height=30,
                  fg_color="#0a4450", hover_color="#085a68",
                  border_width=1, border_color=accent, text_color=accent,
                  command=lambda: _save(app, srv)).grid(
        row=0, column=2, padx=(0, 12), pady=10, sticky="e")

    # ── TabView ───────────────────────────────────────────────────────────────
    tabs = ctk.CTkTabview(parent, fg_color=bg, segmented_button_fg_color=tab_bg,
                          segmented_button_selected_color="#094f5c",
                          segmented_button_selected_hover_color="#1a7080",
                          segmented_button_unselected_color=tab_bg,
                          segmented_button_unselected_hover_color=card_bg)
    tabs.grid(row=1, column=0, sticky="nsew", padx=8, pady=(4, 8))

    # Registra referência para salvar
    app._asm_panel_vars = app._asm_panel_vars if hasattr(app, "_asm_panel_vars") else {}
    app._asm_panel_vars[srv.id] = {}
    vars_ref = app._asm_panel_vars[srv.id]

    for tab_name in ("Administration", "Rules", "Players", "Dinos",
                     "Environment", "Structures", "Chat/HUD", "Custom INI"):
        tabs.add(tab_name)

    _build_tab_administration(tabs.tab("Administration"), srv, vars_ref, bg, accent)
    _build_tab_rules(tabs.tab("Rules"), srv, vars_ref, bg, accent)
    _build_tab_multipliers(tabs.tab("Players"), srv, vars_ref, bg, accent, "players")
    _build_tab_multipliers(tabs.tab("Dinos"), srv, vars_ref, bg, accent, "dinos")
    _build_tab_multipliers(tabs.tab("Environment"), srv, vars_ref, bg, accent, "environment")
    _build_tab_multipliers(tabs.tab("Structures"), srv, vars_ref, bg, accent, "structures")
    _build_tab_chat_hud(tabs.tab("Chat/HUD"), srv, vars_ref, bg, accent)
    _build_tab_custom_ini(tabs.tab("Custom INI"), srv, vars_ref, bg, accent)


# ── Helpers de campo ──────────────────────────────────────────────────────────

def _str_entry(parent, label: str, field: str, srv: AsmServerConfig,
               vars_ref: dict, row: int, accent: str,
               wide: bool = False, pw: bool = False) -> None:
    ctk.CTkLabel(parent, text=label, font=ctk.CTkFont(size=11),
                 anchor="w").grid(row=row, column=0, padx=(8, 4), pady=3, sticky="w")
    v = tk.StringVar(value=str(getattr(srv, field, "")))
    vars_ref[field] = v
    e = ctk.CTkEntry(parent, textvariable=v, show="*" if pw else "",
                     width=300 if wide else 200)
    e.grid(row=row, column=1, padx=(0, 8), pady=3, sticky="ew" if wide else "w")


def _int_entry(parent, label: str, field: str, srv: AsmServerConfig,
               vars_ref: dict, row: int) -> None:
    ctk.CTkLabel(parent, text=label, font=ctk.CTkFont(size=11),
                 anchor="w").grid(row=row, column=0, padx=(8, 4), pady=3, sticky="w")
    v = tk.StringVar(value=str(getattr(srv, field, 0)))
    vars_ref[field] = v
    ctk.CTkEntry(parent, textvariable=v, width=100).grid(
        row=row, column=1, padx=(0, 8), pady=3, sticky="w")


def _float_entry(parent, label: str, field: str, srv: AsmServerConfig,
                 vars_ref: dict, row: int) -> None:
    ctk.CTkLabel(parent, text=label, font=ctk.CTkFont(size=11),
                 anchor="w").grid(row=row, column=0, padx=(8, 4), pady=3, sticky="w")
    v = tk.StringVar(value=str(getattr(srv, field, 1.0)))
    vars_ref[field] = v
    ctk.CTkEntry(parent, textvariable=v, width=100).grid(
        row=row, column=1, padx=(0, 8), pady=3, sticky="w")


def _bool_check(parent, label: str, field: str, srv: AsmServerConfig,
                vars_ref: dict, row: int, accent: str, col: int = 0) -> None:
    v = tk.BooleanVar(value=bool(getattr(srv, field, False)))
    vars_ref[field] = v
    ctk.CTkCheckBox(parent, text=label, variable=v,
                    checkmark_color=accent, border_color=accent,
                    font=ctk.CTkFont(size=11)).grid(
        row=row, column=col, columnspan=2, padx=(8, 4), pady=3, sticky="w")


def _section_label(parent, text: str, row: int, accent: str) -> None:
    ctk.CTkLabel(parent, text=text,
                 font=ctk.CTkFont(size=12, weight="bold"),
                 text_color=accent).grid(
        row=row, column=0, columnspan=2, padx=8, pady=(10, 2), sticky="w")


def _scrollable_tab(tab) -> ctk.CTkScrollableFrame:
    tab.grid_columnconfigure(0, weight=1)
    tab.grid_rowconfigure(0, weight=1)
    sf = ctk.CTkScrollableFrame(tab, fg_color="transparent", corner_radius=0)
    sf.grid(row=0, column=0, sticky="nsew")
    sf.grid_columnconfigure(1, weight=1)
    return sf


# ── Aba Administration ────────────────────────────────────────────────────────

def _build_tab_administration(tab, srv: AsmServerConfig, vars_ref: dict,
                               bg: str, accent: str) -> None:
    sf = _scrollable_tab(tab)

    _section_label(sf, "Sessão",         0,  accent)
    _str_entry(sf, "Nome no gerenciador",  "name",            srv, vars_ref,  1, accent, wide=True)
    _str_entry(sf, "Nome da sessão",       "session_name",    srv, vars_ref,  2, accent, wide=True)
    _str_entry(sf, "Pasta de instalação",  "install_dir",     srv, vars_ref,  3, accent, wide=True)
    _str_entry(sf, "Mapa",                 "server_map",      srv, vars_ref,  4, accent)

    _section_label(sf, "Rede",             5,  accent)
    _int_entry(sf,   "Porta (game)",        "server_port",     srv, vars_ref,  6)
    _int_entry(sf,   "Porta (query)",       "query_port",      srv, vars_ref,  7)
    _int_entry(sf,   "Max jogadores",       "max_players",     srv, vars_ref,  8)
    _str_entry(sf,   "IP (MultiHome)",      "server_ip",       srv, vars_ref,  9, accent)

    _section_label(sf, "Senhas",           10, accent)
    _str_entry(sf,  "Senha do servidor",    "server_password", srv, vars_ref, 11, accent, pw=True)
    _str_entry(sf,  "Senha de admin",       "admin_password",  srv, vars_ref, 12, accent, pw=True)
    _str_entry(sf,  "Senha spectator",      "spectator_password", srv, vars_ref, 13, accent, pw=True)

    _section_label(sf, "RCON",             14, accent)
    _bool_check(sf,  "Habilitar RCON",      "rcon_enabled",    srv, vars_ref, 15, accent)
    _int_entry(sf,   "Porta RCON",          "rcon_port",       srv, vars_ref, 16)

    _section_label(sf, "Saves / Misc",     17, accent)
    _float_entry(sf, "Auto-save (min)",     "auto_save_period", srv, vars_ref, 18)
    _str_entry(sf,   "Alt Save Directory",  "alt_save_directory_name", srv, vars_ref, 19, accent)
    _str_entry(sf,   "Cluster ID",          "cross_ark_cluster_id", srv, vars_ref, 20, accent)
    _str_entry(sf,   "Args adicionais",     "additional_args", srv, vars_ref, 21, accent, wide=True)

    _section_label(sf, "Mods (IDs, um por linha)", 22, accent)
    sf.grid_rowconfigure(23, weight=1)
    mods_text = ctk.CTkTextbox(sf, height=80, font=ctk.CTkFont(size=11))
    mods_text.grid(row=23, column=0, columnspan=2, padx=8, pady=3, sticky="ew")
    mods_text.insert("1.0", "\n".join(srv.active_mods))
    vars_ref["_mods_text"] = mods_text


# ── Aba Rules ─────────────────────────────────────────────────────────────────

def _build_tab_rules(tab, srv: AsmServerConfig, vars_ref: dict,
                     bg: str, accent: str) -> None:
    sf = _scrollable_tab(tab)

    _section_label(sf, "Modo de jogo",          0, accent)
    _bool_check(sf, "PvP habilitado",            "enable_pvp",             srv, vars_ref,  1, accent)
    _bool_check(sf, "Hardcore",                  "enable_hardcore",         srv, vars_ref,  2, accent)
    _bool_check(sf, "Construção em caverna (PvE)","allow_cave_building_pve", srv, vars_ref,  3, accent)

    _section_label(sf, "Dificuldade",            4, accent)
    _bool_check(sf, "Override dificuldade oficial","enable_difficulty_override", srv, vars_ref, 5, accent)
    _float_entry(sf, "OverrideOfficialDifficulty","override_official_difficulty", srv, vars_ref, 6)
    _float_entry(sf, "DifficultyOffset",          "difficulty_offset",     srv, vars_ref,  7)

    _section_label(sf, "Transfers / Tributo",    8, accent)
    _bool_check(sf, "Permitir downloads tributo", "enable_tribute_downloads", srv, vars_ref, 9, accent)
    _bool_check(sf, "Bloquear download survivors","prevent_download_survivors", srv, vars_ref,10, accent)
    _bool_check(sf, "Bloquear download items",    "prevent_download_items",  srv, vars_ref, 11, accent)
    _bool_check(sf, "Bloquear download dinos",    "prevent_download_dinos",  srv, vars_ref, 12, accent)
    _bool_check(sf, "Bloquear upload survivors",  "prevent_upload_survivors", srv, vars_ref,13, accent)
    _bool_check(sf, "Bloquear upload items",      "prevent_upload_items",   srv, vars_ref, 14, accent)
    _bool_check(sf, "Bloquear upload dinos",      "prevent_upload_dinos",   srv, vars_ref, 15, accent)

    _section_label(sf, "Tribos / Doenças",       16, accent)
    _int_entry(sf,  "Max membros na tribo",       "max_tribe_size",         srv, vars_ref, 17)
    _bool_check(sf, "Alianças entre tribos",      "allow_tribe_alliances",  srv, vars_ref, 18, accent)
    _bool_check(sf, "Doenças habilitadas",        "enable_diseases",        srv, vars_ref, 19, accent)
    _bool_check(sf, "Prevenir PvP offline",       "prevent_pvp_offline",    srv, vars_ref, 20, accent)
    _bool_check(sf, "Gamma PvP",                  "allow_pvp_gamma",        srv, vars_ref, 21, accent)
    _bool_check(sf, "Receitas customizadas",      "allow_custom_recipes",   srv, vars_ref, 22, accent)


# ── Aba Multipliers genérica ──────────────────────────────────────────────────

_MULT_FIELDS: dict[str, list[tuple]] = {
    "players": [
        ("XP Multiplier",                   "xp_multiplier"),
        ("Player Damage",                   "player_damage_multiplier"),
        ("Player Resistance",               "player_resistance_multiplier"),
        ("Water Drain",                     "player_water_drain_multiplier"),
        ("Food Drain",                      "player_food_drain_multiplier"),
        ("Stamina Drain",                   "player_stamina_drain_multiplier"),
        ("Health Recovery",                 "player_health_recovery_multiplier"),
        ("Harvesting Damage",               "player_harvesting_damage_multiplier"),
        ("Crafting Skill Bonus",            "crafting_skill_bonus_multiplier"),
    ],
    "dinos": [
        ("Dino Damage",                     "dino_damage_multiplier"),
        ("Tamed Dino Damage",               "tamed_dino_damage_multiplier"),
        ("Dino Resistance",                 "dino_resistance_multiplier"),
        ("Tamed Dino Resistance",           "tamed_dino_resistance_multiplier"),
        ("Max Tamed Dinos",                 "max_tamed_dinos"),
        ("Dino Count",                      "dino_count_multiplier"),
        ("Taming Speed",                    "taming_speed_multiplier"),
        ("Mating Interval",                 "mating_interval_multiplier"),
        ("Egg Hatch Speed",                 "egg_hatch_speed_multiplier"),
        ("Baby Mature Speed",               "baby_mature_speed_multiplier"),
        ("Baby Food Consumption",           "baby_food_consumption_multiplier"),
        ("Baby Cuddle Interval",            "baby_cuddle_interval_multiplier"),
        ("Baby Imprinting Stat Scale",      "baby_imprinting_stat_scale"),
        ("Passive Tame Interval",           "passive_tame_interval_multiplier"),
        ("Dino Harvesting Damage",          "dino_harvesting_damage_multiplier"),
    ],
    "environment": [
        ("Harvest Amount",                  "harvest_amount_multiplier"),
        ("Harvest Health",                  "harvest_health_multiplier"),
        ("Resources Respawn",               "resources_respawn_multiplier"),
        ("Day Cycle Speed",                 "day_cycle_speed_scale"),
        ("Day Time Speed",                  "day_time_speed_scale"),
        ("Night Time Speed",                "night_time_speed_scale"),
        ("Global Spoiling Time",            "global_spoiling_time_multiplier"),
        ("Item Decomposition Time",         "global_item_decomposition_multiplier"),
        ("Corpse Decomposition Time",       "global_corpse_decomposition_multiplier"),
        ("Crop Decay Speed",                "crop_decay_speed_multiplier"),
        ("Crop Growth Speed",               "crop_growth_speed_multiplier"),
        ("Hair Growth Speed",               "hair_growth_speed_multiplier"),
        ("Base Temperature",                "base_temperature_multiplier"),
    ],
    "structures": [
        ("Structure Resistance",            "structure_resistance_multiplier"),
        ("Structure Damage",                "structure_damage_multiplier"),
        ("Max Structures In Range",         "max_structures_in_range"),
        ("Per Platform Max Structures",     "per_platform_max_structures_multiplier"),
        ("Max Platform Saddle Structures",  "max_platform_saddle_structures"),
        ("PvE Structure Decay Period",      "pve_structure_decay_period_multiplier"),
        ("PvE Structure Decay Destruction", "pve_structure_decay_destruction_period"),
        ("Auto Destroy Old Structures",     "auto_destroy_old_structures_multiplier"),
        ("Turrets Range",                   "limit_turrets_range"),
        ("Turrets Num",                     "limit_turrets_num"),
    ],
}

_BOOL_FIELDS: dict[str, list[tuple]] = {
    "dinos": [
        ("Disable Imprint Buff",            "disable_imprint_buff"),
        ("Allow Anyone Baby Imprint",       "allow_anyone_baby_imprint"),
        ("Disable Dino Riding",             "disable_dino_riding"),
        ("Disable Dino Taming",             "disable_dino_taming"),
        ("Allow Cave Flyers",               "allow_cave_flyers"),
        ("Disable Dino Decay PvE",          "disable_dino_decay_pve"),
        ("Enable Flyer Carry PvE",          "enable_flyer_carry"),
    ],
    "environment": [
        ("Disable Weather Fog",             "disable_weather_fog"),
    ],
    "structures": [
        ("Enable Structure Decay PvE",      "enable_structure_decay_pve"),
        ("Force All Structure Locking",     "force_all_structure_locking"),
        ("Disable Structure Placement Collision", "disable_structure_placement_collision"),
        ("Limit Turrets In Range",          "limit_turrets_in_range"),
    ],
    "players": [
        ("Allow Flyer Carry PvE",           "enable_flyer_carry"),
    ],
}


def _build_tab_multipliers(tab, srv: AsmServerConfig, vars_ref: dict,
                            bg: str, accent: str, group: str) -> None:
    sf = _scrollable_tab(tab)

    r = 0
    for label, field in _MULT_FIELDS.get(group, []):
        val = getattr(srv, field, None)
        if isinstance(val, bool):
            _bool_check(sf, label, field, srv, vars_ref, r, accent)
        elif isinstance(val, int):
            _int_entry(sf, label, field, srv, vars_ref, r)
        else:
            _float_entry(sf, label, field, srv, vars_ref, r)
        r += 1

    bools = _BOOL_FIELDS.get(group, [])
    if bools:
        _section_label(sf, "Opções", r, accent)
        r += 1
        for label, field in bools:
            _bool_check(sf, label, field, srv, vars_ref, r, accent)
            r += 1


# ── Aba Chat / HUD ─────────────────────────────────────────────────────────────

def _build_tab_chat_hud(tab, srv: AsmServerConfig, vars_ref: dict,
                         bg: str, accent: str) -> None:
    sf = _scrollable_tab(tab)

    _section_label(sf, "Chat",                   0, accent)
    _bool_check(sf, "Voice chat global",          "global_voice_chat",          srv, vars_ref, 1, accent)
    _bool_check(sf, "Proximity chat",             "proximity_chat",             srv, vars_ref, 2, accent)
    _bool_check(sf, "Notificar entrada (join)",   "player_joined_notifications", srv, vars_ref, 3, accent)
    _bool_check(sf, "Notificar saída (leave)",    "player_leave_notifications", srv, vars_ref, 4, accent)

    _section_label(sf, "HUD / Visual",           5, accent)
    _bool_check(sf, "Crosshair",                  "allow_crosshair",            srv, vars_ref, 6, accent)
    _bool_check(sf, "HUD habilitado",             "allow_hud",                  srv, vars_ref, 7, accent)
    _bool_check(sf, "Terceira pessoa",            "allow_third_person_view",    srv, vars_ref, 8, accent)
    _bool_check(sf, "Mostrar posição no mapa",   "show_map_player_location",   srv, vars_ref, 9, accent)
    _bool_check(sf, "Floating damage text",       "show_floating_damage_text",  srv, vars_ref,10, accent)
    _bool_check(sf, "Hit markers",                "allow_hit_markers",          srv, vars_ref,11, accent)


# ── Aba Custom INI ─────────────────────────────────────────────────────────────

def _build_tab_custom_ini(tab, srv: AsmServerConfig, vars_ref: dict,
                           bg: str, accent: str) -> None:
    tab.grid_columnconfigure(0, weight=1)
    tab.grid_rowconfigure(1, weight=1)

    ctk.CTkLabel(tab, text="Conteúdo injetado direto no GameUserSettings.ini:",
                 font=ctk.CTkFont(size=11), text_color="#7ab8c8").grid(
        row=0, column=0, padx=8, pady=(8, 2), sticky="w")

    gus_box = ctk.CTkTextbox(tab, font=ctk.CTkFont(family="Consolas", size=11))
    gus_box.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0, 8))

    # Preenche com seções existentes
    for sec in srv.custom_ini_sections:
        if sec.get("file", "GUS").upper() in ("GUS", "GAMEUSERSETTINGS.INI"):
            gus_box.insert("end", f"[{sec.get('section','')}]\n")
            for e in sec.get("entries", []):
                gus_box.insert("end", f"{e['key']}={e['value']}\n")
            gus_box.insert("end", "\n")

    vars_ref["_custom_ini_text"] = gus_box


# ── Salvar ─────────────────────────────────────────────────────────────────────

def _save(app: "ARKServerManagerApp", srv: AsmServerConfig) -> None:
    """Lê os vars_ref e persiste o AsmServerConfig."""
    vars_ref = getattr(app, "_asm_panel_vars", {}).get(srv.id, {})

    from dataclasses import fields as _fields
    field_types = {f.name: f.type for f in _fields(AsmServerConfig)}

    for field_name, var in vars_ref.items():
        if field_name.startswith("_"):
            continue
        ftype = field_types.get(field_name)
        try:
            raw = var.get()
            if ftype in ("bool", bool) or str(ftype) == "bool":
                setattr(srv, field_name, bool(raw))
            elif ftype in ("int", int) or str(ftype) == "int":
                setattr(srv, field_name, int(float(raw)))
            elif ftype in ("float", float) or str(ftype) == "float":
                setattr(srv, field_name, float(raw))
            else:
                setattr(srv, field_name, str(raw))
        except Exception:
            pass

    # Mods da caixa de texto
    mods_box = vars_ref.get("_mods_text")
    if mods_box:
        lines = mods_box.get("1.0", "end").strip().splitlines()
        srv.active_mods = [l.strip() for l in lines if l.strip()]

    app.asm_config_manager.update_server(srv)

    import customtkinter as ctk2
    msg = ctk2.CTkToplevel(app)
    msg.title("Salvo")
    msg.geometry("260x90")
    msg.grab_set()
    ctk2.CTkLabel(msg, text="✅  Configurações salvas!",
                  font=ctk2.CTkFont(size=13)).pack(expand=True)
    app.after(1200, msg.destroy)
