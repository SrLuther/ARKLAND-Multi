# oBobonic — bot Discord embutido

O oBobonic roda **dentro do ARKLAND Server Manager** (painel *oBobonic* na sidebar). Não existe mais
pasta externa, `bot.py`, `.env` nem Python separado.

## Capacidades (somente estas três)

| Cog | Arquivo | Comandos / comportamento |
|-----|---------|--------------------------|
| Administração | `src/discord_bot/admin.py` | `!reload`/`!recarregar`, `!load`/`!carregar`, `!unload`/`!descarregar`, `!restart`/`!reboot`/`!reiniciar`, `!shutdown`/`!desligar` (somente administradores; confirmação por reação ✅/❌ em restart/shutdown). Nomes de cog aceitos: `voicemanager`, `moderation`, `admin`. |
| Moderação | `src/discord_bot/moderation.py` | `!faxina`/`!purgeall`, `!limpar`/`!clear <caracteres>`, `!limpezageral`/`!limparall @usuário [limite]` (quarentena + purge global); filtro automático de convites do Discord e de palavrões. |
| Salas de voz | `src/discord_bot/voice_manager.py` | Entrar no **lobby** cria a sala "Sala de 🗣️ Nome" (limite 10, dono com gerenciar/mover/mutar/ensurdecer); sala vazia é excluída. |

Adaptações em relação ao projeto original (oBobonicClean):

- `!restart` reinicia **apenas o bot embutido** (o original usava `sys.exit(24)` com supervisor externo); `!shutdown` desliga só o bot, o app continua aberto.
- As salas de voz temporárias são gravadas em `voice_temp_channels.json` e limpas no próximo boot (o original perdia o rastreio ao reiniciar).
- Filtros de moderação ignoram mensagens privadas (DM).
- Caches de canal/cargo são por instância do bot (reinício não reaproveita objetos antigos).

## Como executa

`EmbeddedBotRunner` (`src/discord_bot/runner.py`) sobe uma **thread** com event loop asyncio dedicado no
processo do app. Subprocesso foi descartado porque o app é um EXE PyInstaller (`sys.executable` é o
próprio app, não existe `python -m`). `discord.py` só é importado dentro da thread.

- *Reiniciar ao crash*: reconexão automática com backoff (3 s, 6 s … até 30 s), no máximo 5 falhas seguidas.
  Erros fatais (token inválido, intents não habilitadas) **não** são repetidos.
- *Iniciar com o app*: inicia ~4,5 s após abrir o app, se houver token configurado.
- Ao fechar o app o bot é encerrado (`shutdown_obobonic_for_app`).

## Configuração (no painel)

Gravada em `%APPDATA%\ARKLAND-ServerManager\config.json` → `obobonic` (mesmo local dos demais segredos do app;
o token nunca vai para log — logs passam por redação).

| Campo | Uso |
|-------|-----|
| Token do bot | login |
| Client ID (opcional) | link de convite; vazio = derivado do token |
| ID do servidor | exibição/validação de presença do bot |
| Prefixo | padrão `!` |
| Lobby de voz | canal que cria salas temporárias (precisa estar numa categoria) |
| Canal de logs | logs de moderação/admin |
| Cargo de quarentena | aplicado por `!limpezageral` |

Dados do bot: `%APPDATA%\ARKLAND-ServerManager\obobonic\` (`palavroes.txt` editável — reinicie o bot para aplicar —
e `voice_temp_channels.json`).

## Dev Portal (obrigatório)

Em **Bot → Privileged Gateway Intents** ative **Server Members Intent** e **Message Content Intent**.
Use «Convidar bot» no painel (permissões: gerenciar canais/mensagens/cargos, mover/mutar/ensurdecer membros,
reações, embeds, histórico — **sem** Administrator). O cargo do bot deve ficar **acima** do cargo de quarentena.

## Migração da versão antiga

- Configs antigas (`project_path`, `start_hidden`, `health_check_before_start`) são lidas sem erro e **ignoradas**
  (`start_hidden`/RCON deixaram de existir; as opções *Iniciar com o app* e *Reiniciar ao crash* são preservadas).
- Se havia pasta antiga com token válido, o app **oferece uma vez** importar token, IDs (`GUILD_ID`,
  `LOBBY_CHANNEL_ID`, `CANAL_LOGS_ID`, `QUARANTINE_ROLE_ID`, com fallback aos defaults do `config.py`) e
  `palavroes.txt`. Também há o botão *Importar dados do bot antigo* (escolhe a pasta, leitura única).
  Nunca é dependência em runtime.

## Empacotamento

`requirements.txt` inclui `discord.py>=2.4.0`; `ARKLAND-Multi.spec` usa `collect_all('discord')` e
`collect_all('aiohttp')` e lista os módulos `src.discord_bot.*` como hiddenimports (cogs são carregados
por `load_extension`, import dinâmico).

## Testes

`tests/test_obobonic_bot.py` (config/persistência/migração/importação), `tests/test_discord_bot_logic.py`,
`tests/test_discord_bot_runner.py`, `tests/test_discord_bot_cogs.py` (mocks, requer discord.py),
`tests/test_obobonic_panel_persistence.py` (UI Tk; é pulado sem display).
