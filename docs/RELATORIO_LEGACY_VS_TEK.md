# Relatório: Modo Legado (Primitivo) vs TEK

**Data:** 12/06/2026  
**Versão analisada:** v1.9.13  
**Escopo:** comparar o que o modo legado fazia (ou foi projetado para fazer) com o TEK atual (`main.py` → `app_tek.py`).

---

## Contexto

| | Legado | TEK |
|---|--------|-----|
| App principal | `src/app.py` (7 abas inline) + `src/pages/server_panel.py` (17 abas modulares) | `src/app_tek.py` |
| Config servidor | `ServerConfig` (`src/server_config.py`) | `AsmServerConfig` (`src/asm_engine/asm_server_config.py`) |
| Save / INI | `server_save.py` + `ArkIniManager` | `asm_server_panel._save()` + `asm_ini_manager.write_ini()` |
| Start/stop | `ServerManager` | `AsmServerManager` |

**Nota:** o legado modular (`server_panel.py` + `build_tab_*`) está **parcialmente desconectado** de `app.py` — vários `app._*` referenciados nas pages não existem em `app.py`. A comparação abaixo usa o legado **como projetado** (módulos em `src/pages/`), que é o contrato funcional mais completo.

---

## CRÍTICO — ausente ou quebrado no TEK

### 1. BattleMetrics (contagem online real)
- **Legado:** `battlemetrics_id` em `ServerConfig`; poller em `server_manager.py`; badge no painel (`server_panel.py`).
- **TEK:** `_on_bm_update` é no-op — `src/app_tek.py` (~L1652).
- **Impacto:** dashboard TEK não consulta API BattleMetrics.

### 2. Histórico de alterações (ChangeLogger)
- **Legado:** `server_save.py` registra diff via `snapshot_server` / `diff_snapshots`; UI em `build_tab_historico.py`.
- **TEK:** `_save()` em `asm_server_panel.py` não registra histórico; sem aba equivalente.

### 3. Gerenciamento de Plugins ArkApi
- **Legado:** aba Plugins em `app.py` (~L1989+) — instalar/remover ZIP, listar DLLs.
- **TEK:** sem UI equivalente.

### 4. Mod Auto-Updater global
- **Legado:** `ModAutoUpdater` no boot de `app.py`; painel na aba Mods.
- **TEK:** mods via `asm_workshop.py` / card do dashboard (manual); sem updater global com broadcast.

### 5. Dynamic Config HTTP (INI sem reiniciar)
- **Legado:** `dynamic_config_enabled` em `ServerConfig`; push em `push_dynamic_config.py`; parâmetro `-DynamicConfigURL` no launch.
- **TEK:** campo e fluxo ausentes em `AsmServerConfig` / `asm_ini_manager`.
- **Extra:** `auto_start_dynamic_configs.py` existe mas **não é chamado** em nenhum boot.

### 6. Chat ao vivo + broadcasts agendados
- **Legado:** aba 💬 Chat (`tab_chat.py`); broadcasts via `broadcast_sched_*.py` e `scheduled_tasks`.
- **TEK:** seção “Bate-papo” só configura flags INI; RCON em janela separada (`asm_rcon_window.py`) sem chat live.
- **Bug:** `asm_scheduler_tick.py` referencia `enable_scheduled_broadcast`, mas **não existe** em `AsmServerConfig` — código morto.

### 7. Bloqueio de edição com servidor rodando
- **Legado:** banner + save bloqueado (`server_panel.py`, `server_save.py` L28–38).
- **TEK:** botão Salvar sempre ativo; sem aviso de bloqueio.
- **Impacto:** risco de gravar INI com servidor online.

### 8. Backup automático configurável por servidor
- **Legado:** aba Backup (`tab_backup.py`) — intervalo, retenção, includes.
- **TEK:** backup manual (`asm_save_restore.py`); `_asm_do_auto_backup` existe mas `enable_auto_backup` / `auto_backup_time` **não estão** em `AsmServerConfig` nem na UI — scheduler nunca dispara.

