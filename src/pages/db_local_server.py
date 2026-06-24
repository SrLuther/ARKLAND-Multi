"""Gerenciamento do servidor MariaDB portable local para ARKLAND."""
from __future__ import annotations

import json
import os
import subprocess
import threading
import time
import urllib.request
import zipfile
from pathlib import Path
from typing import Callable, Optional

# ── Diretórios ──────────────────────────────────────────────────────────────
_APPDATA = Path(os.environ.get("APPDATA", Path.home())) / "ARKLAND-ServerManager"
_PORT = 3306
_FIREWALL_RULE = "ARKLAND-MariaDB-3306"


def _mariadb_dir() -> Path:
    from ..arkland_environment import default_mariadb_dir
    return default_mariadb_dir()


def _data_dir() -> Path:
    from ..arkland_environment import default_mariadb_data_dir
    return default_mariadb_data_dir()

OnProgress = Optional[Callable[[str], None]]
OnDone     = Optional[Callable[[bool, str], None]]


# ── Classe principal ─────────────────────────────────────────────────────────

class DbLocalServer:
    """Controla o servidor MariaDB portable embutido no app."""

    def __init__(self) -> None:
        self._proc: Optional[subprocess.Popen] = None  # type: ignore[type-arg]
        self._lock = threading.Lock()

    # ── Propriedades ─────────────────────────────────────────────────────────

    @property
    def mysqld_exe(self) -> Path:
        return _mariadb_dir() / "bin" / "mysqld.exe"

    @property
    def mysql_exe(self) -> Path:
        return _mariadb_dir() / "bin" / "mysql.exe"

    @property
    def mysqladmin_exe(self) -> Path:
        return _mariadb_dir() / "bin" / "mysqladmin.exe"

    def is_installed(self) -> bool:
        return self.mysqld_exe.exists()

    def is_initialized(self) -> bool:
        # Só considera inicializado se o schema mysql existe (tabelas de sistema)
        return (_data_dir() / "mysql").is_dir()

    def is_running(self) -> bool:
        """True se nosso processo gerenciado está vivo OU se a porta já está em uso."""
        with self._lock:
            if self._proc is not None and self._proc.poll() is None:
                return True
        # Detecta mysqld externo já rodando na porta
        return self._port_in_use()

    @staticmethod
    def _port_in_use() -> bool:
        import socket
        try:
            with socket.create_connection(("127.0.0.1", _PORT), timeout=1):
                return True
        except OSError:
            return False

    def data_dir(self) -> Path:
        return _data_dir()

    # ── Download + instalação ─────────────────────────────────────────────────

    def download_and_install(self,
                              on_progress: OnProgress = None,
                              on_done: OnDone = None) -> None:
        threading.Thread(
            target=self._download_worker,
            args=(on_progress, on_done),
            daemon=True,
        ).start()

    def _download_worker(self, on_progress: OnProgress,
                          on_done: OnDone) -> None:
        def _prog(msg: str) -> None:
            if on_progress:
                on_progress(msg)

        try:
            _prog("Obtendo URL de download...")
            url = self._resolve_download_url()
            _prog(f"Baixando MariaDB 10.11 LTS...")

            _APPDATA.mkdir(parents=True, exist_ok=True)
            zip_path = _APPDATA / "mariadb_download.zip"

            def _hook(count: int, block: int, total: int) -> None:
                if total > 0:
                    pct = min(int(count * block * 100 / total), 100)
                    _prog(f"Baixando... {pct}%")

            urllib.request.urlretrieve(url, zip_path, _hook)

            _prog("Extraindo arquivos...")
            self._extract(zip_path)
            zip_path.unlink(missing_ok=True)

            _prog("Inicializando banco de dados...")
            self._initialize()

            if on_done:
                on_done(True, "MariaDB instalado com sucesso!")
        except Exception as exc:
            if on_done:
                on_done(False, str(exc))

    @staticmethod
    def _resolve_download_url() -> str:
        """Resolve URL de download do MariaDB 10.11 LTS winx64.

        Estratégia:
        1. Consulta API raiz para descobrir o patch mais recente do 10.11
        2. Constrói URL direta via archive.mariadb.org (mais estável)
        3. Fallback hardcoded para 10.11.13
        """
        FALLBACK_VER = "10.11.13"

        def _archive_url(ver: str) -> str:
            return (f"https://archive.mariadb.org/mariadb-{ver}/"
                    f"winx64-packages/mariadb-{ver}-winx64.zip")

        # Tenta descobrir versão mais recente via API raiz (lightweight)
        try:
            req = urllib.request.Request(
                "https://downloads.mariadb.org/rest-api/mariadb/",
                headers={"User-Agent": "ARKLAND/1.0"},
            )
            with urllib.request.urlopen(req, timeout=8) as r:
                data = json.loads(r.read())

            for rel in data.get("major_releases", []):
                if rel.get("release_id") == "10.11":
                    # Tenta obter a lista de patches pelo endpoint secundário
                    try:
                        sub = urllib.request.Request(
                            "https://downloads.mariadb.org/rest-api/mariadb/10.11/",
                            headers={"User-Agent": "ARKLAND/1.0"},
                        )
                        with urllib.request.urlopen(sub, timeout=6) as sr:
                            sub_data = json.loads(sr.read())
                        releases = sub_data.get("releases", {})
                        if releases:
                            latest = sorted(releases.keys())[-1]
                            for f in releases[latest].get("files", []):
                                name = f.get("file_name", "")
                                if "winx64.zip" in name and "debug" not in name.lower():
                                    pkg = f.get("package_url", "")
                                    if pkg:
                                        return pkg
                            # Sem package_url — constrói via archive
                            return _archive_url(latest)
                    except Exception:
                        pass
                    break
        except Exception:
            pass

        return _archive_url(FALLBACK_VER)

    @staticmethod
    def _extract(zip_path: Path) -> None:
        _mariadb_dir().mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(zip_path, "r") as zf:
            members = zf.namelist()
            # O zip tem um dir raiz como "mariadb-10.11.x-winx64/"
            prefix = members[0].split("/")[0] + "/"
            for member in members:
                if not member.startswith(prefix):
                    continue
                relative = member[len(prefix):]
                if not relative:
                    continue
                target = _mariadb_dir() / relative
                if member.endswith("/"):
                    target.mkdir(parents=True, exist_ok=True)
                else:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with zf.open(member) as src, open(target, "wb") as dst:
                        dst.write(src.read())

    @property
    def mysql_install_db_exe(self) -> Path:
        return _mariadb_dir() / "bin" / "mysql_install_db.exe"

    def _initialize(self) -> tuple[bool, str]:
        """Cria o diretório de dados usando mysql_install_db (MariaDB 10.4+)."""
        import shutil
        # Remove data dir parcial (sem o schema mysql) para reinicializar limpo
        if _data_dir().exists() and not (_data_dir() / "mysql").is_dir():
            shutil.rmtree(_data_dir(), ignore_errors=True)
        _data_dir().mkdir(parents=True, exist_ok=True)
        try:
            install_db = self.mysql_install_db_exe
            if not install_db.exists():
                return False, f"mysql_install_db.exe não encontrado em {install_db}"
            result = subprocess.run(
                [str(install_db),
                 f"--datadir={_data_dir()}"],
                capture_output=True, text=True, timeout=120,
                cwd=str(_mariadb_dir()),  # basedir detectado pelo cwd
            )
            if self.is_initialized():
                return True, "OK"
            out = (result.stdout + result.stderr).strip()[-800:]
            return False, out
        except Exception as exc:
            return False, str(exc)

    # ── Start / Stop ──────────────────────────────────────────────────────────

    @property
    def log_path(self) -> Path:
        return _APPDATA / "mariadb_error.log"

    def start(self) -> tuple[bool, str]:
        """Inicia o mysqld em background. Retorna (ok, mensagem)."""
        if self.is_running():
            return True, "Já está rodando."
        if not self.is_initialized():
            ok, msg = self._initialize()
            if not ok:
                return False, f"Falha na inicialização: {msg}"

        log_file = open(self.log_path, "a", encoding="utf-8", errors="replace")
        cmd = [
            str(self.mysqld_exe),
            f"--basedir={_mariadb_dir()}",
            f"--datadir={_data_dir()}",
            f"--port={_PORT}",
            "--bind-address=0.0.0.0",
            "--skip-networking=0",
            "--console",
        ]
        with self._lock:
            self._proc = subprocess.Popen(
                cmd,
                creationflags=subprocess.CREATE_NO_WINDOW,
                stdout=log_file,
                stderr=log_file,
            )

        # Verifica se o processo não travou imediatamente
        time.sleep(2)
        if self._proc.poll() is not None:
            tail = self._tail_log(20)
            return False, f"mysqld encerrou imediatamente.\n{tail}"

        # Aguarda até 60 s para o servidor aceitar conexões (1ª inicialização é lenta)
        if self._wait_ready(timeout=60):
            return True, "Servidor iniciado."
        # Se o processo ainda está rodando, considera sucesso mesmo sem ping
        if self._proc.poll() is None:
            return True, "Servidor iniciado (ping timeout, mas processo ativo)."
        tail = self._tail_log(20)
        return False, f"mysqld encerrou antes de aceitar conexões.\n{tail}"

    def _wait_ready(self, timeout: int = 20) -> bool:
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self._ping():
                return True
            time.sleep(0.5)
        return False

    def _ping(self) -> bool:
        """Verifica se mysqld está aceitando conexões TCP."""
        return self._port_in_use()

    def _tail_log(self, lines: int = 20) -> str:
        try:
            text = self.log_path.read_text(encoding="utf-8", errors="replace")
            return "\n".join(text.splitlines()[-lines:])
        except Exception:
            return ""

    def stop(self) -> None:
        """Para o mysqld graciosamente."""
        with self._lock:
            if not self._proc or self._proc.poll() is not None:
                self._proc = None
                return
            try:
                pwd = self.get_root_password()
                cmd = [str(self.mysqladmin_exe), "-u", "root"]
                cmd += [f"--password={pwd}"] if pwd else ["--password="]
                cmd += [f"--port={_PORT}", "--protocol=TCP", "shutdown"]
                subprocess.run(cmd, capture_output=True, timeout=10)
            except Exception:
                try:
                    self._proc.terminate()
                except Exception:
                    pass
            try:
                self._proc.wait(timeout=8)
            except Exception:
                try:
                    self._proc.kill()
                except Exception:
                    pass
            self._proc = None

    # ── Firewall ──────────────────────────────────────────────────────────────

    @staticmethod
    def check_firewall_rule() -> bool:
        """Retorna True se a regra de firewall para 3306 já existe."""
        try:
            cmd = f'netsh advfirewall firewall show rule name="{_FIREWALL_RULE}"'
            result = subprocess.run(
                cmd, shell=True, capture_output=True, text=True, timeout=6,
            )
            # returncode 0 = regra encontrada; qualquer outro = não existe
            return result.returncode == 0
        except Exception:
            return False

    @staticmethod
    def is_admin() -> bool:
        """Retorna True se o processo está rodando como administrador."""
        try:
            import ctypes
            return bool(ctypes.windll.shell32.IsUserAnAdmin())
        except Exception:
            return False

    @staticmethod
    def create_firewall_rule() -> tuple[bool, str]:
        """Cria regra no Windows Firewall para TCP 3306.

        Se já tem admin: usa netsh direto.
        Se não tem admin: lança processo elevado via ShellExecuteW e aguarda.
        Retorna (ok, mensagem).
        """
        if DbLocalServer.check_firewall_rule():
            return True, "Regra já existe."

        # ── Comando netsh ──────────────────────────────────────────────────────
        netsh_cmd = (
            f'netsh advfirewall firewall add rule'
            f' name="{_FIREWALL_RULE}"'
            f' protocol=TCP dir=in localport={_PORT} action=allow'
            f' description="MariaDB portable ARKLAND"'
        )

        if DbLocalServer.is_admin():
            # Já temos privilégios — executa direto
            try:
                result = subprocess.run(
                    netsh_cmd, shell=True,
                    capture_output=True, text=True, timeout=10,
                )
                if DbLocalServer.check_firewall_rule():
                    return True, "Porta 3306 liberada no firewall."
                out = (result.stdout + result.stderr).strip()
                return False, out or f"Código {result.returncode}"
            except Exception as exc:
                return False, str(exc)
        else:
            # Sem admin — eleva apenas este comando via UAC
            import ctypes, tempfile, time as _time
            bat = tempfile.NamedTemporaryFile(
                suffix=".bat", mode="w", delete=False, encoding="utf-8"
            )
            bat.write(f"@echo off\n{netsh_cmd}\n")
            bat.close()
            try:
                ret = ctypes.windll.shell32.ShellExecuteW(
                    None, "runas", "cmd.exe", f'/c "{bat.name}"', None, 0
                )
                if ret <= 32:
                    return False, "UAC cancelado ou acesso negado."
                # Aguarda até 8 s para a regra aparecer
                for _ in range(16):
                    _time.sleep(0.5)
                    if DbLocalServer.check_firewall_rule():
                        return True, "Porta 3306 liberada no firewall."
                return False, "Timeout aguardando criação da regra."
            except Exception as exc:
                return False, str(exc)
            finally:
                try:
                    import os as _os
                    _os.unlink(bat.name)
                except Exception:
                    pass

    @staticmethod
    def remove_firewall_rule() -> None:
        try:
            cmd = f'netsh advfirewall firewall delete rule name="{_FIREWALL_RULE}"'
            subprocess.run(cmd, shell=True, capture_output=True, timeout=6)
        except Exception:
            pass

    # ── Persistência de preferências ─────────────────────────────────────────

    @staticmethod
    def _prefs_path() -> Path:
        return _APPDATA / "db_server_prefs.json"

    @classmethod
    def _load_prefs(cls) -> dict:
        try:
            return json.loads(cls._prefs_path().read_text())
        except Exception:
            return {}

    @classmethod
    def _save_prefs(cls, data: dict) -> None:
        cls._prefs_path().parent.mkdir(parents=True, exist_ok=True)
        cls._prefs_path().write_text(json.dumps(data))

    @classmethod
    def get_autostart(cls) -> bool:
        return bool(cls._load_prefs().get("autostart", False))

    @classmethod
    def set_autostart(cls, value: bool) -> None:
        prefs = cls._load_prefs()
        prefs["autostart"] = value
        cls._save_prefs(prefs)

    @classmethod
    def get_root_password(cls) -> str:
        """Retorna a senha do root configurada localmente (vazia = sem senha)."""
        return cls._load_prefs().get("root_password", "")

    @classmethod
    def set_root_password(cls, password: str) -> None:
        prefs = cls._load_prefs()
        prefs["root_password"] = password
        cls._save_prefs(prefs)

    def apply_root_password(self, new_password: str) -> tuple[bool, str]:
        """Define/altera a senha do root enquanto o servidor está rodando."""
        old_pwd = self.get_root_password()
        try:
            args = [str(self.mysqladmin_exe), "-u", "root"]
            if old_pwd:
                args += [f"--password={old_pwd}"]
            else:
                args += ["--password="]
            args += [f"--port={_PORT}", "--protocol=TCP",
                     "password", new_password]
            result = subprocess.run(args, capture_output=True, text=True, timeout=8)
            if result.returncode == 0:
                self.set_root_password(new_password)
                return True, "Senha do root definida."
            return False, (result.stderr or result.stdout).strip()
        except Exception as exc:
            return False, str(exc)
        except Exception:
            pass
