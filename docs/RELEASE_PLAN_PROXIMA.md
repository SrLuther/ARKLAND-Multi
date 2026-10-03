# Plano de release — próxima versão do ARKLAND Server Manager

> Preparado em 02/10/2026 (snapshot do workspace, com outros agentes ainda editando).
> **Nada foi commitado, publicado, implantado ou reiniciado.** Este documento só descreve o que fazer.
> Reconferir os "números de hoje" (seção 2 e 4) no momento do release — vários agentes ainda estão mexendo.

---

## 0. TL;DR para o coordenador

1. A release real é feita por **um único script**: `_release.ps1 -Version X.Y.Z`. Ele **bumpa, builda, commita (`git add -A`), faz push e publica no GitHub**. Não há "dry-run" — ver seção 5 para o caminho seguro passo a passo.
2. Pré-requisito do script: existir no `CHANGELOG` de `src/version.py` uma entrada com `"version": "X.Y.Z"`. Hoje o topo é `"Unreleased"` → **renomear para a versão nova + data** antes de rodar.
3. Versão proposta: **`1.10.111`** (convenção do projeto = só patch; alternativa `1.11.0`, ver seção 3).
4. Os 3 testes que falhavam (ArkPlayer 1.0.0 vs 1.0.1) eram **testes desatualizados** (plugin 1.0.1 está certo). **Corrigido** (seção 2). Suíte da raiz: **720 passed**.
5. **ALERTA CRÍTICO de plugin:** `plugin/CustomShop/bin/CustomShop.dll` ainda é a **1.10.39** (compilada em 09/08) enquanto `plugin_version.txt`/`PluginInfo.json` já dizem **1.10.40** (código `ShopStore.cpp` alterado hoje). O `build.bat` **só avisa** (`[AVISO]`) se a compilação do CustomShop falhar e embute a DLL velha com PluginInfo novo. Ver seção 6 (verificação do pacote).
6. `build.bat` **não compila o ArkEventHunt** (só CustomShop, CustomDinoDeliver, ArkPlayer). A `ArkEventHunt.dll` 0.5.4 já foi compilada manualmente hoje (22:56) — confirmado que contém "0.5.4". Se mudar o código dele de novo, compilar à mão (`plugin\ArkEventHunt\build_cl.bat`).

---

## 1. Como o release funciona de fato (mapeado do repo)

### 1.1 Fonte de verdade da versão

| Item | Arquivo | Quem altera |
| --- | --- | --- |
| Versão do app | `src/version.py` → `APP_VERSION` (+ `BUILD_DATE`) | `_release.ps1` (regex) — **não editar à mão** |
| Notas de versão | `src/version.py` → lista `CHANGELOG` (1ª entrada) | **Humano** (renomear "Unreleased" → versão) |
| Manifesto de auto-update | `version.json` (`version`, `date`, `download_url`, `changelog[]`) | `_release.ps1` (gerado do CHANGELOG da versão) |
| Instalador Inno Setup | `setup.iss` → `#define ReleaseVersion` | `_release.ps1` |
| Changelog Markdown | `CHANGELOG.md` (raiz) | `scripts/sync_changelog_md.py` (gerado de `version.py`; não editar) |
| Versão de cada plugin | `plugin/<P>/plugin_version.txt` | **Humano** (independente do app; ver 1.3) |
| PluginInfo / header | `plugin/<P>/configs/PluginInfo.json`, `bin/PluginInfo.json`, `src/plugin_version.h` | `scripts/sync_plugin_versions.py --all` (a partir do `.txt`) |
| Changelog do plugin | `plugin/<P>/CHANGELOG.md` (seção `## [X.Y.Z]`) | **Humano** |
| Log do release | `_release_X.Y.Z.log` | saída do script (via `Tee-Object`), commitado na release **seguinte** |

O app (`src/updater.py`) lê `version.json` de `raw.githubusercontent.com/SrLuther/ARKLAND-Multi/main/version.json` e compara como tupla de inteiros (`1.11.0 > 1.10.111` funciona).

### 1.2 O que `_release.ps1 -Version X.Y.Z` faz (na ordem)

1. Valida formato `X.Y.Z`.
2. **Gate de plugins**: `scripts/check_plugin_release_gate.py` (falha o release se algo não bate).
3. Exige entrada `"version": "X.Y.Z"` em `src/version.py`; extrai as `changes` via AST.
4. Reescreve `APP_VERSION`, `BUILD_DATE`, `version.json`, `setup.iss`.
5. `scripts/sync_plugin_versions.py --all` e `scripts/sync_changelog_md.py`.
6. Roda `build.bat` (ver 1.4) e exige `installer\ARKLAND-Multi-Setup-vX.Y.Z.exe`.
7. **Size gate**: WebStore.exe ≤ 80 MB e instalador ≤ 150 MB (senão falha; histórico: v1.10.66 saiu com 427 MB por falta de exclusão no `ARKLAND-WebStore.spec`).
8. **`git add -A` + `git commit -m "release: vX.Y.Z"` + `git push`** (irreversível sem force).
9. Pega token do Windows Credential Manager e **cria a GitHub Release** `vX.Y.Z` com `version.json.changelog` como corpo e anexa o instalador.

