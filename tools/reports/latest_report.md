# ARKLAND-Multi — Project Audit Report

**Gerado em:** 13/06/2026 08:48:34 &nbsp;|&nbsp; **Tempo:** 10.1s &nbsp;|&nbsp; **Score:** 76/100

---

## Resumo

| Métrica | Valor |
|---------|------:|
| Arquivos analisados | 299 |
| Total de issues | 946 |
| Erros | 28 |
| Warnings | 536 |
| Infos | 382 |
| Score geral | **76/100** |

---

## Erros por Categoria

| Categoria | Erros | Warnings | Infos | Total |
|-----------|------:|---------:|------:|------:|
| Imports | 1 | 200 | 336 | 537 |
| Complexidade | 0 | 310 | 0 | 310 |
| Estrutura | 27 | 8 | 21 | 56 |
| Modularização | 0 | 18 | 25 | 43 |

---

## Arquivos Mais Problemáticos (Top 20)

| # | Arquivo | Erros | Warnings | Total |
|--:|---------|------:|---------:|------:|
| 1 | `src\asm_ui\asm_server_panel.py` | 1 | 121 | 124 |
| 2 | `src\app.py` | 1 | 40 | 43 |
| 3 | `src\app_tek.py` | 1 | 26 | 30 |
| 4 | `src\server_manager.py` | 0 | 19 | 21 |
| 5 | `src\pages\customshop_panel.py` | 0 | 18 | 20 |
| 6 | `src\pages\db_manager_panel.py` | 0 | 16 | 19 |
| 7 | `src\ark_ini.py` | 0 | 15 | 16 |
| 8 | `src\pages\tab_crashes.py` | 0 | 8 | 11 |
| 9 | `src\asm_engine\asm_ini_manager.py` | 0 | 8 | 10 |
| 10 | `src\asm_engine\asm_steamcmd.py` | 0 | 7 | 10 |
| 11 | `src\asm_ui\asm_ai_assistant.py` | 0 | 6 | 10 |
| 12 | `src\asm_ui\asm_dashboard.py` | 0 | 7 | 10 |
| 13 | `src\shop_integration.py` | 0 | 8 | 10 |
| 14 | `src\mod_manager.py` | 0 | 7 | 9 |
| 15 | `tools\project_audit.py` | 0 | 6 | 9 |
| 16 | `src\asm_ui\asm_add_server_dialog.py` | 0 | 7 | 8 |
| 17 | `src\asm_ui\spawn_exact_panel.py` | 0 | 6 | 8 |
| 18 | `src\pages\tab_game.py` | 0 | 7 | 8 |
| 19 | `src\remote_agent.py` | 0 | 6 | 8 |
| 20 | `src\ui\server_field_widgets.py` | 0 | 6 | 8 |

---

## Sugestões Automáticas

1. Revisar urgente 'src\app.py' — 1 erro(s) crítico(s)
2. Revisar urgente 'src\app_tek.py' — 1 erro(s) crítico(s)
3. Revisar urgente 'src\asm_ui\asm_server_panel.py' — 1 erro(s) crítico(s)
4. Revisar urgente 'src\dialogs\add_server_dialog.py' — 1 erro(s) crítico(s)
5. Revisar urgente 'src\dialogs\remote_control_dialog.py' — 1 erro(s) crítico(s)
6. Resolver 1 dependência(s) circular(es) — pode causar ImportError em runtime
7. Dividir 'src\app.py' (arquivo enorme)
8. Dividir 'src\asm_ui\asm_server_panel.py' (arquivo enorme)
9. Extrair responsabilidades da classe em 'src\app.py'
10. Extrair responsabilidades da classe em 'src\app_tek.py'
11. Extrair responsabilidades da classe em 'src\asm_ui\spawn_exact_panel.py'
12. Executar 'ruff check . --fix' para remover ~336 imports não utilizados automaticamente
13. 15 arquivo(s) com UI misturada a lógica — considere padrão MVP/MVC

---

## Todos os Issues

### 🔴 Erros

| Arquivo | Linha | Código | Mensagem | Fonte |
|---------|------:|--------|----------|-------|
| `src\app.py` | 1 | `SIZE003` | Arquivo enorme: 4099 linhas (limite: 3000) | ast |
| `src\asm_ui\asm_server_panel.py` | 1 | `SIZE003` | Arquivo enorme: 3875 linhas (limite: 3000) | ast |
| `src\dialogs\add_server_dialog.py` | 1 | `AST001` | SyntaxError: invalid non-printable character U+FEFF | ast |
| `src\dialogs\remote_control_dialog.py` | 1 | `AST001` | SyntaxError: invalid non-printable character U+FEFF | ast |
| `src\pages\broadcast_edit.py` | 1 | `AST001` | SyntaxError: invalid non-printable character U+FEFF | ast |
| `src\pages\build_static_frames.py` | 1 | `AST001` | SyntaxError: invalid non-printable character U+FEFF | ast |
| `src\pages\chat_process.py` | 1 | `AST001` | SyntaxError: invalid non-printable character U+FEFF | ast |
| `src\pages\chat_send.py` | 1 | `AST001` | SyntaxError: invalid non-printable character U+FEFF | ast |
| `src\pages\cluster_delete.py` | 1 | `AST001` | SyntaxError: invalid non-printable character U+FEFF | ast |
| `src\pages\cluster_sync_once.py` | 1 | `AST001` | SyntaxError: invalid non-printable character U+FEFF | ast |
| `src\pages\cluster_sync_start.py` | 1 | `AST001` | SyntaxError: invalid non-printable character U+FEFF | ast |
| `src\pages\collect_gpu_info.py` | 1 | `AST001` | SyntaxError: invalid non-printable character U+FEFF | ast |
| `src\pages\download_steamcmd.py` | 1 | `AST001` | SyntaxError: invalid non-printable character U+FEFF | ast |
| `src\pages\fetch_mod_names_async.py` | 1 | `AST001` | SyntaxError: invalid non-printable character U+FEFF | ast |
| `src\pages\fetch_steam_name.py` | 1 | `AST001` | SyntaxError: invalid non-printable character U+FEFF | ast |
| `src\pages\ini_import.py` | 1 | `AST001` | SyntaxError: invalid non-printable character U+FEFF | ast |
| `src\pages\ini_paste_section.py` | 1 | `AST001` | SyntaxError: invalid non-printable character U+FEFF | ast |
| `src\pages\log_perf_critical.py` | 1 | `AST001` | SyntaxError: invalid non-printable character U+FEFF | ast |
| `src\pages\on_sync_log.py` | 1 | `AST001` | SyntaxError: invalid non-printable character U+FEFF | ast |
| `src\pages\on_update_result.py` | 1 | `AST001` | SyntaxError: invalid non-printable character U+FEFF | ast |
| `src\pages\open_server_panel.py` | 1 | `AST001` | SyntaxError: invalid non-printable character U+FEFF | ast |
| `src\pages\perf_monitor_loop.py` | 1 | `AST001` | SyntaxError: invalid non-printable character U+FEFF | ast |
| `src\pages\performance_panel.py` | 1 | `AST001` | SyntaxError: invalid non-printable character U+FEFF | ast |
| `src\pages\rebuild_server_panel.py` | 1 | `AST001` | SyntaxError: invalid non-printable character U+FEFF | ast |
| `src\pages\remote_panel.py` | 1 | `AST001` | SyntaxError: invalid non-printable character U+FEFF | ast |
| `src\pages\show_cluster_health_dialog.py` | 1 | `AST001` | SyntaxError: invalid non-printable character U+FEFF | ast |
| `src\pages\toast.py` | 1 | `AST001` | SyntaxError: invalid non-printable character U+FEFF | ast |
| `src\app_tek.py` | 1 | `IMP004` | Dependência circular: src.app_tek → src.pages.build_sidebar_tek → src.app_tek | ast |

