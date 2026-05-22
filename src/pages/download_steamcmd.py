from __future__ import annotations
import os
import threading
from typing import TYPE_CHECKING
import io
import subprocess
import zipfile
if TYPE_CHECKING:
    from ..app import ARKServerManagerApp


def download_steamcmd(app: "ARKServerManagerApp") -> None:
    """Baixa, extrai e inicializa o SteamCMD automaticamente."""
    dest_dir = os.path.join(
        os.environ.get("APPDATA", os.path.expanduser("~")),
        "ARKLAND-ServerManager", "steamcmd",
    )
    steamcmd_exe = os.path.join(dest_dir, "steamcmd.exe")

    # Se já existe, apenas confirma o caminho
    if os.path.isfile(steamcmd_exe):
        app._steamcmd_var.set(steamcmd_exe)
        app._steamcmd_status_lbl.configure(
            text="✅  SteamCMD já instalado. Caminho configurado automaticamente.",
            text_color="#4CAF50",
        )
        return

    app._steamcmd_dl_btn.configure(state="disabled", text="⏳  Baixando...")
    app._steamcmd_status_lbl.configure(
        text="Baixando SteamCMD da Valve... aguarde.", text_color="gray60"
    )

    def _worker() -> None:
        try:
            os.makedirs(dest_dir, exist_ok=True)

            # Download
            app.after(0, lambda: app._steamcmd_status_lbl.configure(
                text="📥  Baixando steamcmd.zip...", text_color="gray60"))
            with urllib.request.urlopen(app._STEAMCMD_URL, timeout=60) as resp:
                data = resp.read()

            # Extração
            app.after(0, lambda: app._steamcmd_status_lbl.configure(
                text="📦  Extraindo...", text_color="gray60"))
            with zipfile.ZipFile(io.BytesIO(data)) as zf:
                zf.extractall(dest_dir)

            if not os.path.isfile(steamcmd_exe):
                raise FileNotFoundError("steamcmd.exe não encontrado após extração.")

            # Primeira execução para atualizar os arquivos do SteamCMD
            app.after(0, lambda: app._steamcmd_status_lbl.configure(
                text="⚙️  Inicializando SteamCMD (primeira execução)...", text_color="gray60"))
            import subprocess
            subprocess.run(
                [steamcmd_exe, "+quit"],
                cwd=dest_dir,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=120,
            )

            # Sucesso
            def _on_success() -> None:
                app._steamcmd_var.set(steamcmd_exe)
                app._steamcmd_dl_btn.configure(state="normal", text="⬇  Baixar SteamCMD")
                app._steamcmd_status_lbl.configure(
                    text="✅  SteamCMD instalado com sucesso! Caminho configurado automaticamente.",
                    text_color="#4CAF50",
                )
                # Salva a configuração imediatamente
                app.config_manager.config.steamcmd_path = steamcmd_exe
                app.mod_manager.steamcmd_path = steamcmd_exe
                app.config_manager.save()

            app.after(0, _on_success)

        except Exception as exc:
            def _on_error(e: Exception = exc) -> None:
                app._steamcmd_dl_btn.configure(state="normal", text="⬇  Baixar SteamCMD")
                app._steamcmd_status_lbl.configure(
                    text=f"❌  Erro ao baixar SteamCMD: {e}",
                    text_color="#f44336",
                )
            app.after(0, _on_error)

    threading.Thread(target=_worker, daemon=True, name="SteamCMDDownload").start()

