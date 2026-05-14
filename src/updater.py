"""
Verificador e instalador de atualizações do ARKLAND - Server Manager.

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
from typing import Any, Callable, Optional
from urllib.parse import urlparse

_requests: Any = None
try:
    import requests as _requests  # type: ignore[import-untyped]
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
        """
        Lança um agente PowerShell separado que:
          1. Aguarda este processo fechar
          2. Baixa o instalador
          3. Instala silenciosamente
          4. Reinicia o app
        O app pode fechar imediatamente após chamar este método.
        """
        try:
            parsed = urlparse(info.download_url)
            if parsed.scheme not in ("http", "https"):
                raise ValueError("URL de download inválida.")
            self._launch_updater_agent(info.download_url, info.version)
            if on_done:
                on_done(True, "")
        except Exception as exc:
            if on_done:
                on_done(False, str(exc))

    @staticmethod
    def _launch_updater_agent(download_url: str, version: str = "") -> None:
        """
        Quando empacotado (frozen), lança ARKLAND-Updater.exe com os args necessários.
        Em modo dev (ou se o exe não for encontrado), cria e lança um script PowerShell.
        """
        import os
        import sys
        from pathlib import Path

        pid = os.getpid()
        app_exe = sys.executable

        # ── Tenta usar ARKLAND-Updater.exe (só disponível no build frozen) ────
        if getattr(sys, "frozen", False):
            updater_exe = Path(sys.executable).parent / "ARKLAND-Updater.exe"
            if updater_exe.exists():
                subprocess.Popen(
                    [
                        str(updater_exe),
                        "--url",     download_url,
                        "--pid",     str(pid),
                        "--exe",     app_exe,
                        "--version", version,
                    ],
                    creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
                    close_fds=True,
                )
                return

        # ── Fallback: script PowerShell temporário ────────────────────────────
        ps1 = tempfile.NamedTemporaryFile(
            delete=False,
            suffix=".ps1",
            prefix="ARKLAND-updater-",
            mode="w",
            encoding="utf-8",
        )
        safe_url     = download_url.replace("'", "''")   # escape aspas simples no PS1
        safe_exe     = app_exe.replace("'", "''")
        safe_ps1     = ps1.name.replace("'", "''")

        ps1.write(
            "# ARKLAND Updater Agent — gerado automaticamente\n"
            "$ErrorActionPreference = 'Stop'\n"
            "$host.UI.RawUI.WindowTitle = 'ARKLAND - Atualizando...'\n"
            "\n"
            "function Write-Step($msg) {\n"
            "    Write-Host \"`n>> $msg\" -ForegroundColor Cyan\n"
            "}\n"
            "\n"
            f"$appPid  = {pid}\n"
            f"$appExe  = '{safe_exe}'\n"
            f"$dlUrl   = '{safe_url}'\n"
            f"$ps1Path = '{safe_ps1}'\n"
            "$installer = Join-Path $env:TEMP 'ARKLAND-Update-Setup.exe'\n"
            "\n"
            "# 1. Aguarda o app fechar\n"
            "Write-Step 'Aguardando o ARKLAND fechar...'\n"
            "while (Get-Process -Id $appPid -ErrorAction SilentlyContinue) {\n"
            "    Start-Sleep -Milliseconds 400\n"
            "}\n"
            "Start-Sleep -Seconds 1\n"
            "\n"
            "# 2. Baixa o instalador\n"
            "Write-Step 'Baixando atualizacao...'\n"
            "try {\n"
            "    $wc = New-Object System.Net.WebClient\n"
            "    $wc.DownloadFile($dlUrl, $installer)\n"
            "} catch {\n"
            "    Write-Host \"ERRO no download: $_\" -ForegroundColor Red\n"
            "    Read-Host 'Pressione Enter para fechar'\n"
            "    exit 1\n"
            "}\n"
            "\n"
            "# 3. Instala silenciosamente\n"
            "Write-Step 'Instalando...'\n"
            "try {\n"
            "    Start-Process -FilePath $installer -ArgumentList '/VERYSILENT /SUPPRESSMSGBOXES /NORESTART /SP-' -Wait\n"
            "} catch {\n"
            "    Write-Host \"ERRO na instalacao: $_\" -ForegroundColor Red\n"
            "    Read-Host 'Pressione Enter para fechar'\n"
            "    exit 1\n"
            "}\n"
            "\n"
            "# 4. Reinicia o app\n"
            "Write-Step 'Iniciando ARKLAND...'\n"
            "if (Test-Path -LiteralPath $appExe) {\n"
            "    Start-Process -FilePath $appExe\n"
            "}\n"
            "\n"
            "# Limpeza\n"
            "Remove-Item -LiteralPath $installer -Force -ErrorAction SilentlyContinue\n"
            "Remove-Item -LiteralPath $ps1Path   -Force -ErrorAction SilentlyContinue\n"
        )
        ps1.close()

        subprocess.Popen(
            [
                "powershell.exe",
                "-WindowStyle", "Normal",
                "-NonInteractive",
                "-ExecutionPolicy", "Bypass",
                "-File", ps1.name,
            ],
            creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
            close_fds=True,
        )