### 🟡 Warnings

| Arquivo | Linha | Código | Mensagem | Fonte |
|---------|------:|--------|----------|-------|
| `src\app.py` | 139 | `FUNC001` | Função '__init__': 67 linhas (máx: 50) | ast |
| `src\app.py` | 221 | `FUNC001` | Função '_build_sidebar': 71 linhas (máx: 50) | ast |
| `src\app.py` | 359 | `FUNC001` | Função '_build_sync_panel': 96 linhas (máx: 50) | ast |
| `src\app.py` | 605 | `FUNC001` | Função '_build_server_card': 66 linhas (máx: 50) | ast |
| `src\app.py` | 690 | `FUNC001` | Função '_build_server_panel': 123 linhas (máx: 50) | ast |
| `src\app.py` | 818 | `FUNC001` | Função '_build_tab_general': 192 linhas (máx: 50) | ast |
| `src\app.py` | 1015 | `FUNC001` | Função '_build_tab_game': 335 linhas (máx: 50) | ast |
| `src\app.py` | 1015 | `FUNC003` | Função '_build_tab_game': 4 funções aninhadas (alta complexidade) | ast |
| `src\app.py` | 1355 | `FUNC001` | Função '_build_tab_advanced': 229 linhas (máx: 50) | ast |
| `src\app.py` | 1589 | `FUNC001` | Função '_build_tab_mods': 63 linhas (máx: 50) | ast |
| `src\app.py` | 1653 | `FUNC001` | Função '_build_auto_update_panel': 70 linhas (máx: 50) | ast |
| `src\app.py` | 1764 | `FUNC001` | Função '_refresh_mods_list': 62 linhas (máx: 50) | ast |
| `src\app.py` | 1827 | `FUNC001` | Função '_open_mod_search_dialog': 132 linhas (máx: 50) | ast |
| `src\app.py` | 1827 | `FUNC003` | Função '_open_mod_search_dialog': 4 funções aninhadas (alta complexidade) | ast |
| `src\app.py` | 1985 | `FUNC001` | Função '_build_tab_plugins': 84 linhas (máx: 50) | ast |
| `src\app.py` | 2072 | `FUNC001` | Função '_refresh_plugins_list': 120 linhas (máx: 50) | ast |
| `src\app.py` | 2233 | `FUNC001` | Função '_install_plugin_from_zip': 60 linhas (máx: 50) | ast |
| `src\app.py` | 2372 | `FUNC001` | Função '_build_tab_rcon': 82 linhas (máx: 50) | ast |
| `src\app.py` | 2492 | `FUNC001` | Função '_build_global_config': 104 linhas (máx: 50) | ast |
| `src\app.py` | 2601 | `FUNC001` | Função '_build_about': 84 linhas (máx: 50) | ast |
| `src\app.py` | 2728 | `FUNC001` | Função '_run_server_install': 68 linhas (máx: 50) | ast |
| `src\app.py` | 2728 | `FUNC003` | Função '_run_server_install': 8 funções aninhadas (alta complexidade) | ast |
| `src\app.py` | 2797 | `FUNC001` | Função '_save_server_config': 175 linhas (máx: 50) | ast |
| `src\app.py` | 2975 | `FUNC001` | Função '_import_ini_from_disk': 188 linhas (máx: 50) | ast |
| `src\app.py` | 3185 | `FUNC001` | Função '_open_sync_ini_dialog': 137 linhas (máx: 50) | ast |
| `src\app.py` | 3353 | `FUNC001` | Função '_open_mod_ini_dialog': 111 linhas (máx: 50) | ast |
| `src\app.py` | 3700 | `FUNC001` | Função '_dialog_add_server': 80 linhas (máx: 50) | ast |
| `src\app.py` | 3939 | `FUNC001` | Função '_download_steamcmd': 78 linhas (máx: 50) | ast |
| `src\app.py` | 3031 | `FUNC001` | Função '_do_import': 121 linhas (máx: 50) | ast |
| `src\app.py` | 3961 | `FUNC001` | Função '_worker': 54 linhas (máx: 50) | ast |
| `src\app.py` | 3055 | `FUNC001` | Função '_load_from_folder': 77 linhas (máx: 50) | ast |
| `src\app.py` | 137 | `CLS001` | Classe 'ARKServerManagerApp': 133 métodos (máx: 30) | ast |
| `src\app.py` | 137 | `CLS002` | Classe 'ARKServerManagerApp': 3963 linhas (máx: 500) | ast |
| `src\app.py` | 3198 | `IMP002` | Import duplicado: 'get_ini_path' de 'ark_ini' | ast |
| `src\app.py` | 3488 | `IMP002` | Import duplicado: 'webbrowser' | ast |
| `src\app.py` | 230 | `IMP002` | Import duplicado: 'Image' de 'PIL' | ast |
| `src\app.py` | 3284 | `IMP002` | Import duplicado: 'shutil' | ast |
| `src\app.py` | 3437 | `IMP002` | Import duplicado: 'ArkIniManager' de 'ark_ini' | ast |
| `src\app.py` | 3983 | `IMP002` | Import duplicado: 'subprocess' | ast |
| `src\app.py` | 154 | `IMP002` | Import duplicado: 'Image' de 'PIL' | ast |
| `src\app_tek.py` | 1 | `SIZE002` | Arquivo grande: 1575 linhas (recomendado: < 1000) | ast |
| `src\app_tek.py` | 48 | `FUNC001` | Função '__init__': 118 linhas (máx: 50) | ast |
| `src\app_tek.py` | 171 | `FUNC001` | Função '_asm_status_tick': 82 linhas (máx: 50) | ast |
| `src\app_tek.py` | 417 | `FUNC001` | Função '_build_sidebar_inline': 141 linhas (máx: 50) | ast |
| `src\app_tek.py` | 656 | `FUNC001` | Função '_show_frame_inline': 67 linhas (máx: 50) | ast |
| `src\app_tek.py` | 1077 | `FUNC001` | Função '_save_global_config': 117 linhas (máx: 50) | ast |
| `src\app_tek.py` | 175 | `FUNC001` | Função '_worker': 68 linhas (máx: 50) | ast |
| `src\app_tek.py` | 42 | `CLS001` | Classe 'ARKServerManagerApp': 121 métodos (máx: 30) | ast |
| `src\app_tek.py` | 42 | `CLS002` | Classe 'ARKServerManagerApp': 1530 linhas (máx: 500) | ast |
| `src\app_tek.py` | 297 | `IMP002` | Import duplicado: 'tkinter' | ast |
| `src\app_tek.py` | 313 | `IMP002` | Import duplicado: 'threading' | ast |
| `src\app_tek.py` | 370 | `IMP002` | Import duplicado: 'json' | ast |
| `src\app_tek.py` | 782 | `IMP002` | Import duplicado: 'effective_session_name' de 'asm_engine.asm_ini_manager' | ast |
| `src\app_tek.py` | 798 | `IMP002` | Import duplicado: 'messagebox' de 'tkinter' | ast |
| `src\app_tek.py` | 936 | `IMP002` | Import duplicado: 'open_asm_workshop' de 'asm_ui.asm_workshop' | ast |
| `src\app_tek.py` | 950 | `IMP002` | Import duplicado: 'threading' | ast |
| `src\app_tek.py` | 979 | `IMP002` | Import duplicado: 'threading' | ast |
| `src\app_tek.py` | 999 | `IMP002` | Import duplicado: 'threading' | ast |
| `src\app_tek.py` | 1312 | `IMP002` | Import duplicado: 'APP_VERSION' de 'version' | ast |
| `src\app_tek.py` | 1435 | `IMP002` | Import duplicado: 'logging' | ast |
| `src\app_tek.py` | 1476 | `IMP002` | Import duplicado: 'threading' | ast |
| `src\app_tek.py` | 439 | `IMP002` | Import duplicado: 'Image' de 'PIL' | ast |
| `src\app_tek.py` | 972 | `IMP002` | Import duplicado: 'logging' | ast |
| `src\app_tek.py` | 992 | `IMP002` | Import duplicado: 'logging' | ast |
| `src\app_tek.py` | 1006 | `IMP002` | Import duplicado: 'RconClient' de 'rcon_client' | ast |
| `src\app_tek.py` | 215 | `IMP002` | Import duplicado: 'RconClient' de 'rcon_client' | ast |
| `src\ark_ini.py` | 1 | `SIZE002` | Arquivo grande: 1728 linhas (recomendado: < 1000) | ast |
| `src\ark_ini.py` | 377 | `FUNC001` | Função 'populate_config_from_gus': 184 linhas (máx: 50) | ast |
| `src\ark_ini.py` | 563 | `FUNC001` | Função 'populate_config_from_game_ini': 155 linhas (máx: 50) | ast |
| `src\ark_ini.py` | 827 | `FUNC001` | Função '_parse_npc_spawn_container': 51 linhas (máx: 50) | ast |
| `src\ark_ini.py` | 1321 | `FUNC001` | Função 'save_game_user_settings': 134 linhas (máx: 50) | ast |
| `src\ark_ini.py` | 1456 | `FUNC001` | Função 'save_game_ini': 222 linhas (máx: 50) | ast |
| `src\ark_ini.py` | 839 | `IMP002` | Import duplicado: 're' | ast |
| `src\ark_ini.py` | 923 | `IMP002` | Import duplicado: 're' | ast |
| `src\ark_ini.py` | 981 | `IMP002` | Import duplicado: 're' | ast |
| `src\ark_ini.py` | 1004 | `IMP002` | Import duplicado: 're' | ast |
| `src\ark_ini.py` | 1049 | `IMP002` | Import duplicado: 're' | ast |
| `src\ark_ini.py` | 1094 | `IMP002` | Import duplicado: 're' | ast |
| `src\ark_ini.py` | 1458 | `IMP002` | Import duplicado: 're' | ast |
| `src\ark_ini.py` | 1617 | `IMP002` | Import duplicado: 'io' | ast |
| `src\ark_ini.py` | 1695 | `IMP002` | Import duplicado: 're' | ast |
| `src\asm_engine\asm_cloud_backup.py` | 159 | `IMP002` | Import duplicado: 'boto3' | ast |
| `src\asm_engine\asm_cloud_backup.py` | 199 | `IMP002` | Import duplicado: 'boto3' | ast |
| `src\asm_engine\asm_cloud_backup.py` | 222 | `IMP002` | Import duplicado: 'boto3' | ast |
| `src\asm_engine\asm_game_list_ini.py` | 161 | `FUNC001` | Função 'populate_lists_from_game_ini': 52 linhas (máx: 50) | ast |
| `src\asm_engine\asm_ini_manager.py` | 367 | `FUNC001` | Função 'write_ini': 126 linhas (máx: 50) | ast |
| `src\asm_engine\asm_ini_manager.py` | 530 | `FUNC001` | Função 'read_ini': 91 linhas (máx: 50) | ast |
| `src\asm_engine\asm_ini_manager.py` | 623 | `FUNC001` | Função 'read_ini_from_paths': 83 linhas (máx: 50) | ast |
| `src\asm_engine\asm_ini_manager.py` | 741 | `FUNC001` | Função '_launch_dash_flags': 90 linhas (máx: 50) | ast |
| `src\asm_engine\asm_ini_manager.py` | 601 | `IMP002` | Import duplicado: 're' | ast |
| `src\asm_engine\asm_ini_manager.py` | 686 | `IMP002` | Import duplicado: 're' | ast |
| `src\asm_engine\asm_ini_manager.py` | 656 | `IMP002` | Import duplicado: 'fields' de 'dataclasses' | ast |
| `src\asm_engine\asm_ini_manager.py` | 704 | `IMP002` | Import duplicado: 'populate_lists_from_game_ini' de 'asm_game_list_ini' | ast |
| `src\asm_engine\asm_server_manager.py` | 197 | `FUNC001` | Função 'scan_running_servers': 56 linhas (máx: 50) | ast |
| `src\asm_engine\asm_server_manager.py` | 293 | `FUNC001` | Função '_start_worker': 101 linhas (máx: 50) | ast |
| `src\asm_engine\asm_server_manager.py` | 519 | `IMP002` | Import duplicado: 'psutil' | ast |
| `src\asm_engine\asm_steamcmd.py` | 336 | `FUNC001` | Função '_worker': 74 linhas (máx: 50) | ast |
| `src\asm_engine\asm_steamcmd.py` | 477 | `FUNC001` | Função '_create_dot_mod_from_mod_info': 59 linhas (máx: 50) | ast |
| `src\asm_engine\asm_steamcmd.py` | 537 | `FUNC001` | Função '_copy_mod_to_server': 59 linhas (máx: 50) | ast |
| `src\asm_engine\asm_steamcmd.py` | 37 | `CLS002` | Classe 'AsmSteamCmd': 559 linhas (máx: 500) | ast |
| `src\asm_engine\asm_steamcmd.py` | 281 | `IMP002` | Import duplicado: 'subprocess' | ast |
| `src\asm_engine\asm_steamcmd.py` | 308 | `IMP002` | Import duplicado: 're' | ast |
| `src\asm_engine\asm_steamcmd.py` | 439 | `IMP002` | Import duplicado: 're' | ast |
| `src\asm_ui\asm_add_server_dialog.py` | 134 | `FUNC001` | Função 'asm_add_server_dialog': 274 linhas (máx: 50) | ast |
| `src\asm_ui\asm_add_server_dialog.py` | 134 | `FUNC003` | Função 'asm_add_server_dialog': 13 funções aninhadas (alta complexidade) | ast |
| `src\asm_ui\asm_add_server_dialog.py` | 265 | `FUNC001` | Função '_show_import_dir': 70 linhas (máx: 50) | ast |
| `src\asm_ui\asm_add_server_dialog.py` | 337 | `FUNC001` | Função '_show_import_profile': 58 linhas (máx: 50) | ast |
| `src\asm_ui\asm_add_server_dialog.py` | 357 | `IMP002` | Import duplicado: 'filedialog' de 'tkinter' | ast |
| `src\asm_ui\asm_add_server_dialog.py` | 202 | `IMP002` | Import duplicado: 'filedialog' de 'tkinter' | ast |
| `src\asm_ui\asm_add_server_dialog.py` | 1 | `MOD003` | 'asm_add_server_dialog.py' tem 407 linhas — extrair sub-componentes | ast |
| `src\asm_ui\asm_ai_assistant.py` | 53 | `FUNC001` | Função '_offline_advice': 64 linhas (máx: 50) | ast |
| `src\asm_ui\asm_ai_assistant.py` | 221 | `FUNC001` | Função '_build_ui': 103 linhas (máx: 50) | ast |
| `src\asm_ui\asm_ai_assistant.py` | 331 | `FUNC001` | Função '_open_help': 140 linhas (máx: 50) | ast |
| `src\asm_ui\asm_ai_assistant.py` | 331 | `FUNC003` | Função '_open_help': 5 funções aninhadas (alta complexidade) | ast |
| `src\asm_ui\asm_ai_assistant.py` | 586 | `IMP002` | Import duplicado: 'Path' de 'pathlib' | ast |
| `src\asm_ui\asm_ai_assistant.py` | 587 | `IMP002` | Import duplicado: 'os' | ast |
| `src\asm_ui\asm_dashboard.py` | 49 | `FUNC001` | Função 'build_asm_dashboard': 161 linhas (máx: 50) | ast |
| `src\asm_ui\asm_dashboard.py` | 212 | `FUNC001` | Função '_refresh_asm_dashboard': 192 linhas (máx: 50) | ast |
| `src\asm_ui\asm_dashboard.py` | 212 | `FUNC003` | Função '_refresh_asm_dashboard': 6 funções aninhadas (alta complexidade) | ast |
| `src\asm_ui\asm_dashboard.py` | 282 | `IMP002` | Import duplicado: 'threading' | ast |
| `src\asm_ui\asm_dashboard.py` | 290 | `IMP002` | Import duplicado: 'threading' | ast |
| `src\asm_ui\asm_dashboard.py` | 300 | `IMP002` | Import duplicado: 'threading' | ast |
| `src\asm_ui\asm_dashboard.py` | 375 | `IMP002` | Import duplicado: 'threading' | ast |
| `src\asm_ui\asm_engram_editor.py` | 198 | `FUNC001` | Função '_refresh_table': 54 linhas (máx: 50) | ast |
| `src\asm_ui\asm_engram_editor.py` | 267 | `IMP002` | Import duplicado: 're' | ast |
| `src\asm_ui\asm_file_manager.py` | 112 | `FUNC001` | Função '__init__': 92 linhas (máx: 50) | ast |
| `src\asm_ui\asm_file_manager.py` | 255 | `FUNC001` | Função '_render_listing': 96 linhas (máx: 50) | ast |
| `src\asm_ui\asm_file_manager.py` | 366 | `FUNC001` | Função '_open_editor_window': 59 linhas (máx: 50) | ast |
| `src\asm_ui\asm_firewall.py` | 140 | `FUNC001` | Função '__init__': 85 linhas (máx: 50) | ast |
| `src\asm_ui\asm_firewall.py` | 277 | `IMP002` | Import duplicado: 'threading' | ast |
| `src\asm_ui\asm_import_ini_dialog.py` | 327 | `FUNC001` | Função '_build_file_section': 58 linhas (máx: 50) | ast |
| `src\asm_ui\asm_import_ini_dialog.py` | 388 | `FUNC001` | Função '_build_categories_section': 56 linhas (máx: 50) | ast |
| `src\asm_ui\asm_import_ini_dialog.py` | 485 | `FUNC001` | Função '_build_sync_section': 63 linhas (máx: 50) | ast |
| `src\asm_ui\asm_import_ini_dialog.py` | 1 | `MOD003` | 'asm_import_ini_dialog.py' tem 714 linhas — extrair sub-componentes | ast |
| `src\asm_ui\asm_monitor_window.py` | 121 | `FUNC001` | Função '_build_ui': 57 linhas (máx: 50) | ast |
| `src\asm_ui\asm_perf_chart.py` | 57 | `FUNC001` | Função '__init__': 64 linhas (máx: 50) | ast |
| `src\asm_ui\asm_perf_chart.py` | 156 | `IMP002` | Import duplicado: 'psutil' | ast |
| `src\asm_ui\asm_player_list.py` | 85 | `FUNC001` | Função '__init__': 104 linhas (máx: 50) | ast |
| `src\asm_ui\asm_player_list.py` | 222 | `FUNC001` | Função '_render': 78 linhas (máx: 50) | ast |
| `src\asm_ui\asm_rcon_window.py` | 74 | `FUNC001` | Função '__init__': 147 linhas (máx: 50) | ast |
| `src\asm_ui\asm_save_restore.py` | 89 | `FUNC001` | Função '__init__': 96 linhas (máx: 50) | ast |
| `src\asm_ui\asm_save_restore.py` | 188 | `FUNC001` | Função '_reload_list': 71 linhas (máx: 50) | ast |
| `src\asm_ui\asm_server_card.py` | 56 | `FUNC001` | Função 'build_asm_server_card': 309 linhas (máx: 50) | ast |
| `src\asm_ui\asm_server_card.py` | 56 | `FUNC003` | Função 'build_asm_server_card': 7 funções aninhadas (alta complexidade) | ast |
| `src\asm_ui\asm_server_log_window.py` | 57 | `FUNC001` | Função '_build_ui': 71 linhas (máx: 50) | ast |
| `src\asm_ui\asm_server_panel.py` | 109 | `FUNC001` | Função 'build_asm_server_panel': 508 linhas (máx: 50) | ast |
| `src\asm_ui\asm_server_panel.py` | 109 | `FUNC003` | Função 'build_asm_server_panel': 18 funções aninhadas (alta complexidade) | ast |
| `src\asm_ui\asm_server_panel.py` | 670 | `FUNC002` | Função '_str_entry': 10 parâmetros (máx: 7) | ast |
| `src\asm_ui\asm_server_panel.py` | 705 | `FUNC002` | Função '_bool_check': 9 parâmetros (máx: 7) | ast |
| `src\asm_ui\asm_server_panel.py` | 870 | `FUNC001` | Função '_build_administracao': 532 linhas (máx: 50) | ast |
| `src\asm_ui\asm_server_panel.py` | 870 | `FUNC003` | Função '_build_administracao': 24 funções aninhadas (alta complexidade) | ast |
| `src\asm_ui\asm_server_panel.py` | 1498 | `FUNC001` | Função '_build_rules': 73 linhas (máx: 50) | ast |
| `src\asm_ui\asm_server_panel.py` | 1721 | `FUNC001` | Função '_build_players': 64 linhas (máx: 50) | ast |
| `src\asm_ui\asm_server_panel.py` | 1721 | `FUNC003` | Função '_build_players': 5 funções aninhadas (alta complexidade) | ast |
| `src\asm_ui\asm_server_panel.py` | 1791 | `FUNC001` | Função '_build_dinos': 91 linhas (máx: 50) | ast |
| `src\asm_ui\asm_server_panel.py` | 1791 | `FUNC003` | Função '_build_dinos': 6 funções aninhadas (alta complexidade) | ast |
| `src\asm_ui\asm_server_panel.py` | 1888 | `FUNC001` | Função '_build_breeding': 60 linhas (máx: 50) | ast |
| `src\asm_ui\asm_server_panel.py` | 2004 | `FUNC001` | Função '_build_structures': 52 linhas (máx: 50) | ast |
| `src\asm_ui\asm_server_panel.py` | 2062 | `FUNC001` | Função '_build_engrams': 57 linhas (máx: 50) | ast |
| `src\asm_ui\asm_server_panel.py` | 2125 | `FUNC001` | Função '_build_server_files': 111 linhas (máx: 50) | ast |
| `src\asm_ui\asm_server_panel.py` | 2242 | `FUNC001` | Função '_build_level_progressions': 232 linhas (máx: 50) | ast |
| `src\asm_ui\asm_server_panel.py` | 2242 | `FUNC003` | Função '_build_level_progressions': 6 funções aninhadas (alta complexidade) | ast |
| `src\asm_ui\asm_server_panel.py` | 2565 | `FUNC001` | Função '_build_tool_launcher': 60 linhas (máx: 50) | ast |
| `src\asm_ui\asm_server_panel.py` | 2565 | `FUNC002` | Função '_build_tool_launcher': 11 parâmetros (máx: 7) | ast |
| `src\asm_ui\asm_server_panel.py` | 2698 | `FUNC001` | Função '_build_crafting_overrides': 63 linhas (máx: 50) | ast |
| `src\asm_ui\asm_server_panel.py` | 2767 | `FUNC001` | Função '_build_stack_overrides': 54 linhas (máx: 50) | ast |
| `src\asm_ui\asm_server_panel.py` | 2827 | `FUNC001` | Função '_build_spawner_overrides': 88 linhas (máx: 50) | ast |
| `src\asm_ui\asm_server_panel.py` | 2921 | `FUNC001` | Função '_build_supply_crate_overrides': 74 linhas (máx: 50) | ast |
| `src\asm_ui\asm_server_panel.py` | 3115 | `FUNC001` | Função '_build_ini_editor': 391 linhas (máx: 50) | ast |
| `src\asm_ui\asm_server_panel.py` | 3115 | `FUNC003` | Função '_build_ini_editor': 21 funções aninhadas (alta complexidade) | ast |
| `src\asm_ui\asm_server_panel.py` | 3585 | `FUNC001` | Função '_sync_ui_to_cfg': 97 linhas (máx: 50) | ast |
| `src\asm_ui\asm_server_panel.py` | 3743 | `FUNC001` | Função '_open_preset_dialog': 133 linhas (máx: 50) | ast |
| `src\asm_ui\asm_server_panel.py` | 1113 | `FUNC001` | Função '_add_mod_row': 76 linhas (máx: 50) | ast |
| `src\asm_ui\asm_server_panel.py` | 1347 | `FUNC001` | Função '_build_admin_tail': 53 linhas (máx: 50) | ast |
| `src\asm_ui\asm_server_panel.py` | 3225 | `FUNC001` | Função '_render_items': 67 linhas (máx: 50) | ast |
| `src\asm_ui\asm_server_panel.py` | 746 | `IMP002` | Import duplicado: 'get_theme' de 'ui_constants' | ast |
| `src\asm_ui\asm_server_panel.py` | 1430 | `IMP002` | Import duplicado: 'CardSpec' de 'ui.server_field_widgets' | ast |
| `src\asm_ui\asm_server_panel.py` | 1430 | `IMP002` | Import duplicado: 'add_collapsible_help' de 'ui.server_field_widgets' | ast |
| `src\asm_ui\asm_server_panel.py` | 1430 | `IMP002` | Import duplicado: 'begin_tek_section' de 'ui.server_field_widgets' | ast |
| `src\asm_ui\asm_server_panel.py` | 1430 | `IMP002` | Import duplicado: 'build_cards_layout' de 'ui.server_field_widgets' | ast |
| `src\asm_ui\asm_server_panel.py` | 1452 | `IMP002` | Import duplicado: 'CardSpec' de 'ui.server_field_widgets' | ast |
| `src\asm_ui\asm_server_panel.py` | 1452 | `IMP002` | Import duplicado: 'add_collapsible_help' de 'ui.server_field_widgets' | ast |
| `src\asm_ui\asm_server_panel.py` | 1452 | `IMP002` | Import duplicado: 'begin_tek_section' de 'ui.server_field_widgets' | ast |
| `src\asm_ui\asm_server_panel.py` | 1452 | `IMP002` | Import duplicado: 'build_cards_layout' de 'ui.server_field_widgets' | ast |
| `src\asm_ui\asm_server_panel.py` | 1499 | `IMP002` | Import duplicado: 'CardSpec' de 'ui.server_field_widgets' | ast |
| `src\asm_ui\asm_server_panel.py` | 1499 | `IMP002` | Import duplicado: 'add_collapsible_help' de 'ui.server_field_widgets' | ast |
| `src\asm_ui\asm_server_panel.py` | 1499 | `IMP002` | Import duplicado: 'begin_tek_section' de 'ui.server_field_widgets' | ast |
| `src\asm_ui\asm_server_panel.py` | 1578 | `IMP002` | Import duplicado: 'CardSpec' de 'ui.server_field_widgets' | ast |
| `src\asm_ui\asm_server_panel.py` | 1578 | `IMP002` | Import duplicado: 'add_collapsible_help' de 'ui.server_field_widgets' | ast |
| `src\asm_ui\asm_server_panel.py` | 1578 | `IMP002` | Import duplicado: 'begin_tek_section' de 'ui.server_field_widgets' | ast |
| `src\asm_ui\asm_server_panel.py` | 1578 | `IMP002` | Import duplicado: 'build_cards_layout' de 'ui.server_field_widgets' | ast |
| `src\asm_ui\asm_server_panel.py` | 1607 | `IMP002` | Import duplicado: 'CardSpec' de 'ui.server_field_widgets' | ast |
| `src\asm_ui\asm_server_panel.py` | 1607 | `IMP002` | Import duplicado: 'add_collapsible_help' de 'ui.server_field_widgets' | ast |
| `src\asm_ui\asm_server_panel.py` | 1607 | `IMP002` | Import duplicado: 'begin_tek_section' de 'ui.server_field_widgets' | ast |
| `src\asm_ui\asm_server_panel.py` | 1607 | `IMP002` | Import duplicado: 'build_cards_layout' de 'ui.server_field_widgets' | ast |
| `src\asm_ui\asm_server_panel.py` | 1628 | `IMP002` | Import duplicado: 'CardSpec' de 'ui.server_field_widgets' | ast |
| `src\asm_ui\asm_server_panel.py` | 1628 | `IMP002` | Import duplicado: 'add_collapsible_help' de 'ui.server_field_widgets' | ast |
| `src\asm_ui\asm_server_panel.py` | 1628 | `IMP002` | Import duplicado: 'begin_tek_section' de 'ui.server_field_widgets' | ast |
| `src\asm_ui\asm_server_panel.py` | 1628 | `IMP002` | Import duplicado: 'build_cards_layout' de 'ui.server_field_widgets' | ast |
| `src\asm_ui\asm_server_panel.py` | 1722 | `IMP002` | Import duplicado: 'add_card_header' de 'ui.server_field_widgets' | ast |

