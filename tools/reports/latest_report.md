# ARKLAND-Multi — Project Audit Report

**Gerado em:** 21/05/2026 20:28:09 &nbsp;|&nbsp; **Tempo:** 8.3s &nbsp;|&nbsp; **Score:** 88/100

---

## Resumo

| Métrica | Valor |
|---------|------:|
| Arquivos analisados | 204 |
| Total de issues | 502 |
| Erros | 0 |
| Warnings | 210 |
| Infos | 292 |
| Score geral | **88/100** |

---

## Erros por Categoria

| Categoria | Erros | Warnings | Infos | Total |
|-----------|------:|---------:|------:|------:|
| Imports | 0 | 29 | 274 | 303 |
| Complexidade | 0 | 139 | 0 | 139 |
| Estrutura | 0 | 5 | 8 | 13 |
| Modularização | 0 | 4 | 10 | 14 |
| Tkinter | 0 | 33 | 0 | 33 |

---

## Arquivos Mais Problemáticos (Top 20)

| # | Arquivo | Erros | Warnings | Total |
|--:|---------|------:|---------:|------:|
| 1 | `src\app.py` | 0 | 6 | 38 |
| 2 | `src\ark_ini.py` | 0 | 15 | 16 |
| 3 | `src\server_manager.py` | 0 | 15 | 16 |
| 4 | `src\pages\tab_plugins.py` | 0 | 12 | 13 |
| 5 | `tools\project_audit.py` | 0 | 6 | 9 |
| 6 | `src\pages\tab_crashes.py` | 0 | 5 | 7 |
| 7 | `src\pages\tab_general.py` | 0 | 4 | 7 |
| 8 | `src\pages\tab_loot.py` | 0 | 6 | 7 |
| 9 | `src\pages\tab_spawns.py` | 0 | 6 | 7 |
| 10 | `src\dialogs\remote_control_dialog.py` | 0 | 4 | 6 |
| 11 | `src\pages\ini_import.py` | 0 | 5 | 6 |
| 12 | `src\dialogs\create_buff_dialog.py` | 0 | 4 | 5 |
| 13 | `src\pages\tab_advanced.py` | 0 | 3 | 5 |
| 14 | `src\pages\tab_game.py` | 0 | 3 | 5 |
| 15 | `src\server_config.py` | 0 | 2 | 5 |
| 16 | `src\breeding_calculator.py` | 0 | 2 | 4 |
| 17 | `src\dialogs\mod_ini_dialog.py` | 0 | 3 | 4 |
| 18 | `src\dialogs\mod_search_dialog.py` | 0 | 2 | 4 |
| 19 | `src\dialogs\open_presets_manager.py` | 0 | 2 | 4 |
| 20 | `src\mod_auto_updater.py` | 0 | 3 | 4 |

---

## Sugestões Automáticas

1. Extrair responsabilidades da classe em 'src\app.py'
2. Executar 'ruff check . --fix' para remover ~274 imports não utilizados automaticamente
3. 5 arquivo(s) com UI misturada a lógica — considere padrão MVP/MVC

---

## Todos os Issues

### 🟡 Warnings

