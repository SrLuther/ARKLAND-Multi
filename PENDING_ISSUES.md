# Problemas Pendentes — ARKLAND Server Manager

> Este arquivo é usado para anotar pendências e problemas a investigar posteriormente.
> Adicione entradas aqui sempre que identificar um bug ou melhoria que não será resolvido imediatamente.

---

## [✅ RESOLVIDO] Crash ArkShopUI.dll — 26/05/2026

**Status:** ✅ RESOLVIDO em 26/05/2026 — Causa raiz identificada: **conflito de banco MySQL entre ArkShop e Permissions** (ambos usando `MysqlDB: "arkshop"`). Fix: alterar `Permissions/config.json → MysqlDB: "ark_permission"`.

**Arquivos corrigidos:** `src/mod_manager.py`, `src/mod_auto_updater.py`, `src/config_manager.py`, `src/pages/global_config.py`, `src/pages/save_global_config.py`, `src/pages/start_mod_auto_updater.py`

---

### Sintoma

Crash fatal do servidor ARK ~5 minutos após um jogador conectar, **somente quando o servidor era iniciado pelo ARKLAND-Multi**. Quando iniciado pelo ASM (ArkServerManager), o servidor funcionava normalmente.

Stack trace do crash:

```text
Fatal error!
ArkShopUI.dll!UnknownFunction (0x0000000180006590)
ArkShopUI.dll!UnknownFunction (0x00000001800103c5)
VERSION.dll!ArkApi::Commands::CheckOnTimerCallbacks()
VERSION.dll!ArkApi::Hook_AGameState_DefaultTimer()
ShooterGameServer.exe!FTimerManager::Tick()
```

### Causa raiz REAL (26/05/2026)

ArkShop e Permissions estavam ambos configurados com `MysqlDB: "arkshop"` no Servidor 01 (ARKLAND Primitive). Ambos criam uma tabela `Players` no mesmo banco MySQL com schemas incompatíveis:

| Plugin | Tabela | Schema |
| --- | --- | --- |
| ArkShop.dll | `Players` | `SteamId, Points, ...` |
| Permissions.dll | `Players` | `SteamId, GroupName, ...` |

O `ArkShopUI.dll` chama `Permissions::GetGroupName(steamId)` no timer callback (~5min após jogador conectar). O Permissions lê a tabela `Players` do banco `arkshop` — que é a tabela do ArkShop (sem coluna `GroupName`) — retorna NULL/lixo → crash em `ArkShopUI.dll!0x6590`.

O servidor Crystal não crashava porque seu `Permissions/config.json` já usava `MysqlDB: "ark_permission"` (banco separado).

### Fix aplicado (26/05/2026)

- Arquivo: `<servidor>/ShooterGame/Binaries/Win64/ArkApi/Plugins/Permissions/config.json`
- Alterado: `"MysqlDB": "arkshop"` → `"MysqlDB": "ark_permission"`
- Resultado: servidor inicia sem crash, loja funciona ✅

> **Nota:** As correções de T1–T11 (`.mod`, DLLs, variáveis de ambiente, etc.) foram investigações com hipóteses incorretas e não têm relação com a causa real do crash.

---

---

### Histórico de investigação (T1–T10 — todas fracassadas)

#### Tentativa 1 — Hipótese `_MEIPASS\z.dll` (22/05/2026) ❌ Não resolveu

**Hipótese:** O PyInstaller prepend `_MEIPASS` ao PATH; `z.dll` gerava conflito de DLL no servidor filho.
**Fix aplicado:** `_build_server_env()` remove `_MEIPASS` do PATH + `CREATE_NEW_CONSOLE`.

**Resultado:** Crash persistiu com os mesmos endereços (`0x6590`, `0x103c5`). Fix não resolveu.

---

#### Tentativa 2 — Hipótese `Permissions.dll` v2.1 incompatível (22/05/2026) ⏳ Em teste

**Hipótese:** Comparando plugins do servidor com crash vs servidor saudável (sem crash):

| Plugin | Servidor com crash | Servidor saudável |
| --- | --- | --- |
| ArkShop.dll | 5214 KB — 06/08/2025 | 5214 KB — 06/08/2025 ✅ igual |
| ArkShopUI.dll | 7585 KB — 06/08/2025 | 7585 KB — 06/08/2025 ✅ igual |
| **Permissions.dll** | **5045 KB — 06/08/2025 (v2.1)** | **4950 KB — 21/10/2022 (v2.0)** ❌ diferente |