> _336 issue(s) adicionais omitidos. Veja `latest_report.json` para lista completa._

### 🔵 Infos

| Arquivo | Linha | Código | Mensagem | Fonte |
|---------|------:|--------|----------|-------|
| `src\app.py` | 4 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\app.py` | 1 | `MOD001` | Mistura UI (661 refs) + lógica (71 refs) — considere separar em camadas | ast |
| `src\app_tek.py` | 6 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\app_tek.py` | 11 | `IMP001` | Import possivelmente não utilizado: 'webbrowser' | ast |
| `src\app_tek.py` | 1 | `MOD001` | Mistura UI (78 refs) + lógica (25 refs) — considere separar em camadas | ast |
| `src\ark_ini.py` | 5 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\ark_ini_fields.py` | 1 | `SIZE001` | Arquivo acima do recomendado: 671 linhas (alvo: < 500) | ast |
| `src\ark_ini_fields.py` | 5 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\ark_ini_fields.py` | 8 | `IMP001` | Import possivelmente não utilizado: 'io' | ast |
| `src\ark_ini_spawn.py` | 5 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\ark_log_watcher.py` | 7 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\asm_engine\asm_cloud_backup.py` | 9 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\asm_engine\asm_cloud_backup.py` | 11 | `IMP001` | Import possivelmente não utilizado: 'hashlib' | ast |
| `src\asm_engine\asm_cloud_backup.py` | 15 | `IMP001` | Import possivelmente não utilizado: 'zipfile' | ast |
| `src\asm_engine\asm_config_manager.py` | 6 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\asm_engine\asm_folder_manager.py` | 6 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\asm_engine\asm_game_list_ini.py` | 2 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\asm_engine\asm_ini_manager.py` | 1 | `SIZE001` | Arquivo acima do recomendado: 859 linhas (alvo: < 500) | ast |
| `src\asm_engine\asm_ini_manager.py` | 20 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\asm_engine\asm_preset_manager.py` | 5 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\asm_engine\asm_preset_manager.py` | 9 | `IMP001` | Import possivelmente não utilizado: 'uuid' | ast |
| `src\asm_engine\asm_preset_manager.py` | 10 | `IMP001` | Import possivelmente não utilizado: 'asdict' | ast |
| `src\asm_engine\asm_preset_manager.py` | 13 | `IMP001` | Import possivelmente não utilizado: 'Optional' | ast |
| `src\asm_engine\asm_server_config.py` | 6 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\asm_engine\asm_server_config.py` | 10 | `IMP001` | Import possivelmente não utilizado: 'Optional' | ast |
| `src\asm_engine\asm_server_manager.py` | 1 | `SIZE001` | Arquivo acima do recomendado: 532 linhas (alvo: < 500) | ast |
| `src\asm_engine\asm_server_manager.py` | 5 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\asm_engine\asm_server_manager.py` | 1 | `MOD002` | 3 classes no mesmo arquivo: _PsutilProcessWrapper, AsmServerInstance, AsmServerManager… — considere dividir | ast |
| `src\asm_engine\asm_steamcmd.py` | 1 | `SIZE001` | Arquivo acima do recomendado: 595 linhas (alvo: < 500) | ast |
| `src\asm_engine\asm_steamcmd.py` | 8 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\asm_engine\asm_steamcmd.py` | 1 | `MOD001` | Mistura UI (9 refs) + lógica (16 refs) — considere separar em camadas | ast |
| `src\asm_ui\asm_add_server_dialog.py` | 5 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\asm_ui\asm_ai_assistant.py` | 1 | `SIZE001` | Arquivo acima do recomendado: 619 linhas (alvo: < 500) | ast |
| `src\asm_ui\asm_ai_assistant.py` | 6 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\asm_ui\asm_ai_assistant.py` | 12 | `IMP001` | Import possivelmente não utilizado: 'Optional' | ast |
| `src\asm_ui\asm_ai_assistant.py` | 1 | `MOD001` | Mistura UI (62 refs) + lógica (11 refs) — considere separar em camadas | ast |
| `src\asm_ui\asm_dashboard.py` | 6 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\asm_ui\asm_dashboard.py` | 8 | `IMP001` | Import possivelmente não utilizado: 'platform' | ast |
| `src\asm_ui\asm_dashboard.py` | 1 | `MOD001` | Mistura UI (55 refs) + lógica (10 refs) — considere separar em camadas | ast |
| `src\asm_ui\asm_engram_editor.py` | 6 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\asm_ui\asm_engram_editor.py` | 9 | `IMP001` | Import possivelmente não utilizado: 'Any' | ast |
| `src\asm_ui\asm_engram_editor.py` | 9 | `IMP001` | Import possivelmente não utilizado: 'Optional' | ast |
| `src\asm_ui\asm_file_manager.py` | 11 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\asm_ui\asm_file_manager.py` | 15 | `IMP001` | Import possivelmente não utilizado: 'tk' | ast |
| `src\asm_ui\asm_firewall.py` | 16 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\asm_ui\asm_firewall.py` | 19 | `IMP001` | Import possivelmente não utilizado: 'Optional' | ast |
| `src\asm_ui\asm_firewall.py` | 1 | `MOD001` | Mistura UI (34 refs) + lógica (9 refs) — considere separar em camadas | ast |
| `src\asm_ui\asm_import_ini_dialog.py` | 1 | `SIZE001` | Arquivo acima do recomendado: 714 linhas (alvo: < 500) | ast |
| `src\asm_ui\asm_import_ini_dialog.py` | 10 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\asm_ui\asm_monitor_window.py` | 5 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\asm_ui\asm_monitor_window.py` | 12 | `IMP001` | Import possivelmente não utilizado: 'Any' | ast |
| `src\asm_ui\asm_monitor_window.py` | 12 | `IMP001` | Import possivelmente não utilizado: 'Optional' | ast |
| `src\asm_ui\asm_perf_chart.py` | 13 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\asm_ui\asm_player_list.py` | 11 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\asm_ui\asm_player_list.py` | 16 | `IMP001` | Import possivelmente não utilizado: 'tk' | ast |
| `src\asm_ui\asm_rcon_window.py` | 11 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\asm_ui\asm_rcon_window.py` | 20 | `IMP001` | Import possivelmente não utilizado: 'RconError' | ast |
| `src\asm_ui\asm_save_restore.py` | 11 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\asm_ui\asm_server_card.py` | 6 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\asm_ui\asm_server_card.py` | 8 | `IMP001` | Import possivelmente não utilizado: 'time' | ast |
| `src\asm_ui\asm_server_log_window.py` | 5 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\asm_ui\asm_server_log_window.py` | 10 | `IMP001` | Import possivelmente não utilizado: 'Optional' | ast |
| `src\asm_ui\asm_server_panel.py` | 5 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\asm_ui\asm_server_panel.py` | 1 | `MOD001` | Mistura UI (496 refs) + lógica (11 refs) — considere separar em camadas | ast |
| `src\asm_ui\asm_spawner_editor.py` | 6 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\asm_ui\asm_spawner_editor.py` | 10 | `IMP001` | Import possivelmente não utilizado: 'Any' | ast |
| `src\asm_ui\asm_spawner_editor.py` | 10 | `IMP001` | Import possivelmente não utilizado: 'Dict' | ast |
| `src\asm_ui\asm_spawner_editor.py` | 1 | `MOD002` | 3 classes no mesmo arquivo: _SpawnEntry, _SpawnContainer, _SpawnerEditorWindow… — considere dividir | ast |
| `src\asm_ui\asm_steamcmd_ui.py` | 2 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\asm_ui\asm_tribe_log.py` | 5 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\asm_ui\asm_tribe_log.py` | 1 | `MOD001` | Mistura UI (22 refs) + lógica (6 refs) — considere separar em camadas | ast |
| `src\asm_ui\asm_workshop.py` | 1 | `SIZE001` | Arquivo acima do recomendado: 505 linhas (alvo: < 500) | ast |
| `src\asm_ui\asm_workshop.py` | 12 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\asm_ui\asm_workshop.py` | 1 | `MOD001` | Mistura UI (54 refs) + lógica (11 refs) — considere separar em camadas | ast |
| `src\asm_ui\spawn_exact_panel.py` | 1 | `SIZE001` | Arquivo acima do recomendado: 988 linhas (alvo: < 500) | ast |
| `src\asm_ui\spawn_exact_panel.py` | 17 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\backup_manager.py` | 9 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\battlemetrics_client.py` | 7 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\beacon_client.py` | 5 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\breeding_calculator.py` | 1 | `SIZE001` | Arquivo acima do recomendado: 608 linhas (alvo: < 500) | ast |
| `src\breeding_calculator.py` | 12 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\buff_manager.py` | 1 | `SIZE001` | Arquivo acima do recomendado: 783 linhas (alvo: < 500) | ast |
| `src\buff_manager.py` | 8 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\buff_manager.py` | 1 | `MOD002` | 4 classes no mesmo arquivo: BuffRates, BuffPreset, BuffEvent, BuffManager… — considere dividir | ast |
| `src\change_logger.py` | 5 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\config_manager.py` | 1 | `MOD002` | 10 classes no mesmo arquivo: DiscordNotifyConfig, BackupConfig, AutoUpdateConfig, ShutdownConfig… — considere dividir | ast |
| `src\crash_details_helper.py` | 5 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\crash_parser.py` | 7 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\db_setup_resources.py` | 2 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\db_setup_resources.py` | 5 | `IMP001` | Import possivelmente não utilizado: 're' | ast |
| `src\db_setup_resources.py` | 9 | `IMP001` | Import possivelmente não utilizado: 'Optional' | ast |
| `src\dialogs\clone_config_dialog.py` | 2 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\dialogs\create_buff_dialog.py` | 1 | `SIZE001` | Arquivo acima do recomendado: 503 linhas (alvo: < 500) | ast |
| `src\dialogs\create_buff_dialog.py` | 1 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\dialogs\mod_download_dialog.py` | 7 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\dialogs\mod_download_dialog.py` | 9 | `IMP001` | Import possivelmente não utilizado: 'tk' | ast |
| `src\dialogs\mod_ini_dialog.py` | 2 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\dialogs\mod_search_dialog.py` | 2 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\dialogs\mod_search_dialog.py` | 1 | `MOD001` | Mistura UI (58 refs) + lógica (9 refs) — considere separar em camadas | ast |
| `src\dialogs\open_presets_manager.py` | 1 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\dialogs\open_presets_manager.py` | 2 | `IMP001` | Import possivelmente não utilizado: 'tk' | ast |
| `src\dialogs\sync_ini_dialog.py` | 2 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\discord_notifier.py` | 8 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\discord_notifier.py` | 316 | `IMP001` | Import possivelmente não utilizado: 'ConfigManager' | ast |
| `src\dynamic_config_server.py` | 15 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\mod_auto_updater.py` | 1 | `SIZE001` | Arquivo acima do recomendado: 504 linhas (alvo: < 500) | ast |
| `src\mod_auto_updater.py` | 13 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\mod_changelog_scraper.py` | 14 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\mod_manager.py` | 1 | `SIZE001` | Arquivo acima do recomendado: 657 linhas (alvo: < 500) | ast |
| `src\mod_manager.py` | 6 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\obelisk_client.py` | 7 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\pages\add_admin_id.py` | 1 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\pages\add_mod.py` | 1 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\pages\add_sync_cycle.py` | 1 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\pages\add_sync_folder.py` | 1 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\pages\asm_scheduler_tick.py` | 2 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\pages\asm_scheduler_tick.py` | 6 | `IMP001` | Import possivelmente não utilizado: 'ASM_STATUS_RUNNING' | ast |
| `src\pages\asm_start_server.py` | 2 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\pages\auto_start_dynamic_configs.py` | 1 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\pages\auto_start_servers.py` | 1 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\pages\auto_start_sync.py` | 1 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\pages\auto_start_sync.py` | 2 | `IMP001` | Import possivelmente não utilizado: 'os' | ast |
| `src\pages\broadcast_add.py` | 1 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\pages\broadcast_delete.py` | 1 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\pages\broadcast_rcon.py` | 1 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\pages\broadcast_refresh_list.py` | 1 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\pages\broadcast_refresh_list.py` | 3 | `IMP001` | Import possivelmente não utilizado: 'tk' | ast |
| `src\pages\broadcast_render_row.py` | 1 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\pages\broadcast_render_row.py` | 2 | `IMP001` | Import possivelmente não utilizado: 'tk' | ast |
| `src\pages\broadcast_sched_add.py` | 2 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\pages\broadcast_sched_delete.py` | 2 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\pages\broadcast_sched_refresh.py` | 2 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\pages\broadcast_sched_send_now.py` | 2 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\pages\broadcast_sched_tick.py` | 7 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\pages\broadcast_sched_toggle.py` | 2 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
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
| `src\pages\build_sidebar_tek.py` | 2 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\pages\build_sidebar_tek.py` | 5 | `IMP001` | Import possivelmente não utilizado: 'tk' | ast |
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
| `src\pages\chat_fetch.py` | 4 | `IMP001` | Import possivelmente não utilizado: 'datetime' | ast |
| `src\pages\chat_poll_loop.py` | 1 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\pages\chat_toggle_poll.py` | 1 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\pages\check_updates_manual.py` | 1 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\pages\clear_all_mods.py` | 1 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\pages\clear_server_log.py` | 1 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\pages\clear_server_log.py` | 2 | `IMP001` | Import possivelmente não utilizado: 'tk' | ast |
| `src\pages\cluster_detail.py` | 1 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\pages\cluster_import_from_manual.py` | 1 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\pages\cluster_new.py` | 1 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\pages\cluster_save.py` | 1 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\pages\cluster_save.py` | 2 | `IMP001` | Import possivelmente não utilizado: 'os' | ast |
| `src\pages\clusters_refresh_list.py` | 1 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\pages\clusters_refresh_list.py` | 2 | `IMP001` | Import possivelmente não utilizado: 'tk' | ast |
| `src\pages\collect_server_stats.py` | 1 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\pages\confirm_delete_backup.py` | 1 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\pages\confirm_remove_server.py` | 1 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\pages\confirm_restore_backup.py` | 1 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\pages\content_host.py` | 6 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\pages\content_host.py` | 11 | `IMP001` | Import possivelmente não utilizado: 'ctk' | ast |
| `src\pages\customshop_panel.py` | 8 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\pages\customshop_panel.py` | 1 | `MOD001` | Mistura UI (218 refs) + lógica (23 refs) — considere separar em camadas | ast |
| `src\pages\db_local_server.py` | 2 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\pages\db_manager_panel.py` | 2 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\pages\db_manager_panel.py` | 10 | `IMP001` | Import possivelmente não utilizado: 'Optional' | ast |
| `src\pages\db_manager_panel.py` | 1 | `MOD001` | Mistura UI (233 refs) + lógica (16 refs) — considere separar em camadas | ast |
| `src\pages\db_setup_wizard.py` | 2 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |
| `src\pages\dialog_add_server.py` | 2 | `IMP001` | Import possivelmente não utilizado: 'annotations' | ast |

> _182 issue(s) adicionais omitidos. Veja `latest_report.json` para lista completa._
