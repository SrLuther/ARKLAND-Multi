# Problemas Pendentes — ARKLAND Server Manager

> Este arquivo é usado para anotar pendências e problemas a investigar posteriormente.
> Adicione entradas aqui sempre que identificar um bug ou melhoria que não será resolvido imediatamente.

---

## ~~[BUG] `mod_auto_updater.py` — `__import__("threading")` desnecessário~~ ✅ RESOLVIDO

**Arquivo:** `src/mod_auto_updater.py`, linha 127  
**Descrição:** `threading` já é importado no topo do módulo, mas na função `_install_missing_mods` era usado `__import__("threading").Event()` em vez de `threading.Event()` diretamente.  
**Correção aplicada:** substituído por `threading.Event()`.

---

## ~~[BUG] `server_manager.py` — `_update_restart` acessa `_instances` sem lock~~ ✅ RESOLVIDO

**Arquivo:** `src/server_manager.py`, linhas 328–337  
**Descrição:** O closure `_update_restart` lia `self._instances.get(sid)` diretamente em loop, sem adquirir `self._lock`.  
**Correção aplicada:** acesso ao dicionário agora envolto em `with self._lock`.

---

## ~~[MEMORY LEAK] `server_manager.py` — `_sched_fired`/`_sched_warned` crescem indefinidamente~~ ✅ RESOLVIDO

**Arquivo:** `src/server_manager.py`, linhas 255–256  
**Descrição:** Os dicionários acumulavam entradas a cada dia de operação e nunca eram limpos.  
**Correção aplicada:** `_scheduler_tick` agora remove entradas cujo valor (`date`) seja anterior a `today` no início de cada ciclo.

---

## ~~[SEGURANÇA] `remote_agent.py` — token vazio bypassa autenticação~~ ✅ RESOLVIDO

**Arquivo:** `src/remote_agent.py`, linha 66–67  
**Descrição:** Com `token=""` (padrão), qualquer requisição com `Authorization: Bearer` passava na verificação.  
**Correção aplicada:** `_auth()` rejeita imediatamente se `agent._token` for vazio (`if not agent._token: return False`).

---

---

## ~~[BUG] `server_manager.py` — `restart_server._do` e `_reconnect_monitor` sem lock~~ ✅ RESOLVIDO

**Arquivos:** `src/server_manager.py`, linhas ~581–588 e ~494–530  
**Descrição:** O closure `_do` de `restart_server` e o método `_reconnect_monitor` acessavam `self._instances.get(server_id)` e modificavam atributos como `inst.process`/`inst.pid` sem adquirir `self._lock`.  
**Correção aplicada:** acessos a `self._instances` e mutações de `inst` envolvidos em `with self._lock` em ambos os locais.

---

## ~~[BUG] `mod_manager.py` — race condition em `_active` (TOCTOU)~~ ✅ RESOLVIDO

**Arquivo:** `src/mod_manager.py`, linhas ~87 e ~262  
**Descrição:** `download_mods()` e `install_server()` checavam `self._active` sem lock — dois threads poderiam iniciar operações simultaneamente.  
**Correção aplicada:** adicionado `self._lock = threading.Lock()` e a verificação+atribuição de `_active` agora é feita atomicamente com `with self._lock` em ambos os métodos.

---

## ~~[RISCO] `config_manager.py` — `save()` / `save_servers()` não são atômicos~~ ✅ RESOLVIDO

**Arquivo:** `src/config_manager.py`  
**Descrição:** Escritas diretas nos arquivos de destino poderiam resultar em arquivos corrompidos em caso de crash durante a gravação.  
**Correção aplicada:** todos os três métodos agora gravam em arquivo `.tmp` e usam `Path.replace()` para rename atômico.

---

## ~~[MANUTENÇÃO] `updater.py` — PowerShell fallback usa `System.Net.WebClient` (deprecated)~~ ✅ RESOLVIDO

**Arquivo:** `src/updater.py`, método `_launch_updater_agent`  
**Descrição:** O script PowerShell gerado usava `New-Object System.Net.WebClient` / `DownloadFile()`, deprecado no .NET 6+.  
**Correção aplicada:** substituído por `Invoke-WebRequest -Uri $dlUrl -OutFile $installer -UseBasicParsing`.

---

## ~~[BUG] `buff_manager.py` — usa `ServerChat` em vez de `Broadcast`~~ ✅ RESOLVIDO

**Arquivo:** `src/buff_manager.py`, método `_rcon_broadcast`  
**Descrição:** O BUFF manager enviava avisos via `ServerChat`, que só aparece no chat, enquanto o resto do código usa `Broadcast` (mensagem em destaque na tela).  
**Correção aplicada:** substituído `ServerChat` por `Broadcast`.

---

## [BUILD] Plugin C++ `CustomShop.dll` — ✅ BUILD SUCCEEDED