> Padrão de uso (conforme `_release_*.log`):
> `.\_release.ps1 -Version 1.10.111 *>&1 | Tee-Object -FilePath _release_1.10.111.log`

### 1.3 Gate de versão dos plugins (`scripts/check_plugin_release_gate.py`)

Para cada um de CustomShop, CustomDinoDeliver, ArkPlayer, ArkEventHunt:

- `plugin_version.txt` == `configs/PluginInfo.json` `VersionLabel` == `bin/PluginInfo.json` == `src/plugin_version.h`.
- `CHANGELOG.md` do plugin tem seção `## [versão atual]`.
- Se `src/`, `CMakeLists.txt`, `*.vcxproj*`, `build*.bat` mudaram **desde o último commit que alterou `plugin_version.txt`**, a versão atual precisa ser **maior** que a do commit.

Testes que cobrem isso: `tests/test_plugin_release_gate.py`, `tests/test_plugin_versions.py`, `tests/test_arkplayer_deploy.py`, `tests/test_arkeventhunt_deploy.py`. **O gate não verifica o binário** (DLL) — só texto/versão.

Estado hoje (`python scripts\check_plugin_release_gate.py` → **OK**):

| Plugin | `plugin_version.txt` | Mudou desde a release 1.10.110? | Status |
| --- | --- | --- | --- |
| CustomShop | **1.10.40** | sim (`ShopStore.cpp/.h`) — já bumpado, CHANGELOG ok | **DLL ainda 1.10.39 (recompilar!)** |
| CustomDinoDeliver | 1.10.16 | não | ok |
| ArkPlayer | 1.0.1 | não | ok (ver seção 2) |
| ArkEventHunt | **0.5.4** | sim — bumpado, CHANGELOG ok | DLL contém "0.5.4" ✅ |

> A **Vitrine de Recursos** (`docs/VITRINE_RECURSOS_SPEC.md`, `resource_vitrine_*.py`) diz que traz mudança no plugin CustomShop (`/vitrine`, `/confirmar`, `/mercado`). Se esse agente mexer mais em `plugin/CustomShop/src/**`, ele precisa bumpar `plugin_version.txt` de novo (ex.: 1.10.41, 1.11.0…), escrever a seção no `CHANGELOG.md` e rodar `python scripts\sync_plugin_versions.py --plugin CustomShop`. **Re-rodar o gate no fim.**

### 1.4 Build (`build.bat`, chamado pelo `_release.ps1`)

Usa `.python-full\python.exe` (Python 3.12.13 com tkinter), nesta ordem:

1. `pip install -r requirements.txt` + `plugin\arkshop_web\requirements.txt` + `pyinstaller`.
2. `scripts\sync_plugin_versions.py --all`.
3. Compila DLLs com MSVC (`build_cl.bat` de cada plugin): **CustomShop → CustomDinoDeliver → ArkPlayer** (ArkEventHunt **não**). `SKIP_PLUGIN_BUILD=1` pula tudo. **Falha de compilação = só `[AVISO]` e usa a DLL antiga.**
4. PyInstaller (4 specs, sempre `--noconfirm`):
   - `.python-full\python.exe -m PyInstaller --noconfirm ARKLAND-Multi.spec` → `dist\ARKLAND-ServerManager.exe` (onefile, `uac_admin=True`)
   - `... ARKLAND-Updater.spec` → `dist\ARKLAND-Updater.exe`
   - `scripts\build_regulamento_html.py`
   - `... ARKLAND-WebStore.spec` → `dist\ARKLAND-WebStore.exe`
5. Inno Setup (`ISCC.exe /Q setup.iss`) → `installer\ARKLAND-Multi-Setup-vX.Y.Z.exe` (empacota os 3 EXEs + `setup_db.sql/bat`).
6. `scripts\sync_changelog_md.py`.

### 1.5 Como os plugins vão embutidos e chegam nos servidores