O servidor com crash usa `Permissions v2.1` (MinApiVersion 3.55). O ArkShopUI chama a API do Permissions durante timer callbacks (verificação de grupos VIP). A v2.1 pode ter incompatibilidade com o ArkShopUI 1.12.

**Resultado:** ❌ Crash persistiu com os mesmos endereços após downgrade para v2.0. Permissions não é a causa.

---

#### Tentativa 3 — Debug profundo via logging + ProcMon (22/05/2026) ⏳ Em andamento

**Objetivo:** Confirmar definitivamente se `_MEIPASS` ainda está contaminando o PATH do servidor, e identificar qual DLL é carregada de onde.

**Ações implementadas:**

- Logging detalhado adicionado em `server_manager.py` antes do `subprocess.Popen`:
  - Mostra valor de `sys._MEIPASS`
  - Lista entradas `_MEI*` residuais no PATH filtrado
  - Busca `z.dll` e `libmariadb.dll` em cada diretório do PATH
- Captura via **Process Monitor (Sysinternals)** para rastrear carregamento de DLLs:
  - Filtro: `Process Name is ShooterGameServer.exe` + `Operation is Load Image`
  - Comparar sequência de DLLs entre início via ARKLAND-Multi vs ASM

**Como reproduzir para coleta:**

1. Iniciar ARKLAND-Multi e observar os logs do servidor na UI (mensagens `[ENV-DEBUG]`)
2. Confirmar se `z.dll` ou `libmariadb.dll` aparecem de caminhos inesperados
3. Rodar ProcMon em paralelo para captura de baixo nível

---

#### Tentativa 4 — ENV-DEBUG em arquivo + RunServer.cmd + CREATE_BREAKAWAY_FROM_JOB (22/05/2026) ⏳ Em teste

**Hipótese A — Job Object herdado do PyInstaller:**
O ARKLAND-Multi é um executável PyInstaller com modo onefile. O Windows cria automaticamente um **Job Object** para o processo PyInstaller, e processos filhos criados com `subprocess.Popen` herdam esse Job Object (a menos que `CREATE_BREAKAWAY_FROM_JOB` seja passado). Estar dentro do Job Object do ARKLAND pode impor restrições (quota de memória, CPU throttling, shutdown) que disparam o crash no timer callback ~4 minutos após a inicialização completa do servidor.

O ASM usa `start /normal ShooterGameServer.exe ...`, que lança um processo completamente desanexado — sem herança de Job Object.

**Hipótese B — Ausência de RunServer.cmd:**
O ASM gera um arquivo `RunServer.cmd` em `ShooterGame\Saved\Config\WindowsServer\`. Screenshot do diretório com ARKLAND confirmou que o arquivo **não existia**. Algum plugin (possivelmente ArkShopUI ou ArkApi) pode verificar a existência ou conteúdo desse arquivo durante inicialização.

**Fixes aplicados em v1.3.33:**

```python
# 1. CREATE_BREAKAWAY_FROM_JOB — sai completamente do job object do PyInstaller
_CREATE_BREAKAWAY_FROM_JOB = 0x01000000
proc = subprocess.Popen(
    full_cmd,
    cwd=_dbg_cwd,
    creationflags=subprocess.CREATE_NEW_CONSOLE | _CREATE_BREAKAWAY_FROM_JOB,
    env=_build_server_env(),
)

