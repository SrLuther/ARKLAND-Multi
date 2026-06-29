"""
Motor de sincronização bidirecional para o ARKLAND - Server Manager.

Lógica:
  A cada N segundos realiza dois passes:
    1. Pasta local (ARK Cluster) → Pasta compartilhada
    2. Pasta compartilhada       → Pasta local (ARK Cluster)
  Em cada passe, um arquivo só é copiado se:
    - Não existir no destino, OU
    - A origem for mais recente que o destino (tolerância de 500 ms)
  Resultado: ambas as pastas ficam sempre com os arquivos mais recentes.

  Pastas remotas (outra máquina com ARKLAND rodando) são suportadas usando
  o prefixo  @remote|<identity_code>|<caminho_remoto>  no lugar do caminho.
"""
import shutil
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Optional

_REMOTE_PREFIX     = "@remote|"   # legado: @remote|BASE64|path
_REMOTE_PREFIX_NEW = "@remote:"   # novo:   @remote:HOST:PORT|path


def _fmt_size(size: int) -> str:
    kb = size / 1024
    return f"{kb:.1f} KB" if kb < 1024 else f"{kb / 1024:.2f} MB"


# ── Abstrações de pasta ───────────────────────────────────────────────────────

class _LocalSyncFolder:
    """Representa uma pasta local para sync."""

    def __init__(self, path: Path) -> None:
        self._path = path

    @property
    def label(self) -> str:
        return str(self._path)

    @property
    def exists(self) -> bool:
        return self._path.is_dir()

    def list_files(self) -> list:
        result = []
        for f in self._path.rglob("*"):
            if f.is_file():
                rel = f.relative_to(self._path).as_posix()
                st  = f.stat()
                result.append({"rel": rel, "mtime": st.st_mtime, "size": st.st_size})
        return result

    def read_file(self, rel: str) -> bytes:
        return (self._path / rel).read_bytes()

    def write_file(self, rel: str, data: bytes) -> None:
        target = self._path / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)


class _RemoteSyncFolder:
    """Representa uma pasta em outra máquina acessível via RemoteAgent HTTP."""

    def __init__(self, client: Any, root: str, name: str = "") -> None:
        self._client = client
        self._root   = root
        self._name   = name or root

    @property
    def label(self) -> str:
        return f"[remoto:{self._name}] {self._root}"

    @property
    def exists(self) -> bool:
        return True  # verificado ao chamar list_files

    def list_files(self) -> list:
        return self._client.fs_list(self._root)

    def read_file(self, rel: str) -> bytes:
        return self._client.fs_read(self._root, rel)

    def write_file(self, rel: str, data: bytes) -> None:
        result = self._client.fs_write(self._root, rel, data)
        if isinstance(result, dict) and "error" in result:
            raise OSError(result["error"])