- `ARKLAND-Multi.spec` embute em `plugins/` (dentro do EXE): `CustomShop.dll`, `libmariadb.dll`, `z.dll`, `CustomDinoDeliver.dll`, `ArkPlayer.dll`, `ArkEventHunt.dll`; e os `PluginInfo.json` em `plugins/customshop`, `customdino`, `arkplayer`, `arkeventhunt` (+ `config.json` padrão de ArkPlayer e ArkEventHunt, `Permissions/configs/config.json`).
- `src/plugin_versions.py` lê o `PluginInfo.json` embutido → "versão esperada". Na UI (abas Plugins/Loja) cada mapa mostra instalado × esperado (`match/outdated/newer/missing`).
- **Não há atualização automática de plugin nos mapas.** O admin precisa, no app novo, usar «Instalar/Atualizar» (`install_*_all` em `src/shop_integration.py`, painéis CustomShop/TEK) — copia a DLL + PluginInfo para `ShooterGame/Binaries/Win64/ArkApi/Plugins/<Plugin>/`; **config.json existente não é sobrescrito**. A DLL só vale **após reiniciar o servidor de jogo daquele mapa** (a DLL fica carregada pelo ArkApi).
- A Web Store (`ARKLAND-WebStore.exe`) vem no mesmo instalador, mas é um processo **separado no host da loja**: precisa ser substituído/reiniciado manualmente lá.

---

## 2. Por que falhavam os testes de ArkPlayer — causa e correção (APLICADA)

**Sintoma:** `test_arkplayer_deploy.py::test_install_arkplayer_copies_config_and_info` e `test_plugin_release_gate.py::test_bundled_versions_match_plugin_version_txt` com `assert '1.0.1' == '1.0.0'`. (`test_plugin_release_gate` como arquivo hoje só tem esse caso falhando; o gate em si passa.)

**Causa:** os dois testes tinham `"1.0.0"` **hardcoded**. O plugin ArkPlayer foi bumpado para **1.0.1** na release v1.10.83 (`272d531b`, 20/07/2026: "config.json ausente: warning + defaults"). Evidências de que **1.0.1 é o lado certo**: `plugin_version.txt` = 1.0.1; `configs/` e `bin/PluginInfo.json` `VersionLabel` = 1.0.1; `src/plugin_version.h` = 1.0.1; `plugin/ArkPlayer/CHANGELOG.md` tem `## [1.0.1] - 2026-07-20`; gate OK; o `_release_1.10.110.log` já imprimia "ArkPlayer: PluginInfo.json -> v1.0.1"; e o teste vizinho `test_deploy_arkplayer_copies_bundled_plugin_info` já usa 1.0.1. Nenhuma alteração no plugin ou no bundle era necessária.

**Correção mínima aplicada (só testes, sem tocar em plugin/bundle/arquivos reservados):**

- `tests/test_arkplayer_deploy.py`: o assert passou a comparar `read_plugin_info_version(...)` com `read_plugin_version_file("ArkPlayer")` (lê `plugin_version.txt`) e importa `read_plugin_version_file`.
- `tests/test_plugin_release_gate.py`: `assert expected_plugin_version("ArkPlayer") == "1.0.0"` → compara com `read_plugin_version_file("ArkPlayer")`.

Resultado: `pytest tests/test_arkplayer_deploy.py tests/test_plugin_release_gate.py tests/test_plugin_versions.py` → **19 passed**; `pytest tests` (raiz inteira) → **720 passed**. Assim os testes não quebram mais a cada bump de ArkPlayer.

---

## 3. Versão proposta

**`1.10.111`** (patch).

- Convenção do projeto: toda release recente é patch dentro de 1.10.x, inclusive as com Feat (ex.: 1.10.107/110). O `_release.ps1`, `setup.iss`, `version.json` e o updater funcionam sem surpresas.
- Conteúdo do Unreleased justificaria **minor** (`1.11.0`): bot Discord embutido, nova página Diagnóstico, abas Dinos/Itens, vitrine de recursos com tabelas novas e plugin novo. É seguro tecnicamente (comparação por tupla de inteiros). Decisão de marca/produto do coordenador; se escolher `1.11.0`, trocar todos os `1.10.111` abaixo.

---

## 4. Auditoria do spec / requirements / imports

