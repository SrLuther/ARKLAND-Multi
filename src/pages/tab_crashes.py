from __future__ import annotations

import tkinter as tk
from typing import TYPE_CHECKING

import customtkinter as ctk  # type: ignore[reportMissingImports]

from ..ui_constants import _RED_DARK, _RED_HOVER, _CARD_BG
import shutil
import subprocess

from tkinter import messagebox
if TYPE_CHECKING:
    from ..app import ARKServerManagerApp
    from ..server_config import ServerConfig


def build_tab_crashes(app: "ARKServerManagerApp", parent, srv: "ServerConfig") -> None:  # noqa: C901
    """Aba de gerenciamento de crashes — lista e interpreta histórico de crashes."""
    import shutil
    import subprocess
    from ..server_manager import _list_crash_records

    parent.grid_columnconfigure(0, weight=1)
    parent.grid_rowconfigure(1, weight=1)

    # ── Barra de controles ────────────────────────────────────────────────
    bar = ctk.CTkFrame(parent, fg_color=_CARD_BG, corner_radius=8)
    bar.grid(row=0, column=0, sticky="ew", padx=8, pady=(8, 4))
    bar.grid_columnconfigure(1, weight=1)

    ctk.CTkLabel(bar, text="🔴  Histórico de Crashes",
                 font=ctk.CTkFont(size=13, weight="bold"),
                 text_color="#d08080").grid(row=0, column=0, padx=12, pady=8, sticky="w")

    summary_lbl = ctk.CTkLabel(bar, text="", text_color="gray60",
                               font=ctk.CTkFont(size=11))
    summary_lbl.grid(row=0, column=1, padx=8, pady=8, sticky="w")

    btn_row = ctk.CTkFrame(bar, fg_color="transparent")
    btn_row.grid(row=0, column=2, padx=8, pady=4, sticky="e")

    # ── Área rolável de cards ─────────────────────────────────────────────
    scroll = ctk.CTkScrollableFrame(parent, fg_color="transparent")
    scroll.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0, 8))
    scroll.grid_columnconfigure(0, weight=1)

    def _refresh() -> None:
        for w in btn_row.winfo_children():
            w.destroy()
        for w in scroll.winfo_children():
            w.destroy()

        if not srv.install_dir:
            ctk.CTkLabel(scroll,
                         text="⚠  Configure o diretório de instalação primeiro.",
                         text_color="orange").grid(row=0, column=0, pady=20)
            return

        records = _list_crash_records(srv.install_dir)
        total_kb = sum(r["dump_size_kb"] for r in records)
        if records:
            total_mb = total_kb / 1024
            summary_lbl.configure(
                text=f"{len(records)} crash(es) registrado(s)   •   {total_mb:.1f} MB em dumps")
        else:
            summary_lbl.configure(text="Nenhum crash registrado")

        ctk.CTkButton(btn_row, text="🔄 Atualizar", height=28, width=100,
                      fg_color="#3a3a5a", hover_color="#252540",
                      font=ctk.CTkFont(size=11),
                      command=_refresh).pack(side="left", padx=(0, 6))

        if records:
            def _clear_all() -> None:
                if not messagebox.askyesno(
                    "Limpar crashes",
                    f"Apagar todos os {len(records)} registro(s) de crash?\n"
                    "Os arquivos .dmp e CrashContext serão excluídos permanentemente.",
                    parent=app,
                ):
                    return
                for r in records:
                    try:
                        shutil.rmtree(r["path"], ignore_errors=True)
                    except Exception:
                        pass
                _refresh()

            ctk.CTkButton(btn_row, text="🗑 Limpar todos", height=28, width=130,
                          fg_color=_RED_DARK, hover_color=_RED_HOVER,
                          font=ctk.CTkFont(size=11),
                          command=_clear_all).pack(side="left")

        if not records:
            ctk.CTkLabel(
                scroll,
                text="✅  Nenhum crash registrado.\n\n"
                     "Os crashes do servidor aparecerão aqui automaticamente.",
                text_color="gray55",
                font=ctk.CTkFont(size=12),
            ).grid(row=0, column=0, pady=40)
            return

        for idx, rec in enumerate(records):
            _build_crash_card(scroll, idx, rec)

    def _build_crash_card(frame, idx: int, rec: dict) -> None:
        ts_str = rec["timestamp"].strftime("%d/%m/%Y  %H:%M:%S")
        culprit = rec.get("culprit", "")
        has_culprit = bool(culprit)

        card = ctk.CTkFrame(frame, corner_radius=8,
                            fg_color="#2a1a1a" if has_culprit else "#1e1e2e",
                            border_width=1,
                            border_color="#5a2020" if has_culprit else "#3a3a55")
        card.grid(row=idx, column=0, padx=4, pady=(0, 8), sticky="ew")
        card.grid_columnconfigure(0, weight=1)

        # Cabeçalho
        hdr = ctk.CTkFrame(card,
                           fg_color="#3a1515" if has_culprit else "#252535",
                           corner_radius=6)
        hdr.grid(row=0, column=0, padx=6, pady=(6, 0), sticky="ew")
        hdr.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(hdr, text="💥",
                     font=ctk.CTkFont(size=14)
                     ).grid(row=0, column=0, padx=(10, 4), pady=6)
        ctk.CTkLabel(hdr, text=ts_str,
                     font=ctk.CTkFont(size=12, weight="bold"),
                     text_color="#e08080" if has_culprit else "#d0d0e0",
                     anchor="w").grid(row=0, column=1, padx=0, pady=6, sticky="w")

        if culprit:
            ctk.CTkLabel(hdr, text=f"⚠ {culprit}",
                         font=ctk.CTkFont(size=11, weight="bold"),
                         text_color="#ffaa44",
                         anchor="e").grid(row=0, column=2, padx=(4, 8), pady=6, sticky="e")

        if rec.get("has_dump"):
            ctk.CTkLabel(hdr, text=f"📄 {rec['dump_size_kb']} KB",
                         font=ctk.CTkFont(size=10),
                         text_color="gray60",
                         anchor="e").grid(row=0, column=3, padx=(0, 10), pady=6, sticky="e")

        body_row = 1

        # Diagnóstico
        diag = rec.get("diagnosis", "")
        if diag:
            diag_f = ctk.CTkFrame(card, fg_color="#1a2a1a", corner_radius=4)
            diag_f.grid(row=body_row, column=0, padx=8, pady=(6, 0), sticky="ew")
            diag_f.grid_columnconfigure(1, weight=1)
            ctk.CTkLabel(diag_f, text="🔍",
                         font=ctk.CTkFont(size=12)
                         ).grid(row=0, column=0, padx=(8, 4), pady=6)
            ctk.CTkLabel(diag_f, text=diag,
                         font=ctk.CTkFont(size=11),
                         text_color="#80d080",
                         anchor="w", wraplength=700,
                         ).grid(row=0, column=1, padx=(0, 8), pady=6, sticky="w")
            body_row += 1

        # Mensagem de erro
        err_msg = rec.get("error_message", "")
        if err_msg:
            ctk.CTkLabel(card, text="Mensagem de erro:",
                         text_color="gray55", font=ctk.CTkFont(size=10),
                         anchor="w").grid(row=body_row, column=0, padx=(12, 0),
                                          pady=(6, 0), sticky="w")
            body_row += 1
            err_box = ctk.CTkTextbox(card, height=52,
                                     font=ctk.CTkFont(family="Consolas", size=10),
                                     fg_color="#1a1a2a", text_color="#e08080")
            err_box.insert("end", err_msg)
            err_box.configure(state="disabled")
            err_box.grid(row=body_row, column=0, padx=8, pady=(0, 0), sticky="ew")
            body_row += 1

        # Call stack
        stack = rec.get("call_stack") or rec.get("log_lines", [])
        if stack:
            ctk.CTkLabel(card, text="Call stack:",
                         text_color="gray55", font=ctk.CTkFont(size=10),
                         anchor="w").grid(row=body_row, column=0, padx=(12, 0),
                                          pady=(6, 0), sticky="w")
            body_row += 1
            stack_h = min(130, max(52, len(stack) * 16))
            stk_box = ctk.CTkTextbox(card, height=stack_h,
                                      font=ctk.CTkFont(family="Consolas", size=10),
                                      fg_color="#12121e", text_color="#a0a0c0")
            for line in stack:
                stk_box.insert("end", line + "\n")
            stk_box.configure(state="disabled")
            stk_box.grid(row=body_row, column=0, padx=8, pady=(0, 0), sticky="ew")
            body_row += 1

        # Botões de ação
        act_row = ctk.CTkFrame(card, fg_color="transparent")
        act_row.grid(row=body_row, column=0, padx=8, pady=(4, 8), sticky="w")

        ctk.CTkButton(
            act_row, text="📁 Abrir pasta", height=24, width=110,
            fg_color="#3a3a5a", hover_color="#252540",
            font=ctk.CTkFont(size=10),
            command=lambda p=rec["path"]: subprocess.Popen(["explorer", p]),
        ).pack(side="left", padx=(0, 6))

        def _del_one(p: str = rec["path"]) -> None:
            if messagebox.askyesno(
                "Apagar crash",
                "Apagar este registro de crash?\nO arquivo .dmp será excluído permanentemente.",
                parent=app,
            ):
                try:
                    shutil.rmtree(p, ignore_errors=True)
                except Exception:
                    pass
                _refresh()

        ctk.CTkButton(
            act_row, text="🗑 Apagar", height=24, width=80,
            fg_color=_RED_DARK, hover_color=_RED_HOVER,
            font=ctk.CTkFont(size=10),
            command=_del_one,
        ).pack(side="left")

    _refresh()

