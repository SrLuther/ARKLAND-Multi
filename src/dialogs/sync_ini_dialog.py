"""Dialog: sincronizar arquivos INI entre servidores."""
from __future__ import annotations

import os
import shutil
import tkinter as tk
from tkinter import messagebox
from typing import TYPE_CHECKING

import customtkinter as ctk  # type: ignore[reportMissingImports]

from ..ui_constants import _BLUE, _BLUE_HOVER, _GREEN_DARK, _GREEN_HOVER

if TYPE_CHECKING:
    from ..app import ARKServerManagerApp


def open_sync_ini_dialog(app: "ARKServerManagerApp", source_server_id: str) -> None:
    """Abre diálogo para escolher quais servidores receberão os INIs do servidor atual."""
    src = app.config_manager.get_server(source_server_id)
    if not src:
        return
    if not src.install_dir or not os.path.isdir(src.install_dir):
        messagebox.showwarning(
            "Sem diretório",
            "Configure e salve o Diretório de Instalação antes de sincronizar.",
            parent=app,
        )
        return

    from ..ark_ini import get_ini_path as _get_ini_path
    gus_path  = _get_ini_path(src.install_dir, "GameUserSettings.ini")
    game_path = _get_ini_path(src.install_dir, "Game.ini")
    if not gus_path.exists() and not game_path.exists():
        messagebox.showwarning(
            "Arquivos não encontrados",
            f"Nenhum INI encontrado em:\n{gus_path.parent}\n\n"
            "Salve as configurações primeiro para gerar os arquivos.",
            parent=app,
        )
        return

    other_servers = [s for s in app.config_manager.servers if s.id != source_server_id]
    if not other_servers:
        messagebox.showinfo(
            "Sem outros servidores",
            "Nenhum outro servidor cadastrado para sincronizar.",
            parent=app,
        )
        return

    # ── Diálogo de seleção ────────────────────────────────────────────────
    dlg = ctk.CTkToplevel(app)
    dlg.title("Sincronizar INI entre servidores")
    dlg.geometry("480x420")
    dlg.resizable(False, False)
    dlg.grab_set()

    ctk.CTkLabel(
        dlg,
        text=f"Copiar INIs de  '{src.name}'  para:",
        font=ctk.CTkFont(size=14, weight="bold"),
    ).pack(padx=24, pady=(20, 4), anchor="w")

    ctk.CTkLabel(
        dlg,
        text="Serão copiados: GameUserSettings.ini e Game.ini\n"
             "Os arquivos de destino serão substituídos.",
        text_color="gray55", font=ctk.CTkFont(size=10), justify="left",
    ).pack(padx=24, pady=(0, 12), anchor="w")

    chk_vars: dict = {}
    scroll_f = ctk.CTkScrollableFrame(dlg, fg_color="transparent", height=200)
    scroll_f.pack(fill="both", expand=True, padx=20, pady=4)

    for s in other_servers:
        var = tk.BooleanVar(value=True)
        chk_vars[s.id] = var
        row_f = ctk.CTkFrame(scroll_f, fg_color="transparent")
        row_f.pack(fill="x", pady=2)
        ctk.CTkCheckBox(
            row_f, text=s.name,
            variable=var,
            checkmark_color="white", fg_color=_GREEN_DARK, hover_color=_GREEN_HOVER,
        ).pack(side="left", padx=8)
        if s.install_dir:
            ctk.CTkLabel(
                row_f, text=s.install_dir,
                text_color="gray45", font=ctk.CTkFont(size=10),
            ).pack(side="left", padx=(4, 0))
        else:
            ctk.CTkLabel(
                row_f, text="(sem diretório configurado)",
                text_color="#ff6666", font=ctk.CTkFont(size=10),
            ).pack(side="left", padx=(4, 0))

    files_frame = ctk.CTkFrame(dlg, fg_color="transparent")
    files_frame.pack(padx=20, pady=(8, 4), anchor="w")
    copy_gus_var  = tk.BooleanVar(value=True)
    copy_game_var = tk.BooleanVar(value=True)
    ctk.CTkCheckBox(
        files_frame, text="GameUserSettings.ini",
        variable=copy_gus_var,
        checkmark_color="white", fg_color=_BLUE, hover_color=_BLUE_HOVER,
    ).pack(side="left", padx=(0, 16))
    ctk.CTkCheckBox(
        files_frame, text="Game.ini",
        variable=copy_game_var,
        checkmark_color="white", fg_color=_BLUE, hover_color=_BLUE_HOVER,
    ).pack(side="left")

    btn_row = ctk.CTkFrame(dlg, fg_color="transparent")
    btn_row.pack(pady=(12, 20))

    def _do_sync():
        targets = [s for s in other_servers if chk_vars[s.id].get()]
        if not targets:
            messagebox.showwarning("Nada selecionado", "Selecione ao menos um servidor.", parent=dlg)
            return
        errors = []
        copied = 0
        for s in targets:
            if not s.install_dir or not os.path.isdir(s.install_dir):
                errors.append(f"{s.name}: diretório inválido")
                continue
            dst_dir = _get_ini_path(s.install_dir, "GameUserSettings.ini").parent
            dst_dir.mkdir(parents=True, exist_ok=True)
            if copy_gus_var.get() and gus_path.exists():
                shutil.copy2(str(gus_path), str(dst_dir / "GameUserSettings.ini"))
                copied += 1
            if copy_game_var.get() and game_path.exists():
                shutil.copy2(str(game_path), str(dst_dir / "Game.ini"))
                copied += 1

        dlg.destroy()
        msg = f"{copied} arquivo(s) copiado(s) para {len(targets)} servidor(es)."
        if errors:
            msg += "\n\nErros:\n" + "\n".join(errors)
            messagebox.showwarning("Sincronização concluída com avisos", msg, parent=app)
        else:
            messagebox.showinfo("Sincronização concluída", msg, parent=app)

    ctk.CTkButton(
        btn_row, text="🔄  Sincronizar", width=140, height=38,
        fg_color="#6a3aaa", hover_color="#7a4abb",
        command=_do_sync,
    ).pack(side="left", padx=(0, 10))
    ctk.CTkButton(
        btn_row, text="Cancelar", width=100, height=38,
        fg_color="#3a3a5a", hover_color="#252540",
        command=dlg.destroy,
    ).pack(side="left")
