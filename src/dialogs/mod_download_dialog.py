"""Dialog de progresso de download de mods.

Exibe uma lista de mods com status em tempo real (Aguardando → Baixando →
Instalado / Erro) enquanto o SteamCMD roda em janela própria.
Mensagens Python-side (cópia, .mod) aparecem no log embutido.
"""
from __future__ import annotations

import tkinter as tk
from typing import TYPE_CHECKING, List

import customtkinter as ctk  # type: ignore[reportMissingImports]

from ..ui_constants import _CARD_BG

if TYPE_CHECKING:
    from ..app import ARKServerManagerApp


# Mapeamento de status → (texto, cor)
_STATUS_MAP = {
    "waiting":   ("⏳  Aguardando",  "gray50"),
    "updating":  ("🔄  Baixando...", "#4FC3F7"),
    "installed": ("✅  Instalado",   "#66BB6A"),
    "error":     ("❌  Erro",        "#EF5350"),
}


def open_mod_download_dialog(
    app: "ARKServerManagerApp",
    server_id: str,
    mod_ids: List[str],
) -> None:
    """Abre o dialog e inicia o download com SteamCMD visível."""
    srv = app.config_manager.get_server(server_id)
    if not srv:
        return

    dlg = ctk.CTkToplevel(app)
    dlg.title("Download de Mods")
    dlg.geometry("660x520")
    dlg.resizable(True, True)
    dlg.lift()
    dlg.focus_force()
    dlg.grid_columnconfigure(0, weight=1)
    dlg.grid_rowconfigure(1, weight=1)
    dlg.grid_rowconfigure(2, weight=0)

    # ── Cabeçalho ─────────────────────────────────────────────────────────
    hdr = ctk.CTkFrame(dlg, fg_color=_CARD_BG, corner_radius=10)
    hdr.grid(row=0, column=0, padx=12, pady=(12, 4), sticky="ew")
    hdr.grid_columnconfigure(0, weight=1)

    ctk.CTkLabel(
        hdr, text="⬇️  Download de Mods",
        font=ctk.CTkFont(size=16, weight="bold"),
    ).grid(row=0, column=0, padx=16, pady=(12, 2), sticky="w")

    status_header = ctk.CTkLabel(
        hdr,
        text=f"{len(mod_ids)} mod(s) na fila  •  Um único SteamCMD baixa todos de uma vez",
        text_color="gray55", font=ctk.CTkFont(size=11),
    )
    status_header.grid(row=1, column=0, padx=16, pady=(0, 12), sticky="w")

    # ── Lista de mods ─────────────────────────────────────────────────────
    list_card = ctk.CTkScrollableFrame(dlg, fg_color=_CARD_BG, corner_radius=10)
    list_card.grid(row=1, column=0, padx=12, pady=(4, 4), sticky="nsew")
    list_card.grid_columnconfigure(1, weight=1)

    status_labels: dict[str, ctk.CTkLabel] = {}

    for idx, mid in enumerate(mod_ids):
        row_bg = "#252538" if idx % 2 == 0 else "transparent"
        row_f = ctk.CTkFrame(list_card, fg_color=row_bg, corner_radius=6, height=38)
        row_f.pack(fill="x", pady=1)
        row_f.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            row_f, text=f"#{idx + 1}", width=32,
            text_color="gray50", font=ctk.CTkFont(size=11),
        ).grid(row=0, column=0, padx=(8, 4))

        name = srv.mod_names.get(mid, "")
        display = f"{mid}  —  {name}" if name else mid
        ctk.CTkLabel(
            row_f, text=display,
            font=ctk.CTkFont(family="Courier New", size=12),
            anchor="w",
        ).grid(row=0, column=1, padx=4, sticky="w")

        txt, col = _STATUS_MAP["waiting"]
        lbl = ctk.CTkLabel(
            row_f, text=txt, text_color=col,
            font=ctk.CTkFont(size=11), width=140, anchor="e",
        )
        lbl.grid(row=0, column=2, padx=(4, 12))
        status_labels[mid] = lbl

    # ── Log Python-side ───────────────────────────────────────────────────
    log_card = ctk.CTkFrame(dlg, fg_color=_CARD_BG, corner_radius=10)
    log_card.grid(row=2, column=0, padx=12, pady=(4, 4), sticky="ew")
    log_card.grid_columnconfigure(0, weight=1)

    ctk.CTkLabel(
        log_card, text="Log", text_color="gray55",
        font=ctk.CTkFont(size=10),
    ).grid(row=0, column=0, padx=12, pady=(6, 0), sticky="w")

    log_box = ctk.CTkTextbox(
        log_card, height=110, state="disabled",
        font=ctk.CTkFont(family="Courier New", size=10),
    )
    log_box._textbox.tag_configure("info",    foreground="#e0e0e0")
    log_box._textbox.tag_configure("warning", foreground="#ffaa44")
    log_box._textbox.tag_configure("error",   foreground="#ff6666")
    log_box._textbox.tag_configure("debug",   foreground="#888888")
    log_box.grid(row=1, column=0, padx=12, pady=(2, 8), sticky="ew")

    # ── Botão fechar ──────────────────────────────────────────────────────
    close_btn = ctk.CTkButton(
        dlg, text="Fechar", width=120, height=34, state="disabled",
        command=dlg.destroy,
    )
    close_btn.grid(row=3, column=0, pady=(4, 12))

    # ── Callbacks para o dialog ───────────────────────────────────────────

    def _set_status(mid: str, key: str) -> None:
        lbl = status_labels.get(mid)
        if not lbl:
            return
        txt, col = _STATUS_MAP.get(key, (key, "gray70"))
        try:
            lbl.configure(text=txt, text_color=col)
        except Exception:
            pass

    def _append_log(msg: str, level: str = "info") -> None:
        if level == "debug":
            return  # linhas do SteamCMD não chegam aqui (show_console=True)
        try:
            log_box.configure(state="normal")
            log_box._textbox.insert("end", f"{msg}\n", level)
            log_box.configure(state="disabled")
            log_box._textbox.see("end")
        except Exception:
            pass

    def _on_progress_dlg(mid: str, status: str) -> None:
        def _apply(m: str = mid, s: str = status) -> None:
            _set_status(m, s)
            if s == "updating":
                status_header.configure(
                    text=f"Baixando mods via SteamCMD…  ({len(mod_ids)} em um único processo)",
                    text_color="#4FC3F7",
                )
        dlg.after(0, _apply)

    def _on_log_dlg(msg: str, level: str = "info") -> None:
        dlg.after(0, lambda: _append_log(msg, level))

    def _on_done(ok: bool) -> None:
        summary = "✅  Concluído com sucesso." if ok else "⚠️  Concluído com erros — verifique o log."
        color   = "#66BB6A" if ok else "#ffaa44"
        dlg.after(0, lambda: status_header.configure(text=summary, text_color=color))
        dlg.after(0, lambda: close_btn.configure(state="normal"))
        dlg.after(0, lambda: app._refresh_mods_list(server_id))

    # ── Inicia o download ─────────────────────────────────────────────────
    _append_log("⏳ Iniciando SteamCMD…", "info")
    _append_log("A auto-atualização pode levar 1–2 min antes do download aparecer.", "info")
    app.mod_manager.steamcmd_path = app.config_manager.config.steamcmd_path
    app.mod_manager.download_mods(
        mod_ids,
        srv.install_dir,
        on_done=_on_done,
        on_log=_on_log_dlg,
        on_progress=_on_progress_dlg,
        show_console=True,
    )