# 2. RunServer.cmd gerado a cada start em ShooterGame/Saved/Config/WindowsServer/
_run_server_dir = Path(cfg.install_dir) / "ShooterGame" / "Saved" / "Config" / "WindowsServer"
_run_server_dir.mkdir(parents=True, exist_ok=True)
(_run_server_dir / "RunServer.cmd").write_text(
    f"@echo off\r\ncd /d \"{_dbg_cwd}\"\r\n{full_cmd}\r\n",
    encoding="utf-8",
)
```

Adicionalmente: dump completo do ambiente em `Binaries/Win64/_arkland_debug.txt` para diagnóstico futuro.

**Resultado:** ⏳ Crash persistiu (confirmado em teste v1.3.33). Tentativa 4 não resolveu. → Ver Tentativa 5.

---

#### Tentativa 5 — Remoção de variáveis PyInstaller do ambiente do servidor (22/05/2026) ❌ Não resolveu

**Evidência direta via `_arkland_debug.txt`** (gerado pela v1.3.32+):

```ini
TCL_LIBRARY=C:\Users\ARKSER~1\AppData\Local\Temp\_MEI117682\_tcl_data
TK_LIBRARY=C:\Users\ARKSER~1\AppData\Local\Temp\_MEI117682\_tk_data
_PYI_APPLICATION_HOME_DIR=C:\Users\ARKSER~1\AppData\Local\Temp\_MEI117682
_PYI_ARCHIVE_FILE=C:\Program Files (x86)\ARKLAND-ServerManager\ARKLAND-ServerManager.exe
_PYI_PARENT_PROCESS_LEVEL=1
__COMPAT_LAYER=DetectorsAppHealth        ← SUSPEITO PRINCIPAL
CHROME_CRASHPAD_PIPE_NAME=\\.\pipe\crashpad_4396_HZCCNBQFYLJHBJJT
```

**Hipótese — `__COMPAT_LAYER=DetectorsAppHealth`:**
O Windows aplica shims de compatibilidade ao processo ARKLAND (DetectorsAppHealth = monitoramento de saúde de app). Esse flag é herdado pelo ShooterGameServer.exe via variável de ambiente. Os shims interceptam chamadas de sistema — potencialmente interferindo no SEH (Structured Exception Handling) do ArkApi:

- `CheckOnTimerCallbacks()` usa try/catch ou `__try/__except` para capturar exceções nos callbacks de plugins
- Com o shim ativo, o Windows pode interceptar a exceção ANTES que o ArkApi possa capturá-la
- Resultado: exceção interna do ArkShopUI (null pointer, uso de ponteiro inválido) vira crash fatal

**Fix aplicado em v1.3.34** — `_build_server_env()` agora remove explicitamente:

```python
_vars_to_remove = (
    'TCL_LIBRARY',
    'TK_LIBRARY',
    '_PYI_APPLICATION_HOME_DIR',
    '_PYI_ARCHIVE_FILE',
    '_PYI_PARENT_PROCESS_LEVEL',
    '__COMPAT_LAYER',
    'CHROME_CRASHPAD_PIPE_NAME',
)
```

**Resultado:** ❌ Crash persistiu (confirmado em teste v1.3.34). `__COMPAT_LAYER` e variáveis PyInstaller não são a causa. → Ver Tentativa 6.

---

#### Tentativa 6 — Lançamento via `cmd.exe /c RunServer.cmd` (método idêntico ao ASM) (22/05/2026) ❌ Não resolveu

**Descoberta da causa raiz (análise do source ArkShopUI/ArkShop):**

Repositório oficial: <https://github.com/ArkServerApi/ASE-Plugins/releases> — source do ArkShop.dll disponível; ArkShopUI.dll é **binário fechado** (só o helper header está disponível).

Após análise das tentativas anteriores, a única diferença que ainda não foi tentada é o **método exato de criação do processo** pelo ASM:

- **ASM:** `cmd.exe /c RunServer.cmd` → dentro do cmd: `start "ARK Server" /min /normal "exe" args`
  - `start` chama `CreateProcessW` com `STARTF_USESHOWWINDOW | SW_SHOWMINIMIZED`
  - `bInheritHandles = FALSE` (cmd.exe)  
  - O processo é filho do cmd.exe, não do ASM
- **ARKLAND (Tentativas 1–5):** `subprocess.Popen(full_cmd, creationflags=CREATE_NEW_CONSOLE|BREAKAWAY_FROM_JOB)`
  - Processo criado diretamente pelo Python
  - Diferença em `STARTUPINFO` (sem `STARTF_USESHOWWINDOW`)

O RunServer.cmd já era **gerado** desde v1.3.33, mas **não era usado** para lançar o servidor — apenas para satisfazer plugins que verificavam sua existência.

**Fix aplicado em v1.3.35:**

O servidor agora é lançado **via `cmd.exe /c RunServer.cmd`** (exatamente como o ASM faz). Como o cmd.exe sai imediatamente após executar `start`, o PID do ShooterGameServer.exe é rastreado com `psutil` após o lançamento via `_find_server_process()`. Foi adicionada a classe `_PsutilProcessWrapper` para compatibilidade com o restante do código que usa a interface `subprocess.Popen`.

```python
# Lançamento via cmd.exe/RunServer.cmd (idêntico ao ASM)
_launch_time = datetime.now()
_cmd_proc = subprocess.Popen(
    ["cmd.exe", "/c", str(_run_server_cmd_path)],
    cwd=_dbg_cwd,
    creationflags=subprocess.CREATE_NEW_CONSOLE,
    env=_dbg_env,
)
_cmd_proc.wait(timeout=15)  # cmd.exe sai rápido após "start"
_raw = _find_server_process(cfg.install_dir, _launch_time, timeout=20.0)
proc = _PsutilProcessWrapper(_raw)  # wrapper compatível com Popen
```

Fallback para Popen direto se RunServer.cmd ou psutil não estiverem disponíveis.

**Resultado:** ❌ Crash persistiu (confirmado em teste v1.3.35). Processo lançado via `cmd.exe /c RunServer.cmd` idêntico ao ASM, mas o crash ocorreu igualmente aos 5 minutos. → Ver Tentativa 7.

---

#### Tentativa 7 — Redirecionamento do `TEMP`/`TMP` para pasta dedicada do servidor (22/05/2026) ❌ Substituída pela T8

**Hipótese — `%TEMP%` compartilhado com PyInstaller:**

O PyInstaller (modo onefile) extrai todos os seus arquivos (Python 3.12, DLLs, etc.) para `%TEMP%\_MEI######` enquanto o ARKLAND está em execução. A variável de ambiente `TEMP` do servidor aponta para o **mesmo diretório** (`C:\Users\ARKSER~1\AppData\Local\Temp`).

