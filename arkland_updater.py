"""
ARKLAND Updater — agente de atualização independente do ARKLAND - Server Manager.

Lançado automaticamente pelo app principal quando uma nova versão é detectada.
Após o app principal fechar, este processo:
  1. Baixa o novo installer com barra de progresso
  2. Executa o installer silenciosamente
  3. Reinicia o ARKLAND - Server Manager
  4. Fecha sozinho

Uso:
    arkland_updater.exe --url <url> --pid <pid> --exe <caminho> [--version <v>]
"""
from __future__ import annotations

import argparse
import ctypes
import os
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import urlretrieve

try:
    import customtkinter as ctk
    _CTK = True
except ImportError:
    import tkinter as ctk  # type: ignore[no-redef]
    _CTK = False

# ── Paleta (igual ao app principal) ──────────────────────────────────────────
_BG       = "#111118"
_CARD_BG  = "#1e1e30"
_GREEN    = "#4CAF50"


def _validate_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"URL com esquema não permitido: '{parsed.scheme}'")


class UpdaterApp:
    def __init__(self, url: str, pid: int, app_exe: str, version: str) -> None:
        self._url     = url
        self._pid     = pid
        self._app_exe = app_exe
        self._version = version

        if _CTK:
            ctk.set_appearance_mode("dark")
            ctk.set_default_color_theme("blue")
            self._root = ctk.CTk()
        else:
            import tkinter as tk
            self._root = tk.Tk()

        self._root.title("ARKLAND Updater")
        self._root.geometry("480x230")
        self._root.resizable(False, False)
        self._root.protocol("WM_DELETE_WINDOW", self._noop)

        # Tenta definir ícone (ignora se não encontrado)
        _ico = Path(sys.executable).parent / "ig" / "ArkLandBR.ico"
        if not _ico.exists():
            _ico = Path(__file__).parent / "ig" / "ArkLandBR.ico"
        try:
            self._root.iconbitmap(str(_ico))
        except Exception:
            pass

        # Centraliza na tela
        self._root.update_idletasks()
        sw = self._root.winfo_screenwidth()
        sh = self._root.winfo_screenheight()
        self._root.geometry(f"480x230+{(sw - 480) // 2}+{(sh - 230) // 2}")

        self._build_ui()
        self._root.after(300, self._start_worker)

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        if not _CTK:
            return

        outer = ctk.CTkFrame(self._root, fg_color=_BG)
        outer.pack(fill="both", expand=True)

        card = ctk.CTkFrame(outer, fg_color=_CARD_BG, corner_radius=12)
        card.pack(fill="both", expand=True, padx=24, pady=24)

        title = "Atualizando ARKLAND - Server Manager"
        if self._version:
            title += f"  →  v{self._version}"

        ctk.CTkLabel(
            card,
            text=title,
            font=ctk.CTkFont(size=14, weight="bold"),
        ).pack(pady=(18, 4))

        self._status_lbl = ctk.CTkLabel(
            card,
            text="Aguardando o app fechar...",
            text_color="gray70",
            font=ctk.CTkFont(size=12),
        )
        self._status_lbl.pack(pady=(0, 12))

        self._progress = ctk.CTkProgressBar(card, width=400, height=14, corner_radius=6)
        self._progress.pack(pady=(0, 8))
        self._progress.set(0)

        self._detail_lbl = ctk.CTkLabel(
            card,
            text="",
            text_color="gray50",
            font=ctk.CTkFont(size=11),
        )
        self._detail_lbl.pack()

    def _set_status(self, text: str, detail: str = "") -> None:
        def _apply() -> None:
            if _CTK:
                self._status_lbl.configure(text=text)
                self._detail_lbl.configure(text=detail)
        self._root.after(0, _apply)

    def _set_progress(self, pct: float) -> None:
        def _apply() -> None:
            if _CTK:
                self._progress.set(max(0.0, min(1.0, pct)))
        self._root.after(0, _apply)

    def _noop(self) -> None:
        pass

    # ── Worker ────────────────────────────────────────────────────────────────

    def _start_worker(self) -> None:
        threading.Thread(target=self._run, daemon=True, name="UpdaterWorker").start()

    def _run(self) -> None:
        try:
            # 1. Aguarda o app principal fechar
            self._set_status("Aguardando o ARKLAND fechar...")
            self._set_progress(0.05)
            self._wait_pid(self._pid)
            time.sleep(0.8)
            self._set_progress(0.10)

            # 2. Baixar installer
            filename = self._url.split("/")[-1]
            self._set_status("Baixando atualização...", filename)
            installer = self._download()
            self._set_progress(0.82)

            # 3. Instalar
            self._set_status("Instalando...", "Aguarde, isso pode levar alguns segundos.")
            self._set_progress(0.86)
            self._install(installer)
            self._set_progress(0.96)

            # 4. Reiniciar app
            self._set_status("Instalação concluída!", "Iniciando ARKLAND...")
            self._set_progress(1.0)
            time.sleep(1.2)
            self._relaunch()

            # 5. Limpar e fechar
            try:
                os.unlink(installer)
            except Exception:
                pass
            self._root.after(0, self._root.destroy)

        except Exception as exc:
            self._set_status(f"Erro: {exc}", "Feche esta janela manualmente.")
            # Permite fechar em caso de erro
            self._root.after(
                0,
                lambda: self._root.protocol("WM_DELETE_WINDOW", self._root.destroy),
            )

    def _wait_pid(self, pid: int) -> None:
        """Aguarda o processo terminar via WinAPI (sem polling ativo)."""
        SYNCHRONIZE = 0x00100000
        try:
            kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
            handle = kernel32.OpenProcess(SYNCHRONIZE, False, pid)
            if handle:
                kernel32.WaitForSingleObject(handle, 0xFFFFFFFF)  # INFINITE
                kernel32.CloseHandle(handle)
                return
        except Exception:
            pass
        # Fallback: polling por os.kill
        while True:
            try:
                os.kill(pid, 0)
            except OSError:
                break
            time.sleep(0.5)

    def _download(self) -> str:
        _validate_url(self._url)
        tmp = tempfile.NamedTemporaryFile(
            delete=False, suffix=".exe", prefix="ARKLAND-Update-"
        )
        tmp_path = tmp.name
        tmp.close()

        def _hook(count: int, block: int, total: int) -> None:
            if total > 0:
                pct = 0.10 + (count * block / total) * 0.70
                self._set_progress(min(pct, 0.80))
                mb_done  = count * block / 1_048_576
                mb_total = total / 1_048_576
                self._set_status(
                    "Baixando atualização...",
                    f"{mb_done:.1f} MB / {mb_total:.1f} MB",
                )

        urlretrieve(self._url, tmp_path, reporthook=_hook)
        return tmp_path

    def _install(self, installer: str) -> None:
        proc = subprocess.run(
            [installer, "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/SP-"],
            timeout=300,
        )
        # Inno Setup: 0 = sucesso; 5 = já estava na versão mais recente (sem ação)
        if proc.returncode not in (0, 5):
            raise RuntimeError(f"Instalador retornou código {proc.returncode}")

    def _relaunch(self) -> None:
        exe = Path(self._app_exe)
        if exe.exists():
            subprocess.Popen(
                [str(exe)],
                creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
                close_fds=True,
            )

    def run(self) -> None:
        self._root.mainloop()


# ── Entry-point ───────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="ARKLAND Updater — baixa e instala atualizações do ARKLAND - Server Manager"
    )
    parser.add_argument("--url",     required=True,  help="URL do installer (.exe)")
    parser.add_argument("--pid",     required=True,  type=int, help="PID do app principal")
    parser.add_argument("--exe",     required=True,  help="Caminho do executável principal")
    parser.add_argument("--version", default="",     help="Número da versão a instalar")
    args = parser.parse_args()

    app = UpdaterApp(
        url=args.url,
        pid=args.pid,
        app_exe=args.exe,
        version=args.version,
    )
    app.run()


if __name__ == "__main__":
    main()
