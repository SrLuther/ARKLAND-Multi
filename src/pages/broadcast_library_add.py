from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from tkinter import messagebox

if TYPE_CHECKING:
    from ..app_tek import ARKServerManagerApp

from .broadcast_profile_io import get_library, normalize_entry, set_library


def broadcast_library_add(app: "ARKServerManagerApp", label: str, message: str) -> bool:
    label = (label or "").strip()
    message = (message or "").strip()
    if not label or not message:
        messagebox.showwarning(
            "Campos obrigatórios",
            "Preencha o rótulo e o texto da mensagem.",
            parent=app,
        )
        return False

    now = datetime.now(timezone.utc).isoformat()
    entry = normalize_entry({
        "id": str(uuid.uuid4()),
        "label": label,
        "message": message,
        "created_at": now,
        "updated_at": now,
    })
    lib = get_library(app)
    lib.append(entry)
    set_library(app, lib)
    return True