- **ASM (.NET):** não cria nenhum arquivo em `%TEMP%` — o `%TEMP%` do servidor está limpo
- **ARKLAND (PyInstaller):** `%TEMP%\_MEI142882\` contém `python312.dll`, `libmariadb.dll`, `z.dll`, `_ssl.pyd`, etc.

Se ArkShopUI.dll no seu timer de 5 minutos executa qualquer operação no diretório `%TEMP%` (scan por DLLs, `LoadLibraryEx` com LOAD_LIBRARY_SEARCH_USER_DIRS, criação de arquivos temporários com nomes previsíveis), pode encontrar os arquivos Python/PyInstaller e crashar com acesso inválido à memória.

**Fix aplicado em v1.3.36:**

Em `_start_worker`, após `_build_server_env()`, redireciona `TEMP` e `TMP` para uma pasta dedicada dentro do diretório de instalação do servidor:

```python
# Tentativa 7: TEMP dedicado para o servidor
_server_temp = Path(cfg.install_dir) / "ArkTemp"
_server_temp.mkdir(parents=True, exist_ok=True)
_dbg_env["TEMP"] = str(_server_temp)
_dbg_env["TMP"] = str(_server_temp)
```

Isso garante que o servidor nunca "veja" os arquivos do PyInstaller em `%TEMP%`, independente do método de lançamento.

**Resultado:** ❌ Não chegou a ser testada — substituída pela Tentativa 8 após análise do source do ASM revelar diferença fundamental no método de lançamento (`UseShellExecute=true`).

---

#### Tentativa 8 — Replicação exata do método de lançamento do ASM: `os.startfile()` / ShellExecute (22/05/2026) ❌ Não resolveu

**Hipótese — Herança de handles e ambiente via `CreateProcess`:**

Análise do source do ASM (`ServerApp.cs`, `ServerProfile.cs`) revelou:

1. O ASM gera `RunServer.cmd` com conteúdo: `start "<ProfileName>" /normal "<exe>" <args>`
2. O ASM lança o arquivo via `UseShellExecute = true` (equivalente Python: `os.startfile()`)

`ShellExecute` (= `os.startfile`) é **fundamentalmente diferente** de `subprocess.Popen` (`CreateProcess`):

| | ASM (`ShellExecute`) | ARKLAND (`CreateProcess`) |
| --- | --- | --- |
| Ambiente herdado | Ambiente do Desktop do usuário — isolado do ASM | Ambiente do processo Python/PyInstaller |
| Handles herdados | **Nenhum** | Herda todos os handles abertos do PyInstaller |
| Job objects | Não herda | Potencialmente herda job object do PyInstaller |

Em todas as tentativas anteriores (inclusive T6 com `cmd.exe /c RunServer.cmd`), o ARKLAND ainda usava `subprocess.Popen` com `env=_dbg_env`, o que ainda usa `CreateProcess` com herança de handles do processo PyInstaller. O ASM nunca entra nesse fluxo — ele usa ShellExecute desde o início.

**Fix aplicado em v1.3.37:**

RunServer.cmd gerado com conteúdo idêntico ao ASM (sem `@echo off`, sem `cd /d`):

```python
_rsc.write_text(
    f'start "{cfg.server_name}" /normal {full_cmd}\r\n',
    encoding="utf-8",
)
```

Lançamento via `os.startfile()` (= `ShellExecute`) em vez de `subprocess.Popen`:

```python
os.startfile(str(_run_server_cmd_path))
time.sleep(2)  # aguarda cmd.exe processar o start
_raw = _find_server_process(cfg.install_dir, _launch_time, timeout=20.0)
proc = _PsutilProcessWrapper(_raw)
```

**Resultado:** ❌ Crash persistiu (confirmado em 23/05/2026). `os.startfile()` / ShellExecute é idêntico ao ASM em herança de ambiente e handles, mas o crash ocorreu igualmente. Descoberta crítica neste teste: o crash acontece **mesmo com o ARKLAND fechado** — o processo de gerenciamento não é a causa. → Ver Tentativa 9.

---

Nova função `_build_server_env()` que remove `_MEIPASS` do PATH antes de passar o ambiente ao servidor:

```python
def _build_server_env() -> dict:
    env = os.environ.copy()
    if hasattr(sys, '_MEIPASS'):
        meipass = sys._MEIPASS.rstrip(os.sep)
        parts = [p for p in env.get('PATH', '').split(os.pathsep)
                 if p.rstrip(os.sep) != meipass]
        env['PATH'] = os.pathsep.join(parts)
    return env
