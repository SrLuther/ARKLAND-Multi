from __future__ import annotations

import os
import re
import time
import threading
import tkinter as tk
from typing import TYPE_CHECKING

import customtkinter as ctk  # type: ignore[reportMissingImports]

from ..server_config import ARK_MAPS, ARK_MAP_NAMES
from ..ui_constants import (
    _GREEN, _GREEN_DARK, _GREEN_HOVER,
    _BLUE, _BLUE_HOVER,
    _CARD_BG, _BG,
    _FORM_FONT_BOLD, _FORM_FONT_HINT, _FORM_LABEL_FG, _FORM_HINT_FG,
    _ARK_OFFICIAL_EVENTS, _ARK_EVENT_ID_TO_LABEL,
)

if TYPE_CHECKING:
    from ..app import ARKServerManagerApp
    from ..server_config import ServerConfig


def build_tab_general(app: "ARKServerManagerApp", parent, srv: "ServerConfig") -> None:  # noqa: C901
    # ── Barra de salvar fixada no topo ────────────────────────────────────
    save_bar = tk.Frame(parent, bg=_BG, height=52)
    save_bar.pack(side="top", fill="x")
    save_bar.pack_propagate(False)
    ctk.CTkButton(
        save_bar, text="💾  Salvar & Aplicar Configurações",
        height=36, font=ctk.CTkFont(size=13, weight="bold"),
        fg_color=_GREEN_DARK, hover_color=_GREEN_HOVER,
        command=lambda: app._save_server_config(srv.id),
    ).pack(side="left", padx=(16, 0), pady=8)
    ctk.CTkButton(
        save_bar, text="⬆️  Importar INI do Disco",
        height=36, width=190, fg_color=_BLUE, hover_color=_BLUE_HOVER,
        command=lambda: app._import_ini_from_disk(srv.id),
    ).pack(side="left", padx=(10, 0), pady=8)
    ctk.CTkButton(
        save_bar, text="🔄  Sincronizar INI",
        height=36, width=160, fg_color="#6a3aaa", hover_color="#7a4abb",
        command=lambda: app._open_sync_ini_dialog(srv.id),
    ).pack(side="left", padx=(10, 0), pady=8)
    ctk.CTkButton(
        save_bar, text="📋  Clonar Configurações",
        height=36, width=190, fg_color="#3a5a2a", hover_color="#4a6a3a",
        command=lambda: app._open_clone_config_dialog(srv.id),
    ).pack(side="left", padx=(10, 0), pady=8)

    # ── Scroll 2 colunas ──────────────────────────────────────────────────
    scroll = ctk.CTkScrollableFrame(parent, fg_color=_CARD_BG)
    scroll.pack(fill="both", expand=True, padx=4, pady=4)
    scroll.grid_columnconfigure(0, weight=1, uniform="gcol")
    scroll.grid_columnconfigure(1, weight=1, uniform="gcol")
    # Suspende o recálculo de scrollregion durante o build (elimina O(n²))
    scroll.unbind("<Configure>")

    w = app._server_widgets[srv.id]
    _INNER = "#16162a"

    def _make_card(col: int, grow: int, colspan: int = 1) -> tk.Frame:
        c = tk.Frame(scroll, bg=_INNER,
                     highlightthickness=1, highlightbackground="#2a2a45")
        c.grid(row=grow, column=col, columnspan=colspan,
               padx=8, pady=6, sticky="new")
        c.columnconfigure(0, weight=1)
        return c

    def _head(cnt: tk.Frame, text: str) -> None:
        tk.Label(cnt, text=text, bg=_INNER, fg="#c8c8e8",
                 font=ctk.CTkFont(size=12, weight="bold"),
                 anchor="w").pack(fill="x", padx=10, pady=(8, 2))
        tk.Frame(cnt, bg=_GREEN, height=1).pack(fill="x", padx=10, pady=(0, 6))

    def _fld(cnt: tk.Frame, label: str, hint: str, var,
             is_pass: bool = False, browse: bool = False,
             combo: Optional[List] = None) -> None:
        app._register_config_item(srv.id, label.rstrip(": "), hint, "Geral")
        fr = tk.Frame(cnt, bg=_INNER)
        fr.pack(fill="x", padx=10, pady=(0, 4))
        fr.columnconfigure(0, weight=1)
        tk.Label(fr, text=label, anchor="w", bg=_INNER,
                 fg=_FORM_LABEL_FG, font=_FORM_FONT_BOLD).grid(row=0, column=0, sticky="w")
        if combo:
            ctk.CTkComboBox(fr, variable=var, values=combo, height=34).grid(
                row=1, column=0, sticky="ew", pady=(2, 0))
        elif browse:
            bf = tk.Frame(fr, bg=_INNER)
            bf.grid(row=1, column=0, sticky="ew", pady=(2, 0))
            bf.columnconfigure(0, weight=1)
            ctk.CTkEntry(bf, textvariable=var, height=34).grid(
                row=0, column=0, sticky="ew", padx=(0, 6))
            ctk.CTkButton(bf, text="📁", width=34, height=34,
                          command=lambda v=var: app._browse_dir(v)).grid(row=0, column=1)
        else:
            ctk.CTkEntry(fr, textvariable=var, height=34,
                         show="*" if is_pass else "").grid(
                row=1, column=0, sticky="ew", pady=(2, 0))
        if hint:
            tk.Label(fr, text=hint, anchor="w", bg=_INNER, fg=_FORM_HINT_FG,
                     font=_FORM_FONT_HINT, justify="left").grid(
                row=2, column=0, sticky="w", pady=(1, 2))

    def _chk(cnt: tk.Frame, label: str, hint: str, var) -> None:
        app._register_config_item(srv.id, label, hint, "Geral")
        fr = tk.Frame(cnt, bg=_INNER)
        fr.pack(fill="x", padx=10, pady=(0, 4))
        ctk.CTkCheckBox(fr, text=label, variable=var,
                        checkmark_color="white", fg_color=_GREEN_DARK,
                        hover_color=_GREEN_HOVER).pack(anchor="w")
        if hint:
            tk.Label(fr, text=hint, bg=_INNER, fg=_FORM_HINT_FG,
                     font=_FORM_FONT_HINT, anchor="w").pack(
                anchor="w", padx=(26, 0), pady=(0, 2))

    # ── Variáveis ─────────────────────────────────────────────────────────
    w["name"]            = tk.StringVar(value=srv.name)
    w["install_dir"]     = tk.StringVar(value=srv.install_dir)
    w["server_name"]     = tk.StringVar(value=srv.server_name)
    w["map"]             = tk.StringVar(value=srv.map)
    w["server_password"] = tk.StringVar(value=srv.server_password)
    w["admin_password"]  = tk.StringVar(value=srv.admin_password)
    w["rcon_password"]   = tk.StringVar(value=srv.rcon_password)
    w["max_players"]     = tk.StringVar(value=str(srv.max_players))
    w["server_port"]     = tk.StringVar(value=str(srv.server_port))
    w["peer_port"]       = tk.StringVar(value=str(srv.server_port + 1))
    w["query_port"]      = tk.StringVar(value=str(srv.query_port))
    w["rcon_port"]       = tk.StringVar(value=str(srv.rcon_port))
    w["public_ip"]        = tk.StringVar(value=srv.public_ip)
    w["battlemetrics_id"] = tk.StringVar(value=srv.battlemetrics_id)
    w["extra_args"]       = tk.StringVar(value=srv.extra_args)
    _evt_label = _ARK_EVENT_ID_TO_LABEL.get(srv.active_event, srv.active_event)
    w["active_event"]    = tk.StringVar(value=_evt_label)
    w["auto_save"]       = tk.StringVar(value=str(srv.auto_save_period))
    w["rcon_enabled"]       = tk.BooleanVar(value=srv.rcon_enabled)
    w["use_battleye"]       = tk.BooleanVar(value=srv.use_battleye)
    w["use_allcores"]       = tk.BooleanVar(value=srv.use_allcores)
    w["cpu_core_count"]     = tk.StringVar()
    w["force_respawn"]      = tk.BooleanVar(value=srv.force_respawn_dinos)
    w["whitelist_only"]     = tk.BooleanVar(value=srv.whitelist_only)
    w["auto_restart_crash"] = tk.BooleanVar(value=srv.auto_restart_on_crash)
    w["auto_update_start"]  = tk.BooleanVar(value=srv.auto_update_on_start)
    w["crossplay"]          = tk.BooleanVar(value=srv.crossplay)
    w["epic_only"]          = tk.BooleanVar(value=srv.epic_only)
    w["use_vivox"]          = tk.BooleanVar(value=srv.use_vivox)
    w["use_item_dupe_check"]= tk.BooleanVar(value=srv.use_item_dupe_check)
    w["prevent_spawn_anim"] = tk.BooleanVar(value=srv.prevent_spawn_animations)
    w["show_floating_dmg"]  = tk.BooleanVar(value=srv.show_floating_damage_text)
    w["server_ip"]           = tk.StringVar(value=srv.server_ip)
    w["public_ip_for_epic"]  = tk.StringVar(value=srv.public_ip_for_epic)
    w["use_raw_sockets"]     = tk.BooleanVar(value=srv.use_raw_sockets)
    w["no_net_threading"]    = tk.BooleanVar(value=srv.no_net_threading)
    w["force_net_threading"] = tk.BooleanVar(value=srv.force_net_threading)
    w["spectator_password"]  = tk.StringVar(value=srv.spectator_password)
    w["enable_ban_list_url"] = tk.BooleanVar(value=srv.enable_ban_list_url)
    w["ban_list_url"]        = tk.StringVar(value=srv.ban_list_url)
    w["rcon_server_game_log_buffer"] = tk.StringVar(value=str(srv.rcon_server_game_log_buffer))
    w["admin_logging"]               = tk.BooleanVar(value=srv.admin_logging)
    w["enable_extinction_event"]          = tk.BooleanVar(value=srv.enable_extinction_event)
    w["extinction_event_time_interval"]   = tk.StringVar(value=str(srv.extinction_event_time_interval))
    w["disable_vac"]                      = tk.BooleanVar(value=srv.disable_vac)
    w["disable_anti_speed_hack"]          = tk.BooleanVar(value=srv.disable_anti_speed_hack)
    w["speed_hack_bias"]                  = tk.StringVar(value=str(srv.speed_hack_bias))
    w["disable_player_move_physics_opt"]  = tk.BooleanVar(value=srv.disable_player_move_physics_opt)
    w["use_cache"]                        = tk.BooleanVar(value=srv.use_cache)
    w["use_old_save_format"]              = tk.BooleanVar(value=srv.use_old_save_format)
    w["use_no_memory_bias"]               = tk.BooleanVar(value=srv.use_no_memory_bias)
    w["stasis_keep_controllers"]          = tk.BooleanVar(value=srv.stasis_keep_controllers)
    w["use_no_hang_detection"]            = tk.BooleanVar(value=srv.use_no_hang_detection)
    w["server_allow_ansel"]               = tk.BooleanVar(value=srv.server_allow_ansel)
    w["no_dinos"]                         = tk.BooleanVar(value=srv.no_dinos)
    w["force_dx10"]                       = tk.BooleanVar(value=srv.force_dx10)
    w["force_shader_model4"]              = tk.BooleanVar(value=srv.force_shader_model4)
    w["force_low_memory"]                 = tk.BooleanVar(value=srv.force_low_memory)
    w["enable_allow_cave_flyers"]         = tk.BooleanVar(value=srv.enable_allow_cave_flyers)
    w["enable_auto_destroy_structures"]   = tk.BooleanVar(value=srv.enable_auto_destroy_structures)
    w["enable_no_fish_loot"]              = tk.BooleanVar(value=srv.enable_no_fish_loot)
    w["enable_web_alarm"]                 = tk.BooleanVar(value=srv.enable_web_alarm)
    w["web_alarm_key"]                    = tk.StringVar(value=srv.web_alarm_key)
    w["web_alarm_url"]                    = tk.StringVar(value=srv.web_alarm_url)
    w["enable_server_admin_logs"]                 = tk.BooleanVar(value=srv.enable_server_admin_logs)
    w["server_admin_logs_include_tribe_logs"]     = tk.BooleanVar(value=srv.server_admin_logs_include_tribe_logs)
    w["server_rcon_output_tribe_logs"]            = tk.BooleanVar(value=srv.server_rcon_output_tribe_logs)
    w["notify_admin_commands_in_chat"]            = tk.BooleanVar(value=srv.notify_admin_commands_in_chat)
    w["allow_hide_damage_source_from_logs"]       = tk.BooleanVar(value=srv.allow_hide_damage_source_from_logs)
    w["max_tribe_logs"]                           = tk.StringVar(value=str(srv.max_tribe_logs))
    w["tribe_log_destroyed_enemy_structures"]     = tk.BooleanVar(value=srv.tribe_log_destroyed_enemy_structures)
    w["enable_auto_force_respawn_wild_dinos_interval"]  = tk.BooleanVar(value=srv.enable_auto_force_respawn_wild_dinos_interval)
    w["server_auto_force_respawn_wild_dinos_interval"]  = tk.StringVar(value=str(srv.server_auto_force_respawn_wild_dinos_interval))
    w["tribute_character_expiration_seconds"] = tk.StringVar(value=str(srv.tribute_character_expiration_seconds))
    w["tribute_item_expiration_seconds"]      = tk.StringVar(value=str(srv.tribute_item_expiration_seconds))
    w["tribute_dino_expiration_seconds"]      = tk.StringVar(value=str(srv.tribute_dino_expiration_seconds))
    w["minimum_dino_reupload_interval"]       = tk.StringVar(value=str(srv.minimum_dino_reupload_interval))
    w["cross_ark_allow_foreign_dino_downloads"] = tk.BooleanVar(value=srv.cross_ark_allow_foreign_dino_downloads)
    w["branch_name"]     = tk.StringVar(value=srv.branch_name)
    w["branch_password"] = tk.StringVar(value=srv.branch_password)

    # ══════════════════════════════════════════════════════════════════════
    # Linha 0 — Identificação + Mapa  |  Acesso + Senhas
    # ══════════════════════════════════════════════════════════════════════
    c_id = _make_card(0, 0)
    _head(c_id, "🖥️  Identificação + 🗺️ Mapa")
    _fld(c_id, "Nome interno:",
         "Label exibido na barra lateral do app.", w["name"])
    _fld(c_id, "Diretório de Instalação:",
         "Pasta onde o ARK Server será instalado/atualizado.",
         w["install_dir"], browse=True)
    _fld(c_id, "Nome do Servidor:",
         "Nome visível na lista de servidores do jogo (Session Name).",
         w["server_name"])
    _fld(c_id, "Mapa:",
         "Selecione o mapa que o servidor irá rodar.", w["map"],
         combo=[f"{ARK_MAP_NAMES.get(m, m)} ({m})" for m in ARK_MAPS])
    tk.Frame(c_id, bg=_INNER, height=8).pack()

    c_ac = _make_card(1, 0)
    _head(c_ac, "🔒  Acesso + 🔑 Acesso Especial")
    _fld(c_ac, "Senha do Servidor:",
         "Senha para entrar. Deixe vazio para servidor público.",
         w["server_password"], is_pass=True)
    _fld(c_ac, "Senha de Admin:",
         "Usada para ativar cheats in-game (enablecheats). Mantenha secreta.",
         w["admin_password"], is_pass=True)
    _fld(c_ac, "Senha RCON:",
         "Senha para conexão via console RCON. Geralmente igual à de admin.",
         w["rcon_password"], is_pass=True)
    _fld(c_ac, "Máx. Jogadores:",
         "Limite de jogadores simultâneos no servidor.", w["max_players"])
    _fld(c_ac, "Senha do Espectador:",
         "Permite entrar no servidor como espectador (SpectatorPassword).",
         w["spectator_password"], is_pass=True)
    _chk(c_ac, "Habilitar Lista de Ban Personalizada",
         "Usa uma URL externa de banimentos em vez da lista padrão da Wildcard.",
         w["enable_ban_list_url"])
    _fld(c_ac, "URL da Lista de Ban:",
         "URL do arquivo .txt com Steam IDs banidos (um por linha).",
         w["ban_list_url"])
    tk.Frame(c_ac, bg=_INNER, height=8).pack()

    # ══════════════════════════════════════════════════════════════════════
    # Linha 1 — Rede e Portas  |  Opções de Inicialização + CPU + Branch
    # ══════════════════════════════════════════════════════════════════════
    c_net = _make_card(0, 1)
    _head(c_net, "🔌  Rede e Portas")

    # Porta do Servidor com exibição da Porta Par
    app._register_config_item(srv.id, "Porta do Servidor",
                               "Porta principal UDP. Padrão: 7777.", "Geral")
    _sp_fr = tk.Frame(c_net, bg=_INNER)
    _sp_fr.pack(fill="x", padx=10, pady=(0, 4))
    _sp_fr.columnconfigure(0, weight=1)
    tk.Label(_sp_fr, text="Porta do Servidor:", anchor="w",
             bg=_INNER, fg=_FORM_LABEL_FG,
             font=_FORM_FONT_BOLD).grid(row=0, column=0, sticky="w")
    _sp_ent = ctk.CTkFrame(_sp_fr, fg_color="transparent")
    _sp_ent.grid(row=1, column=0, sticky="ew", pady=(2, 0))
    _sp_ent.grid_columnconfigure(0, weight=1)
    ctk.CTkEntry(_sp_ent, textvariable=w["server_port"], height=34).grid(
        row=0, column=0, sticky="ew")
    ctk.CTkLabel(_sp_ent, text="Porta Par:", text_color="gray55",
                 font=ctk.CTkFont(size=11)).grid(row=0, column=1, padx=(14, 6))
    ctk.CTkLabel(_sp_ent, textvariable=w["peer_port"],
                 font=ctk.CTkFont(size=13, weight="bold"),
                 text_color="#7ec8e3").grid(row=0, column=2, sticky="w", padx=(0, 6))
    tk.Label(_sp_fr,
             text="Porta principal UDP. Padrão: 7777. Liberar no roteador (UDP).\n"
                  "A Porta Par (port+1) é usada internamente pelo ARK — abra-a no roteador também.",
             anchor="w", bg=_INNER, fg=_FORM_HINT_FG,
             font=_FORM_FONT_HINT, justify="left").grid(
        row=2, column=0, sticky="w", pady=(1, 4))

    def _update_peer_port(*_):
        try:
            w["peer_port"].set(str(int(w["server_port"].get()) + 1))
        except ValueError:
            pass
    w["server_port"].trace_add("write", _update_peer_port)

    _fld(c_net, "Porta de Query:",
         "Porta de consulta Steam. Padrão: 27015. Liberar no roteador (UDP).",
         w["query_port"])
    _fld(c_net, "Porta RCON:",
         "Porta do console remoto. Padrão: 27020. Só abrir se usar RCON externo.",
         w["rcon_port"])

    # IP Público com detecção automática
    app._register_config_item(srv.id, "IP Público",
                               "IP ou hostname que jogadores usam para conectar.", "Geral")
    _ip_fr = tk.Frame(c_net, bg=_INNER)
    _ip_fr.pack(fill="x", padx=10, pady=(0, 4))
    _ip_fr.columnconfigure(0, weight=1)
    tk.Label(_ip_fr, text="IP Público:", anchor="w",
             bg=_INNER, fg=_FORM_LABEL_FG,
             font=_FORM_FONT_BOLD).grid(row=0, column=0, sticky="w")
    _ip_ent = ctk.CTkFrame(_ip_fr, fg_color="transparent")
    _ip_ent.grid(row=1, column=0, sticky="ew", pady=(2, 0))
    _ip_ent.grid_columnconfigure(0, weight=1)
    ctk.CTkEntry(_ip_ent, textvariable=w["public_ip"], height=34,
                 placeholder_text="Ex: 189.123.45.67 ou meuservidor.com").grid(
        row=0, column=0, sticky="ew")
    _ip_btn_fr = ctk.CTkFrame(_ip_ent, fg_color="transparent")
    _ip_btn_fr.grid(row=1, column=0, sticky="e", pady=(4, 4))
    _detect_btn = ctk.CTkButton(
        _ip_btn_fr, text="🔄 Detectar IP", width=120, height=26,
        fg_color=_GREEN_DARK, hover_color=_GREEN_HOVER,
        font=ctk.CTkFont(size=11))
    _detect_btn.pack(side="left", padx=(0, 4))
    _copy_ip_btn = ctk.CTkButton(
        _ip_btn_fr, text="📋 Copiar", width=80, height=26,
        fg_color="#2a2a2a", hover_color="#404040",
        font=ctk.CTkFont(size=11))
    _copy_ip_btn.pack(side="left")

    def _detect_public_ip() -> None:
        _detect_btn.configure(state="disabled", text="⏳...")
        def _fetch() -> None:
            try:
                with urllib.request.urlopen("https://api.ipify.org", timeout=5) as _r:
                    _ip = _r.read().decode().strip()
                def _apply(_detected=_ip) -> None:
                    w["public_ip"].set(_detected)
                    _detect_btn.configure(state="normal", text="🔄 Detectar")
                scroll.after(0, _apply)
            except Exception:
                scroll.after(0, lambda: _detect_btn.configure(state="normal", text="🔄 Detectar"))
        threading.Thread(target=_fetch, daemon=True).start()

    _detect_btn.configure(command=_detect_public_ip)
    _copy_ip_btn.configure(command=lambda: (
        scroll.clipboard_clear(),
        scroll.clipboard_append(w["public_ip"].get()),
    ))
    tk.Label(_ip_fr,
             text="IP ou hostname que jogadores usam para conectar.\n"
                  "Clique em 'Detectar' para obter o IP público da máquina.",
             anchor="w", bg=_INNER, fg=_FORM_HINT_FG,
             font=_FORM_FONT_HINT, justify="left").grid(
        row=2, column=0, sticky="w", pady=(1, 4))

    _fld(c_net, "BattleMetrics ID:",
         "ID numérico do servidor na plataforma BattleMetrics.\n"
         "Ex: 38129676 — usado para confirmar status real e contar jogadores ao vivo.",
         w["battlemetrics_id"])
    _fld(c_net, "IP de Bind (MultiHome):",
         "Força o servidor a usar um IP específico (?MultiHome=). Deixe vazio para usar todos.",
         w["server_ip"])
    _fld(c_net, "IP Público para Epic:",
         "IP/hostname para crossplay Epic/Steam em VPS ou NAT (-PublicIPForEpic=).",
         w["public_ip_for_epic"])
    _chk(c_net, "Sockets UDP Raw (bRawSockets)",
         "Menor overhead de rede. Recomendado apenas com -nonetthreading ou -forcenetthreading.",
         w["use_raw_sockets"])
    _chk(c_net, "Sem Thread de Rede (-nonetthreading)",
         "Desativa threads de rede. Usar somente com bRawSockets ativado.",
         w["no_net_threading"])
    _chk(c_net, "Forçar Thread de Rede (-forcenetthreading)",
         "Força o uso de threads de rede. Usar somente com bRawSockets ativado.",
         w["force_net_threading"])
    tk.Frame(c_net, bg=_INNER, height=8).pack()

    c_opt = _make_card(1, 1)
    _head(c_opt, "⚙️  Opções de Inicialização")
    _fld(c_opt, "Evento Ativo:",
         "Selecione o evento oficial ou deixe vazio para nenhum.",
         w["active_event"], combo=[v for _, v in _ARK_OFFICIAL_EVENTS])
    _fld(c_opt, "Auto-Save (min):",
         "Intervalo de salvamento automático em minutos. Padrão: 15.",
         w["auto_save"])
    _fld(c_opt, "Argumentos Extras:",
         "Parâmetros adicionais de linha de comando. Ex: -ForceAllowCaveFlyers.",
         w["extra_args"])

    import os as _os
    _total_cpu = _os.cpu_count() or 8

    def _int_to_cpu_opt(n: int) -> str:
        if n == -1:
            return "Todos os núcleos"
        if n == 0:
            return "Padrão (ARK decide)"
        return f"{n} núcleo{'s' if n > 1 else ''}"

    _cpu_opts = (
        ["Padrão (ARK decide)", "Todos os núcleos"]
        + [f"{n} núcleo{'s' if n > 1 else ''}" for n in range(1, _total_cpu + 1)]
    )
    w["cpu_core_count"].set(_int_to_cpu_opt(srv.cpu_core_count))
    app._register_config_item(srv.id, "Núcleos de CPU",
                               "Restringe quantos núcleos lógicos o servidor pode usar.", "Geral")
    _cpu_fr = tk.Frame(c_opt, bg=_INNER)
    _cpu_fr.pack(fill="x", padx=10, pady=(0, 4))
    tk.Label(_cpu_fr, text="Núcleos de CPU:", anchor="w",
             bg=_INNER, fg=_FORM_LABEL_FG, font=_FORM_FONT_BOLD).pack(anchor="w")
    tk.Label(_cpu_fr,
             text="Restringe quantos núcleos lógicos o processo do servidor pode usar.\n"
                  "\"Todos\" usa -useallavailablecores. Número específico aplica afinidade.",
             anchor="w", bg=_INNER, fg=_FORM_HINT_FG,
             font=_FORM_FONT_HINT, justify="left").pack(anchor="w")
    ctk.CTkOptionMenu(
        _cpu_fr, variable=w["cpu_core_count"],
        values=_cpu_opts, width=220,
    ).pack(anchor="w", pady=(4, 0))

    _head(c_opt, "🎮  SteamCMD Beta Branch")
    _fld(c_opt, "Nome da Branch:",
         "Branch SteamCMD para instalar/atualizar. Ex: 'preaquatica'. Vazio = versão estável.",
         w["branch_name"])
    _fld(c_opt, "Senha da Branch:",
         "Senha da branch beta, se necessário (-betapassword).",
         w["branch_password"], is_pass=True)
    tk.Frame(c_opt, bg=_INNER, height=8).pack()

    # ══════════════════════════════════════════════════════════════════════
    # Linha 2 — Flags de Servidor  |  Flags de Processo
    # ══════════════════════════════════════════════════════════════════════
    c_flags = _make_card(0, 2)
    _head(c_flags, "🔧  Flags de Servidor")
    for _txt, _hint, _var in [
        ("Habilitar RCON",
         "Ativa o console remoto. Necessário para usar a aba Console RCON.",
         w["rcon_enabled"]),
        ("Usar BattlEye (anti-cheat)",
         "Proteção anti-cheat oficial. Desative para servidores com mods incompatíveis.",
         w["use_battleye"]),
        ("Forçar respawn de dinos",
         "Reseta todos os dinos selvagens ao iniciar o servidor.",
         w["force_respawn"]),
        ("Apenas whitelist",
         "Somente jogadores na whitelist podem entrar no servidor.",
         w["whitelist_only"]),
        ("Auto-restart ao travar",
         "Reinicia o servidor automaticamente caso ocorra um crash.",
         w["auto_restart_crash"]),
        ("Atualizar servidor ao iniciar",
         "Verifica e aplica atualizações via SteamCMD antes de iniciar.",
         w["auto_update_start"]),
        ("Crossplay Epic + Steam",
         "Permite que jogadores da Epic e do Steam se conectem ao mesmo servidor.",
         w["crossplay"]),
        ("Apenas Epic Games",
         "Somente jogadores da Epic Game Store podem se conectar ao servidor.",
         w["epic_only"]),
        ("Vivox (chat de voz)",
         "Ativa o Vivox para comunicação de voz entre jogadores (somente Steam).",
         w["use_vivox"]),
        ("Proteção anti-dupe de itens",
         "Ativa verificação adicional contra duplicação. Pode impactar alguns mods.",
         w["use_item_dupe_check"]),
        ("Sem animação de spawn",
         "Desativa a animação de acordar ao (re)nascer no servidor.",
         w["prevent_spawn_anim"]),
        ("Dano flutuante (estilo RPG)",
         "Exibe texto de dano flutuante no estilo RPG ao atacar/ser atacado.",
         w["show_floating_dmg"]),
    ]:
        _chk(c_flags, _txt, _hint, _var)
    tk.Frame(c_flags, bg=_INNER, height=8).pack()

    c_fproc = _make_card(1, 2)
    _head(c_fproc, "🔧  Flags de Processo")
    for _txt, _hint, _var in [
        ("Desativar VAC / Modo Inseguro (-insecure)",
         "Desativa o anti-cheat VAC da Steam. Use apenas para testes/mods incompatíveis.",
         w["disable_vac"]),
        ("Desativar Anti-SpeedHack (-noantispeedhack)",
         "Desativa a detecção de speedhack nativa do ARK.",
         w["disable_anti_speed_hack"]),
        ("Desativar Otimização de Física do Jogador (-nocombineclientmoves)",
         "Desativa otimização de movimentação do cliente. Pode ajudar com lag.",
         w["disable_player_move_physics_opt"]),
        ("Usar Cache (-usecache)",
         "Ativa o cache de assets do servidor para carregamento mais rápido.",
         w["use_cache"]),
        ("Formato de Save Antigo (-oldsaveformat)",
         "Usa o formato de arquivo de save legado. Útil para compatibilidade com backups.",
         w["use_old_save_format"]),
        ("Sem Bias de Memória (-nomemorybias)",
         "Desativa o viés de alocação de memória. Pode reduzir uso de RAM.",
         w["use_no_memory_bias"]),
        ("Manter Controllers em Stasis (-StasisKeepControllers)",
         "Mantém controllers ativos quando criaturas entram em stasis.",
         w["stasis_keep_controllers"]),
        ("Sem Detecção de Hang (-NoHangDetection)",
         "Desativa o watchdog de travamento do servidor.",
         w["use_no_hang_detection"]),
        ("Permitir Ansel (-ServerAllowAnsel)",
         "Habilita o NVIDIA Ansel para capturas de tela no servidor.",
         w["server_allow_ansel"]),
        ("Sem Dinos (-NoDinos)",
         "Inicia o servidor sem spawnar nenhum dino selvagem.",
         w["no_dinos"]),
        ("Forçar DirectX 10 (-d3d10)",
         "Força o modo DX10. Reduz consumo de VRAM em servidores sem GPU dedicada.",
         w["force_dx10"]),
        ("Forçar Shader Model 4 (-sm4)",
         "Usa shaders SM4 em vez de SM5. Compatível com GPUs mais antigas.",
         w["force_shader_model4"]),
        ("Modo de Baixa Memória (-lowmemory)",
         "Usa texturas de menor resolução para economizar RAM.",
         w["force_low_memory"]),
        ("Permitir Voadores em Cavernas (-ForceAllowCaveFlyers)",
         "Permite que dinos voadores entrem em cavernas.",
         w["enable_allow_cave_flyers"]),
        ("Auto-Destruir Estruturas (-AutoDestroyStructures)",
         "Destrói automaticamente estruturas de tribos extintas.",
         w["enable_auto_destroy_structures"]),
        ("Sem Loot de Peixe (-nofishloot)",
         "Remove itens do inventário de peixes pescados.",
         w["enable_no_fish_loot"]),
    ]:
        _chk(c_fproc, _txt, _hint, _var)
    _fld(c_fproc, "Bias do SpeedHack (-speedhackbias):",
         "Fator de tolerância para a detecção de speedhack. Padrão: 1.0.",
         w["speed_hack_bias"])
    tk.Frame(c_fproc, bg=_INNER, height=8).pack()

    # ══════════════════════════════════════════════════════════════════════
    # Linha 3 — RCON/Logs  |  Dinos + Tributos + Extinção + Web Alarm
    # ══════════════════════════════════════════════════════════════════════
    c_rcon = _make_card(0, 3)
    _head(c_rcon, "📡  RCON / Logs de Admin")
    _chk(c_rcon, "Habilitar Log Administrativo",
         "Registra no log os comandos de admin executados no servidor (AdminLogging).",
         w["admin_logging"])
    _fld(c_rcon, "Buffer do Log RCON:",
         "Quantidade de linhas mantidas no buffer do log de jogo via RCON (padrão: 600).",
         w["rcon_server_game_log_buffer"])
    for _txt, _hint, _var in [
        ("Log de Admin no Console (-servergamelog)",
         "Envia o log do jogo ao console RCON/servidor.",
         w["enable_server_admin_logs"]),
        ("Incluir Logs de Tribo (-servergamelogincludetribelogs)",
         "Inclui eventos de tribos no log de admin.",
         w["server_admin_logs_include_tribe_logs"]),
        ("Logs de Tribo via RCON (-ServerRCONOutputTribeLogs)",
         "Envia logs de tribo pelo canal RCON.",
         w["server_rcon_output_tribe_logs"]),
        ("Notificar Comandos Admin no Chat (-NotifyAdminCommandsInChat)",
         "Exibe no chat dos jogadores quando um admin executa um comando.",
         w["notify_admin_commands_in_chat"]),
        ("Ocultar Fonte de Dano nos Logs",
         "Esconde a origem do dano nos logs de tribo (AllowHideDamageSourceFromLogs).",
         w["allow_hide_damage_source_from_logs"]),
        ("Logar Estruturas Inimigas Destruídas",
         "Registra no log de tribo quando estruturas inimigas são destruídas.",
         w["tribe_log_destroyed_enemy_structures"]),
    ]:
        _chk(c_rcon, _txt, _hint, _var)
    _fld(c_rcon, "Máx. Entradas no Log de Tribo:",
         "Número máximo de entradas no log de tribo (MaxTribeLogs). Padrão: 100.",
         w["max_tribe_logs"])
    tk.Frame(c_rcon, bg=_INNER, height=8).pack()

    c_misc = _make_card(1, 3)
    _head(c_misc, "🦖  Dinos + 🌀 Tributos + ☄️ Extinção")
    _chk(c_misc, "Auto-Forçar Respawn de Dinos Selvagens",
         "Executa automaticamente um respawn forçado de dinos no intervalo definido.",
         w["enable_auto_force_respawn_wild_dinos_interval"])
    _fld(c_misc, "Intervalo de Auto-Respawn (s):",
         "Intervalo em segundos para o respawn automático de dinos. Padrão: 86400 (24h).",
         w["server_auto_force_respawn_wild_dinos_interval"])
    _chk(c_misc, "Habilitar Evento de Extinção",
         "Ativa o evento periódico de extinção (Element Vein / King Titan).",
         w["enable_extinction_event"])
    _fld(c_misc, "Intervalo do Evento (s):",
         "Intervalo entre extinções em segundos. Padrão: 2592000 (~30 dias).",
         w["extinction_event_time_interval"])
    _fld(c_misc, "Expiração de Personagem Tributário (s):",
         "Tempo em segundos até personagem no terminal expirar. 0 = padrão ARK.",
         w["tribute_character_expiration_seconds"])
    _fld(c_misc, "Expiração de Item Tributário (s):",
         "Tempo em segundos até itens no terminal expirarem. 0 = padrão ARK.",
         w["tribute_item_expiration_seconds"])
    _fld(c_misc, "Expiração de Dino Tributário (s):",
         "Tempo em segundos até dinos no terminal expirarem. 0 = padrão ARK.",
         w["tribute_dino_expiration_seconds"])
    _fld(c_misc, "Intervalo Mínimo de Reupload de Dino (s):",
         "Tempo mínimo entre uploads do mesmo dino. 0 = sem restrição.",
         w["minimum_dino_reupload_interval"])
    _chk(c_misc, "Permitir Download de Dinos Externos",
         "Permite baixar dinos de outros clusters mesmo com filtros ativos.",
         w["cross_ark_allow_foreign_dino_downloads"])
    _head(c_misc, "🚨  Web Alarm (-webalarm)")
    _chk(c_misc, "Habilitar Web Alarm",
         "Envia notificações de morte de jogador a uma URL webhook.",
         w["enable_web_alarm"])
    _fld(c_misc, "Chave do Web Alarm:",
         "Token/chave de autenticação enviado junto à notificação.",
         w["web_alarm_key"])
    _fld(c_misc, "URL do Web Alarm:",
         "Endpoint que receberá as notificações POST de morte.",
         w["web_alarm_url"])
    tk.Frame(c_misc, bg=_INNER, height=8).pack()

    # ══════════════════════════════════════════════════════════════════════
    # Linha 4 — MOTD (largura total)
    # ══════════════════════════════════════════════════════════════════════
    c_motd = _make_card(0, 4, colspan=2)
    _head(c_motd, "📢  Mensagem do Dia (MOTD)")
    motd_inner = tk.Frame(c_motd, bg=_INNER)
    motd_inner.pack(fill="x", padx=10, pady=(0, 8))
    motd_inner.columnconfigure(1, weight=1)

    ctk.CTkLabel(motd_inner, text="Mensagem:", width=130, anchor="nw",
                 text_color="gray60").grid(row=0, column=0, padx=(0, 8), pady=(0, 2), sticky="nw")
    w["motd"] = ctk.CTkTextbox(motd_inner, height=240, corner_radius=6,
                               fg_color="#1a1a2e", border_color="#3a3a5a",
                               border_width=1, font=ctk.CTkFont(size=12), wrap="none")
    w["motd"].grid(row=0, column=1, sticky="ew", pady=(0, 4))
    if srv.motd:
        w["motd"].insert("1.0", srv.motd)

    tips_frame = ctk.CTkFrame(motd_inner, fg_color="#16162a", corner_radius=8)
    tips_frame.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(0, 8))
    tips_frame.grid_columnconfigure(0, weight=1)
    ctk.CTkLabel(tips_frame, text="💡  Dicas de Formatação",
                 font=ctk.CTkFont(size=11, weight="bold"),
                 text_color="#a0a0c0", anchor="w").grid(
        row=0, column=0, padx=10, pady=(8, 4), sticky="w")
    ctk.CTkLabel(
        tips_frame,
        text='Cor:  <RichColor Color="R, G, B, 1">seu texto</>     '
             'Nova linha:  \\n     Fechar cor:  </>',
        font=ctk.CTkFont(family="Courier New", size=11),
        text_color="#c8c8e8", anchor="w",
    ).grid(row=1, column=0, padx=10, pady=(0, 6), sticky="w")

    colors_frame = ctk.CTkFrame(tips_frame, fg_color="transparent")
    colors_frame.grid(row=2, column=0, padx=8, pady=(0, 8), sticky="w")
    ctk.CTkLabel(colors_frame, text="Inserir cor:",
                 font=ctk.CTkFont(size=11), text_color="gray50").pack(side="left", padx=(2, 6))
    for _cl, _cv, _fg, _hov in [
        ("🟢 Verde",    "0, 1, 0, 1",       "#1a3a1a", "#2a5a2a"),
        ("🔴 Vermelho", "1, 0, 0, 1",       "#3a1a1a", "#5a2a2a"),
        ("🟡 Amarelo",  "1, 0.85, 0, 1",    "#3a3a10", "#5a5a18"),
        ("🔵 Azul",     "0, 0.6, 1, 1",     "#102040", "#183060"),
        ("🟠 Laranja",  "1, 0.5, 0, 1",     "#3a2010", "#5a3018"),
        ("⚪ Branco",   "1, 1, 1, 1",       "#2a2a2a", "#404040"),
    ]:
        def _make_insert_color(tag_color: str) -> Callable:
            def _insert() -> None:
                tb = w["motd"]
                tag = f'<RichColor Color="{tag_color}">'
                try:
                    tb._textbox.insert("insert", tag)
                except Exception:
                    tb.insert("end", tag)
            return _insert
        ctk.CTkButton(colors_frame, text=_cl, height=26,
                      font=ctk.CTkFont(size=11), fg_color=_fg, hover_color=_hov,
                      command=_make_insert_color(_cv)).pack(side="left", padx=3)

    ctk.CTkButton(
        colors_frame, text="</> Fechar", height=26,
        font=ctk.CTkFont(size=11), fg_color="#2a2a2a", hover_color="#404040",
        command=lambda: (
            w["motd"]._textbox.insert("insert", "</>")
            if hasattr(w["motd"], "_textbox") else
            w["motd"].insert("end", "</>")
        ),
    ).pack(side="left", padx=(8, 3))
    ctk.CTkButton(
        colors_frame, text="↵ \\n", height=26,
        font=ctk.CTkFont(size=11), fg_color="#2a2a2a", hover_color="#404040",
        command=lambda: (
            w["motd"]._textbox.insert("insert", r"\n")
            if hasattr(w["motd"], "_textbox") else
            w["motd"].insert("end", r"\n")
        ),
    ).pack(side="left", padx=3)

    ctk.CTkLabel(motd_inner, text="Duração (s):", width=130, anchor="w",
                 text_color="gray60").grid(row=2, column=0, padx=(0, 8), pady=(4, 0), sticky="w")
    w["motd_duration"] = tk.StringVar(value=str(srv.motd_duration))
    ctk.CTkEntry(motd_inner, textvariable=w["motd_duration"],
                 height=34, width=80).grid(row=2, column=1, pady=(4, 0), sticky="w")

    # ══════════════════════════════════════════════════════════════════════
    # Linha 5 — Agendamentos (largura total)
    # ══════════════════════════════════════════════════════════════════════
    c_sched = _make_card(0, 5, colspan=2)
    _head(c_sched, "⏰  Agendamentos Automáticos")
    sched_outer = ctk.CTkFrame(c_sched, fg_color="transparent")
    sched_outer.pack(fill="x", padx=10, pady=(0, 8))
    sched_outer.grid_columnconfigure(0, weight=1)

    _DAY_LABELS  = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]
    _ACTION_LABELS = {"restart": "Reiniciar", "stop": "Desligar",
                      "update_restart": "Atualizar + Reiniciar"}
    _WARN_OPTS = ["0", "5", "10", "15", "30", "60"]

    w["sched_task_rows"] = []
    sched_rows_frame = ctk.CTkFrame(sched_outer, fg_color="transparent")
    sched_rows_frame.grid(row=0, column=0, sticky="ew", pady=(0, 4))
    sched_rows_frame.grid_columnconfigure(0, weight=1)

    def _add_sched_row(task: dict | None = None) -> None:
        ri = len(w["sched_task_rows"])
        row_fr = ctk.CTkFrame(sched_rows_frame, fg_color="#0e1018",
                              corner_radius=6, border_width=1,
                              border_color="#1e2840")
        row_fr.grid(row=ri, column=0, sticky="ew", pady=(0, 4))

        ev = tk.BooleanVar(value=task.get("enabled", True) if task else True)
        tv = tk.StringVar(value=task.get("time", "03:00") if task else "03:00")
        dv = [tk.BooleanVar(value=(d in (task.get("days", list(range(7)))
                                         if task else list(range(7)))))
              for d in range(7)]
        av = tk.StringVar(value=task.get("action", "restart") if task else "restart")
        wv = tk.StringVar(value=str(task.get("warn_minutes", 15)) if task else "15")

        top = ctk.CTkFrame(row_fr, fg_color="transparent")
        top.pack(fill="x", padx=8, pady=(6, 2))
        ctk.CTkCheckBox(top, text="", variable=ev, width=20,
                        fg_color=_GREEN_DARK, hover_color=_GREEN_HOVER,
                        checkmark_color="white").pack(side="left", padx=(0, 6))
        ctk.CTkLabel(top, text="Hora:", text_color="gray60",
                     font=ctk.CTkFont(size=10)).pack(side="left")
        ctk.CTkEntry(top, textvariable=tv, width=60,
                     font=ctk.CTkFont(size=12),
                     placeholder_text="HH:MM").pack(side="left", padx=(4, 12))
        ctk.CTkLabel(top, text="Ação:", text_color="gray60",
                     font=ctk.CTkFont(size=10)).pack(side="left")
        ctk.CTkOptionMenu(top, variable=av,
                          values=list(_ACTION_LABELS.values()),
                          width=170).pack(side="left", padx=(4, 12))
        ctk.CTkLabel(top, text="Aviso:", text_color="gray60",
                     font=ctk.CTkFont(size=10)).pack(side="left")
        ctk.CTkOptionMenu(top, variable=wv,
                          values=_WARN_OPTS, width=60).pack(side="left", padx=(4, 4))
        ctk.CTkLabel(top, text="min", text_color="gray50",
                     font=ctk.CTkFont(size=10)).pack(side="left", padx=(0, 12))

        def _remove(fr=row_fr, rowdata=None):
            fr.destroy()
            if rowdata in w["sched_task_rows"]:
                w["sched_task_rows"].remove(rowdata)
        rd: dict = {}
        ctk.CTkButton(top, text="✕", width=28, height=24,
                      fg_color="#3a1515", hover_color="#5a2020",
                      font=ctk.CTkFont(size=11),
                      command=lambda: _remove(row_fr, rd)).pack(side="right")

        bot = ctk.CTkFrame(row_fr, fg_color="transparent")
        bot.pack(fill="x", padx=8, pady=(0, 6))
        ctk.CTkLabel(bot, text="Dias:", text_color="gray60",
                     font=ctk.CTkFont(size=10)).pack(side="left", padx=(20, 4))
        for _dlbl, _dvar in zip(_DAY_LABELS, dv):
            ctk.CTkCheckBox(bot, text=_dlbl, variable=_dvar, width=52,
                            fg_color=_GREEN_DARK, hover_color=_GREEN_HOVER,
                            checkmark_color="white",
                            font=ctk.CTkFont(size=10)).pack(side="left", padx=2)

        rd.update({"frame": row_fr, "enabled": ev, "time": tv, "days": dv,
                   "action": av, "warn": wv, "_action_labels": _ACTION_LABELS})
        w["sched_task_rows"].append(rd)

    for t in srv.scheduled_tasks:
        _add_sched_row(t)

    ctk.CTkButton(
        sched_outer, text="+ Adicionar agendamento",
        fg_color="#1a2540", hover_color="#243060", text_color="#8eb0d0",
        height=30, font=ctk.CTkFont(size=11),
        command=_add_sched_row,
    ).grid(row=1, column=0, pady=(0, 10), sticky="w")

    # ══════════════════════════════════════════════════════════════════════
    # Linha 6 — Instalação (largura total)
    # ══════════════════════════════════════════════════════════════════════
    c_inst = _make_card(0, 6, colspan=2)
    _head(c_inst, "⬇️  Instalação / Atualização do Servidor")
    inst_inner = tk.Frame(c_inst, bg=_INNER)
    inst_inner.pack(fill="x", padx=10, pady=(0, 8))
    inst_inner.columnconfigure(0, weight=1)

    btn_row = ctk.CTkFrame(inst_inner, fg_color="transparent")
    btn_row.pack(anchor="w", pady=(0, 6))
    inst_btn = ctk.CTkButton(
        btn_row, text="⬇  Instalar / Atualizar Servidor",
        height=38, width=230,
        fg_color=_GREEN_DARK, hover_color=_GREEN_HOVER,
        command=lambda sid=srv.id: app._run_server_install(sid, validate=False))
    inst_btn.grid(row=0, column=0, padx=(0, 10))
    val_btn = ctk.CTkButton(
        btn_row, text="✅  Verificar Arquivos (validate)",
        height=38, width=230,
        fg_color=_BLUE, hover_color=_BLUE_HOVER,
        command=lambda sid=srv.id: app._run_server_install(sid, validate=True))
    val_btn.grid(row=0, column=1)

    ctk.CTkLabel(
        inst_inner,
        text="Usa o SteamCMD para baixar/atualizar os arquivos do servidor ARK: "
             "Survival Evolved (App 376030).\n"
             "O 'Diretório de Instalação' acima deve estar preenchido. "
             "Salve antes de instalar.",
        text_color="gray45", font=ctk.CTkFont(size=10), justify="left",
    ).pack(anchor="w", pady=(0, 6))

    inst_status = ctk.CTkLabel(inst_inner, text="", text_color="gray60",
                               font=ctk.CTkFont(size=11))
    inst_status.pack(anchor="w", pady=(0, 4))
    inst_log = ctk.CTkTextbox(
        inst_inner, height=160, state="disabled",
        font=ctk.CTkFont(family="Consolas", size=10),
        fg_color="#0d0d18", text_color="#c8c8d8", corner_radius=6)
    inst_log.pack(fill="x")

    app._server_widgets[srv.id]["_inst_status"] = inst_status
    app._server_widgets[srv.id]["_inst_log"]    = inst_log
    app._server_widgets[srv.id]["_inst_btn"]    = inst_btn
    app._server_widgets[srv.id]["_val_btn"]     = val_btn

    # Restaura binding de scrollregion e força único recálculo
    scroll.bind("<Configure>",
                lambda _e, _c=scroll._parent_canvas: _c.configure(scrollregion=_c.bbox("all")))
    scroll._parent_canvas.configure(scrollregion=scroll._parent_canvas.bbox("all"))

