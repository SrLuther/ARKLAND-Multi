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
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
import zipfile
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import urlparse
from urllib.request import Request, urlopen, urlretrieve

if TYPE_CHECKING:
    import customtkinter as ctk
    _CTK = True
else:
    try:
        import customtkinter as ctk  # type: ignore[no-redef]
        _CTK = True
    except ImportError:
        import tkinter as ctk  # type: ignore[no-redef]
        _CTK = False

# ── Paleta (igual ao app principal) ──────────────────────────────────────────
_BG       = "#111118"
_CARD_BG  = "#1e1e30"
_GREEN    = "#4CAF50"

_ARGOS_MODELS = (
    ("translate-en_pb-1_9.argosmodel", "en", "pb", "1.9"),
    ("translate-pb_en-1_9.argosmodel", "pb", "en", "1.9"),
    ("translate-en_es-1_0.argosmodel", "en", "es", "1.0"),
    ("translate-es_en-1_9.argosmodel", "es", "en", "1.9"),
)
_ARGOS_MODEL_BASES = (
    "https://data.argosopentech.com/argospm/v1/",
    "https://argos-net.com/v1/",
)


def _validate_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"URL com esquema não permitido: '{parsed.scheme}'")


class UpdaterApp:
    def __init__(self, url: str, pid: int, app_exe: str, version: str, models_dir: str = "") -> None:
        self._url     = url
        self._pid     = pid
        self._app_exe = app_exe
        self._version = version
        self._models_dir = Path(models_dir) if models_dir else (
            Path(os.environ.get("APPDATA", Path.home()))
            / "ARKLAND-ServerManager" / "arkshop_web" / "translation" / "argos-packages"
        )

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
            time.sleep(0.5)

            # 1b. Mata à força qualquer processo ARKLAND restante
            self._set_status("Encerrando processos restantes...")
            self._kill_lingering()
            time.sleep(0.5)
            self._set_progress(0.10)

            # Deixar os modelos no destino persistente antes de instalar/reabrir o app.
            self._prepare_translation_models()

            # 2. Baixar installer
            filename = self._url.split("/")[-1]
            self._set_status("Baixando atualização...", filename)
            installer = self._download(progress_start=0.62, progress_end=0.82)
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
            self._set_status("Falha na atualização.", str(exc)[:120])
            # Se a preparação falhar antes do instalador, volta a abrir a versão atual.
            try:
                self._relaunch()
            except Exception:
                pass
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
            # HANDLE é pointer-sized — definir restype evita truncamento em 64-bit.
            kernel32.OpenProcess.restype = ctypes.c_void_p
            handle = kernel32.OpenProcess(SYNCHRONIZE, False, pid)
            if handle:
                _TIMEOUT_MS = 20_000  # 20 s — fallback: _kill_lingering cuida do resto
                kernel32.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
                kernel32.WaitForSingleObject(handle, _TIMEOUT_MS)
                kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
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

    def _kill_lingering(self) -> None:
        """Mata à força todos os processos ARKLAND restantes e aguarda confirmação.

        Usa taskkill para encerrar, depois verifica via tasklist se os processos
        realmente morreram — repetindo até 5 vezes antes de prosseguir.
        """
        _TARGET_EXES = (
            "ARKLAND-ServerManager.exe",
            "ARKLAND-Multi.exe",
            "ARKLAND-WebStore.exe",
        )

        # 1ª passada: mata pelo nome — NÃO usamos /T (árvore) pois o próprio
        # updater é filho do app principal e seria encerrado junto.
        for exe_name in _TARGET_EXES:
            try:
                subprocess.run(
                    ["taskkill", "/F", "/IM", exe_name],
                    capture_output=True,
                )
            except Exception:
                pass

        # Verifica e repete até confirmar que todos morreram (até 10 s)
        for attempt in range(10):
            time.sleep(1)
            still_alive = []
            for exe_name in _TARGET_EXES:
                try:
                    result = subprocess.run(
                        ["tasklist", "/FI", f"IMAGENAME eq {exe_name}", "/NH"],
                        capture_output=True, text=True,
                    )
                    if exe_name.lower() in result.stdout.lower():
                        still_alive.append(exe_name)
                except Exception:
                    pass
            if not still_alive:
                break
            # Ainda há processos — mata novamente
            for exe_name in still_alive:
                try:
                    subprocess.run(
                        ["taskkill", "/F", "/IM", exe_name],
                        capture_output=True,
                    )
                except Exception:
                    pass
            self._set_status(
                "Encerrando processos restantes...",
                f"Tentativa {attempt + 1}/10 — aguardando {', '.join(still_alive)}",
            )

    def _download(self, progress_start: float = 0.10, progress_end: float = 0.80) -> str:
        _validate_url(self._url)
        tmp = tempfile.NamedTemporaryFile(
            delete=False, suffix=".exe", prefix="ARKLAND-Update-"
        )
        tmp_path = tmp.name
        tmp.close()

        def _hook(count: int, block: int, total: int) -> None:
            if total > 0:
                pct = progress_start + (count * block / total) * (progress_end - progress_start)
                self._set_progress(min(pct, progress_end))
                mb_done  = count * block / 1_048_576
                mb_total = total / 1_048_576
                self._set_status(
                    "Baixando atualização...",
                    f"{mb_done:.1f} MB / {mb_total:.1f} MB",
                )

        urlretrieve(self._url, tmp_path, reporthook=_hook)
        return tmp_path

    def _installed_model_pairs(self) -> set[tuple[str, str, str]]:
        installed: set[tuple[str, str, str]] = set()
        if not self._models_dir.exists():
            return installed
        for metadata_path in self._models_dir.glob("**/metadata.json"):
            try:
                metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
                installed.add((
                    str(metadata.get("from_code", "")),
                    str(metadata.get("to_code", "")),
                    str(metadata.get("package_version", "")),
                ))
            except (OSError, ValueError, TypeError):
                continue
        return installed

    @staticmethod
    def _validate_argos_archive(path: Path, source: str, target: str, version: str) -> None:
        with zipfile.ZipFile(path) as archive:
            metadata_item = None
            expanded_size = 0
            for item in archive.infolist():
                member = Path(item.filename.replace("\\", "/"))
                if member.is_absolute() or member.drive or ".." in member.parts:
                    raise ValueError("o pacote contém um caminho inválido")
                expanded_size += item.file_size
                if expanded_size > 500 * 1024 * 1024:
                    raise ValueError("o pacote excede 500 MB após extração")
                if item.filename.endswith("metadata.json"):
                    metadata_item = item
            if metadata_item is None:
                raise ValueError("metadata.json não encontrado no pacote")
            metadata = json.loads(archive.read(metadata_item).decode("utf-8"))
            if (metadata.get("from_code"), metadata.get("to_code")) != (source, target):
                raise ValueError("o par de idiomas do pacote não corresponde ao arquivo")
            if str(metadata.get("package_version", "")) != version:
                raise ValueError("a versão do pacote não corresponde ao arquivo")

    def _download_argos_model(
        self, filename: str, source: str, target: str, version: str, destination: Path
    ) -> None:
        errors = []
        for base_url in _ARGOS_MODEL_BASES:
            tmp_path = destination.with_suffix(destination.suffix + ".part")
            try:
                request = Request(base_url + filename, headers={"User-Agent": "ARKLAND-Updater/1.0"})
                with urlopen(request, timeout=90) as response, tmp_path.open("wb") as output:
                    total = int(response.headers.get("Content-Length", "0") or 0)
                    received = 0
                    while True:
                        chunk = response.read(1024 * 1024)
                        if not chunk:
                            break
                        output.write(chunk)
                        received += len(chunk)
                        if total:
                            fraction = min(1.0, received / total)
                            pct = 0.10 + (self._model_index + fraction) / self._model_count * 0.52
                            self._set_progress(pct)
                            self._set_status(
                                "Baixando pacotes de tradução...",
                                f"{filename} — {received / 1048576:.0f} / {total / 1048576:.0f} MB",
                            )
                if not zipfile.is_zipfile(tmp_path):
                    raise ValueError("o download não é um arquivo ZIP Argos válido")
                self._set_status("Validando pacote de tradução...", filename)
                self._validate_argos_archive(tmp_path, source, target, version)
                tmp_path.replace(destination)
                return
            except Exception as exc:
                errors.append(f"{base_url}: {exc}")
                try:
                    tmp_path.unlink(missing_ok=True)
                except OSError:
                    pass
        raise RuntimeError(f"Não foi possível baixar {filename}. " + " | ".join(errors))

    def _prepare_translation_models(self) -> None:
        installed = self._installed_model_pairs()
        missing = [model for model in _ARGOS_MODELS if (model[1], model[2], model[3]) not in installed]
        if not missing:
            self._set_status("Pacotes de tradução já estão instalados.")
            self._set_progress(0.62)
            return

        self._models_dir.mkdir(parents=True, exist_ok=True)
        stage_dir = Path(tempfile.mkdtemp(prefix=".argos-update-", dir=self._models_dir))
        self._model_count = len(missing)
        try:
            for index, (filename, source, target, _version) in enumerate(missing):
                self._model_index = index
                self._set_status(
                    "Preparando modelos de tradução antes de atualizar...",
                    f"Pacote {index + 1} de {len(missing)}: {filename}",
                )
                self._download_argos_model(filename, source, target, _version, stage_dir / filename)

            # Só publica os arquivos no destino quando todos os pacotes foram validados.
            for filename, _source, _target, _version in missing:
                (stage_dir / filename).replace(self._models_dir / filename)
            self._set_progress(0.62)
            self._set_status("Modelos preparados.", "A Web Store os instalará ao iniciar.")
        finally:
            try:
                for child in stage_dir.iterdir():
                    child.unlink(missing_ok=True)
                stage_dir.rmdir()
            except OSError:
                pass

    def _free_updater_exe(self) -> None:
        """Renomeia o próprio .exe para liberar o arquivo para o installer.

        No Windows, um processo em execução pode ser renomeado (o handle interno
        permanece válido), mas não pode ser sobrescrito diretamente. Renomear
        libera o nome 'ARKLAND-Updater.exe' para que o Inno Setup possa gravar
        a nova versão sem erro de "arquivo em uso".
        """
        try:
            self_path = Path(sys.executable)
            if self_path.suffix.lower() != ".exe":
                return  # modo dev (python.exe) — sem ação
            if "updater" not in self_path.name.lower():
                return  # segurança extra: só atua no updater
            old_path = self_path.with_name(self_path.stem + ".old.exe")
            try:
                old_path.unlink(missing_ok=True)
            except Exception:
                pass
            self_path.rename(old_path)
        except Exception:
            pass  # se falhar, o installer tentará mesmo assim

    def _install(self, installer: str) -> None:
        # Libera o próprio exe para ser sobrescrito pelo installer
        self._free_updater_exe()
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
    parser.add_argument("--models-dir", default="", help="Pasta persistente dos pacotes Argos")
    args = parser.parse_args()

    app = UpdaterApp(
        url=args.url,
        pid=args.pid,
        app_exe=args.exe,
        version=args.version,
        models_dir=args.models_dir,
    )
    app.run()


if __name__ == "__main__":
    main()
