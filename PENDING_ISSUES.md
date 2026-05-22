# Problemas Pendentes — ARKLAND Server Manager

> Este arquivo é usado para anotar pendências e problemas a investigar posteriormente.
> Adicione entradas aqui sempre que identificar um bug ou melhoria que não será resolvido imediatamente.

---

## [TESTE] `server_manager.py` — Fix do crash ao conectar jogadores (aguardando confirmação em produção)

**Status:** ✅ Fix aplicado em v1.3.28 — ⏳ aguardando teste em produção

**Arquivo corrigido:** `src/server_manager.py`

---

### Sintoma

Crash fatal do servidor ARK imediatamente após um jogador conectar, **somente quando o servidor era iniciado pelo ARKLAND-Multi**. Quando iniciado pelo ASM (ArkServerManager), o servidor funcionava normalmente.

Stack trace do crash:

```text
Fatal error!
ArkShopUI.dll!UnknownFunction (0x0000000180006590)
ArkShopUI.dll!UnknownFunction (0x00000001800103c5)
VERSION.dll!ArkApi::Commands::CheckOnTimerCallbacks()
VERSION.dll!ArkApi::Hook_AGameState_DefaultTimer()
ShooterGameServer.exe!FTimerManager::Tick()
```

---

### Histórico de investigação

#### Tentativa 1 — Hipótese `_MEIPASS\z.dll` → Fix v1.3.28 (22/05/2026) ❌ Não resolveu

**Hipótese:** O PyInstaller (modo onefile) extrai os arquivos para `%TEMP%\_MEIxxxxxx\` e prepend esse diretório ao `PATH` do processo Python. O PyInstaller detecta `z.dll` (zlib do CustomShop) como dependência binária e a copia para `_MEIPASS\z.dll`. O servidor filho herdava o PATH modificado → `libmariadb.dll` carregava a `z.dll` errada → crash no timer callback do ArkShopUI.

**Fix aplicado:** `_build_server_env()` remove `_MEIPASS` do PATH + `CREATE_NEW_CONSOLE` no `subprocess.Popen`.

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

#### Tentativa 6 — Lançamento via `cmd.exe /c RunServer.cmd` (método idêntico ao ASM) (22/05/2026) ⏳ Em teste

**Descoberta da causa raiz (análise do source ArkShopUI/ArkShop):**

Repositório oficial: https://github.com/ArkServerApi/ASE-Plugins/releases — source do ArkShop.dll disponível; ArkShopUI.dll é **binário fechado** (só o helper header está disponível).

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

**Resultado:** ⏳ aguardando teste em produção

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

### Checklist de confirmação

- [ ] Instalar v1.3.28 no servidor de produção
- [ ] Iniciar o servidor **pelo ARKLAND-Multi** (não pelo ASM)
- [ ] Conectar um jogador e aguardar alguns minutos sem crash
- [ ] Confirmar que ArkShopUI, ArkShop e Permissions funcionam normalmente
- [ ] Marcar como ✅ RESOLVIDO