| Arquivo | Linha | Código | Mensagem | Fonte |
|---------|------:|--------|----------|-------|
| `src\app.py` | 1 | `SIZE002` | Arquivo grande: 1366 linhas (recomendado: < 1000) | ast |
| `src\app.py` | 98 | `FUNC001` | Função '__init__': 121 linhas (máx: 50) | ast |
| `src\app.py` | 96 | `CLS001` | Classe 'ARKServerManagerApp': 211 métodos (máx: 30) | ast |
| `src\app.py` | 96 | `CLS002` | Classe 'ARKServerManagerApp': 1270 linhas (máx: 500) | ast |
| `src\app.py` | 1069 | `IMP002` | Import duplicado: 'webbrowser' | ast |
| `src\app.py` | 113 | `IMP002` | Import duplicado: 'Image' de 'PIL' | ast |
| `src\ark_ini.py` | 1 | `SIZE002` | Arquivo grande: 1644 linhas (recomendado: < 1000) | ast |
| `src\ark_ini.py` | 347 | `FUNC001` | Função 'populate_config_from_gus': 181 linhas (máx: 50) | ast |
| `src\ark_ini.py` | 530 | `FUNC001` | Função 'populate_config_from_game_ini': 154 linhas (máx: 50) | ast |
| `src\ark_ini.py` | 749 | `FUNC001` | Função '_parse_npc_spawn_container': 51 linhas (máx: 50) | ast |
| `src\ark_ini.py` | 1242 | `FUNC001` | Função 'save_game_user_settings': 130 linhas (máx: 50) | ast |
| `src\ark_ini.py` | 1373 | `FUNC001` | Função 'save_game_ini': 221 linhas (máx: 50) | ast |
| `src\ark_ini.py` | 761 | `IMP002` | Import duplicado: 're' | ast |
| `src\ark_ini.py` | 845 | `IMP002` | Import duplicado: 're' | ast |
| `src\ark_ini.py` | 903 | `IMP002` | Import duplicado: 're' | ast |
| `src\ark_ini.py` | 926 | `IMP002` | Import duplicado: 're' | ast |
| `src\ark_ini.py` | 971 | `IMP002` | Import duplicado: 're' | ast |
| `src\ark_ini.py` | 1016 | `IMP002` | Import duplicado: 're' | ast |
| `src\ark_ini.py` | 1375 | `IMP002` | Import duplicado: 're' | ast |
| `src\ark_ini.py` | 1533 | `IMP002` | Import duplicado: 'io' | ast |
| `src\ark_ini.py` | 1611 | `IMP002` | Import duplicado: 're' | ast |
| `src\backup_manager.py` | 100 | `FUNC001` | Função 'do_backup': 60 linhas (máx: 50) | ast |
| `src\beacon_client.py` | 95 | `FUNC001` | Função 'authenticate_async': 82 linhas (máx: 50) | ast |
| `src\beacon_client.py` | 112 | `FUNC001` | Função '_worker': 63 linhas (máx: 50) | ast |
| `src\breeding_calculator.py` | 231 | `FUNC001` | Função 'open_breeding_calculator': 353 linhas (máx: 50) | ast |
| `src\breeding_calculator.py` | 231 | `FUNC003` | Função 'open_breeding_calculator': 6 funções aninhadas (alta complexidade) | ast |
| `src\change_logger.py` | 89 | `FUNC001` | Função 'snapshot_server': 52 linhas (máx: 50) | ast |
| `src\dialogs\add_server_dialog.py` | 15 | `FUNC001` | Função 'dialog_add_server': 135 linhas (máx: 50) | ast |
| `src\dialogs\add_server_dialog.py` | 15 | `FUNC003` | Função 'dialog_add_server': 4 funções aninhadas (alta complexidade) | ast |
| `src\dialogs\clone_config_dialog.py` | 17 | `FUNC001` | Função 'open_clone_config_dialog': 99 linhas (máx: 50) | ast |
| `src\dialogs\create_buff_dialog.py` | 20 | `FUNC001` | Função 'open_create_buff_dialog': 326 linhas (máx: 50) | ast |
| `src\dialogs\create_buff_dialog.py` | 20 | `FUNC003` | Função 'open_create_buff_dialog': 5 funções aninhadas (alta complexidade) | ast |
| `src\dialogs\create_buff_dialog.py` | 27 | `TK001` | Uso de 'messagebox' sem import explícito | ast |
| `src\dialogs\create_buff_dialog.py` | 1 | `MOD003` | 'create_buff_dialog.py' tem 346 linhas — extrair sub-componentes | ast |
| `src\dialogs\mod_ini_dialog.py` | 16 | `FUNC001` | Função 'open_mod_ini_dialog': 220 linhas (máx: 50) | ast |
| `src\dialogs\mod_ini_dialog.py` | 16 | `FUNC003` | Função 'open_mod_ini_dialog': 4 funções aninhadas (alta complexidade) | ast |
| `src\dialogs\mod_ini_dialog.py` | 58 | `FUNC001` | Função '_show_section_picker': 88 linhas (máx: 50) | ast |
| `src\dialogs\mod_search_dialog.py` | 20 | `FUNC001` | Função 'open_mod_search_dialog': 132 linhas (máx: 50) | ast |
| `src\dialogs\mod_search_dialog.py` | 20 | `FUNC003` | Função 'open_mod_search_dialog': 4 funções aninhadas (alta complexidade) | ast |
| `src\dialogs\open_presets_manager.py` | 10 | `FUNC001` | Função 'open_presets_manager': 65 linhas (máx: 50) | ast |
| `src\dialogs\open_presets_manager.py` | 62 | `TK001` | Uso de 'messagebox' sem import explícito | ast |
| `src\dialogs\remote_control_dialog.py` | 20 | `FUNC001` | Função 'open_remote_control': 236 linhas (máx: 50) | ast |
| `src\dialogs\remote_control_dialog.py` | 20 | `FUNC003` | Função 'open_remote_control': 14 funções aninhadas (alta complexidade) | ast |
| `src\dialogs\remote_control_dialog.py` | 144 | `FUNC001` | Função '_rebuild_servers': 80 linhas (máx: 50) | ast |
| `src\dialogs\remote_control_dialog.py` | 144 | `FUNC003` | Função '_rebuild_servers': 4 funções aninhadas (alta complexidade) | ast |
| `src\dialogs\sync_ini_dialog.py` | 18 | `FUNC001` | Função 'open_sync_ini_dialog': 135 linhas (máx: 50) | ast |
| `src\discord_notifier.py` | 73 | `FUNC001` | Função 'notify_status': 91 linhas (máx: 50) | ast |
| `src\mod_auto_updater.py` | 206 | `FUNC001` | Função '_handle_mod_update': 180 linhas (máx: 50) | ast |
| `src\mod_auto_updater.py` | 410 | `IMP002` | Import duplicado: 'RconClient' de 'rcon_client' | ast |
| `src\mod_auto_updater.py` | 410 | `IMP002` | Import duplicado: 'RconError' de 'rcon_client' | ast |
| `src\mod_manager.py` | 149 | `FUNC001` | Função '_download_worker': 108 linhas (máx: 50) | ast |
| `src\mod_manager.py` | 283 | `FUNC001` | Função '_install_server_worker': 61 linhas (máx: 50) | ast |
| `src\mod_manager.py` | 392 | `FUNC001` | Função '_create_dot_mod_from_mod_info': 94 linhas (máx: 50) | ast |
| `src\pages\add_admin_id.py` | 17 | `TK001` | Uso de 'messagebox' sem import explícito | ast |
| `src\pages\add_mod.py` | 12 | `TK001` | Uso de 'messagebox' sem import explícito | ast |
| `src\pages\broadcast_add.py` | 14 | `TK001` | Uso de 'messagebox' sem import explícito | ast |
| `src\pages\broadcast_delete.py` | 12 | `TK001` | Uso de 'messagebox' sem import explícito | ast |
| `src\pages\broadcast_rcon.py` | 8 | `FUNC001` | Função 'broadcast_rcon': 51 linhas (máx: 50) | ast |
| `src\pages\broadcast_rcon.py` | 33 | `TK001` | Uso de 'messagebox' sem import explícito | ast |
| `src\pages\broadcast_refresh_list.py` | 9 | `FUNC001` | Função 'broadcast_refresh_list': 62 linhas (máx: 50) | ast |
| `src\pages\broadcast_test.py` | 12 | `TK001` | Uso de 'messagebox' sem import explícito | ast |
| `src\pages\build_about.py` | 10 | `FUNC001` | Função 'build_about': 84 linhas (máx: 50) | ast |
| `src\pages\build_auto_update_panel.py` | 11 | `FUNC001` | Função 'build_auto_update_panel': 70 linhas (máx: 50) | ast |
| `src\pages\build_buffs_panel.py` | 10 | `FUNC001` | Função 'build_buffs_panel': 62 linhas (máx: 50) | ast |
| `src\pages\build_clusters_panel.py` | 10 | `FUNC001` | Função 'build_clusters_panel': 52 linhas (máx: 50) | ast |
| `src\pages\build_config_search_bar.py` | 10 | `FUNC001` | Função 'build_config_search_bar': 118 linhas (máx: 50) | ast |
| `src\pages\build_config_search_bar.py` | 10 | `FUNC003` | Função 'build_config_search_bar': 4 funções aninhadas (alta complexidade) | ast |
| `src\pages\build_config_search_bar.py` | 39 | `FUNC001` | Função '_on_change': 84 linhas (máx: 50) | ast |
| `src\pages\build_server_card.py` | 12 | `FUNC001` | Função 'build_server_card': 86 linhas (máx: 50) | ast |
| `src\pages\build_server_card.py` | 12 | `FUNC003` | Função 'build_server_card': 4 funções aninhadas (alta complexidade) | ast |
| `src\pages\build_sync_panel.py` | 10 | `FUNC001` | Função 'build_sync_panel': 99 linhas (máx: 50) | ast |
| `src\pages\build_tab_admins.py` | 11 | `FUNC001` | Função 'build_tab_admins': 74 linhas (máx: 50) | ast |
| `src\pages\build_tab_historico.py` | 11 | `FUNC001` | Função 'build_tab_historico': 52 linhas (máx: 50) | ast |
| `src\pages\cancel_buff.py` | 8 | `TK001` | Uso de 'messagebox' sem import explícito | ast |
| `src\pages\clear_all_mods.py` | 12 | `TK001` | Uso de 'messagebox' sem import explícito | ast |
| `src\pages\cluster_detail.py` | 17 | `FUNC001` | Função 'build_cluster_detail': 303 linhas (máx: 50) | ast |
| `src\pages\cluster_detail.py` | 242 | `IMP002` | Import duplicado: 'os' | ast |
| `src\pages\cluster_save.py` | 9 | `FUNC001` | Função 'cluster_save': 53 linhas (máx: 50) | ast |
| `src\pages\cluster_save.py` | 36 | `IMP002` | Import duplicado: 'os' | ast |
| `src\pages\collect_gpu_info.py` | 7 | `FUNC001` | Função 'collect_gpu_info': 51 linhas (máx: 50) | ast |
| `src\pages\confirm_delete_backup.py` | 9 | `TK001` | Uso de 'messagebox' sem import explícito | ast |
| `src\pages\confirm_remove_server.py` | 10 | `TK001` | Uso de 'messagebox' sem import explícito | ast |
| `src\pages\confirm_restore_backup.py` | 15 | `TK001` | Uso de 'messagebox' sem import explícito | ast |
| `src\pages\do_manual_backup.py` | 22 | `TK001` | Uso de 'messagebox' sem import explícito | ast |
| `src\pages\download_all_mods.py` | 10 | `TK001` | Uso de 'messagebox' sem import explícito | ast |
| `src\pages\download_steamcmd.py` | 9 | `FUNC001` | Função 'download_steamcmd': 78 linhas (máx: 50) | ast |
| `src\pages\download_steamcmd.py` | 31 | `FUNC001` | Função '_worker': 54 linhas (máx: 50) | ast |
| `src\pages\export_profile.py` | 25 | `TK001` | Uso de 'messagebox' sem import explícito | ast |
| `src\pages\get_cluster_health.py` | 8 | `FUNC001` | Função 'get_cluster_health': 156 linhas (máx: 50) | ast |
| `src\pages\get_cpu_temp.py` | 23 | `IMP002` | Import duplicado: 'subprocess' | ast |
| `src\pages\get_nvidia_gpu_pct.py` | 10 | `IMP002` | Import duplicado: 'subprocess' | ast |
| `src\pages\get_nvidia_gpu_temp.py` | 10 | `IMP002` | Import duplicado: 'subprocess' | ast |
| `src\pages\global_config.py` | 14 | `FUNC001` | Função 'build_global_config': 169 linhas (máx: 50) | ast |
| `src\pages\historico_clear.py` | 10 | `TK001` | Uso de 'messagebox' sem import explícito | ast |
| `src\pages\import_profile.py` | 8 | `FUNC001` | Função 'import_profile': 52 linhas (máx: 50) | ast |
| `src\pages\import_profile.py` | 21 | `IMP002` | Import duplicado: 'json' | ast |
| `src\pages\import_profile.py` | 27 | `TK001` | Uso de 'messagebox' sem import explícito | ast |
| `src\pages\ini_import.py` | 17 | `FUNC001` | Função 'import_ini_from_disk': 179 linhas (máx: 50) | ast |
| `src\pages\ini_import.py` | 17 | `FUNC003` | Função 'import_ini_from_disk': 5 funções aninhadas (alta complexidade) | ast |
| `src\pages\ini_import.py` | 74 | `FUNC001` | Função '_do_import': 109 linhas (máx: 50) | ast |
| `src\pages\ini_import.py` | 149 | `IMP002` | Import duplicado: 'threading' | ast |
| `src\pages\ini_import.py` | 100 | `IMP002` | Import duplicado: 'get_ini_path' de 'ark_ini' | ast |
| `src\pages\ini_paste_section.py` | 10 | `FUNC001` | Função 'ini_paste_section': 105 linhas (máx: 50) | ast |
| `src\pages\ini_reload.py` | 9 | `FUNC001` | Função 'ini_reload': 57 linhas (máx: 50) | ast |
| `src\pages\ini_save.py` | 8 | `FUNC001` | Função 'ini_save': 66 linhas (máx: 50) | ast |
| `src\pages\ini_save.py` | 73 | `TK001` | Uso de 'messagebox' sem import explícito | ast |
| `src\pages\minimize_to_tray.py` | 11 | `TK001` | Uso de 'messagebox' sem import explícito | ast |
| `src\pages\on_download_done.py` | 12 | `TK001` | Uso de 'messagebox' sem import explícito | ast |
| `src\pages\on_server_status_change.py` | 11 | `FUNC001` | Função 'on_server_status_change': 77 linhas (máx: 50) | ast |
| `src\pages\on_server_status_change.py` | 12 | `FUNC001` | Função '_do': 75 linhas (máx: 50) | ast |
| `src\pages\perf_monitor_loop.py` | 8 | `FUNC001` | Função 'perf_monitor_loop': 111 linhas (máx: 50) | ast |
| `src\pages\perf_monitor_loop.py` | 35 | `FUNC002` | Função '_update': 8 parâmetros (máx: 7) | ast |
| `src\pages\performance_panel.py` | 15 | `FUNC001` | Função 'build_performance_panel': 165 linhas (máx: 50) | ast |
| `src\pages\player_add_admin.py` | 17 | `TK001` | Uso de 'messagebox' sem import explícito | ast |
| `src\pages\player_ban.py` | 8 | `TK001` | Uso de 'messagebox' sem import explícito | ast |
| `src\pages\player_kick.py` | 8 | `TK001` | Uso de 'messagebox' sem import explícito | ast |
| `src\pages\rcon_auto_connect_tick.py` | 10 | `FUNC001` | Função 'rcon_auto_connect_tick': 60 linhas (máx: 50) | ast |
| `src\pages\rebuild_server_sidebar.py` | 10 | `FUNC001` | Função 'rebuild_server_sidebar': 64 linhas (máx: 50) | ast |
| `src\pages\refresh_buffs_ui.py` | 10 | `FUNC001` | Função 'refresh_buffs_ui': 103 linhas (máx: 50) | ast |
| `src\pages\refresh_mods_list.py` | 11 | `FUNC001` | Função 'refresh_mods_list': 102 linhas (máx: 50) | ast |
| `src\pages\refresh_remote_instances_list.py` | 10 | `FUNC001` | Função 'refresh_remote_instances_list': 121 linhas (máx: 50) | ast |
| `src\pages\refresh_remote_instances_list.py` | 10 | `FUNC003` | Função 'refresh_remote_instances_list': 5 funções aninhadas (alta complexidade) | ast |
| `src\pages\refresh_remote_instances_list.py` | 110 | `TK001` | Uso de 'messagebox' sem import explícito | ast |
| `src\pages\remote_panel.py` | 16 | `FUNC001` | Função 'build_remote_panel': 209 linhas (máx: 50) | ast |
| `src\pages\remote_panel.py` | 16 | `FUNC003` | Função 'build_remote_panel': 7 funções aninhadas (alta complexidade) | ast |
| `src\pages\remote_panel.py` | 128 | `TK001` | Uso de 'messagebox' sem import explícito | ast |
| `src\pages\run_server_install.py` | 9 | `FUNC001` | Função 'run_server_install': 110 linhas (máx: 50) | ast |
| `src\pages\run_server_install.py` | 9 | `FUNC003` | Função 'run_server_install': 12 funções aninhadas (alta complexidade) | ast |
| `src\pages\run_server_install.py` | 12 | `TK001` | Uso de 'messagebox' sem import explícito | ast |
| `src\pages\save_global_config.py` | 27 | `TK001` | Uso de 'messagebox' sem import explícito | ast |
| `src\pages\save_sync_config.py` | 22 | `TK001` | Uso de 'messagebox' sem import explícito | ast |
| `src\pages\server_panel.py` | 20 | `FUNC001` | Função 'build_server_panel': 211 linhas (máx: 50) | ast |
| `src\pages\server_save.py` | 12 | `FUNC001` | Função 'save_server_config': 574 linhas (máx: 50) | ast |
| `src\pages\server_save.py` | 422 | `FUNC001` | Função '_collect_loot_crates': 93 linhas (máx: 50) | ast |
| `src\pages\show_cluster_health_dialog.py` | 10 | `FUNC001` | Função 'show_cluster_health_dialog': 81 linhas (máx: 50) | ast |
| `src\pages\sidebar.py` | 15 | `FUNC001` | Função 'build_sidebar': 105 linhas (máx: 50) | ast |
| `src\pages\start_remote_agent.py` | 25 | `TK001` | Uso de 'messagebox' sem import explícito | ast |
| `src\pages\start_server.py` | 21 | `TK001` | Uso de 'messagebox' sem import explícito | ast |
| `src\pages\tab_advanced.py` | 21 | `FUNC001` | Função 'build_tab_advanced': 549 linhas (máx: 50) | ast |
| `src\pages\tab_advanced.py` | 21 | `FUNC003` | Função 'build_tab_advanced': 7 funções aninhadas (alta complexidade) | ast |
| `src\pages\tab_advanced.py` | 75 | `FUNC002` | Função '_fld': 8 parâmetros (máx: 7) | ast |
| `src\pages\tab_backup.py` | 15 | `FUNC001` | Função 'build_tab_backup': 127 linhas (máx: 50) | ast |
| `src\pages\tab_chat.py` | 18 | `FUNC001` | Função 'build_tab_chat': 181 linhas (máx: 50) | ast |
| `src\pages\tab_crashes.py` | 15 | `FUNC001` | Função 'build_tab_crashes': 212 linhas (máx: 50) | ast |
| `src\pages\tab_crashes.py` | 15 | `FUNC003` | Função 'build_tab_crashes': 4 funções aninhadas (alta complexidade) | ast |
| `src\pages\tab_crashes.py` | 45 | `FUNC001` | Função '_refresh': 59 linhas (máx: 50) | ast |
| `src\pages\tab_crashes.py` | 105 | `FUNC001` | Função '_build_crash_card': 120 linhas (máx: 50) | ast |
| `src\pages\tab_crashes.py` | 73 | `TK001` | Uso de 'messagebox' sem import explícito | ast |
| `src\pages\tab_game.py` | 16 | `FUNC001` | Função 'build_tab_game': 535 linhas (máx: 50) | ast |
| `src\pages\tab_game.py` | 16 | `FUNC003` | Função 'build_tab_game': 20 funções aninhadas (alta complexidade) | ast |
| `src\pages\tab_game.py` | 402 | `FUNC001` | Função '_build_plsm_table': 96 linhas (máx: 50) | ast |
| `src\pages\tab_general.py` | 24 | `FUNC001` | Função 'build_tab_general': 791 linhas (máx: 50) | ast |
| `src\pages\tab_general.py` | 24 | `FUNC003` | Função 'build_tab_general': 13 funções aninhadas (alta complexidade) | ast |
| `src\pages\tab_general.py` | 698 | `FUNC001` | Função '_add_sched_row': 60 linhas (máx: 50) | ast |
| `src\pages\tab_general.py` | 374 | `IMP002` | Import duplicado: 'os' | ast |
| `src\pages\tab_ini_mods.py` | 18 | `FUNC001` | Função 'build_tab_ini_mods': 122 linhas (máx: 50) | ast |
| `src\pages\tab_loot.py` | 15 | `FUNC001` | Função 'build_tab_loot': 295 linhas (máx: 50) | ast |
| `src\pages\tab_loot.py` | 15 | `FUNC003` | Função 'build_tab_loot': 12 funções aninhadas (alta complexidade) | ast |
| `src\pages\tab_loot.py` | 59 | `FUNC001` | Função '_add_entry_row': 70 linhas (máx: 50) | ast |
| `src\pages\tab_loot.py` | 59 | `FUNC002` | Função '_add_entry_row': 10 parâmetros (máx: 7) | ast |
| `src\pages\tab_loot.py` | 130 | `FUNC001` | Função '_add_item_set_row': 79 linhas (máx: 50) | ast |
| `src\pages\tab_loot.py` | 210 | `FUNC001` | Função '_add_crate_card': 85 linhas (máx: 50) | ast |
| `src\pages\tab_mods.py` | 16 | `FUNC001` | Função 'build_tab_mods': 95 linhas (máx: 50) | ast |
| `src\pages\tab_plugins.py` | 1 | `SIZE002` | Arquivo grande: 1562 linhas (recomendado: < 1000) | ast |
| `src\pages\tab_plugins.py` | 24 | `FUNC001` | Função 'build_tab_plugins': 1538 linhas (máx: 50) | ast |
| `src\pages\tab_plugins.py` | 24 | `FUNC003` | Função 'build_tab_plugins': 43 funções aninhadas (alta complexidade) | ast |
| `src\pages\tab_plugins.py` | 557 | `FUNC001` | Função '_add_ek_kit_item': 83 linhas (máx: 50) | ast |
| `src\pages\tab_plugins.py` | 557 | `FUNC002` | Função '_add_ek_kit_item': 8 parâmetros (máx: 7) | ast |
| `src\pages\tab_plugins.py` | 889 | `FUNC001` | Função '_collect_edit_kit': 56 linhas (máx: 50) | ast |
| `src\pages\tab_plugins.py` | 1177 | `FUNC001` | Função '_convert_arkshop': 92 linhas (máx: 50) | ast |
| `src\pages\tab_plugins.py` | 1302 | `FUNC001` | Função '_save_config': 120 linhas (máx: 50) | ast |
| `src\pages\tab_plugins.py` | 1424 | `FUNC001` | Função '_refresh_status': 136 linhas (máx: 50) | ast |
| `src\pages\tab_plugins.py` | 1424 | `FUNC003` | Função '_refresh_status': 4 funções aninhadas (alta complexidade) | ast |
| `src\pages\tab_plugins.py` | 1441 | `FUNC001` | Função '_apply_status': 107 linhas (máx: 50) | ast |
| `src\pages\tab_plugins.py` | 1282 | `TK001` | Uso de 'messagebox' sem import explícito | ast |
| `src\pages\tab_rcon.py` | 15 | `FUNC001` | Função 'build_tab_rcon': 82 linhas (máx: 50) | ast |
| `src\pages\tab_spawns.py` | 16 | `FUNC001` | Função 'build_tab_spawns': 387 linhas (máx: 50) | ast |
| `src\pages\tab_spawns.py` | 16 | `FUNC003` | Função 'build_tab_spawns': 8 funções aninhadas (alta complexidade) | ast |
| `src\pages\tab_spawns.py` | 68 | `FUNC001` | Função '_build_spawn_section': 209 linhas (máx: 50) | ast |
| `src\pages\tab_spawns.py` | 68 | `FUNC003` | Função '_build_spawn_section': 4 funções aninhadas (alta complexidade) | ast |
| `src\pages\tab_spawns.py` | 302 | `FUNC001` | Função '_build_dino_mult_section': 63 linhas (máx: 50) | ast |
| `src\pages\tab_spawns.py` | 100 | `FUNC001` | Função '_add_container': 163 linhas (máx: 50) | ast |
| `src\remote_agent.py` | 110 | `FUNC001` | Função 'start': 182 linhas (máx: 50) | ast |
| `src\remote_agent.py` | 110 | `FUNC003` | Função 'start': 7 funções aninhadas (alta complexidade) | ast |
| `src\remote_agent.py` | 203 | `FUNC001` | Função 'do_POST': 76 linhas (máx: 50) | ast |
| `src\server_config.py` | 584 | `FUNC001` | Função 'build_launch_args': 187 linhas (máx: 50) | ast |
| `src\server_config.py` | 379 | `IMP002` | Import duplicado: 'asdict' de 'dataclasses' | ast |
| `src\server_manager.py` | 1 | `SIZE002` | Arquivo grande: 1177 linhas (recomendado: < 1000) | ast |
| `src\server_manager.py` | 135 | `FUNC001` | Função '_parse_crash_folder': 71 linhas (máx: 50) | ast |
| `src\server_manager.py` | 221 | `FUNC001` | Função '_read_crash_info': 94 linhas (máx: 50) | ast |
| `src\server_manager.py` | 401 | `FUNC001` | Função '_scheduler_tick': 73 linhas (máx: 50) | ast |
| `src\server_manager.py` | 557 | `FUNC001` | Função 'scan_running_servers': 58 linhas (máx: 50) | ast |
| `src\server_manager.py` | 732 | `FUNC001` | Função '_start_worker': 85 linhas (máx: 50) | ast |
| `src\server_manager.py` | 818 | `FUNC001` | Função '_stop_worker': 60 linhas (máx: 50) | ast |
| `src\server_manager.py` | 898 | `FUNC001` | Função '_watch_ark_log': 167 linhas (máx: 50) | ast |
| `src\server_manager.py` | 352 | `CLS002` | Classe 'ServerManager': 826 linhas (máx: 500) | ast |
| `src\server_manager.py` | 137 | `IMP002` | Import duplicado: 're' | ast |
| `src\server_manager.py` | 228 | `IMP002` | Import duplicado: 're' | ast |
| `src\server_manager.py` | 476 | `IMP002` | Import duplicado: 'RconClient' de 'rcon_client' | ast |
| `src\server_manager.py` | 881 | `IMP002` | Import duplicado: 'RconClient' de 'rcon_client' | ast |

