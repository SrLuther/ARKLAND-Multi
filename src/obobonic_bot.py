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
from typing import Callable, Iterator, List, Optional

CREATE_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0

DEFAULT_PROJECT_PATH = r"C:\Users\Ciano\Documents\oBobonicClean"

_ARK_MAP_PREFIX = re.compile(r"^ARK_MAP(\d+)_(NAME|PORT|HOST|PASSWORD|SERVICE|MAX_PLAYERS|QUERY_PORT|BATTLEMETRICS_ID)$")


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


def _venv_python(project_dir: Path) -> Path:
    if sys.platform == "win32":
        return project_dir / ".venv" / "Scripts" / "python.exe"
    return project_dir / ".venv" / "bin" / "python"


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
        self._log_queue: queue.Queue[Optional[str]] = queue.Queue()
        self._hidden_mode = False
        self._hidden_log_handle = None

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

    def validate(self) -> tuple[bool, str]:
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

    def start(self, *, hidden: bool = True) -> tuple[bool, str]:
        if self.is_running:
            return False, "O bot já está em execução."

        ok, msg = self.validate()
        if not ok:
            return False, msg

        python = self.resolve_python()
        assert python is not None
        bot_file = self.project_dir / "bot.py"
        cmd = [str(python), str(bot_file)] if python.name != "py" else ["py", "-3", str(bot_file)]

        kwargs: dict = {
            "cwd": str(self.project_dir),
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
            kwargs["creationflags"] = CREATE_NO_WINDOW
            kwargs["start_new_session"] = True

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

        mode = "oculto" if hidden else "debug"
        return True, f"Bot iniciado ({mode}) — PID {self.process.pid}"

    def stop(self) -> tuple[bool, str]:
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

    def restart(self, *, hidden: bool = True) -> tuple[bool, str]:
        if self.is_running:
            ok, msg = self.stop()
            if not ok:
                return False, msg
            time.sleep(1.0)
        return self.start(hidden=hidden)

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

    def install_dependencies(self, on_line: Optional[Callable[[str], None]] = None) -> tuple[bool, str]:
        python = self.resolve_python()
        if python is None:
            return False, "Python não encontrado."
        req = self.project_dir / "requirements.txt"
        if not req.is_file():
            return False, "requirements.txt não encontrado."
        cmd = [str(python), "-m", "pip", "install", "-r", str(req)]
        if python.name == "py":
            cmd = ["py", "-3", "-m", "pip", "install", "-r", str(req)]
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
