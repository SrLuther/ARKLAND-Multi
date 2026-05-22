from __future__ import annotations
import json
from typing import TYPE_CHECKING
from tkinter import filedialog
from tkinter import messagebox
if TYPE_CHECKING:
    from ..app import ARKServerManagerApp


def import_profile(app: "ARKServerManagerApp") -> None:
    path = filedialog.askopenfilename(
        parent=app,
        title="Importar Perfil ARKLAND",
        filetypes=[
            ("Perfil ARKLAND", "*.arkprofile"),
            ("JSON", "*.json"),
            ("Todos os arquivos", "*.*"),
        ],
    )
    if not path:
        return
    try:
        import json as _json
        with open(path, "r", encoding="utf-8") as fh:
            preview = _json.load(fh)
        servers_raw = preview.get("servers", [])
        count = len(servers_raw)
        if count == 0:
            messagebox.showwarning("Perfil vazio", "O arquivo não contém servidores.", parent=app)
            return
        names_str = "\n".join(f"  • {s.get('name', '?')}" for s in servers_raw[:10])
        if count > 10:
            names_str += f"\n  ... e mais {count - 10}"
        ans = messagebox.askyesnocancel(
            "Importar Perfil",
            f"O perfil contém {count} servidor(es):\n{names_str}\n\n"
            "Sim  → adicionar aos servidores existentes\n"
            "Não  → substituir todos os servidores\n"
            "Cancelar → cancelar",
            parent=app,
        )
        if ans is None:
            return
        replace = not ans  # "Não" = replace=True
        imported = app.config_manager.import_profile(path, replace=replace)
        if replace:
            # Remove instâncias antigas do server_manager
            for inst in app.server_manager.get_all_instances():
                if inst.status in ("stopped", "crashed"):
                    app.server_manager.remove_server(inst.config.id)
        for srv in imported:
            app.server_manager.add_server(srv)
        app._rebuild_server_sidebar()
        app._refresh_dashboard()
        messagebox.showinfo(
            "Perfil importado",
            f"{len(imported)} servidor(es) importado(s) com sucesso.",
            parent=app,
        )
    except Exception as exc:
        messagebox.showerror("Erro ao importar", str(exc), parent=app)

