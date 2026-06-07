"""Instala um plugin ARK a partir de um arquivo ZIP."""
from __future__ import annotations
import os
import threading
import zipfile
from tkinter import messagebox, filedialog
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from ..app import ARKServerManagerApp


def _do_plugin_extract(app, server_id: str, zip_path: str, plugins_path: str) -> None:
    """Extrai o ZIP do plugin em thread background e notifica o resultado."""
    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            names    = zf.namelist()
            top_dirs = {n.split("/")[0] for n in names if "/" in n}
            if len(top_dirs) == 1:
                _safe_extract_zip(zf, plugins_path)
                plugin_name = list(top_dirs)[0]
            else:
                base = os.path.splitext(os.path.basename(zip_path))[0]
                dest = os.path.join(plugins_path, base)
                os.makedirs(dest, exist_ok=True)
                _safe_extract_zip(zf, dest)
                plugin_name = base
        app.after(0, lambda: (
            messagebox.showinfo(
                "Plugin Instalado",
                f"Plugin '{plugin_name}' instalado com sucesso!\n\n"
                "Reinicie o servidor para carregar o plugin.",
                parent=app,
            ),
            app._refresh_plugins_list(server_id),
        ))
    except Exception as exc:
        err_msg = str(exc)
        app.after(0, lambda m=err_msg: messagebox.showerror("Erro ao extrair", m, parent=app))


def install_plugin_from_zip(app, server_id: str) -> None:
    srv = app.config_manager.get_server(server_id)
    if not srv or not srv.install_dir:
        messagebox.showerror("Erro",
            "Configure o diretório de instalação do servidor antes de instalar plugins.",
            parent=app)
        return
    plugins_path = app._plugins_dir(srv.install_dir)
    if not os.path.isdir(plugins_path):
        if messagebox.askyesno(
            "Criar pasta de Plugins?",
            "A pasta de Plugins não existe ainda.\n"
            "Deseja criá-la? (O ArkApi precisa estar instalado para que os plugins funcionem.)",
            parent=app,
        ):
            os.makedirs(plugins_path, exist_ok=True)
        else:
            return
    zip_path = filedialog.askopenfilename(
        title="Selecionar ZIP do Plugin",
        filetypes=[("Arquivo ZIP", "*.zip"), ("Todos", "*.*")],
        parent=app,
    )
    if not zip_path:
        return
    threading.Thread(target=_do_plugin_extract,
                     args=(app, server_id, zip_path, plugins_path), daemon=True).start()