| Verificação | Resultado |
| --- | --- |
| `requirements.txt` | Adicionado `discord.py>=2.4.0` (instalado: 2.7.1, + aiohttp 3.14.1, certifi). Em Python 3.12 não precisa `audioop-lts` (só 3.13+, que o próprio discord.py declara). **Coerente.** |
| `ARKLAND-Multi.spec` | Já tem `collect_all('discord')` + `collect_all('aiohttp')` (datas/binaries/hiddenimports), `hiddenimports` explícitos `discord`, `discord.ext.commands`, `aiohttp`, `certifi`, `src.discord_bot{,.bot,.admin,.moderation,.voice_manager}` e `collect_submodules('src')` (cobre `src.discord_bot.*` e `src.diagnostics.*`; `src/__init__.py` e `src/diagnostics/__init__.py` existem). **Sem módulo faltando.** |
| Imports reais (`python -c`, `.python-full`) | OK: `discord`, `aiohttp`, `certifi`, todos `src.discord_bot.*` (settings, logic, storage, legacy_import, cache, runner, bot, admin, moderation, voice_manager), todos `src.diagnostics.*` (boot, logging_setup, collector, doctor, sender, redact, events, ini_events, arkapi, servers, paths), `src.pages.build_diagnostics`, `src.obobonic_bot`, `src.pages.obobonic_panel`, `src.version`. |
| Datas novos no app | Nenhum necessário (bot e diagnóstico não usam arquivos empacotados; dados vão para `%APPDATA%\ARKLAND-ServerManager\{obobonic,logs,diagnostics}`). |
| `ARKLAND-WebStore.spec` | **Não mudou.** Já inclui `static/` inteiro (pega `index.html`, `redeem_docs.js`), `discord`. Os módulos novos (`dino_levels`, `diagnostics_routes`, `resource_vitrine_{migrate,routes,service}`, `market_fee`, `payment_jobs`…) são importados por `import` estático (dentro ou fora de funções) em `app.py`, então o PyInstaller os detecta; todos usam só flask/sqlalchemy/stdlib. Conferir no log do build que não há "missing module" desses nomes (ver 6.3). |
| `plugin/arkshop_web/requirements.txt` | Não lista `discord.py`/`requests` (preexistente; `build.bat` instala o `requirements.txt` da raiz primeiro, então o build funciona). Opcional: adicionar `discord.py` ali para consistência. |
| Peso do pacote | `discord`+`aiohttp` entram no EXE principal (~+10 MB estimado). O gate de 150 MB do instalador deve continuar passando (último: ver `_release_1.10.110.log`); conferir o tamanho final. |

**Comando do PyInstaller (para quando for a hora; NÃO rodado agora):**

```powershell
cd d:\DOC\arkland-multi
.\.python-full\python.exe -m PyInstaller --noconfirm ARKLAND-Multi.spec      # -> dist\ARKLAND-ServerManager.exe
.\.python-full\python.exe -m PyInstaller --noconfirm ARKLAND-Updater.spec    # -> dist\ARKLAND-Updater.exe
.\.python-full\python.exe scripts\build_regulamento_html.py                  # antes do WebStore
.\.python-full\python.exe -m PyInstaller --noconfirm ARKLAND-WebStore.spec   # -> dist\ARKLAND-WebStore.exe
```

(o `build.bat` já faz tudo isso em ordem; preferir `build.bat`.)

**Riscos evidentes no spec:** nenhum módulo faltando. Pontos de atenção: (a) `collect_all('discord')` avisará de `nacl` ausente (voz) — inofensivo, o bot não usa áudio; (b) o `.gitignore` não protege `plugin/arkshop_web/support_steamids.json` (ver riscos).

---

## 5. Plano executável (checklist ordenado)

> Rodar tudo em PowerShell em `d:\DOC\arkland-multi`, com `$py = ".\.python-full\python.exe"`.

### Fase A — Congelar (quando todos os agentes avisarem "terminei")

- [ ] **A1.** Confirmar com cada agente que parou de editar. `git status --short` e `git diff --stat` — revisar a lista; nada inesperado.
- [ ] **A2.** Higiene antes do `git add -A` do script (ver riscos R3/R4): decidir sobre `plugin/arkshop_web/support_steamids.json` (untracked, hoje `[]`; o `app.py` diz que esse arquivo "não fica no repositório" → **apagar ou ignorar**, não commitar) e conferir `plugin/CustomShop/catalog.json` (1 linha alterada — é intencional?).
- [ ] **A3.** Plugins: cada agente de plugin deve ter bumpado `plugin_version.txt` + `CHANGELOG.md` do plugin. Rodar:
  ```powershell
  & $py scripts\sync_plugin_versions.py --all
  & $py scripts\check_plugin_release_gate.py
  ```
  Esperado: `OK: gate de versão dos plugins`. Anotar as versões finais (alvo atual: CustomShop **1.10.40** ou maior se a vitrine bumpar, CustomDinoDeliver 1.10.16, ArkPlayer 1.0.1, ArkEventHunt **0.5.4**).

### Fase B — Notas de versão (única edição manual em `src/version.py`)

- [ ] **B1.** Em `src/version.py`: trocar a entrada do topo `"version": "Unreleased", "date": ""` por `"version": "1.10.111", "date": "2026-10-XX"` (data do dia). Garantir que **todos** os agentes adicionaram suas linhas (vitrine de recursos ainda **não** tem linha no Unreleased hoje; Dino-gênero/nível, bulk, diagnóstico, bot, MP etc. já têm). Não mexer em `APP_VERSION`/`BUILD_DATE` (o script faz).
- [ ] **B2.** (recomendado) Encurtar/organizar as linhas mais longas — elas viram o corpo do GitHub Release e o texto do `version.json` mostrado no Sobre/atualizador. Usar o rascunho da seção 7 como base.
- [ ] **B3.** `& $py -c "import ast,sys; ast.parse(open('src/version.py',encoding='utf-8').read()); print('version.py OK')"`.

### Fase C — Testes (gate)

