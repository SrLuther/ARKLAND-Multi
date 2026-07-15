"""Salva configurações globais do modo TEK."""
from __future__ import annotations
import os
import sys
import tkinter as tk
from tkinter import messagebox
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from ..app_tek import ARKTEKApp


def _g(app, attr: str, ty=tk.StringVar, strip: bool = False):
    v = getattr(app, attr, ty()).get()
    return v.strip() if strip else v


def _save_discord(app, dc) -> None:
    dc.enabled       = _g(app, "_discord_enabled_var",        tk.BooleanVar)
    dc.webhook_url   = _g(app, "_discord_url_var",            strip=True)
    dc.sender_name   = _g(app, "_discord_sender_var",         strip=True) or "ARKLAND"
    dc.notify_start  = _g(app, "_discord_notify_start",       tk.BooleanVar)
    dc.notify_stop   = _g(app, "_discord_notify_stop",        tk.BooleanVar)
    dc.notify_crash  = _g(app, "_discord_notify_crash",       tk.BooleanVar)
    dc.notify_update = _g(app, "_discord_notify_update",      tk.BooleanVar)
    dc.notify_backup = _g(app, "_discord_notify_backup",      tk.BooleanVar)
    dc.mod_changelog_webhook = _g(app, "_discord_mod_changelog_hook", strip=True)


def _save_backup(app, bk) -> None:
    bk.backup_dir          = _g(app, "_bk_dir_var",           strip=True)
    bk.include_savegames   = _g(app, "_bk_include_saves_var", tk.BooleanVar)
    bk.include_config      = _g(app, "_bk_include_config_var", tk.BooleanVar)
    bk.limit_backup_count  = _g(app, "_bk_limit_count_var",   tk.BooleanVar)
    try:
        bk.max_backup_count = max(1, int(_g(app, "_bk_max_count_var")))
    except ValueError:
        bk.max_backup_count = 10
    bk.exclude_old_backups = bk.limit_backup_count
    bk.rcon_broadcast_mode = _g(app, "_bk_rcon_mode_var")
    bk.save_message        = _g(app, "_bk_save_msg_var")
    bk.auto_backup         = _g(app, "_bk_auto_var",          tk.BooleanVar)
    bk.backup_interval     = _g(app, "_bk_interval_var",      strip=True)


def _save_auto_update(app, au) -> None:
    au.cache_dir                    = _g(app, "_au_cache_dir_var",      strip=True)
    au.update_interval              = _g(app, "_au_interval_var",       strip=True)
    au.smart_cache_copy             = _g(app, "_au_smart_cache_var",    tk.BooleanVar)
    au.validate_server_files        = _g(app, "_au_validate_var",       tk.BooleanVar)
    au.update_in_parallel           = _g(app, "_au_parallel_var",       tk.BooleanVar)
    au.update_delay_seconds         = _g(app, "_au_delay_var",          tk.IntVar)
    au.show_update_reason           = _g(app, "_au_show_reason_var",    tk.BooleanVar)
    au.update_reason_prefix         = _g(app, "_au_reason_prefix_var")
    au.replace_restart_after_update = _g(app, "_au_replace_restart_var", tk.BooleanVar)


def _save_shutdown(app, sd) -> None:
    sd.check_online_players = _g(app, "_sd_check_online_var",  tk.BooleanVar)
    sd.send_msgs_to_client  = _g(app, "_sd_send_msgs_var",     tk.BooleanVar)
    sd.grace_period_minutes = _g(app, "_sd_grace_var",         tk.IntVar)
    sd.msg1                 = _g(app, "_sd_msg1_var")
    sd.msg2                 = _g(app, "_sd_msg2_var")
    sd.msg3                 = _g(app, "_sd_msg3_var")
    sd.save_message         = _g(app, "_sd_save_msg_var")
    sd.cancel_message       = _g(app, "_sd_cancel_msg_var")
    sd.show_reason_all_msgs = _g(app, "_sd_show_reason_var",   tk.BooleanVar)


def _save_alert_messages(app, am) -> None:
    am.server_stopped       = _g(app, "_al_stopped_var")
    am.server_shutting_down = _g(app, "_al_shutting_var")
    am.server_started       = _g(app, "_al_started_var")
    am.include_ip_port      = _g(app, "_al_incl_ip_var",    tk.BooleanVar)
    am.ip_port_format       = _g(app, "_al_ip_fmt_var")
    am.backup_error         = _g(app, "_al_bk_err_var")
    am.shutdown_error       = _g(app, "_al_sd_err_var")
    am.restart_error        = _g(app, "_al_rst_err_var")
    am.update_error         = _g(app, "_al_upd_err_var")
    am.update_result        = _g(app, "_al_upd_res_var")
    am.server_update_msg    = _g(app, "_al_srv_upd_var")
    am.server_status        = _g(app, "_al_srv_stat_var")
    am.mod_update_detected  = _g(app, "_al_mod_upd_var")
    am.players_changed      = _g(app, "_al_players_var")
    am.dino_respawn         = _g(app, "_al_dino_var")


