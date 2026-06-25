"""Gerenciamento do bot Discord oBobonicClean (subprocesso externo)."""
from __future__ import annotations

import os
import queue
import re
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

CREATE_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0
CREATE_NEW_PROCESS_GROUP = 0x00000200 if sys.platform == "win32" else 0

DEFAULT_PROJECT_PATH = r"C:\Users\Ciano\Documents\oBobonicClean"

_ARK_MAP_PREFIX = re.compile(
    r"^ARK_MAP(\d+)_(NAME|PORT|HOST|PASSWORD|SERVICE|MAX_PLAYERS|QUERY_PORT|BATTLEMETRICS_ID)$"
)
_ENV_KEY_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_TOKEN_PLACEHOLDERS = frozenset({
    "",
    "token_falso_para_dev",
    "seu_token_aqui",
    "discord_token",
    "xxx",
})


@dataclass
class ArkMapEntry:
    index: int
    name: str = ""
    port: str = ""
    host: str = ""
    password: str = ""
    service: str = ""
    max_players: str = "50"
    query_port: str = ""
    battlemetrics_id: str = ""

    def is_valid(self) -> bool:
        return bool(self.name.strip() and self.port.strip())


@dataclass
class MapHealthResult:
    name: str
    host: str
    rcon_port: int
    rcon_ok: bool = False
    rcon_detail: str = ""
    query_ok: bool = False
    players: Optional[int] = None
    max_players: Optional[int] = None

    @property
    def online(self) -> bool:
        return self.rcon_ok or self.query_ok

    @property
    def status_label(self) -> str:
        if self.rcon_ok:
            if self.players is not None:
                cap = self.max_players if self.max_players is not None else "?"
                return f"Online — {self.players}/{cap} jogadores"
            return "Online (RCON OK)"
        if self.query_ok:
            if self.players is not None:
                cap = self.max_players if self.max_players is not None else "?"
                return f"Online — {self.players}/{cap} (query)"
            return "Online (query)"
        return "Offline"


def _venv_python(project_dir: Path) -> Path:
    if sys.platform == "win32":
        return project_dir / ".venv" / "Scripts" / "python.exe"
    return project_dir / ".venv" / "bin" / "python"


def _system_python_candidates() -> List[List[str]]:
    cmds: List[List[str]] = []
    if sys.platform == "win32":
        cmds.append(["py", "-3"])
    for name in ("python", "python3", "python.exe", "python3.exe"):
        cmds.append([name])
    return cmds


def _resolve_system_python() -> Optional[List[str]]:
    flags = CREATE_NO_WINDOW if sys.platform == "win32" else 0
    for cmd in _system_python_candidates():
        try:
            result = subprocess.run(
                [*cmd, "--version"],
                capture_output=True,
                text=True,
                creationflags=flags,
            )
            if result.returncode == 0:
                return cmd
        except OSError:
            continue
    return None


def parse_ark_maps_from_env(text: str) -> List[ArkMapEntry]:
    """Extrai entradas ARK_MAP* de um arquivo .env."""
    maps: dict[int, ArkMapEntry] = {}
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if "=" not in stripped:
            continue
        key, _, value = stripped.partition("=")
        key = key.strip()
        value = value.strip()
        m = _ARK_MAP_PREFIX.match(key)
        if not m:
            continue
        idx = int(m.group(1))
        field_name = m.group(2).lower()
        entry = maps.setdefault(idx, ArkMapEntry(index=idx))
        if field_name == "name":
            entry.name = value
        elif field_name == "port":
            entry.port = value
        elif field_name == "host":
            entry.host = value
        elif field_name == "password":
            entry.password = value
        elif field_name == "service":
            entry.service = value
        elif field_name == "max_players":
            entry.max_players = value
        elif field_name == "query_port":
            entry.query_port = value
        elif field_name == "battlemetrics_id":
            entry.battlemetrics_id = value
    return [maps[i] for i in sorted(maps) if maps[i].is_valid()]


