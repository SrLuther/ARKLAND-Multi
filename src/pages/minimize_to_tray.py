from __future__ import annotations
import os
import threading
from typing import TYPE_CHECKING
from tkinter import messagebox
if TYPE_CHECKING:
    from ..app import ARKServerManagerApp


def minimize_to_tray(app: "ARKServerManagerApp") -> None:
    if not _PYSTRAY_OK or pystray is None or _PILImage is None:
        messagebox.showwarning(
            "Dependências ausentes",
            "Minimizar para bandeja requer pystray e Pillow instalados.",
            parent=app,
        )
        return

    app.withdraw()
    if app._tray_icon:
        return  # já existe

    try:
        img = _PILImage.open(_resource_path(os.path.join("ig", "ArkLandBR.png"))).resize((64, 64))
    except Exception:
        # Cria ícone genérico verde se a imagem não estiver disponível
        img = _PILImage.new("RGBA", (64, 64), "#4CAF50")

    menu = pystray.Menu(
        pystray.MenuItem("Abrir ARKLAND", app._restore_from_tray, default=True),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Sair", lambda icon, item: app.after(0, app._do_quit)),
    )
    app._tray_icon = pystray.Icon(
        "ARKLAND-ServerManager",
        img,
        "ARKLAND - Server Manager",
        menu,
    )
    threading.Thread(
        target=app._tray_icon.run,
        daemon=True,
        name="TrayIconThread",
    ).start()

