from __future__ import annotations
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from ..app import ARKServerManagerApp


def lookup_admin_preview(app: "ARKServerManagerApp", server_id: str, steam_id: str) -> None:
    """Busca o nome Steam e atualiza o label de preview."""
    w = app._server_widgets.get(server_id, {})
    # Só atualiza se o campo ainda contém o mesmo ID que disparou o lookup
    if w.get("new_admin_id") and w["new_admin_id"].get().strip() != steam_id:
        return

    def _done(name: Optional[str]):
        # Executa na thread principal via after
        def _update():
            lbl = w.get("_admin_name_preview")
            if not lbl:
                return
            # Verifica novamente se o ID não mudou
            if w.get("new_admin_id") and w["new_admin_id"].get().strip() != steam_id:
                return
            if name:
                lbl.configure(text=f"✅  {name}", text_color="#4ade80")
            else:
                lbl.configure(text="⚠️  Perfil privado ou ID inválido", text_color="#f87171")
        try:
            app.after(0, _update)
        except Exception:
            pass

    app._fetch_steam_name(steam_id, _done)