def write_ark_maps_to_env(text: str, maps: List[ArkMapEntry]) -> str:
    """Atualiza ou insere blocos ARK_MAP no conteúdo .env."""
    lines = text.splitlines()
    keep: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            key = stripped.split("=", 1)[0].strip()
            if _ARK_MAP_PREFIX.match(key):
                continue
        keep.append(line)
    while keep and not keep[-1].strip():
        keep.pop()
    if maps:
        keep.append("")
        keep.append("# --- Mapas ARK (salas) — editado pelo ARKLAND TEK ---")
        for entry in maps:
            if not entry.is_valid():
                continue
            n = entry.index
            keep.append(f"ARK_MAP{n}_NAME={entry.name}")
            keep.append(f"ARK_MAP{n}_PORT={entry.port}")
            if entry.host:
                keep.append(f"ARK_MAP{n}_HOST={entry.host}")
            if entry.password:
                keep.append(f"ARK_MAP{n}_PASSWORD={entry.password}")
            if entry.service:
                keep.append(f"ARK_MAP{n}_SERVICE={entry.service}")
            if entry.max_players:
                keep.append(f"ARK_MAP{n}_MAX_PLAYERS={entry.max_players}")
            if entry.query_port:
                keep.append(f"ARK_MAP{n}_QUERY_PORT={entry.query_port}")
            if entry.battlemetrics_id:
                keep.append(f"ARK_MAP{n}_BATTLEMETRICS_ID={entry.battlemetrics_id}")
            keep.append("")
    return "\n".join(keep).rstrip() + "\n"


def update_env_keys(text: str, updates: Dict[str, str]) -> str:
    """Atualiza chaves simples no .env (preserva comentários e blocos ARK_MAP)."""
    if not updates:
        return text
    lines = text.splitlines()
    seen: set[str] = set()
    out: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            key = stripped.split("=", 1)[0].strip()
            if key in updates and _ENV_KEY_RE.match(key):
                out.append(f"{key}={updates[key]}")
                seen.add(key)
                continue
        out.append(line)
    pending = [k for k in updates if k not in seen and _ENV_KEY_RE.match(k)]
    if pending:
        if out and out[-1].strip():
            out.append("")
        out.append("# --- Atualizado pelo ARKLAND TEK (oBobonic) ---")
        for key in pending:
            out.append(f"{key}={updates[key]}")
    result = "\n".join(out)
    if not result.endswith("\n"):
        result += "\n"
    return result


def read_env_value(text: str, key: str) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        k, _, v = stripped.partition("=")
        if k.strip() == key:
            return v.strip()
    return ""


def validate_discord_token(env_text: str) -> Tuple[bool, str]:
    token = read_env_value(env_text, "DISCORD_TOKEN")
    if not token:
        return False, "DISCORD_TOKEN ausente no .env do bot."
    low = token.lower().strip()
    if low in _TOKEN_PLACEHOLDERS or len(token) < 20:
        return False, "DISCORD_TOKEN inválido ou placeholder no .env."
    if token.count(".") < 2:
        return False, "DISCORD_TOKEN parece malformado (formato Discord esperado)."
    return True, "Token Discord OK"


def load_dotenv_dict(project_dir: Path) -> Dict[str, str]:
    """Carrega pares chave=valor do .env (sem expandir variáveis)."""
    env_path = project_dir / ".env"
    result: Dict[str, str] = {}
    if not env_path.is_file():
        return result
    try:
        text = env_path.read_text(encoding="utf-8")
    except OSError:
        return result
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, _, value = stripped.partition("=")
        key = key.strip()
        if _ENV_KEY_RE.match(key):
            result[key] = value.strip()
    return result


def build_subprocess_env(project_dir: Path) -> Dict[str, str]:
    """Monta ambiente para subprocesso com variáveis do .env do bot."""
    env = os.environ.copy()
    env.update(load_dotenv_dict(project_dir))
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    return env


