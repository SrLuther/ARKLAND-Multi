# Diagnóstico (logs, doctor, pacote .zip)

Infraestrutura única para os dois modos (clássico e TEK). Código em `src/diagnostics/`,
tela em `src/pages/build_diagnostics.py` (sidebar → **🩺 Diagnóstico**).

## Como funciona

| Peça | Arquivo | O que faz |
|---|---|---|
| Logging central | `logging_setup.py` | `setup_logging()` roda cedo (`main.py`) e `attach_to_app()` liga o hook do Tk. Arquivo rotativo 2 MB × 5. |
| Eventos de domínio | `events.py` | `diag_event(categoria, msg, **campos)` e o decorador `diag_call`. |
| Mascaramento | `redact.py` | Lista central de regras; usado no log, no coletor, no resumo do Discord. |
| Doctor | `doctor.py` | Checagens independentes → `{id, title, severity, detail, hint}`. |
| Coletor | `collector.py` | Monta o `.zip` (limite de tamanho, reduz logs/INIs em passos). |
| Envio | `sender.py` | Discord (webhook) e Web Store (`POST /api/diagnostics`). Nunca levanta exceção. |
| Endpoint | `plugin/arkshop_web/diagnostics_routes.py` | Recebe/guarda os pacotes na Web Store. |

## Onde ficam os arquivos

- Logs: `%APPDATA%\ARKLAND-ServerManager\logs\arkland.log` (+ `.1` … `.5`)
- Pacotes: `%APPDATA%\ARKLAND-ServerManager\diagnostics\arkland-diagnostico-AAAAMMDD-HHMMSS.zip`
- Preferências da tela (nível de log, URL do webhook): `%APPDATA%\ARKLAND-ServerManager\diagnostics.json`
  (a URL do webhook fica em texto simples nesse arquivo; dentro do `.zip` ela aparece mascarada).
- Nível de log: botão na tela, variável `ARKLAND_LOG_LEVEL` ou `log_level` em `diagnostics.json`.
  Padrão `INFO`. `ARKLAND_AGENT_DEBUG_FILE=1` reativa o arquivo NDJSON antigo de `agent_dbg`.

Formato de cada linha: `data | NÍVEL | v<versão>/<modo> | thread | logger:módulo:linha | mensagem`.

## Exceções não tratadas

`sys.excepthook`, `threading.excepthook`, `sys.unraisablehook`, `report_callback_exception` do Tk e o
handler do asyncio gravam o traceback completo no log. A UI recebe só um aviso discreto (toast),
no máximo 1 a cada 30 s; o mesmo traceback repetido é resumido por 60 s (sem laço de popups).

## Gerar e enviar

1. **Verificar saúde** — roda o doctor em segundo plano e pinta OK / AVISO / ERRO com a dica de correção.
2. **Gerar diagnóstico (.zip)** — salva em `diagnostics\` e abre a pasta. Reaproveita o último resultado do doctor.
3. **Enviar para Discord** — cola a URL do webhook (`https://discord.com/api/webhooks/…`); posta o zip
   (limite ~8 MB; acima disso envia só o resumo + aviso e o `.zip` fica local).
4. **Enviar para a Web Store** — usa a URL e a API key de *Configurações › Loja*. Limite 25 MB.

Todo envio é **opt-in**: só acontece ao clicar no botão e confirmar o aviso
«serão enviados logs e configs com segredos mascarados». Nada é enviado automaticamente.

### Endpoint da Web Store

- `POST /api/diagnostics` — cabeçalho `X-API-Key`; multipart com `file` (zip) e opcionais
  `app_version`, `ui_mode`, `machine`, `note`, `doctor_summary` (JSON). Resposta `201 {"ok":true,"id":"AAAAMMDD-HHMMSS-xxxxxxxx"}`.
  Rate-limit 6/hora e 20/dia por IP; tamanho máx. `ARKSHOP_DIAGNOSTICS_MAX_MB` (25); retenção
  `ARKSHOP_DIAGNOSTICS_KEEP` (100). O nome do arquivo do cliente é ignorado (id gerado no servidor),
  o zip só é validado (nunca extraído).
- `GET /api/admin/diagnostics` e `GET /api/admin/diagnostics/<id>/download` — sessão admin.
- Destino: `<pasta de dados da Web Store>\diagnostics\<id>.zip` + `<id>.json` (metadados).

## O que é mascarado

Antes de gravar no log **e** antes de entrar no zip (`redact_text` / `redact_obj` / `redact_ini_text`):

- valores de chaves com `token`, `password/passwd/pwd/senha`, `secret`, `api_key`, `webhook`, `authorization`,
  `cookie`, `credential`, `private_key`, `hash`, `signature`, `bearer` (JSON, dict Python, `chave=valor`, INI, `chave: valor`);
- URLs de webhook do Discord, token de bot do Discord, JWT, tokens de provedores (GitHub, Slack, etc.),
  `Authorization: Bearer/Basic`, `usuário:senha@` em URLs;
- varredura **por valor**: segredos encontrados nos `*.json` do app são removidos até de texto solto (logs);
- arquivos de config cujo nome contém `token/secret/credential/cookie/keystore` não entram no zip.

Valores vazios e booleanos são mantidos (para que «senha em branco» continue diagnosticável).
**Não** são anonimizados nesta versão: IPs, nomes de servidor e SteamIDs — mas já existem regras opcionais
(`ipv4`, `steamid64`) desligadas por padrão.

Estender (um só lugar, `redact.py`):

```python
from src.diagnostics import redact
redact.add_sensitive_keyword("minha_chave")          # qualquer chave que contenha o termo
redact.add_rule("meu_token", r"MT-[A-Za-z0-9]{20,}")  # padrão livre
redact.enable_optional_rule("ipv4")                   # liga a anonimização opcional
```

## Como criar uma checagem no doctor

```python
from src.diagnostics.doctor import DoctorContext, register_check, ok, warn, err

@register_check("minha_checagem", "Título legível")
def _check(ctx: DoctorContext):
    # ctx.servers (ServerView), ctx.app_config (config.json), ctx.config_dir
    if tudo_certo:
        return ok("minha_checagem", "Título legível", "Detalhe")
    return warn("minha_checagem", "Título legível", "O que houve", hint="Como corrigir")
```

Pode devolver um `CheckResult` ou uma lista. Cada checagem roda na própria thread com timeout (15 s);
exceção ou estouro de tempo vira um resultado **ERRO** daquela checagem, sem derrubar as demais.
Checagens atuais: `python_deps`, `app_data`/`app_log`, `config_files`, `steamcmd`, `disk_space`,
`backup_paths`, `servers_present`, `ports_duplicated`, `webstore` e, por servidor, `server_install`,
`server_inis`, `server_admin_password`, `server_arkapi`, `server_plugins`, `server_permissions`
(`ArkApi\Plugins\Permissions\Permissions.dll`, só presença em disco) e `server_level_toggle`.

## Eventos de domínio já instrumentados

Boot (versão/modo/caminhos), salvar perfil (clássico e TEK), `read_ini`/`write_ini` (linhas de rampa e
`player_level_progressions_enabled`), carga/gravação de `config.json`/`servers.json`/`asm_servers.json`,
start/stop/crash de servidor, download de mods/instalação via SteamCMD, instalação de plugin por zip,
sync de plugins/servidores com a Web Store e push de status. `agent_dbg` (`src/_agent_debug_log.py`) agora
encaminha para `diag_event` (nível DEBUG).

## Testes

`python -m pytest tests/test_diag_*.py plugin/arkshop_web/tests/test_diagnostics_routes.py -q`