- [ ] **C1.** Suíte do app (raiz): `& $py -m pytest tests -q -p no:cacheprovider` → hoje **720 passed**, 0 falhas pré-existentes ignoradas (as 3 de ArkPlayer já foram corrigidas).
- [ ] **C2.** Suítes de plugin/versão isoladas (rápidas): `& $py -m pytest tests/test_plugin_release_gate.py tests/test_plugin_versions.py tests/test_arkplayer_deploy.py tests/test_arkeventhunt_deploy.py -q -p no:cacheprovider`.
- [ ] **C3.** Suíte da Web Store (a partir do diretório dela — **não** usar `pytest tests` sem filtro: existem `tests/test_app_output.txt` / `test_app_full_output.txt` em UTF-16 que quebram a coleta):
  ```powershell
  cd plugin\arkshop_web
  $f = Get-ChildItem tests -Filter test_*.py | % { "tests/" + $_.Name }
  ..\..\.python-full\python.exe -m pytest @f -q -p no:cacheprovider
  cd ..\..
  ```
  Observação: **não consegui obter baseline desta suíte** — a execução completa passou de 14 min sem terminar (workspace com outros agentes editando/testando em paralelo; o processo pode ainda estar rodando em segundo plano na minha sessão); rodar por arquivo (`pytest tests/test_X.py`) para localizar lentidão/hang. A suíte é **pesada/lenta** (vários minutos de CPU) — rodar quando o PC estiver livre dos outros agentes. Se algum teste de agente em andamento falhar, tratar com o dono; falhas por rede/DB externo não são esperadas (usam mocks).
- [ ] **C4.** Smoke de import (seção 4) repetido no final: `& $py -c "import src.discord_bot.runner, src.diagnostics.boot, src.app_tek, src.app"` (precisa de display para a UI; se falhar só por tkinter/headless, ignorar).

### Fase D — Compilar DLLs (antes do build.bat, para ver erros de verdade)

- [ ] **D1.** CustomShop (obrigatório se `plugin_version.txt` > versão embutida na DLL):
  ```powershell
  cd plugin\CustomShop; cmd /c build_cl.bat; cd ..\..
  ```
  Conferir "BUILD SUCCEEDED (v<versão>)".
- [ ] **D2.** ArkEventHunt (o `build.bat` NÃO faz): `cd plugin\ArkEventHunt; cmd /c build_cl.bat; cd ..\..` — só se o código mudou desde a DLL atual (hoje a DLL de 22:56 já é 0.5.4).
- [ ] **D3.** CustomDinoDeliver/ArkPlayer: sem mudanças → o `build.bat` recompila de qualquer forma (gera `.obj`/`.dll` binariamente idênticos, mas aparecem como modificados no git; é o padrão de todas as releases).
- [ ] **D4.** Verificar a DLL embutida contém a versão (função na seção 6.1).

### Fase E — Release (IRREVERSÍVEL: commit + push + GitHub Release)

**Só executar com OK explícito do usuário.**

- [ ] **E1.** `.\_release.ps1 -Version 1.10.111 *>&1 | Tee-Object -FilePath _release_1.10.111.log`
- [ ] **E2.** Se falhar *antes* do passo `git add -A` (gate, changelog, build, size gate) nada foi commitado — corrigir e rodar de novo. Se falhar depois do push (token/GitHub), a release do GitHub pode ser criada à mão com o instalador de `installer\`.

**Alternativa "build sem publicar"** (para validar o pacote antes de decidir): rodar só o que não commita —

```powershell
& $py scripts\check_plugin_release_gate.py
& $py scripts\sync_plugin_versions.py --all
& $py scripts\sync_changelog_md.py
cmd /c build.bat 2>&1 | Tee-Object -FilePath build_out.txt   # gera dist\ e installer\ (installer fica com a versão do setup.iss atual = 1.10.110; para validar o nome, rode antes o bump manual de ReleaseVersion — não faça commit)
```

> Observação: sem rodar `_release.ps1`, `APP_VERSION`/`setup.iss`/`version.json` ficam na versão antiga — serve só para testar o pacote, não para publicar.

### Fase F — Pós-release (manual, nesta ordem)

1. Baixar o instalador publicado e instalar numa máquina de teste (não de produção).
2. Verificar pacote embutido (seção 6).
3. **Web Store** (host da loja): substituir `ARKLAND-WebStore.exe` e reiniciar **fora do horário de pico**; conferir log de boot (criação das tabelas da vitrine, sem exceção) e `GET /api/...` de saúde.
4. **Servidores de jogo**: por mapa, no app novo → «Instalar/Atualizar plugins»; agendar o restart de cada mapa (um de cada vez, com aviso no chat). Só os mapas que precisam de DLL nova (ver lista abaixo).
5. Re-sincronizar servidores/loja pelo app (para `query_port` aparecer nos cards da home).
6. Mercado Pago: conferir a URL do webhook (`https://<dominio>/api/payments/webhook`) e `GET /api/admin/pix/webhook-diagnostics`.