### 9. Auto-start de servidores ao abrir o app
- **Legado:** `auto_start_on_launch` em `ServerConfig` + `auto_start_servers.py`.
- **TEK:** ausente.
- **Extra:** `auto_start_servers()` **também não é invocado** em `app.py`.

### 10. System tray ao fechar
- **Legado:** `app.py` — `protocol("WM_DELETE_WINDOW")`, `_minimize_to_tray`.
- **TEK:** opção `minimize_to_tray` salva em config global, mas **sem handler** de fechamento em `app_tek.py`.

---

## DIFERENTE — mesma intenção, implementação distinta

### Gravações em disco

| Arquivo / ação | Legado | TEK |
|----------------|--------|-----|
| INI (GUS/Game/Engine) | `ArkIniManager.save_all()` | `asm_ini_manager.write_ini()` |
| `AllowedCheaterSteamIDs.txt` | `server_save.py` (ao salvar) | Salvar **e** iniciar (`asm_server_manager.py`) — **corrigido v1.9.13** |
| Whitelist / Exclusive Join IDs | Flag `whitelist_only` → CLI `?ExclusiveJoin`; IDs no JSON | Listas `whitelist_ids` / `exclusive_join_ids` no JSON + flag `exclusive_join`; **sem arquivo .txt** dedicado |
| Whitelist via jogador online | — | RCON `AllowPlayerToJoinNoCheck` (`asm_player_list.py`) — **não persiste** no JSON/arquivo |
| RunServer.cmd | `server_manager.py` | `asm_server_manager.py` (gera + `os.startfile`) |

### Start / Stop / Restart

| | Legado | TEK |
|---|--------|-----|
| Antes do start | `_save_server_config(silent=True)` | `_asm_persist_server()` (widgets→JSON→INI) |
| Validação pré-start | básica | ports, admin password, map mod (`app_tek.py` ~L870+) |
| Reconnect processo existente | implícito | `try_reconnect_server` + scan no boot |
| Cancelar start | botão “Cancelar” em busy | botões desabilitados durante start |

### Painel do servidor — abas legado vs seções TEK

**Legado (`server_panel.py`) sem equivalente direto:**

| Aba legado | TEK |
|------------|-----|
| Spawns / Loot (editores visuais) | Raw text + SpawnExact + editores ASM |
| 📝 INI estruturado | INI raw + import dialog |
| Admins (aba dedicada + preview Steam) | “Arquivos do Servidor” (lista texto) |
| 💬 Chat | Ausente |
| 📋 Histórico | Ausente |
| Backup (aba) | Janela Save/Restore no card |
| 🔴 Crashes (por servidor) | Página global Crashes |
| Plugins | Ausente |
| Barra de busca na config | Ausente |

**TEK tem e reorganiza (estilo ASM):** ~28 seções — Presets, PGM, Engramas visual, SpawnExact, Discord/servidor, Gerenciamento Automático, Firewall, Cloud backup, AI assistant, etc.

### Agendamento

| | Legado | TEK |
|---|--------|-----|
| Modelo | `scheduled_tasks[]` — dias da semana, stop, update+restart, aviso | Reinício diário simples (`enable_auto_restart`, `auto_restart_time`) |
| Broadcast | via Chat + scheduler legado | código em `asm_scheduler_tick.py` sem campos no config |

### Integrações compartilhadas (com wiring distinto)

| Feature | Legado | TEK |
|---------|--------|-----|
| RCON | aba embutida | janela `asm_rcon_window.py` |
| Web Store auto-start | `app.py` / `app_tek.py` | sidebar Loja + Banco |
| Crashes | aba por servidor | monitor global |
| Performance | sidebar | sidebar + cards dashboard |
| Clone config entre servidores | `clone_config_dialog.py` | ausente |
| Sync INI multi-target | `sync_ini_dialog.py` | `asm_import_ini_dialog.py` (import, não clone) |

---

## LEGADO APENAS — provavelmente intencional ou substituído