```

Subprocess call alterado para usar `CREATE_NEW_CONSOLE` + `env=_build_server_env()`:

```python
proc = subprocess.Popen(
    full_cmd,
    cwd=str(Path(exe_path).parent),
    creationflags=subprocess.CREATE_NEW_CONSOLE,
    env=_build_server_env(),
)
```

---

#### Tentativa 9 — `?GameModIds=` na linha de comando vs `ActiveMods=` no INI (23/05/2026) ⏳ Em teste

**Descobertas que motivam esta hipótese:**

1. **O crash acontece mesmo com o ARKLAND fechado** (confirmado T8) → o gerenciador não é a causa.
2. **O crash só ocorre quando há um jogador conectado** → o timer do ArkShopUI (5 min) é inofensivo com servidor vazio; crasha no primeiro ciclo após jogador entrar.
3. **Mod `2693727499` (MX-E Ark Shop UI) está instalado em TODOS os servidores** — inclusive nos saudáveis (Crystal Isles / Brighamia). O usuário confirmou que o mod é carregado em todos eles.
4. **Diferença estrutural identificada na linha de comando:**
   - Servidor 01 (problemático): `?GameModIds=2693727499,3726048146` na linha de comando
   - Servidores saudáveis (ASM): **sem `?GameModIds=`** na linha de comando — mods carregados via `ActiveMods=` no `GameUserSettings.ini`

**Hipótese:**

O ARKLAND-Multi faz as duas coisas ao mesmo tempo:

- Escreve `ActiveMods=2693727499,3726048146` em `GameUserSettings.ini` (`ark_ini.py` linha 1284)
- Adiciona `?GameModIds=2693727499,3726048146` na linha de comando (`server_config.py` linha 651)

O ASM usa apenas `ActiveMods=` no INI — sem `?GameModIds=` na linha de comando.

Quando `?GameModIds=` está na linha de comando, ele **sobrepõe** a lista do INI. Isso pode causar uma diferença sutil na sequência/contexto de inicialização dos mods que, combinada com o ArkShopUI.dll V1.12, resulta em estado inválido ao processar jogadores no timer.

**Fix implementado em v1.3.38:** `?GameModIds=` removido de `server_config.py`. Mods carregados exclusivamente via `ActiveMods=` no `GameUserSettings.ini` — igual ao comportamento do ASM.

**Resultado:** ❌ Crash persistiu (confirmado em 23/05/2026). Remover `?GameModIds=` não foi suficiente. → Ver Tentativa 10.

---

#### Tentativa 10 — Remoção do plugin CustomShop (23/05/2026) ⏳ Em teste

**Descoberta que motiva esta hipótese:**

O plugin CustomShop (`plugin/CustomShop/src/`) registra dois hooks no ArkApi:

- `Hook_AShooterGameMode_HandleNewPlayer` — chama `CustomShop::Data::InitPlayer(player)` a cada jogador que entra
- `Hook_AShooterGameMode_BeginPlay` — chama `InitPlayer` para todos os jogadores conectados ao iniciar

O `InitPlayer` aciona `ShopBridge::GetOrAddShopBuff()` que aplica um buff permanente do mod FC_ArkShopUI (`ArkShopUI_Buff_FCAS`). Essa operação de buff pode estar interferindo com o estado interno do `ArkShopUI.dll` que é processado 5 min depois no timer `FTimerManager::Tick() → Hook_AGameState_DefaultTimer() → ArkShopUI.dll!0x6590`.

O crash ocorre APENAS quando um jogador está conectado, o que é exatamente quando `HandleNewPlayer` / `GetOrAddShopBuff` são acionados. Sem o CustomShop, o buff nunca é aplicado e o ArkShopUI.dll processa o timer sem estado corrompido.

**Fix implementado em v1.3.39:**

- Aba "Plugins" removida da UI do ARKLAND (CustomShop descontinuado)
- Auto-desinstalação do CustomShop no startup do ARKLAND para qualquer servidor que o tenha instalado
- Servidor deve ser reiniciado após a atualização para garantir que o plugin não seja carregado

**Resultado:** ❌ Crash persistiu. CustomShop não era a causa. → Ver Tentativa 11.

---

#### Tentativa 11 — Fix do arquivo `.mod` (modPath errado) (25/05/2026) ❌ Não resolveu

**Hipótese:** Comparação binária dos arquivos `.mod` revelou diferença crítica:

| Campo | ARKLAND gerado (304 bytes) | Steam Client oficial (255 bytes) |
| --- | --- | --- |
| `modPath` | `../../../ShooterGame/Content/Mods/2693727499` | `` (vazio) |

O ARK usa `modPath` vazio como caminho padrão para montar o VFS do mod. Com o campo preenchido incorretamente, o ARK falha no mount, a classe Blueprint `ArkShopUI_Buff_FCAS` fica `null` e o timer callback crasha ~5 min após um jogador conectar.

**Fix aplicado em v1.3.40–41:**

- ARKLAND não gera mais `.mod` files — usa exclusivamente o arquivo oficial do Steam Client
- `_find_official_dot_mod(mod_id)`: localiza `.mod` via registro do Windows + `libraryfolders.vdf`
- `repair_mod_files()`: substitui `.mod` incorretos pelo arquivo oficial

**Resultado:** ❌ Crash persistiu. `.mod` file não era a causa (ou fix incompleto — instalação já tinha `.mod` correto). → Ver Tentativa 12.

---

#### Tentativa 12 — Remoção de `__COMPAT_LAYER` antes do `os.startfile()` (25/05/2026) ❌ Não resolveu

**Hipótese:** O Windows aplica o shim `DetectorsAppHealth` ao `ARKLAND-Multi.exe`. Esse shim era propagado via variável de ambiente `__COMPAT_LAYER` para o `ShooterGameServer.exe`, potencialmente interceptando o SEH do ArkApi antes que ele pudesse capturar exceções internas do ArkShopUI.

**Fix aplicado em v1.3.44:** `__COMPAT_LAYER` removido do ambiente imediatamente antes do `os.startfile()` e restaurado após o lançamento.

**Resultado:** ❌ Crash persistiu. `__COMPAT_LAYER` não era a causa.

---

### Fatos confirmados (25/05/2026)

- Crash acontece mesmo com ARKLAND **completamente fechado**
- Crash acontece ao rodar **RunServer.cmd direto** (sem ARKLAND)
- **INI files comparados e idênticos** em estrutura entre ARKLAND e ASM
- **CLI params testados manualmente** (remoção de `?SessionName=`, `?ServerPassword=`, `?ServerAdminPassword=`, `?RCONEnabled=`, `?RCONPort=`): não resolveu
- São instalações **SEPARADAS** — ARKLAND instala o servidor do zero via SteamCMD, não reutiliza arquivos do ASM
- O ASM com a mesma config e mesmo DB **funciona sem crash**

---

### Tentativa 13 — Apontar ARKLAND para instalação do ASM (✅ CONCLUÍDA — 26/05/2026)

**Hipótese:** O problema está em algum arquivo que o ARKLAND instala diferente do ASM (não no que ele escreve antes de cada start).

**Procedimento:**

1. No ARKLAND, criar servidor temporário com `install_dir` apontando para o diretório onde o ASM instalou o servidor (sem reinstalar nada)
2. Manter mesmos parâmetros (porta, senha, mods, etc.)
3. Iniciar pelo ARKLAND (ele escreverá RunServer.cmd e INIs normalmente)
4. Conectar um jogador → aguardar 10 minutos

**Resultado: ✅ NÃO CRASHOU** — servidor funcionou normalmente com a instalação do ASM, iniciado pelo ARKLAND.

**Conclusão confirmada:** O problema **não está** no que o ARKLAND escreve (RunServer.cmd / INI) antes de cada start. O problema está em **algum arquivo que o ARKLAND instala via SteamCMD diferente do ASM**. → Ver Tentativa 14.

---

### Tentativa 14 — Comparação binária das duas instalações (⏳ PENDENTE)

**Hipótese:** O SteamCMD instalado pelo ARKLAND produz algum arquivo diferente em relação à instalação feita pelo ASM. Pode ser um binário, DLL, arquivo de configuração ou estrutura de diretório.

**Procedimento:**

1. Listar e comparar os arquivos das duas instalações — foco em:
   - `ShooterGame/Binaries/Win64/` — DLLs e `.exe`
   - `ShooterGame/Plugins/` — ArkApi, DLLs de plugins
   - `Engine/Binaries/Win64/` — DLLs do engine
   - `ShooterGame/Content/Mods/` — arquivos `.mod`
2. Diff de tamanho + hash (MD5/SHA1) de cada arquivo suspeito
3. Identificar qualquer arquivo presente em uma instalação e ausente na outra
4. Identificar qualquer arquivo com tamanho ou hash diferente entre as duas

**Comando sugerido (PowerShell):**

```powershell
# Comparar hashes de todos os arquivos nas duas pastas
$asm  = "C:\<CAMINHO_ASM>"
$ark  = "C:\<CAMINHO_ARKLAND>"
$left  = Get-ChildItem $asm  -Recurse -File | ForEach-Object { [pscustomobject]@{ Path=$_.FullName.Replace($asm,""); Hash=(Get-FileHash $_.FullName -Algorithm MD5).Hash } }
$right = Get-ChildItem $ark  -Recurse -File | ForEach-Object { [pscustomobject]@{ Path=$_.FullName.Replace($ark,""); Hash=(Get-FileHash $_.FullName -Algorithm MD5).Hash } }
Compare-Object $left $right -Property Path,Hash
```

**Interpretação:**

- Arquivo presente só na instalação do ASM → o SteamCMD do ARKLAND não baixa esse arquivo
- Arquivo com hash diferente → versão diferente instalada pelo SteamCMD do ARKLAND vs ASM
- Arquivo presente só no ARKLAND → arquivo extra sendo copiado incorretamente

---

### Referência ASM Source

**Path local:** `C:\Users\Ciano\Documents\_asm_src\ARK Server Manager\`

Arquivos-chave:

- `Lib/ServerProfile.cs` — ~300 campos com `[IniFileEntry]`, categorias: Administration / Rules / ChatAndNotifications / HudAndVisuals / Players / Dinos / Environment / Structures
- `Lib/ServerRuntime.cs` — start/stop/monitor do servidor
- `Lib/ServerApp.cs` — SteamCMD update/install
- `Lib/ServerRCON.cs` — RCON
- `Windows/ServerSettingsControl.xaml` — UI completa (608KB)
- `Config.settings` — RunServer.cmd em `ShooterGame\Saved\Config\WindowsServer\`, flags: `-nosteamclient -game -server -log`

**Diferenças CLI ASM vs ARKLAND:**

| Parâmetro | ASM | ARKLAND |
| --- | --- | --- |
| `?SessionName=` | Só no INI | CLI + INI |
| `?ServerPassword=` | Só no INI | CLI + INI |
| `?ServerAdminPassword=` | Só no INI | CLI + INI |
| `?RCONEnabled=` / `?RCONPort=` | Só no INI | CLI + INI |
| `?Port=` / `?QueryPort=` | Só como `?param` | `?param` + `-flag` (duplicado) |
| Ordem das flags | `-nosteamclient -game -server -log` | `-server -log -nosteamclient -game` |

### Checklist T14

- [ ] Obter o caminho exato das duas instalações (ASM e ARKLAND)
- [ ] Rodar o diff de hashes (comando PowerShell acima)
- [ ] Identificar arquivos diferentes ou ausentes
- [ ] Registrar resultado e planejar T15