---

## 6. Verificação do pacote embutido (versões de plugin)

### 6.1 Antes do instalador (árvore de trabalho)

```powershell
foreach ($p in 'CustomShop','CustomDinoDeliver','ArkPlayer','ArkEventHunt') {
  $v   = (Get-Content "plugin\$p\plugin_version.txt").Trim()
  $dll = Get-ChildItem "plugin\$p\bin\$p.dll"
  $txt = [Text.Encoding]::ASCII.GetString([IO.File]::ReadAllBytes($dll.FullName))
  "{0,-18} txt={1,-8} DLL contém versão? {2}   DLL={3:dd/MM HH:mm}  PluginInfo={4}" -f $p,$v,$txt.Contains($v),$dll.LastWriteTime,((Get-Content "plugin\$p\bin\PluginInfo.json" -Raw | ConvertFrom-Json).VersionLabel)
}
```

**Todos têm de dar `True`.** Medido hoje: CustomShop **False** (DLL de 09/08 = 1.10.39 → precisa recompilar), CustomDinoDeliver True, ArkPlayer True, ArkEventHunt True (compilada 02/10 22:56).

### 6.2 Depois do build

- `python -m pytest tests/test_plugin_versions.py tests/test_plugin_release_gate.py -q` (usa o bin/ atual = mesmo que o EXE embute).
- Tamanhos: `dist\ARKLAND-WebStore.exe` ≤ 80 MB, instalador ≤ 150 MB (o script já falha se estourar).
- Opcional: extrair o EXE com `pyi-archive_viewer dist\ARKLAND-ServerManager.exe` e conferir as entradas `plugins/*.dll`, `plugins/*/PluginInfo.json`.

### 6.3 Avisos do PyInstaller a procurar

`build\ARKLAND-Multi\warn-ARKLAND-Multi.txt` e `build\ARKLAND-WebStore\warn-ARKLAND-WebStore.txt`: procurar por `missing module named` com `discord_bot`, `diagnostics`, `dino_levels`, `diagnostics_routes`, `resource_vitrine`. (Avisos de `nacl`, `audioop`, `uvloop` etc. são conhecidos/ok.)

---

## 7. Rascunho das notas de release (usuário final / admin)

> Título sugerido: **ARKLAND Server Manager 1.10.111** — Diagnóstico, bot Discord embutido, Dinos de qualquer nível e correção das doações.

### Legenda de impacto

- 🎮 **Reiniciar o servidor de jogo (mapa)**: só quando a DLL do plugin é atualizada.
- 🌐 **Reiniciar a Web Store**: troca do `ARKLAND-WebStore.exe` e restart do processo.
- 🗄️ **Migração de banco**: executada sozinha ao subir a Web Store (idempotente).
- 💻 **Só atualizar o app**: nada a reiniciar no jogo.

### App (Server Manager) 💻

- **Nova página «Diagnóstico»** (modo clássico e TEK): «Verificar saúde» (OK/AVISO/ERRO com dica de correção), «Gerar diagnóstico (.zip)», nível de log, abrir pasta de logs. Envio ao Discord ou à Web Store é **opcional e com confirmação** — nada vai automaticamente.
- **Log central** em `%APPDATA%\ARKLAND-ServerManager\logs\arkland.log` (rotação 2 MB × 5) com **segredos mascarados** (tokens, senhas, API keys, webhooks). Exceções não tratadas agora são registradas.
- **Verificações de saúde**: install_dir/ShooterGameServer, INIs, ArkApi, plugins, Permissions, portas duplicadas, senha admin em branco, espaço em disco, SteamCMD, Web Store.
- **Correção — «Progressões customizadas» (Nível do jogador)**: a opção desmarcada agora permanece desmarcada após reiniciar o app (mesmo com o servidor no ar).
- **Correção — Status dos servidores**: os cards passam a mostrar/copiar **IP:QueryPort** (ex.: 27015, a porta dos favoritos da Steam), não a porta do jogo. Mantém fallback com aviso.

### Bot Discord (oBobonic) 💻