**Localização:** `plugin/CustomShop/`  
**DLL gerada em:** `plugin/CustomShop/bin/CustomShop.dll`  
**Lib de importação:** `plugin/CustomShop/bin/CustomShop.lib`

### Ambiente de build

| Item         |                      Valor                    |
|--------------|-----------------------------------------------|
| Compilador   | MSVC 14.51.36231 (Visual Studio 18 Community) |
| Windows SDK  | 10.0.26100.0                                  |
| cl.exe       | `C:\Program Files\Microsoft Visual Studio\18\Community\VC\Tools\MSVC\14.51.36231\bin\Hostx64\x64\cl.exe` |
| ArkApi SDK | `plugin/CustomShop/ArkServerAPI/version/Core/Public/` |
| Build script | `plugin/CustomShop/build_cl.bat` |
| Flags críticas | `/DUNICODE /D_UNICODE /DARK_GAME /std:c++17 /EHsc /MT` |

### Correções aplicadas até o build final

1. **`build_cl.bat`** — renomeados `CL`→`CL_EXE` e `LINK`→`LINK_EXE` (variáveis reservadas do MSVC); adicionados `/DUNICODE /D_UNICODE`

2. **`src/pch.h`** — `#include <API/ARK/Ark.h>` colocado ANTES de `<Windows.h>` para evitar redefinição de `TCHAR` (C2371)

3. **`src/Main.cpp`** — loops em `TWeakObjectPtr<APlayerController>` iterados por valor (não `const&`) pois `Get()` não é `const`

4. **`src/Commands.cpp`**:
   - Adicionado helper `SplitCmd(FString*)` que converte `FString` para `std::vector<std::string>` via `std::istringstream`, evitando `ParseIntoArray` com literal `wchar_t` (incompatível com `TCHAR*`)
   - Substituídas TODAS as chamadas `ParseIntoArray` + `TArray<FString>` pelo helper em: `CmdBuyItem`, `CmdGetShopItems`, `CmdAdminAddPoints`, `CmdAdminSetPoints`, `CmdAdminGetPoints`
   - Adicionados `#undef max` / `#undef min` para evitar conflito com macros do Windows e `std::max`
   - Loop em `CmdAdminReload` corrigido para iterar por valor

5. **`src/ShopBridge.cpp`**:
   - `FName(TEXT("..."))` substituído por `FName("...")` (narrow `const char*`) — o SDK não expõe construtor `FName(const TCHAR*)`, apenas `FName(const char*, EFindName)`
   - Loop `for (const TWeakObjectPtr<APlayerController>& wpc : ...)` corrigido para iteração por valor
   - `UVictoryCore::BPLoadClass(buff_path)` corrigido para `BPLoadClass(&buff_path)`

6. **`src/ShopStore.cpp`** — `RunCommands` corrigida para receber `AShooterPlayerController*` e usar `controller->ConsoleCommand(&result, &fscmd, true)` (método não existe em `AShooterGameMode`)

7. **`ArkServerAPI/version/Core/Public/API/UE/UE.h`** — adicionado overload `FName(const char* Name)` usando `Init(Name, 0, EFindName::FNAME_Add, true, -1)` (o SDK só expunha o construtor 2-param; nota: `EFindName` é `enum class`, exige qualificação `EFindName::FNAME_Add`)

### Próximos passos (deploy)

1. Copiar `bin/CustomShop.dll` para `<ArkServer>/ShooterGame/Binaries/Win64/ArkApi/Plugins/CustomShop/CustomShop.dll`
2. Copiar `configs/config.json` (template) para o mesmo diretório
3. Configurar `config.json` com as chaves de banco, preços dos itens e kit definitions
4. Reiniciar o servidor ARK para carregar o plugin

### Estrutura final de arquivos do plugin

```bash
plugin/CustomShop/
├── build_cl.bat               ← script de build (cmd, não MSBuild)
├── bin/
│   ├── CustomShop.dll         ← ✅ DLL gerada
│   └── CustomShop.lib         ← lib de importação
├── src/
│   ├── pch.h                  ← ARK headers ANTES de Windows.h
│   ├── Main.cpp               ← PluginLoad / PluginUnload
│   ├── Commands.cpp           ← comandos RCON/console (BuyItem, Shop.AddPoints, etc.)
│   ├── ShopBridge.cpp         ← GetSteamId, FindPlayer, GetOrAddShopBuff
│   ├── ShopConfig.h/.cpp      ← leitura de config.json
│   ├── ShopData.h/.cpp        ← serialização JSON para o cliente mod
│   ├── ShopPoints.h/.cpp      ← gerenciamento de pontos (SQLite)
│   └── ShopStore.h/.cpp       ← lógica de compra/kit
├── ArkServerAPI/
│   ├── out_lib/ArkApi.lib
│   └── version/Core/Public/   ← SDK headers (UE.h modificado)
└── configs/
    └── config.json            ← template de configuração
```