class SyncEngine:
    def __init__(
        self,
        config,
        on_log: Optional[Callable[[str, str], None]] = None,
        on_status_change: Optional[Callable[[str], None]] = None,
        on_stats_update: Optional[Callable[[dict], None]] = None,
    ) -> None:
        self._config = config
        self._on_log = on_log or (lambda msg, level: None)
        self._on_status_change = on_status_change or (lambda s: None)
        self._on_stats_update = on_stats_update or (lambda s: None)

        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()          # evita execuções simultâneas
        self._stats = {
            "total_synced": 0,
            "last_sync": "—",
            "errors": 0,
            "cycles": 0,
            "error_list": [],
        }

    # ── Controle público ───────────────────────────────────────────────────────

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def stats(self) -> dict:
        return self._stats.copy()

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(
            target=self._loop, daemon=True, name="ArkSyncThread"
        )
        self._thread.start()
        self._on_status_change("running")
        self._log("Sincronização iniciada.", "info")

    def stop(self) -> None:
        if not self._running:
            return
        self._running = False
        self._on_status_change("stopped")
        self._log("Sincronização parada.", "info")

    def sync_once(self) -> None:
        """Executa um ciclo imediato em background (não inicia o loop)."""
        threading.Thread(
            target=self._run_cycle, daemon=True, name="ArkForceSyncThread"
        ).start()

    # ── Loop interno ───────────────────────────────────────────────────────────

    def _loop(self) -> None:
        while self._running:
            self._run_cycle()
            interval = max(1, getattr(self._config, "sync_interval", 5))
            time.sleep(interval)

    def clear_errors(self) -> None:
        """Zera o contador e a lista de erros."""
        self._stats["errors"] = 0
        self._stats["error_list"] = []
        self._on_stats_update(self._stats.copy())

    def _add_error(self, message: str, etype: str = "") -> None:
        """Registra um erro: incrementa contador, salva na lista e emite log."""
        ts = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        self._stats["errors"] += 1
        self._stats["error_list"].append(
            {"time": ts, "type": etype, "message": message}
        )
        self._log(message, "error")

    def _run_cycle(self) -> None:
        """Executa um ciclo de sync com lock para evitar sobreposição."""
        if not self._lock.acquire(blocking=False):
            return  # já está sincronizando
        try:
            self._sync()
        except Exception as exc:
            self._add_error(f"Erro inesperado: {exc}", "geral")
        finally:
            self._lock.release()

    # ── Lógica de sincronização ────────────────────────────────────────────────

    def _make_folder(self, path_str: str) -> Optional[Any]:
        """Cria _LocalSyncFolder ou _RemoteSyncFolder a partir de uma string de caminho.

        Suporta dois formatos:
          novo    @remote:HOST:PORT|remote_path   (token buscado em tempo real)
          legado  @remote|BASE64|remote_path      (token do BASE64 ignorado; usa instância salva)
        Em ambos os casos o token é sempre buscado de config.remote_instances pelo host+porta,
        eliminando o problema de "token congelado" ao regenerar o token da instância remota.
        """
        if path_str.startswith(_REMOTE_PREFIX_NEW):
            # Novo formato: @remote:HOST:PORT|remote_path
            rest  = path_str[len(_REMOTE_PREFIX_NEW):]
            parts = rest.split("|", 1)
            if len(parts) != 2:
                self._log(f"Formato inválido de pasta remota: {path_str!r}", "error")
                return None
            addr, remote_path = parts
            addr_parts = addr.rsplit(":", 1)
            if len(addr_parts) != 2:
                self._log(f"Endereço inválido no caminho remoto: {addr!r}", "error")
                return None
            host, port_str = addr_parts
            port = int(port_str)
            name = host

        elif path_str.startswith(_REMOTE_PREFIX):
            # Legado: @remote|BASE64|remote_path  — decodifica só para extrair host+port
            rest  = path_str[len(_REMOTE_PREFIX):]
            parts = rest.split("|", 1)
            if len(parts) != 2:
                self._log(f"Formato inválido de pasta remota: {path_str!r}", "error")
                return None
            code, remote_path = parts
            try:
                from .remote_agent import parse_identity_code
                identity = parse_identity_code(code)
                host = identity["h"]
                port = identity["p"]
                name = identity.get("n", host)
            except Exception as exc:
                self._log(f"Erro ao decodificar caminho remoto: {exc}", "error")
                return None

        else:
            return _LocalSyncFolder(Path(path_str))

        # Busca token ATUAL da instância salva (evita token congelado)
        instances = getattr(self._config, "remote_instances", []) or []
        inst = next(
            (i for i in instances
             if i.get("host") == host and int(i.get("port", 32440)) == port),
            None,
        )
        token = inst.get("token", "") if inst else ""
        if inst and inst.get("name"):
            name = inst["name"]
        try:
            from .remote_agent import RemoteClient
            client = RemoteClient(host, port, token)
            return _RemoteSyncFolder(client, remote_path, name=name)
        except Exception as exc:
            self._log(f"Erro ao conectar pasta remota: {exc}", "error")
            return None

    def _sync(self) -> None:
        cycles = getattr(self._config, "sync_cycles", None) or []

        # Compatibilidade com config legado (local_cluster_path / shared_path)
        if not cycles:
            local_str  = getattr(self._config, "local_cluster_path", "").strip()
            shared_str = getattr(self._config, "shared_path", "").strip()
            if local_str and shared_str:
                cycles = [[local_str, shared_str]]

        if not cycles:
            self._log("Nenhum ciclo configurado. Acesse a aba Sincronização.", "warning")
            return

        total_synced = 0
        for idx, cycle in enumerate(cycles):
            if isinstance(cycle, dict):
                folder_paths = cycle.get("folders", [])
                numeric_only = bool(cycle.get("numeric_only", False))
                config_json_only = bool(cycle.get("config_json_only", False))
            elif isinstance(cycle, list):
                folder_paths = cycle
                numeric_only = False
                config_json_only = False
            else:
                continue
            folder_objs = [self._make_folder(str(p)) for p in folder_paths if str(p).strip()]
            folder_objs = [f for f in folder_objs if f is not None]
            # Verifica pastas locais existentes; pastas remotas são verificadas pelo list_files
            valid: list = []
            for f in folder_objs:
                if isinstance(f, _LocalSyncFolder) and not f.exists:
                    self._log(f"[Ciclo {idx + 1}] Pasta não encontrada: {f.label}", "warning")
                else:
                    valid.append(f)
            if len(valid) < 2:
                continue
            total_synced += self._sync_cycle(
                idx + 1, valid,
                numeric_only=numeric_only,
                config_json_only=config_json_only,
            )

        self._stats["cycles"] += 1
        self._stats["last_sync"] = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

        if total_synced > 0:
            self._stats["total_synced"] += total_synced
            self._log(
                f"Sync #{self._stats['cycles']}: {total_synced} arquivo(s) copiado(s)  "
                f"[acumulado: {self._stats['total_synced']}]",
                "success",
            )
        elif getattr(self._config, "log_debug", False):
            self._log(f"Ciclo #{self._stats['cycles']}: nenhuma alteração.", "debug")

        self._on_stats_update(self._stats.copy())

    def _sync_cycle(
        self,
        cycle_num: int,
        folders: list,
        numeric_only: bool = False,
        config_json_only: bool = False,
    ) -> int:
        """Sync N-way: pre-fetcha lista de arquivos e propaga a versão mais nova."""
        # Pre-fetch: lista os arquivos de cada pasta uma vez (HTTP ou disco)
        folder_files: list = []
        for folder in folders:
            try:
                entries   = folder.list_files()
                file_dict = {e["rel"]: e for e in entries}
            except Exception as exc:
                self._add_error(
                    f"[Ciclo {cycle_num}] Leitura '{folder.label}': {exc}  "
                    f"— ciclo abortado para evitar cópias indevidas.",
                    "I/O",
                )
                return 0   # ← aborta o ciclo inteiro se qualquer pasta falhar
            folder_files.append((folder, file_dict))

        # Coleta todos os caminhos relativos conhecidos
        all_rels: set = set()
        for _, fd in folder_files:
            all_rels.update(fd.keys())

        count = 0
        for rel in all_rels:
            rel_name = Path(rel).name.lower()
            if config_json_only and rel_name != "config.json":
                continue
            if numeric_only and not Path(rel).stem.isdigit():
                continue
            # Encontra a pasta com a versão mais recente
            newest_folder = None
            newest_mtime  = -1.0
            newest_size   = 0
            for folder, fd in folder_files:
                entry = fd.get(rel)
                if entry and entry["mtime"] > newest_mtime:
                    newest_mtime  = entry["mtime"]
                    newest_folder = folder
                    newest_size   = entry.get("size", 0)
            if newest_folder is None:
                continue

            # Propaga para as pastas desatualizadas
            for folder, fd in folder_files:
                if folder is newest_folder:
                    continue
                dst_entry = fd.get(rel)
                if dst_entry and dst_entry["mtime"] >= newest_mtime - 0.5:
                    continue  # já está atualizado
                try:
                    data   = newest_folder.read_file(rel)
                    folder.write_file(rel, data)
                    count += 1
                    action   = "novo" if dst_entry is None else "atualizado"
                    size_str = _fmt_size(newest_size) if newest_size else "?"
                    self._log(
                        f"  ↪ [C{cycle_num}][{action}] {rel}  ({size_str})"
                        f"  {newest_folder.label} → {folder.label}",
                        "debug",
                    )
                except Exception as exc:
                    self._add_error(f"[Ciclo {cycle_num}] Cópia '{rel}': {exc}", "I/O")
        return count

    def _copy_newer(self, src_root: Path, dst_root: Path) -> int:
        """Copia para dst_root todos os arquivos de src_root que forem mais novos."""
        count = 0
        try:
            for src_file in src_root.rglob("*"):
                if not src_file.is_file():
                    continue
                rel = src_file.relative_to(src_root)
                dst_file = dst_root / rel
                if self._should_copy(src_file, dst_file):
                    dst_file.parent.mkdir(parents=True, exist_ok=True)
                    is_new = not dst_file.exists()
                    shutil.copy2(src_file, dst_file)
                    count += 1
                    action = "novo" if is_new else "atualizado"
                    try:
                        size_kb = src_file.stat().st_size / 1024
                        size_str = f"{size_kb:.1f} KB" if size_kb < 1024 else f"{size_kb/1024:.2f} MB"
                    except OSError:
                        size_str = "?"
                    self._log(
                        f"  ↪ [{action}] {rel}  ({size_str})  "
                        f"{src_root.name} → {dst_root.name}",
                        "debug",
                    )
        except PermissionError as exc:
            self._add_error(f"Permissão negada: {exc}", "permissão")
        except OSError as exc:
            self._add_error(f"Erro de I/O: {exc}", "I/O")
        return count

    @staticmethod
    def _should_copy(src: Path, dst: Path) -> bool:
        if not dst.exists():
            return True
        try:
            # Copia se origem for mais nova que destino (tolerância 500 ms)
            return src.stat().st_mtime > dst.stat().st_mtime + 0.5
        except OSError:
            return True

    # ── Utilitário ────────────────────────────────────────────────────────────

    def _log(self, message: str, level: str = "info") -> None:
        ts = datetime.now().strftime("%H:%M:%S")
        self._on_log(f"[{ts}] {message}", level)
