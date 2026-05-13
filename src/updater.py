"""
Verificador e instalador de atualizações do ARKLAND-Multi.

Formato esperado do JSON remoto (update_url):
{
    "version": "1.1.0",
    "date": "2026-06-01",
    "download_url": "https://example.com/ARKLAND-Multi-Setup-v1.1.0.exe",
    "changelog": ["Novidade 1", "Correção 2"]
}
"""
import subprocess
import tempfile
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional
from urllib.parse import urlparse

try:
    import requests as _requests
    _HAS_REQUESTS = True
except ImportError:
    _HAS_REQUESTS = False


@dataclass
class UpdateInfo:
    version: str
    date: str
    download_url: str
    changelog: list = field(default_factory=list)

    def is_newer_than(self, current: str) -> bool:
        def _parse(v: str) -> tuple:
            try:
                return tuple(int(x) for x in v.lstrip("v").split("."))
            except ValueError:
                return (0,)
        return _parse(self.version) > _parse(current)


class UpdateChecker:
    def __init__(
        self,
        on_log: Optional[Callable[[str, str], None]] = None,
    ) -> None:
        self._on_log = on_log or (lambda msg, level: None)
        self._latest: Optional[UpdateInfo] = None
        self._checking = False

    @property
    def latest(self) -> Optional[UpdateInfo]:
        return self._latest

    @property
    def is_checking(self) -> bool:
        return self._checking

    def check_async(
        self,
        url: str,
        on_result: Optional[Callable[[Optional[UpdateInfo]], None]] = None,
    ) -> None:
        """Verifica atualizações em background. Chama on_result no thread atual."""
        if not url or not url.strip():
            if on_result:
                on_result(None)
            return
        if self._checking:
            return
        threading.Thread(
            target=self._worker,
            args=(url.strip(), on_result),
            daemon=True,
            name="ArkUpdateChecker",
        ).start()

    def _worker(
        self,
        url: str,
        on_result: Optional[Callable[[Optional[UpdateInfo]], None]],
    ) -> None:
        self._checking = True
        result: Optional[UpdateInfo] = None
        try:
            result = self._fetch(url)
            self._latest = result
        except Exception as exc:
            self._on_log(f"[update] Erro ao verificar atualizações: {exc}", "warning")
        finally:
            self._checking = False
            if on_result:
                on_result(result)

    def _fetch(self, url: str) -> UpdateInfo:
        if not _HAS_REQUESTS:
            raise RuntimeError(
                "'requests' não está instalado. Execute: pip install requests"
            )
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            raise ValueError(f"URL inválida: esquema '{parsed.scheme}' não suportado.")
        resp = _requests.get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        return UpdateInfo(
            version=str(data["version"]),
            date=str(data.get("date", "")),
            download_url=str(data["download_url"]),
            changelog=list(data.get("changelog", [])),
        )

    def download_and_install(
        self,
        info: UpdateInfo,
        on_progress: Optional[Callable[[int], None]] = None,
        on_done: Optional[Callable[[bool, str], None]] = None,
    ) -> None:
        """Baixa o instalador e o executa em background."""
        threading.Thread(
            target=self._download_worker,
            args=(info, on_progress, on_done),
            daemon=True,
            name="ArkUpdateDownload",
        ).start()

    def _download_worker(
        self,
        info: UpdateInfo,
        on_progress: Optional[Callable[[int], None]],
        on_done: Optional[Callable[[bool, str], None]],
    ) -> None:
        try:
            if not _HAS_REQUESTS:
                raise RuntimeError("'requests' não está instalado.")
            parsed = urlparse(info.download_url)
            if parsed.scheme not in ("http", "https"):
                raise ValueError("URL de download inválida.")

            resp = _requests.get(info.download_url, stream=True, timeout=120)
            resp.raise_for_status()

            total = int(resp.headers.get("content-length", 0))
            downloaded = 0
            suffix = Path(parsed.path).suffix or ".exe"

            tmp = tempfile.NamedTemporaryFile(
                delete=False,
                suffix=suffix,
                prefix="ARKLAND-Multi-Update-",
            )
            with tmp as fh:
                for chunk in resp.iter_content(chunk_size=65536):
                    if chunk:
                        fh.write(chunk)
                        downloaded += len(chunk)
                        if total and on_progress:
                            on_progress(int(downloaded * 100 / total))

            self._launch_via_updater_script(tmp.name)
            if on_done:
                on_done(True, tmp.name)
        except Exception as exc:
            if on_done:
                on_done(False, str(exc))

    @staticmethod
    def _launch_via_updater_script(installer_path: str) -> None:
        """
        Cria um script PowerShell temporário que aguarda o processo atual
        encerrar e só então executa o instalador. Mais confiável que .bat
        em processos sem console (DETACHED_PROCESS).
        """
        import os

        pid = os.getpid()

        ps1 = tempfile.NamedTemporaryFile(
            delete=False,
            suffix=".ps1",
            prefix="ARKLAND-updater-",
            mode="w",
            encoding="utf-8",
        )
        # Backslashes em strings PowerShell entre aspas duplas não precisam escape.
        # Apenas "$", "`" e `"` precisam.
        safe_installer = installer_path.replace('"', '`"')
        safe_ps1 = ps1.name.replace('"', '`"')
        ps1.write(
            f'$id = {pid}\n'
            f'while (Get-Process -Id $id -ErrorAction SilentlyContinue) {{\n'
            f'    Start-Sleep -Milliseconds 500\n'
            f'}}\n'
            f'Start-Sleep -Seconds 1\n'
            f'Start-Process -FilePath "{safe_installer}"\n'
            f'Remove-Item -LiteralPath "{safe_ps1}" -Force -ErrorAction SilentlyContinue\n'
        )
        ps1.close()

        subprocess.Popen(
            [
                "powershell.exe",
                "-WindowStyle", "Hidden",
                "-NonInteractive",
                "-ExecutionPolicy", "Bypass",
                "-File", ps1.name,
            ],
            creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
            close_fds=True,
        )