- **Bot embutido no app**: roda dentro do Server Manager (discord.py incluído). Não precisa de pasta externa, `bot.py`, `.env` ou Python separado.
- Cogs portados: administração (`!reload/!load/!unload/!restart/!shutdown`), moderação (`!faxina/!limpar/!limpezageral`, filtros de convite e palavrão) e salas de voz temporárias.
- **Painel reformulado**: token, ID do servidor, lobby, canal de logs e cargo de quarentena direto no app; status ao vivo; «Convidar bot» com as permissões certas; **«Importar dados do bot antigo»** (leitura única).
- Removidos: Pasta do bot, Instalar deps, Abrir pasta, Sync TEK → .env, Backup/Restaurar .env, Modo oculto, Verificar RCON.
- **Correção**: opções «Iniciar com o app / Reiniciar ao crash» voltavam ao valor antigo; `config.json` agora é gravado de forma atômica e o erro é mostrado.
- ⚠️ Admin: após atualizar, abrir o painel, preencher/importar os dados do bot e só então iniciar. Dados ficam em `%APPDATA%\ARKLAND-ServerManager\obobonic\`.

### Web Store 🌐

- **Doações PIX/cartão (Mercado Pago)** — correção importante: pagamentos já pagos que ficavam ABANDONADO/PENDENTE (webhook perdido) agora são recuperados (consulta ao MP com retentativas; assinatura inválida deixa de derrubar o webhook; limite subiu para 3000/h). Novo botão admin **«↻ Reconsultar no MP»** no log de suporte (crédito único, nunca duplica; valor menor que o pacote não credita). Novos avisos de diagnóstico do webhook. Opcionais: `mp_notification_url`, `mp_auto_reconcile` (varredura 5 min, desligada), `mp_webhook_strict_signature`. **Conferir no painel do MP** (Webhooks > Pagamentos) a URL `https://<dominio>/api/payments/webhook`.
- **Dinos de qualquer nível**: abas «Dinos» e «Dinos 200» unificadas em **«Dinos»** com chips de nível dinâmicos; qualquer nível de 1 até o teto (padrão 500; configurável `shop_dino_level_max` / `ARKSHOP_DINO_LEVEL_MAX`). Links antigos `dinos200` redirecionam com filtro 200. Catálogo antigo é lido com nível inferido e gravado com `Level` explícito.
- **Badges de Gênero/Nível nos cards** (♂ Macho / ♀ Fêmea / Casal / Aleatório, «Nv. 200»); gênero inferido aparece tracejado; entrega só fixa se `Dinos[].Gender` existir.
- **Itens da Loja (admin)**: abas «Dinossauros» e «Itens» com contagem e busca; **seleção em lote** com «Incluir no Comércio», «Remover do Comércio» e «Deletar» (confirmação, até 200 itens, auditado).
- **Editor de item/kit**: removidos os botões de atalho de licença (o painel de LicenseGrant e o checkbox de registrar licença continuam iguais).
- **Tutoriais + Mídias unificados**: vídeos no topo de «Tutoriais», guias abaixo; links antigos redirecionam.
- **Status dos servidores na home** com IP:QueryPort (ver App).
- **Diagnóstico**: novo `POST /api/diagnostics` (recebe o .zip enviado pelo app, com limite/rate-limit/retenção) e listagem/download admin. Detalhes em `docs/DIAGNOSTICO.md`.
- **Vitrine de Recursos** (mercado P2P de recursos em âmbar; ver `docs/VITRINE_RECURSOS_SPEC.md`) — *incluir aqui a descrição final quando o agente concluir; hoje ainda não há linha no Unreleased.* 🗄️ cria tabelas (`market_resource_catalog`, `market_resource_settings`, estoque/claims) ao subir. Depende do plugin CustomShop novo para o uso em jogo (`/vitrine`, `/confirmar`, `/mercado`).
- 🗄️ **Migração de banco**: só a Vitrine de Recursos (tabelas novas, idempotente, via `ensure_resource_vitrine_schema` no boot). As demais mudanças verificadas não adicionam `ALTER/CREATE TABLE` (os diffs de `pix_payments.py`/`payment_jobs.py` não têm DDL; a migração de catálogo de dinos é do JSON do catálogo, feita ao salvar via `POST /api/config`). *Reconferir no fim com `git diff | Select-String "ALTER TABLE|CREATE TABLE|ADD COLUMN"`, porque os agentes ainda editam `app.py`.* **Fazer backup do MySQL antes de reiniciar a Web Store.**

### Plugins 🎮

> Os plugins são embutidos no app. Para valer nos mapas: atualizar o app → «Instalar/Atualizar» → **reiniciar cada mapa**.

| Plugin | Versão | O que muda | Reiniciar mapa? |
| --- | --- | --- | --- |
| **CustomShop** | **1.10.40** (ou superior, se a vitrine bumpar) | `public_codes` da Auditoria Dinos passam a valer para qualquer Level ≥ 1 (antes só L1/L200). Sem isso, kits com dinos Lv 50/100/225 desalinham os códigos. Vitrine de recursos (`/vitrine`) quando concluída. | **Sim** (DLL) — recomendado fazer junto com a Web Store nova |
| **ArkEventHunt** | **0.5.4** | Fim do aviso falso «Permissions.dll não encontrado»; grupos de admin passam a ser resolvidos (`IsPlayerInGroup`); avisos de `WebApiKey` vazia / `WebApiUrl` local. | **Sim** (DLL), só nos mapas com Event Hunt |
| CustomDinoDeliver | 1.10.16 | sem mudança | não |
| ArkPlayer | 1.0.1 | sem mudança | não |