> _10 issue(s) adicionais omitidos. Veja `latest_report.json` para lista completa._

### 🔵 Infos

| Arquivo | Linha | Código | Mensagem | Fonte |
|---------|------:|--------|----------|-------|
| `src\app.py` | 4 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\app.py` | 6 | `IMP001` | Import possivelmente não utilizado: 'io' | ast |
| `src\app.py` | 7 | `IMP001` | Import possivelmente não utilizado: 'json' | ast |
| `src\app.py` | 9 | `IMP001` | Import possivelmente não utilizado: 'platform' | ast |
| `src\app.py` | 10 | `IMP001` | Import possivelmente não utilizado: 'socket' | ast |
| `src\app.py` | 11 | `IMP001` | Import possivelmente não utilizado: 'sys' | ast |
| `src\app.py` | 14 | `IMP001` | Import possivelmente não utilizado: 'ttk' | ast |
| `src\app.py` | 16 | `IMP001` | Import possivelmente não utilizado: 'urllib' | ast |
| `src\app.py` | 17 | `IMP001` | Import possivelmente não utilizado: 're' | ast |
| `src\app.py` | 18 | `IMP001` | Import possivelmente não utilizado: 'uuid' | ast |
| `src\app.py` | 20 | `IMP001` | Import possivelmente não utilizado: 'zipfile' | ast |
| `src\app.py` | 21 | `IMP001` | Import possivelmente não utilizado: 'timezone' | ast |
| `src\app.py` | 21 | `IMP001` | Import possivelmente não utilizado: 'timedelta' | ast |
| `src\app.py` | 22 | `IMP001` | Import possivelmente não utilizado: 'Path' | ast |
| `src\app.py` | 23 | `IMP001` | Import possivelmente não utilizado: 'messagebox' | ast |
| `src\app.py` | 24 | `IMP001` | Import possivelmente não utilizado: 'Callable' | ast |
| `src\app.py` | 59 | `IMP001` | Import possivelmente não utilizado: 'ArkIniManager' | ast |
| `src\app.py` | 60 | `IMP001` | Import possivelmente não utilizado: 'open_breeding_calculator' | ast |
| `src\app.py` | 61 | `IMP001` | Import possivelmente não utilizado: 'RconError' | ast |
| `src\app.py` | 73 | `IMP001` | Import possivelmente não utilizado: 'BUILD_DATE' | ast |
| `src\app.py` | 73 | `IMP001` | Import possivelmente não utilizado: 'CHANGELOG' | ast |
| `src\app.py` | 74 | `IMP001` | Import possivelmente não utilizado: 'PluginManager' | ast |
| `src\app.py` | 75 | `IMP001` | Import possivelmente não utilizado: 'snapshot_server' | ast |
| `src\app.py` | 75 | `IMP001` | Import possivelmente não utilizado: 'diff_snapshots' | ast |
| `src\app.py` | 76 | `IMP001` | Import possivelmente não utilizado: 'parse_ini_text_to_sections' | ast |
| `src\app.py` | 76 | `IMP001` | Import possivelmente não utilizado: 'sections_to_ini_text' | ast |
| `src\app.py` | 77 | `IMP001` | Import possivelmente não utilizado: 'build_dynamic_config' | ast |
| `src\app.py` | 79 | `IMP001` | Import possivelmente não utilizado: 'RemoteClient' | ast |
| `src\app.py` | 79 | `IMP001` | Import possivelmente não utilizado: 'make_identity_code' | ast |
| `src\app.py` | 79 | `IMP001` | Import possivelmente não utilizado: 'parse_identity_code' | ast |
| `src\app.py` | 79 | `IMP001` | Import possivelmente não utilizado: 'local_ip' | ast |
| `src\app.py` | 1 | `MOD001` | Mistura UI (15 refs) + lógica (7 refs) — considere separar em camadas | ast |
| `src\ark_ini.py` | 5 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\backup_manager.py` | 9 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\battlemetrics_client.py` | 7 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\beacon_client.py` | 5 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\breeding_calculator.py` | 1 | `SIZE001` | Arquivo acima do recomendado: 608 linhas (alvo: < 500) | ast |
| `src\breeding_calculator.py` | 12 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\buff_manager.py` | 1 | `SIZE001` | Arquivo acima do recomendado: 634 linhas (alvo: < 500) | ast |
| `src\buff_manager.py` | 8 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\buff_manager.py` | 1 | `MOD002` | 4 classes no mesmo arquivo: BuffRates, BuffPreset, BuffEvent, BuffManager… — considere dividir | ast |
| `src\change_logger.py` | 5 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\config_manager.py` | 1 | `MOD002` | 3 classes no mesmo arquivo: DiscordNotifyConfig, AppConfig, ConfigManager… — considere dividir | ast |
| `src\dialogs\add_server_dialog.py` | 1 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\dialogs\clone_config_dialog.py` | 2 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\dialogs\create_buff_dialog.py` | 1 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\dialogs\mod_ini_dialog.py` | 2 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\dialogs\mod_search_dialog.py` | 2 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\dialogs\mod_search_dialog.py` | 1 | `MOD001` | Mistura UI (34 refs) + lógica (6 refs) — considere separar em camadas | ast |
| `src\dialogs\open_presets_manager.py` | 1 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\dialogs\open_presets_manager.py` | 2 | `IMP001` | Import possivelmente não utilizado: 'tk' | ast |
| `src\dialogs\remote_control_dialog.py` | 1 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\dialogs\remote_control_dialog.py` | 1 | `MOD001` | Mistura UI (54 refs) + lógica (7 refs) — considere separar em camadas | ast |
| `src\dialogs\sync_ini_dialog.py` | 2 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\discord_notifier.py` | 8 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\dynamic_config_server.py` | 15 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\mod_auto_updater.py` | 13 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\mod_manager.py` | 6 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\pages\add_admin_id.py` | 1 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\pages\add_mod.py` | 1 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\pages\add_sync_cycle.py` | 1 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\pages\add_sync_folder.py` | 1 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\pages\auto_start_dynamic_configs.py` | 1 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\pages\auto_start_sync.py` | 1 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\pages\auto_start_sync.py` | 2 | `IMP001` | Import possivelmente não utilizado: 'os' | ast |
| `src\pages\broadcast_add.py` | 1 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\pages\broadcast_delete.py` | 1 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\pages\broadcast_edit.py` | 1 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\pages\broadcast_rcon.py` | 1 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\pages\broadcast_refresh_list.py` | 1 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\pages\broadcast_refresh_list.py` | 2 | `IMP001` | Import possivelmente não utilizado: 'tk' | ast |
| `src\pages\broadcast_render_row.py` | 1 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\pages\broadcast_render_row.py` | 2 | `IMP001` | Import possivelmente não utilizado: 'tk' | ast |
| `src\pages\broadcast_send_quick.py` | 1 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\pages\broadcast_test.py` | 1 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\pages\buff_countdown_tick.py` | 1 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\pages\build_about.py` | 1 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\pages\build_active_buff_card.py` | 1 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\pages\build_active_buff_card.py` | 2 | `IMP001` | Import possivelmente não utilizado: 'tk' | ast |
| `src\pages\build_auto_update_panel.py` | 1 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\pages\build_buffs_panel.py` | 1 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\pages\build_clusters_panel.py` | 1 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\pages\build_clusters_panel.py` | 2 | `IMP001` | Import possivelmente não utilizado: 'tk' | ast |
| `src\pages\build_config_search_bar.py` | 1 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\pages\build_dashboard.py` | 1 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\pages\build_dashboard.py` | 2 | `IMP001` | Import possivelmente não utilizado: 'tk' | ast |
| `src\pages\build_history_row.py` | 1 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\pages\build_history_row.py` | 2 | `IMP001` | Import possivelmente não utilizado: 'tk' | ast |
| `src\pages\build_player_row.py` | 1 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\pages\build_player_row.py` | 2 | `IMP001` | Import possivelmente não utilizado: 'tk' | ast |
| `src\pages\build_preset_chip.py` | 1 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\pages\build_preset_chip.py` | 2 | `IMP001` | Import possivelmente não utilizado: 'tk' | ast |
| `src\pages\build_scheduled_buff_row.py` | 1 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\pages\build_scheduled_buff_row.py` | 2 | `IMP001` | Import possivelmente não utilizado: 'tk' | ast |
| `src\pages\build_server_card.py` | 1 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\pages\build_server_card.py` | 2 | `IMP001` | Import possivelmente não utilizado: 'tk' | ast |
| `src\pages\build_static_frames.py` | 1 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\pages\build_static_frames.py` | 2 | `IMP001` | Import possivelmente não utilizado: 'tk' | ast |
| `src\pages\build_sync_panel.py` | 1 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\pages\build_tab_admins.py` | 1 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\pages\build_tab_historico.py` | 1 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\pages\build_tab_jogadores.py` | 1 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\pages\build_tab_logs.py` | 1 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\pages\build_tab_logs.py` | 2 | `IMP001` | Import possivelmente não utilizado: 'tk' | ast |
| `src\pages\cancel_buff.py` | 1 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\pages\chat_append.py` | 1 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\pages\chat_append.py` | 2 | `IMP001` | Import possivelmente não utilizado: 'tk' | ast |
| `src\pages\chat_clear.py` | 1 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\pages\chat_clear.py` | 2 | `IMP001` | Import possivelmente não utilizado: 'tk' | ast |
| `src\pages\chat_fetch.py` | 1 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\pages\chat_poll_loop.py` | 1 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\pages\chat_process.py` | 1 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\pages\chat_send.py` | 1 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\pages\chat_toggle_poll.py` | 1 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\pages\check_updates_manual.py` | 1 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\pages\clear_all_mods.py` | 1 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\pages\clear_server_log.py` | 1 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\pages\clear_server_log.py` | 2 | `IMP001` | Import possivelmente não utilizado: 'tk' | ast |
| `src\pages\cluster_delete.py` | 1 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\pages\cluster_detail.py` | 1 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\pages\cluster_import_from_manual.py` | 1 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\pages\cluster_new.py` | 1 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\pages\cluster_save.py` | 1 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\pages\cluster_save.py` | 2 | `IMP001` | Import possivelmente não utilizado: 'os' | ast |
| `src\pages\cluster_sync_once.py` | 1 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\pages\cluster_sync_start.py` | 1 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\pages\clusters_refresh_list.py` | 1 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\pages\clusters_refresh_list.py` | 2 | `IMP001` | Import possivelmente não utilizado: 'tk' | ast |
| `src\pages\collect_gpu_info.py` | 1 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\pages\collect_server_stats.py` | 1 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\pages\confirm_delete_backup.py` | 1 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\pages\confirm_remove_server.py` | 1 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\pages\confirm_restore_backup.py` | 1 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\pages\do_manual_backup.py` | 1 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\pages\do_quit.py` | 1 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\pages\do_quit.py` | 2 | `IMP001` | Import possivelmente não utilizado: 'os' | ast |
| `src\pages\do_restore.py` | 1 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\pages\download_all_mods.py` | 1 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\pages\download_mod.py` | 1 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\pages\download_steamcmd.py` | 1 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\pages\export_profile.py` | 1 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\pages\fast_fill.py` | 1 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\pages\fast_fill.py` | 2 | `IMP001` | Import possivelmente não utilizado: 'tk' | ast |
| `src\pages\fetch_mod_names_async.py` | 1 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\pages\fetch_steam_name.py` | 1 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\pages\force_sync_once.py` | 1 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\pages\format_countdown.py` | 1 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\pages\get_change_logger.py` | 1 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\pages\get_cluster_health.py` | 1 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\pages\get_cpu_temp.py` | 1 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\pages\get_nvidia_gpu_pct.py` | 1 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\pages\get_nvidia_gpu_temp.py` | 1 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\pages\global_config.py` | 1 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\pages\historico_clear.py` | 1 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\pages\historico_refresh.py` | 1 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\pages\import_profile.py` | 1 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\pages\ini_add_entry.py` | 1 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\pages\ini_add_entry.py` | 2 | `IMP001` | Import possivelmente não utilizado: 'tk' | ast |
| `src\pages\ini_add_entry.py` | 4 | `IMP001` | Import possivelmente não utilizado: 'ctk' | ast |
| `src\pages\ini_add_section.py` | 1 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\pages\ini_add_section.py` | 2 | `IMP001` | Import possivelmente não utilizado: 'tk' | ast |
| `src\pages\ini_del_entry.py` | 1 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\pages\ini_delete_section.py` | 1 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\pages\ini_flush_current.py` | 1 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\pages\ini_import.py` | 1 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\pages\ini_paste_section.py` | 1 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\pages\ini_rebuild_section_list.py` | 1 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\pages\ini_rebuild_section_list.py` | 3 | `IMP001` | Import possivelmente não utilizado: 'tk' | ast |
| `src\pages\ini_reload.py` | 1 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\pages\ini_reload.py` | 2 | `IMP001` | Import possivelmente não utilizado: 'tk' | ast |
| `src\pages\ini_render_entry_row.py` | 1 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\pages\ini_render_section_item.py` | 1 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\pages\ini_render_section_item.py` | 2 | `IMP001` | Import possivelmente não utilizado: 'tk' | ast |
| `src\pages\ini_save.py` | 1 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\pages\ini_select_section.py` | 1 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\pages\init_backup_manager.py` | 1 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\pages\init_buff_manager.py` | 1 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\pages\log_perf_critical.py` | 1 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\pages\lookup_admin_preview.py` | 1 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\pages\minimize_to_tray.py` | 1 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\pages\on_auto_updater_log.py` | 1 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\pages\on_bm_update.py` | 1 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\pages\on_bm_update.py` | 3 | `IMP001` | Import possivelmente não utilizado: 'tk' | ast |
| `src\pages\on_download_done.py` | 1 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\pages\on_server_log.py` | 1 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\pages\on_server_log.py` | 2 | `IMP001` | Import possivelmente não utilizado: 'tk' | ast |
| `src\pages\on_server_status_change.py` | 1 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\pages\on_server_visibility_change.py` | 1 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\pages\on_server_visibility_change.py` | 2 | `IMP001` | Import possivelmente não utilizado: 'tk' | ast |
| `src\pages\on_sync_log.py` | 1 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\pages\on_sync_stats.py` | 1 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\pages\on_sync_status.py` | 1 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\pages\on_update_result.py` | 1 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\pages\on_update_result.py` | 2 | `IMP001` | Import possivelmente não utilizado: 'tk' | ast |
| `src\pages\open_server_panel.py` | 1 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\pages\open_server_panel.py` | 2 | `IMP001` | Import possivelmente não utilizado: 'tk' | ast |
| `src\pages\perf_monitor_loop.py` | 1 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\pages\performance_panel.py` | 1 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\pages\player_add_admin.py` | 1 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\pages\player_ban.py` | 1 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |

> _92 issue(s) adicionais omitidos. Veja `latest_report.json` para lista completa._
