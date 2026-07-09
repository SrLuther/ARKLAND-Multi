"""Seção de emergência — backups .ini e restauração em cluster."""
from __future__ import annotations

import time
import tkinter as tk
from pathlib import Path
from typing import TYPE_CHECKING, Dict, Optional

import customtkinter as ctk  # type: ignore[reportMissingImports]
from tkinter import messagebox

from ..buff_ini_backups import resolve_ini_backup_root
from ..buff_manager import EMERGENCY_RESTORE_DELAY_SEC
from ..buff_server_bridge import list_buff_servers
from ..ui_constants import _CARD_BG, _RED_DARK, _RED_HOVER

if TYPE_CHECKING:
    from ..app import ARKServerManagerApp


def build_buffs_emergency_section(
    app: "ARKServerManagerApp",
    parent,
    row: int,
    srv_id: Optional[str],
) -> int:
    ctk.CTkLabel(
        parent, text="EMERGÊNCIA — BACKUP / RESTAURAÇÃO",
        font=ctk.CTkFont(size=12, weight="bold"), text_color="#ff8866",
    ).grid(row=row, column=0, padx=20, pady=(16, 4), sticky="w")
    row += 1

    card = ctk.CTkFrame(parent, fg_color="#2a1a1a", corner_radius=10)
    card.grid(row=row, column=0, padx=20, pady=(0, 8), sticky="ew")
    card.grid_columnconfigure(0, weight=1)
    row += 1

    backup_root = resolve_ini_backup_root()
    ctk.CTkLabel(
        card,
        text=(
            f"Backups .ini em: {backup_root}\\{{pasta_do_servidor}}\\*.zip\n"
            f"Criados automaticamente antes de alterar GameUserSettings.ini / Game.ini."
        ),
        text_color="gray55",
        font=ctk.CTkFont(size=11),
        justify="left",
    ).grid(row=0, column=0, columnspan=2, padx=16, pady=(14, 6), sticky="w")

    bm = app._buff_manager
    backups: list[Path] = []
    if bm and srv_id:
        backups = bm.list_ini_backups_for(srv_id)

    backup_var = tk.StringVar()
    backup_labels: Dict[str, str] = {}
    combo_values = ["(nenhum backup)"]
    if backups:
        for bp in backups[:15]:
            label = bp.name
            backup_labels[label] = str(bp)
            combo_values.append(label)
        backup_var.set(combo_values[1])

    ctk.CTkLabel(card, text="Backup:", text_color="gray60").grid(
        row=1, column=0, padx=(16, 4), pady=8, sticky="w",
    )
    ctk.CTkComboBox(
        card, variable=backup_var, values=combo_values,
        state="readonly", width=360,
    ).grid(row=1, column=1, padx=(0, 16), pady=8, sticky="w")

    status_var = tk.StringVar(value="")
    status_lbl = ctk.CTkLabel(
        card, textvariable=status_var,
        text_color="#ffaa44", font=ctk.CTkFont(size=11),
    )
    status_lbl.grid(row=2, column=0, columnspan=2, padx=16, pady=(0, 6), sticky="w")

    def _update_emergency_countdown() -> None:
        if not bm:
            return
        state = bm.get_emergency_state()
        if not state:
            status_var.set("")
            return
        left = max(0, int(state["deadline"] - time.monotonic()))
        mins, secs = divmod(left, 60)
        status_var.set(
            f"⏳ Restauração de emergência em andamento — {mins:d}:{secs:02d} restantes "
            f"({len(state['server_ids'])} servidor(es))"
        )
        app.after(1000, _update_emergency_countdown)

    def _restore_one() -> None:
        if not bm or not srv_id:
            messagebox.showwarning("Eventos Globais", "Selecione um servidor.", parent=app)
            return
        sel = backup_var.get()
        bp = backup_labels.get(sel, "")
        if not bp:
            messagebox.showwarning("Eventos Globais", "Nenhum backup selecionado.", parent=app)
            return
        if not messagebox.askyesno(
            "Restaurar backup",
            f"Restaurar INI do servidor a partir de:\n{bp}\n\n"
            "O servidor será reiniciado após SaveWorld.",
            parent=app,
        ):
            return
        err = bm.start_emergency_restore([srv_id], {srv_id: bp}, cluster_wide_warning=False)
        if err:
            messagebox.showerror("Eventos Globais", err, parent=app)
        else:
            _update_emergency_countdown()

    def _restore_cluster() -> None:
        if not bm:
            return
        entries = list_buff_servers(app)
        if not entries:
            return
        if not messagebox.askyesno(
            "Emergência — cluster inteiro",
            "Esta ação irá:\n"
            "1) Avisar TODOS os servidores via broadcast\n"
            "2) Aguardar 5 minutos\n"
            "3) SaveWorld → parar → restaurar INI do backup mais recente → iniciar\n\n"
            "Continuar?",
            parent=app,
            icon="warning",
        ):
            return
        ids = [e.id for e in entries]
        err = bm.start_emergency_restore(ids, {}, cluster_wide_warning=True)
        if err:
            messagebox.showerror("Eventos Globais", err, parent=app)
        else:
            _update_emergency_countdown()

    btn_row = ctk.CTkFrame(card, fg_color="transparent")
    btn_row.grid(row=3, column=0, columnspan=2, padx=16, pady=(4, 14), sticky="ew")

    ctk.CTkButton(
        btn_row, text="↩  Restaurar backup selecionado", width=220, height=32,
        fg_color="#3a2a2a", hover_color="#4a3030",
        command=_restore_one,
    ).pack(side="left", padx=(0, 10))

    ctk.CTkButton(
        btn_row, text="🚨  Emergência — restaurar TODOS (5 min)", width=280, height=32,
        fg_color=_RED_DARK, hover_color=_RED_HOVER,
        command=_restore_cluster,
    ).pack(side="left")

    ctk.CTkLabel(
        card,
        text=f"Countdown de emergência: {EMERGENCY_RESTORE_DELAY_SEC // 60} minutos após o aviso global.",
        text_color="gray45", font=ctk.CTkFont(size=10),
    ).grid(row=4, column=0, columnspan=2, padx=16, pady=(0, 12), sticky="w")

    _update_emergency_countdown()
    return row