def _service_slug(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return f"ark-{slug}.service" if slug else ""


def _asm_display_name(srv: Any) -> str:
    session = (getattr(srv, "session_name", "") or "").strip()
    if session:
        return session
    return (getattr(srv, "name", "") or "Servidor ARK").strip()


def asm_servers_to_ark_maps(
    asm_servers: List[Any],
    *,
    default_host: str = "127.0.0.1",
) -> Tuple[List[ArkMapEntry], str, str, List[str]]:
    """Converte servidores TEK (ASM) em entradas ARK_MAP para o .env do bot."""
    logs: List[str] = []
    eligible = [
        s for s in asm_servers
        if getattr(s, "rcon_port", 0) and int(getattr(s, "rcon_port", 0) or 0) > 0
    ]
    if not eligible:
        return [], default_host, "", ["Nenhum servidor TEK com porta RCON configurada."]

    eligible.sort(key=lambda s: int(getattr(s, "rcon_port", 0) or 0))
    passwords = [
        (getattr(s, "admin_password", "") or "").strip()
        for s in eligible
        if (getattr(s, "admin_password", "") or "").strip()
    ]
    shared_password = passwords[0] if passwords else ""

    hosts = [
        (getattr(s, "server_ip", "") or "").strip()
        for s in eligible
        if (getattr(s, "server_ip", "") or "").strip()
    ]
    ark_host = hosts[0] if hosts else default_host

    maps: List[ArkMapEntry] = []
    for i, srv in enumerate(eligible, start=1):
        name = _asm_display_name(srv)
        rcon_port = int(getattr(srv, "rcon_port", 0) or 0)
        query_port = int(getattr(srv, "query_port", 0) or 0)
        host = (getattr(srv, "server_ip", "") or "").strip() or ark_host
        pwd = (getattr(srv, "admin_password", "") or "").strip()
        max_players = int(getattr(srv, "max_players", 50) or 50)
        entry = ArkMapEntry(
            index=i,
            name=name,
            port=str(rcon_port),
            host=host,
            password=pwd,
            service=_service_slug(getattr(srv, "name", name) or name),
            max_players=str(max_players),
            query_port=str(query_port) if query_port else "",
        )
        maps.append(entry)
        logs.append(
            f"{name}: RCON {rcon_port}, query {query_port or '—'}, "
            f"game {getattr(srv, 'server_port', '—')}"
        )
    logs.insert(0, f"{len(maps)} servidor(es) TEK sincronizado(s).")
    return maps, ark_host, shared_password, logs


def sync_asm_servers_to_env(
    env_text: str,
    asm_servers: List[Any],
    *,
    default_host: str = "127.0.0.1",
) -> Tuple[str, List[ArkMapEntry], List[str]]:
    """Sincroniza portas RCON/query e senha admin dos servidores TEK para o .env do bot."""
    maps, ark_host, shared_pwd, logs = asm_servers_to_ark_maps(
        asm_servers, default_host=default_host,
    )
    if not maps:
        return env_text, [], logs

    updates: Dict[str, str] = {"ARK_HOST": ark_host}
    if shared_pwd:
        updates["ARK_RCON_PASSWORD"] = shared_pwd
    text = update_env_keys(env_text, updates)
    text = write_ark_maps_to_env(text, maps)
    return text, maps, logs


def probe_map_health(
    entry: ArkMapEntry,
    *,
    default_host: str = "127.0.0.1",
    default_password: str = "",
) -> MapHealthResult:
    """Testa RCON e query (A2S) de um mapa."""
    host = (entry.host or default_host or "127.0.0.1").strip() or "127.0.0.1"
    try:
        rcon_port = int(entry.port)
    except ValueError:
        return MapHealthResult(
            name=entry.name, host=host, rcon_port=0,
            rcon_detail="Porta RCON inválida",
        )
    password = (entry.password or default_password or "").strip()
    result = MapHealthResult(name=entry.name, host=host, rcon_port=rcon_port)

    if password and rcon_port:
        try:
            from .rcon_client import RconClient
            from .ui_constants import count_listplayers

            client = RconClient(host, rcon_port, password)
            client.connect()
            ok, resp = client.send_command_safe("ListPlayers")
            client.disconnect()
            result.rcon_ok = ok
            if ok:
                result.players = count_listplayers(resp)
                result.rcon_detail = "RCON conectado"
            else:
                result.rcon_detail = resp or "RCON sem resposta"
        except Exception as exc:
            result.rcon_detail = str(exc)[:120]
    else:
        result.rcon_detail = "Senha RCON ausente"

    qport_raw = (entry.query_port or "").strip()
    if qport_raw:
        try:
            from .server_visibility import probe_a2s_info

            qport = int(qport_raw)
            info = probe_a2s_info(host, qport, timeout=2.5)
            if info:
                result.query_ok = True
                if result.players is None and info.get("players") is not None:
                    result.players = int(info["players"])
                if info.get("max_players") is not None:
                    result.max_players = int(info["max_players"])
        except (ValueError, TypeError):
            pass

    return result


def health_check_maps(
    maps: List[ArkMapEntry],
    env_text: str,
) -> List[MapHealthResult]:
    default_host = read_env_value(env_text, "ARK_HOST") or "127.0.0.1"
    default_password = read_env_value(env_text, "ARK_RCON_PASSWORD")
    return [
        probe_map_health(m, default_host=default_host, default_password=default_password)
        for m in maps
    ]


def read_log_tail(path: Path, max_lines: int = 500) -> str:
    if not path.is_file():
        return ""
    try:
        data = path.read_text(encoding="utf-8", errors="replace")
        lines = data.splitlines()
        return "\n".join(lines[-max_lines:])
    except OSError:
        return ""


class ObobonicBotProcess:
    """Controla o subprocesso do bot oBobonicClean."""

    def __init__(self, project_dir: Path) -> None:
        self.project_dir = project_dir
        self.process: Optional[subprocess.Popen] = None  # type: ignore[type-arg]
        self._reader_thread: Optional[threading.Thread] = None
        self._watch_thread: Optional[threading.Thread] = None
        self._log_queue: queue.Queue[Optional[str]] = queue.Queue()
        self._hidden_mode = False
        self._hidden_log_handle = None
        self._auto_restart = False
        self._stop_watch = threading.Event()
        self._start_lock = threading.Lock()

    @property
    def hidden_log_path(self) -> Path:
        return self.project_dir / ".bot_hidden.log"

    @property
    def is_running(self) -> bool:
        return self.process is not None and self.process.poll() is None

    @property
    def pid(self) -> Optional[int]:
        return self.process.pid if self.process else None

    @property
    def hidden_mode(self) -> bool:
        return self._hidden_mode

    @property
    def auto_restart(self) -> bool:
        return self._auto_restart

    def set_auto_restart(self, enabled: bool) -> None:
        self._auto_restart = enabled

    def resolve_python(self) -> Optional[Path]:
        venv_py = _venv_python(self.project_dir)
        if venv_py.is_file():
            return venv_py
        for name in ("python", "python3", "python.exe", "python3.exe"):
            try:
                result = subprocess.run(
                    [name, "--version"],
                    capture_output=True,
                    text=True,
                    creationflags=CREATE_NO_WINDOW if sys.platform == "win32" else 0,
                )
                if result.returncode == 0:
                    return Path(name)
            except OSError:
                continue
        if sys.platform == "win32":
            try:
                result = subprocess.run(
                    ["py", "-3", "--version"],
                    capture_output=True,
                    text=True,
                    creationflags=CREATE_NO_WINDOW,
                )
                if result.returncode == 0:
                    return Path("py")
            except OSError:
                pass
        return None

    def ensure_venv(
        self,
        on_line: Optional[Callable[[str], None]] = None,
    ) -> Tuple[bool, str]:
        venv_py = _venv_python(self.project_dir)
        if venv_py.is_file():
            return True, "Ambiente virtual (.venv) já existe."
        base = _resolve_system_python()
        if base is None:
            return False, "Python do sistema não encontrado para criar .venv."
        cmd = [*base, "-m", "venv", str(self.project_dir / ".venv")]
        try:
            proc = subprocess.Popen(
                cmd,
                cwd=str(self.project_dir),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                creationflags=CREATE_NO_WINDOW if sys.platform == "win32" else 0,
            )
            assert proc.stdout is not None
            for line in proc.stdout:
                if on_line and line.strip():
                    on_line(line.rstrip())
            proc.wait()
            if proc.returncode == 0 and venv_py.is_file():
                return True, "Ambiente virtual (.venv) criado com sucesso."
            return False, f"Falha ao criar .venv (código {proc.returncode})."
        except Exception as exc:
            return False, str(exc)

    def validate(self, *, check_token: bool = True) -> Tuple[bool, str]:
        if not self.project_dir.is_dir():
            return False, f"Pasta do bot não encontrada:\n{self.project_dir}"
        bot_file = self.project_dir / "bot.py"
        env_file = self.project_dir / ".env"
        if not bot_file.is_file():
            return False, f"bot.py não encontrado em:\n{self.project_dir}"
        if not env_file.is_file():
            return False, f"Arquivo .env não encontrado em:\n{self.project_dir}"
        if self.resolve_python() is None:
            return False, (
                "Python não encontrado.\n"
                "Crie o ambiente virtual (.venv) na pasta do bot ou instale Python 3."
            )
        if check_token:
            try:
                env_text = env_file.read_text(encoding="utf-8")
            except OSError as exc:
                return False, f"Não foi possível ler .env: {exc}"
            ok, msg = validate_discord_token(env_text)
            if not ok:
                return False, msg
        return True, "OK"

    def _read_output(self) -> None:
        assert self.process is not None
        proc = self.process
        try:
            if proc.stdout:
                for line in proc.stdout:
                    self._log_queue.put(line.rstrip("\n\r"))
        except Exception:
            pass
        finally:
            self._log_queue.put(None)

    def _watch_loop(self) -> None:
        while not self._stop_watch.is_set():
            time.sleep(2.0)
            if self._stop_watch.is_set():
                break
            proc = self.process
            if proc is None:
                continue
            code = proc.poll()
            if code is None:
                continue
            self._log_queue.put(f"⚠ Bot encerrou com código {code}.")
            self.process = None
            if self._auto_restart and not self._stop_watch.is_set():
                self._log_queue.put("🔄 Reinício automático em 3s...")
                time.sleep(3.0)
                if self._stop_watch.is_set():
                    break
                with self._start_lock:
                    if self.process is None and self._auto_restart:
                        ok, msg = self.start(hidden=self._hidden_mode, skip_health=True)
                        self._log_queue.put(("✅ " if ok else "⚠ ") + msg)

    def _ensure_watch_thread(self) -> None:
        if self._watch_thread and self._watch_thread.is_alive():
            return
        self._stop_watch.clear()
        self._watch_thread = threading.Thread(target=self._watch_loop, daemon=True)
        self._watch_thread.start()

    def start(
        self,
        *,
        hidden: bool = True,
        skip_health: bool = False,
        health_results: Optional[List[MapHealthResult]] = None,
    ) -> Tuple[bool, str]:
        with self._start_lock:
            if self.is_running:
                return False, "O bot já está em execução."

            ok, msg = self.validate(check_token=True)
            if not ok:
                return False, msg

            if not skip_health and health_results is not None:
                offline = [h for h in health_results if not h.rcon_ok]
                if offline:
                    names = ", ".join(h.name for h in offline[:4])
                    extra = f" (+{len(offline) - 4})" if len(offline) > 4 else ""
                    return False, (
                        f"Health check RCON falhou em: {names}{extra}. "
                        "Corrija portas/senha ou use «Sincronizar TEK»."
                    )

            python = self.resolve_python()
            assert python is not None
            bot_file = self.project_dir / "bot.py"
            if python.name == "py":
                cmd = ["py", "-3", str(bot_file)]
            else:
                cmd = [str(python), str(bot_file)]

            kwargs: dict = {
                "cwd": str(self.project_dir),
                "env": build_subprocess_env(self.project_dir),
                "stdout": subprocess.PIPE,
                "stderr": subprocess.STDOUT,
                "text": True,
                "encoding": "utf-8",
                "errors": "replace",
                "bufsize": 1,
            }

            self._hidden_mode = hidden
            if hidden and sys.platform == "win32":
                self._hidden_log_handle = open(self.hidden_log_path, "a", encoding="utf-8")
                self._hidden_log_handle.write(
                    f"\n{'=' * 60}\nBot iniciado (oculto) — {time.strftime('%Y-%m-%d %H:%M:%S')}\n"
                )
                self._hidden_log_handle.flush()
                kwargs["stdout"] = self._hidden_log_handle
                kwargs["stderr"] = subprocess.STDOUT
                kwargs["creationflags"] = CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP

            try:
                self.process = subprocess.Popen(cmd, **kwargs)
            except Exception as exc:
                if self._hidden_log_handle:
                    self._hidden_log_handle.close()
                    self._hidden_log_handle = None
                return False, f"Erro ao iniciar: {exc}"

            if not hidden:
                self._reader_thread = threading.Thread(target=self._read_output, daemon=True)
                self._reader_thread.start()

            if self._auto_restart:
                self._ensure_watch_thread()

            mode = "oculto" if hidden else "debug"
            return True, f"Bot iniciado ({mode}) — PID {self.process.pid}"

    def stop(self) -> Tuple[bool, str]:
        if not self.is_running:
            self.process = None
            return False, "O bot não está em execução."

        assert self.process is not None
        pid = self.process.pid
        try:
            self.process.terminate()
            try:
                self.process.wait(timeout=8)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=3)
        except Exception as exc:
            return False, f"Erro ao parar (PID {pid}): {exc}"
        finally:
            self.process = None
            self._log_queue.put(None)
            if self._hidden_log_handle:
                try:
                    self._hidden_log_handle.close()
                except Exception:
                    pass
                self._hidden_log_handle = None

        return True, f"Bot parado (PID {pid})"

    def restart(self, *, hidden: bool = True, **kwargs: Any) -> Tuple[bool, str]:
        if self.is_running:
            ok, msg = self.stop()
            if not ok:
                return False, msg
            time.sleep(1.0)
        return self.start(hidden=hidden, **kwargs)

    def drain_logs(self) -> List[str]:
        lines: List[str] = []
        while True:
            try:
                item = self._log_queue.get_nowait()
            except queue.Empty:
                break
            if item is None:
                break
            lines.append(item)
        return lines

    def install_dependencies(
        self,
        on_line: Optional[Callable[[str], None]] = None,
        *,
        create_venv: bool = True,
    ) -> Tuple[bool, str]:
        if create_venv:
            ok_venv, msg_venv = self.ensure_venv(on_line=on_line)
            if not ok_venv:
                return False, msg_venv
            if on_line and "criado" in msg_venv.lower():
                on_line(msg_venv)

        python = self.resolve_python()
        if python is None:
            return False, "Python não encontrado."
        req = self.project_dir / "requirements.txt"
        if not req.is_file():
            return False, "requirements.txt não encontrado."
        if python.name == "py":
            cmd = ["py", "-3", "-m", "pip", "install", "-r", str(req)]
        else:
            cmd = [str(python), "-m", "pip", "install", "-r", str(req)]
        try:
            proc = subprocess.Popen(
                cmd,
                cwd=str(self.project_dir),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                creationflags=CREATE_NO_WINDOW if sys.platform == "win32" else 0,
            )
            assert proc.stdout is not None
            for line in proc.stdout:
                if on_line:
                    on_line(line.rstrip())
            proc.wait()
            if proc.returncode == 0:
                return True, "Dependências instaladas com sucesso."
            return False, f"pip retornou código {proc.returncode}"
        except Exception as exc:
            return False, str(exc)

    def list_cogs(self) -> List[str]:
        try:
            import importlib.util
            spec = importlib.util.spec_from_file_location(
                "obobonic_config", self.project_dir / "config.py"
            )
            if spec and spec.loader:
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
                cogs = getattr(mod, "COGS", [])
                return list(cogs) if isinstance(cogs, list) else []
        except Exception:
            pass
        return []

    def shutdown(self) -> None:
        """Para watcher e subprocesso (ao fechar o app)."""
        self._stop_watch.set()
        self._auto_restart = False
        if self.is_running:
            self.stop()