def _save_discord_bot(app, db) -> None:
    db.enabled            = _g(app, "_db_enabled_var",       tk.BooleanVar)
    db.token              = _g(app, "_db_token_var",          strip=True)
    db.server_id          = _g(app, "_db_server_id_var",      strip=True)
    db.prefix             = _g(app, "_db_prefix_var",         strip=True) or "asm!"
    db.log_level          = _g(app, "_db_log_level_var")
    db.alias_all_profiles = _g(app, "_db_alias_var",          strip=True) or "all"
    db.allow_backup       = _g(app, "_db_allow_backup_var",  tk.BooleanVar)
    db.allow_update       = _g(app, "_db_allow_update_var",  tk.BooleanVar)
    db.allow_restart      = _g(app, "_db_allow_restart_var", tk.BooleanVar)
    db.allow_shutdown     = _g(app, "_db_allow_shutdown_var", tk.BooleanVar)
    db.allow_start        = _g(app, "_db_allow_start_var",   tk.BooleanVar)
    db.allow_stop         = _g(app, "_db_allow_stop_var",    tk.BooleanVar)
    db.allow_all_bots     = _g(app, "_db_all_bots_var",      tk.BooleanVar)


def _save_smtp(app, sm) -> None:
    sm.host                    = _g(app, "_smtp_host_var",      strip=True)
    sm.port                    = _g(app, "_smtp_port_var",      tk.IntVar)
    sm.use_ssl                 = _g(app, "_smtp_ssl_var",       tk.BooleanVar)
    sm.use_default_credentials = _g(app, "_smtp_defcred_var",  tk.BooleanVar)
    sm.username                = _g(app, "_smtp_user_var",      strip=True)
    sm.password                = _g(app, "_smtp_pass_var")
    sm.from_address            = _g(app, "_smtp_from_var",      strip=True)
    sm.to_address              = _g(app, "_smtp_to_var",        strip=True)
    sm.notify_auto_backup      = _g(app, "_smtp_n_backup_var",  tk.BooleanVar)
    sm.notify_auto_update      = _g(app, "_smtp_n_update_var",  tk.BooleanVar)
    sm.notify_auto_shutdown    = _g(app, "_smtp_n_shutdown_var", tk.BooleanVar)
    sm.notify_shutdown_restart = _g(app, "_smtp_n_restart_var", tk.BooleanVar)


def _save_startup_registry(app, cfg, winreg) -> None:
    try:
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        app_key = "ARKLAND-ServerManager"
        exe = sys.executable if getattr(sys, "frozen", False) else (
            f'"{sys.executable}" "{os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "main.py")}"'
        )
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE) as key:
            if cfg.startup_with_windows:
                winreg.SetValueEx(key, app_key, 0, winreg.REG_SZ, exe)
            else:
                try:
                    winreg.DeleteValue(key, app_key)
                except FileNotFoundError:
                    pass
    except Exception:
        pass


def save_global_config_tek(app) -> None:
    import winreg as _winreg  # type: ignore[import]
    cfg = app.config_manager.config
    cfg.steamcmd_path        = _g(app, "_steamcmd_var",            strip=True)
    cfg.default_install_dir  = _g(app, "_default_dir_var",         strip=True)
    cfg.startup_with_windows = _g(app, "_cfg_startup_var",         tk.BooleanVar)
    cfg.minimize_to_tray     = _g(app, "_cfg_minimize_tray_var",   tk.BooleanVar)
    cfg.log_debug            = _g(app, "_cfg_log_debug_var",       tk.BooleanVar)
    cfg.force_day_on_start_enabled = _g(
        app, "_cfg_force_day_enabled_var", tk.BooleanVar
    )
    try:
        cfg.force_day_on_start = max(0, int(_g(app, "_cfg_force_day_var", strip=True) or "20"))
    except ValueError:
        cfg.force_day_on_start = 20
    cfg.steam_api_key        = _g(app, "_steam_api_key_var",       strip=True)
    _save_discord(app, cfg.discord_notify)
    _save_backup(app, cfg.backup)
    _save_auto_update(app, cfg.auto_update)
    _save_shutdown(app, cfg.shutdown)
    _save_alert_messages(app, cfg.alert_messages)
    _save_discord_bot(app, cfg.discord_bot)
    _save_smtp(app, cfg.smtp)
    _save_startup_registry(app, cfg, _winreg)
    app.config_manager.save()
    messagebox.showinfo("Salvo", "Configurações globais salvas!", parent=app)