### Resumo de reinícios

| Ação | Quando |
| --- | --- |
| **Só atualizar o app** | Diagnóstico, bot oBobonic, correções de painel/Nível, status com QueryPort (cards da home precisam também de sync/Web Store) |
| **Reiniciar a Web Store** | Todas as mudanças de Web Store (doações MP, Dinos/gênero/nível, abas Itens, tutoriais, diagnóstico, vitrine). Backup do banco antes (vitrine cria tabelas) |
| **Reiniciar mapa(s)** | CustomShop 1.10.40+ e ArkEventHunt 0.5.4 (substituição de DLL). **Nenhuma outra mudança exige reiniciar o jogo** |
| **Migração de banco** | Apenas Vitrine de Recursos (automática no boot da Web Store) |

---

## 8. Riscos e pontos de atenção

| # | Risco | Impacto | Mitigação |
| --- | --- | --- | --- |
| R1 | **CustomShop.dll embutida pode ficar 1.10.39** com `PluginInfo` 1.10.40 (compilação falha só gera `[AVISO]` no `build.bat`; MSVC no `_release_1.10.110.log` está em `Visual Studio\18\Community`) | App diria "versão esperada 1.10.40" e instalaria DLL antiga → `public_codes` desalinhados silenciosamente | Fase D1 + 6.1 (checar que a DLL contém a versão); abortar se `False` |
| R2 | `build.bat` não compila ArkEventHunt | DLL stale se o código mudar após 22:56 | Compilar à mão (D2) e checar 6.1. Sugestão futura: incluir no `build.bat` |
| R3 | `_release.ps1` faz `git add -A` | Pode commitar lixo/dados locais: `plugin/arkshop_web/support_steamids.json` (untracked, não ignorado; hoje `[]`, mas o app diz que não fica no repo), `catalog.json` alterado, `.obj/.dll` binários (normal neste repo) | Revisar `git status` (A1/A2); apagar ou `.gitignore` o `support_steamids.json`; **nunca** passar `.env`/`.secrets.local` (já ignorados) |
| R4 | `git push` publica `version.json` antes do upload do instalador (script faz commit/push → depois release+asset) | Janela de minutos em que clientes veem versão nova mas o download 404 | Preexistente. Rodar fora do horário de pico; se travar após push, subir o instalador à mão na release |
| R5 | Release é irreversível (push + GitHub Release público; clientes auto-atualizam) | Servidores de produção com muitos jogadores | Validar o instalador numa máquina de teste (Fase F1) **antes** de anunciar; E1 só com OK explícito |
| R6 | Suíte da Web Store é lenta e `pytest tests` sem filtro quebra na coleta (`test_app_output.txt` UTF-16) | Falso negativo no gate | Usar a lista `test_*.py` (C3). Sugestão: apagar/ignorar esses `.txt` |
| R7 | Muitas linhas do Unreleased são enormes (viram corpo do GitHub Release e `version.json`) | Release ilegível | Usar o rascunho da seção 7 (B2) |
| R8 | Vitrine de Recursos (tabelas + plugin) ainda em andamento e sem linha no CHANGELOG | Esquecer bump do CustomShop / nota / backup do banco | A3 + B1; reconferir `plugin_version.txt` do CustomShop no fim |
| R9 | Web Store e jogo reiniciando juntos | Jogadores sem loja/comandos durante o restart | Primeiro Web Store (rápido), depois mapas um a um, com aviso; entrega pendente é retomada (claims) |
| R10 | Bot oBobonic embutido: primeira execução depende do usuário colocar token/IDs no painel | Bot parado após atualizar | Mencionar nas notas; usar «Importar dados do bot antigo» |
| R11 | Instalador pode crescer (+discord/aiohttp no EXE principal) | Estourar gate de 150 MB (improvável) | Gate do script já falha antes de publicar; checar tamanho |

---

## 9. Comandos de referência rápida

```powershell
$py = ".\.python-full\python.exe"

# gate + sincronizações (não commitam)
& $py scripts\check_plugin_release_gate.py
& $py scripts\sync_plugin_versions.py --all
& $py scripts\sync_changelog_md.py

# testes
& $py -m pytest tests -q -p no:cacheprovider
cd plugin\arkshop_web; $f = Get-ChildItem tests -Filter test_*.py | % { "tests/" + $_.Name }; ..\..\.python-full\python.exe -m pytest @f -q -p no:cacheprovider; cd ..\..

# DLLs
cd plugin\CustomShop;    cmd /c build_cl.bat; cd ..\..
cd plugin\ArkEventHunt;  cmd /c build_cl.bat; cd ..\..

# release completo (COMMIT + PUSH + GITHUB RELEASE — só com OK do usuário)
.\_release.ps1 -Version 1.10.111 *>&1 | Tee-Object -FilePath _release_1.10.111.log
```
