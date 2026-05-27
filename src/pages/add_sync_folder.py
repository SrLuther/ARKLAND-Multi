from __future__ import annotations
import tkinter as tk
from tkinter import messagebox
from typing import TYPE_CHECKING
import customtkinter as ctk  # type: ignore[reportMissingImports]
from ..ui_constants import _MAX_SYNC_FOLDERS, _RED_DARK, _BLUE, _BLUE_HOVER, _GREEN_DARK, _GREEN_HOVER
from ..sync_engine import _REMOTE_PREFIX, _REMOTE_PREFIX_NEW
if TYPE_CHECKING:
    from ..app import ARKServerManagerApp


def _make_remote_path(instance: dict, remote_path: str) -> str:
    """Cria a string  @remote:HOST:PORT|remote_path  (sem token embutido)."""
    host = instance.get("host", "")
    port = instance.get("port", 32440)
    return f"{_REMOTE_PREFIX_NEW}{host}:{port}|{remote_path.strip()}"


def _parse_remote_path(path_str: str) -> tuple:
    """
    Retorna (addr_or_code, remote_path) se for caminho remoto, ou (None, path_str) se for local.
    Suporta novo formato (@remote:HOST:PORT|path) e legado (@remote|BASE64|path).
    """
    for prefix in (_REMOTE_PREFIX_NEW, _REMOTE_PREFIX):
        if path_str.startswith(prefix):
            rest  = path_str[len(prefix):]
            parts = rest.split("|", 1)
            if len(parts) == 2:
                return parts[0], parts[1]
    return None, path_str


def add_sync_folder(app: "ARKServerManagerApp", folders_frame, folder_vars: list, add_btn, path: str = "") -> None:
    """Adiciona uma linha de pasta em um ciclo (local ou remota)."""
    if len(folder_vars) >= _MAX_SYNC_FOLDERS:
        return
    var = tk.StringVar(value=path)
    folder_vars.append(var)
    idx = len(folder_vars) - 1

    row = ctk.CTkFrame(folders_frame, fg_color="transparent")
    row.pack(fill="x", pady=2)
    row.grid_columnconfigure(1, weight=1)

    # Detecta se é remota para exibir badge
    code, _rpath = _parse_remote_path(path)
    is_remote_init = code is not None
    badge_var = tk.StringVar(value="🌐" if is_remote_init else "💾")

    ctk.CTkLabel(row, text=f"Pasta {idx + 1}:",
                 text_color="gray50", width=60, anchor="e",
                 font=ctk.CTkFont(size=11)).grid(row=0, column=0, padx=(0, 4))

    entry = ctk.CTkEntry(row, textvariable=var, height=28,
                         placeholder_text="Caminho da pasta...",
                         state="readonly" if is_remote_init else "normal")
    entry.grid(row=0, column=1, padx=(0, 4), sticky="ew")

    # ── Botão Browse local ────────────────────────────────────────────────
    def _browse_local() -> None:
        app._browse_sync_folder(var)
        badge_var.set("💾")
        entry.configure(state="normal")

    browse_btn = ctk.CTkButton(
        row, text="📁", width=30, height=28,
        fg_color="#2a2a40", hover_color="#363656",
        command=_browse_local,
    )
    browse_btn.grid(row=0, column=2, padx=(0, 2))

    # ── Botão Pasta Remota ────────────────────────────────────────────────
    def _open_remote_dialog() -> None:
        instances = getattr(app.config_manager.config, "remote_instances", []) or []
        if not instances:
            messagebox.showinfo(
                "Nenhuma conexão remota",
                "Adicione uma conexão remota na aba Acesso Remoto primeiro.",
                parent=app,
            )
            return

        dlg = ctk.CTkToplevel(app)
        dlg.title("Pasta Remota")
        dlg.geometry("480x220")
        dlg.grab_set()
        dlg.resizable(False, False)

        ctk.CTkLabel(dlg, text="Instância remota:",
                     font=ctk.CTkFont(size=12)).pack(anchor="w", padx=20, pady=(16, 2))
        names = [i.get("name", i.get("host", "?")) for i in instances]
        inst_var = tk.StringVar(value=names[0])
        ctk.CTkComboBox(dlg, values=names, variable=inst_var,
                        width=440).pack(padx=20)

        ctk.CTkLabel(dlg, text="Caminho na máquina remota:",
                     font=ctk.CTkFont(size=12)).pack(anchor="w", padx=20, pady=(12, 2))
        rpath_var = tk.StringVar(
            value=_parse_remote_path(var.get())[1] if (var.get().startswith(_REMOTE_PREFIX_NEW) or var.get().startswith(_REMOTE_PREFIX)) else ""
        )
        ctk.CTkEntry(dlg, textvariable=rpath_var, height=30, width=440,
                     placeholder_text=r"Ex: C:\ARK\ShooterGame\Saved\clusters").pack(padx=20)

        def _confirm() -> None:
            rpath = rpath_var.get().strip()
            if not rpath:
                return
            sel_name = inst_var.get()
            inst = next((i for i in instances
                         if i.get("name", i.get("host", "?")) == sel_name), None)
            if inst is None:
                return
            var.set(_make_remote_path(inst, rpath))
            badge_var.set("🌐")
            entry.configure(state="readonly")
            dlg.destroy()

        ctk.CTkButton(dlg, text="✔  Confirmar", height=34,
                      fg_color=_GREEN_DARK, hover_color=_GREEN_HOVER,
                      command=_confirm).pack(pady=14)

    ctk.CTkButton(
        row, textvariable=badge_var, width=30, height=28,
        fg_color="#2a2a40", hover_color=_BLUE_HOVER,
        command=_open_remote_dialog,
    ).grid(row=0, column=3, padx=(0, 4))

    # ── Botão Remover ─────────────────────────────────────────────────────
    ctk.CTkButton(
        row, text="✕", width=28, height=28,
        fg_color="transparent", hover_color=_RED_DARK, text_color="gray50",
        command=lambda v=var, r=row, ff=folders_frame, fv=folder_vars, ab=add_btn:
            app._remove_sync_folder(ff, fv, v, r, ab),
    ).grid(row=0, column=4)

    add_btn.configure(
        state="disabled" if len(folder_vars) >= _MAX_SYNC_FOLDERS else "normal")

