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

### Fix aplicado (`server_manager.py`)

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