1. **UI tabular 17 abas** — substituída pelo painel ASM scrollável.
2. **Editor visual Spawns/Loot** — substituído por raw + ferramentas ASM.
3. **Badge LAN/WAN no painel** — TEK não implementa `_on_server_visibility_change` (pass).
4. **Sidebar Exportar/Importar perfil** — `pages/sidebar.py`; ausente no TEK.
5. **Servidores primitivos na UI principal** — TEK carrega legado no `server_manager` internamente, mas UI é ASM; remoção via `_confirm_remove_primitive_server`.

---

## PARIDADE OK

1. **`AllowedCheaterSteamIDs.txt`** — `src/ark_server_files.py`; save + start no TEK (v1.9.13).
2. **Web store auto-start** — ambos (`customshop_panel.auto_start_webstore`, modo host).
3. **Sync de pastas / clusters** — `SyncEngine` + painéis compartilhados.
4. **Eventos Sazonais, Clusters, Remoto, Desempenho** — pages compartilhadas; TEK wired na sidebar.
5. **Config global** — backup global, Discord, SMTP, SteamCMD.
6. **RCON funcional** — aba vs janela.
7. **Import INI do disco** — legado `ini_import.py` / TEK `asm_import_ini_dialog.py`.
8. **Exclusive Join (flag CLI)** — `server_config.build_launch_args` / `asm_ini_manager._launch_url_params`.
9. **Persistência antes do start** — ambos salvam config/INI antes de lançar processo.
10. **CustomShop / eventos sazonais bridge** — `buff_server_bridge.py` roteia TEK e legado.
11. **Scan servidores já rodando no boot** — TEK (`_asm_scan_running_servers`); legado não tinha equivalente explícito.

---

## Código legado desconectado (dívida técnica)

Estes módulos existem mas **não estão ligados** ao fluxo atual (`main.py` → TEK):

- `server_panel.py` (17 abas) — `app._build_tab_*` não definidos em `app.py`
- `auto_start_servers.py` — não invocado
- `auto_start_dynamic_configs.py` — não invocado
- `pages/get_change_logger.py` — sem binding no app
- Vários handlers de `pages/` referenciados só pelo painel modular legado

---

## Priorização sugerida (paridade)

| Prioridade | Item | Esforço estimado |
|------------|------|------------------|
| P0 | System tray no TEK (`WM_DELETE_WINDOW` + `minimize_to_tray.py`) | Baixo |
| P0 | Bloqueio save com servidor online | Baixo |
| P1 | Campos `enable_auto_backup` + UI (scheduler já existe) | Médio |
| P1 | Campos `enable_scheduled_broadcast` + UI ou remover código morto | Médio |
| P1 | Whitelist: persistir IDs em arquivo ou documentar uso só via RCON/CLI | Médio |
| P2 | BattleMetrics no dashboard TEK | Médio |
| P2 | Histórico de alterações (ChangeLogger) | Médio |
| P2 | Auto-start servidores ao abrir app | Baixo |
| P3 | Plugins ArkApi UI | Alto |
| P3 | Dynamic Config HTTP | Alto |
| P3 | Chat live + broadcasts (aba legado) | Alto |
| P3 | Mod Auto-Updater global | Médio |

---

## Referências de código

| Tópico | Arquivos |
|--------|----------|
| Save legado | `src/pages/server_save.py` |
| Save TEK | `src/asm_ui/asm_server_panel.py` → `_save()` |
| Admins disco | `src/ark_server_files.py` |
| Start TEK | `src/asm_engine/asm_server_manager.py` |
| Scheduler TEK | `src/pages/asm_scheduler_tick.py` |
| App TEK | `src/app_tek.py` |
| App legado | `src/app.py`, `src/pages/server_panel.py` |
| Config legado | `src/server_config.py` |
| Config TEK | `src/asm_engine/asm_server_config.py` |

---

*Gerado automaticamente a partir da análise do repositório ARKLAND-Multi v1.9.13.*
