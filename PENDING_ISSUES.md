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

## ~~[INCONSISTÊNCIA] `buff_manager.py` — usa `ServerChat` em vez de `Broadcast`~~ ✅ RESOLVIDO

**Arquivo:** `src/buff_manager.py`, método `_rcon_broadcast`  
**Descrição:** O BUFF manager enviava avisos via `ServerChat`, que só aparece no chat, enquanto o resto do código usa `Broadcast` (mensagem em destaque na tela).  
**Correção aplicada:** substituído `ServerChat` por `Broadcast`.
