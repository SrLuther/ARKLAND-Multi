from __future__ import annotations
import threading
import tkinter as tk
from typing import TYPE_CHECKING
import customtkinter as ctk  # type: ignore[reportMissingImports]
from ..ui_constants import _RED_DARK, _RED_HOVER, _BLUE, _BLUE_HOVER
if TYPE_CHECKING:
    from ..app import ARKServerManagerApp


def refresh_mods_list(app: "ARKServerManagerApp", server_id: str, page: int = 0) -> None:
    srv = app.config_manager.get_server(server_id)
    if not srv:
        return
    w = app._server_widgets.get(server_id, {})
    frame: Optional[ctk.CTkScrollableFrame] = w.get("_mods_list_frame")
    if not frame:
        return

    # Paginação
    total = len(srv.mods)
    n_pages = max(1, (total + app._MODS_PAGE - 1) // app._MODS_PAGE)
    page = max(0, min(page, n_pages - 1))
    w["_mods_page"] = page
    start = page * app._MODS_PAGE

    for child in frame.winfo_children():
        child.destroy()

    # Atualizar nav
    sv_nav = w.get("_mods_sv_nav")
    btn_prev = w.get("_mods_btn_prev")
    btn_next = w.get("_mods_btn_next")
    if sv_nav is not None:
        if total:
            sv_nav.set(f"Página {page + 1} de {n_pages}  ·  {total} mod(s)")
        else:
            sv_nav.set("Nenhum mod")
    if btn_prev is not None:
        btn_prev.configure(state="normal" if page > 0 else "disabled")
    if btn_next is not None:
        btn_next.configure(state="normal" if page < n_pages - 1 else "disabled")

    if not srv.mods:
        ctk.CTkLabel(frame, text="Nenhum mod adicionado.",
                     text_color="gray50").pack(pady=20)
        return

    missing_names = [mid for mid in srv.mods if not srv.mod_names.get(mid)]
    if missing_names:
        app._fetch_mod_names_async(server_id, missing_names)

    for idx, mod_id in enumerate(srv.mods[start:start + app._MODS_PAGE]):
        actual_idx = start + idx
        row_bg = "#252538" if actual_idx % 2 == 0 else "transparent"
        row_f = ctk.CTkFrame(frame, fg_color=row_bg, corner_radius=6, height=40)
        row_f.pack(fill="x", pady=1)
        row_f.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(row_f, text=f"#{actual_idx+1}", width=32, text_color="gray50",
                     font=ctk.CTkFont(size=11)).grid(row=0, column=0, padx=(8, 4))

        mod_name = srv.mod_names.get(mod_id, "")
        display = f"{mod_id} - {mod_name}" if mod_name else mod_id
        ctk.CTkLabel(row_f, text=display,
                     font=ctk.CTkFont(family="Courier New", size=13)).grid(
            row=0, column=1, padx=4, sticky="w")

        # Status de instalação verificado em thread para não bloquear a UI
        # (especialmente quando install_dir é um drive de rede)
        status_lbl = ctk.CTkLabel(row_f, text="⏳", text_color="gray55",
                                  font=ctk.CTkFont(size=11))
        status_lbl.grid(row=0, column=2, padx=8)

        def _check_installed(
            _mid=mod_id, _idir=srv.install_dir, _lbl=status_lbl,
        ) -> None:
            ok = app.mod_manager.check_mod_installed(_idir, _mid)
            txt = "✅ instalado" if ok else "❌ não instalado"
            try:
                app.after(0, lambda t=txt, lb=_lbl: lb.configure(text=t))
            except Exception:
                pass

        threading.Thread(target=_check_installed, daemon=True).start()

        has_ini = bool(srv.mod_ini_configs.get(mod_id, {}).get("game_ini", "").strip()
                       or srv.mod_ini_configs.get(mod_id, {}).get("gus_ini", "").strip())
        ini_color = "#5a3a8a" if has_ini else "#2a2a3a"
        ctk.CTkButton(
            row_f, text="⚙️ INI", width=58, height=28,
            fg_color=ini_color, hover_color="#5a3a8a",
            command=lambda mid=mod_id, sid=server_id: app._open_mod_ini_dialog(sid, mid),
        ).grid(row=0, column=3, padx=2)

        ctk.CTkButton(
            row_f, text="🌐", width=32, height=28,
            fg_color="#1a3a6a", hover_color=_BLUE_HOVER,
            command=lambda mid=mod_id: app._open_workshop_page(mid),
        ).grid(row=0, column=4, padx=2)

        ctk.CTkButton(
            row_f, text="⬇️", width=36, height=28,
            fg_color=_BLUE, hover_color=_BLUE_HOVER,
            command=lambda mid=mod_id, sid=server_id: app._download_mod(sid, mid),
        ).grid(row=0, column=5, padx=2)

        ctk.CTkButton(
            row_f, text="🗑", width=32, height=28,
            fg_color=_RED_DARK, hover_color=_RED_HOVER,
            command=lambda mid=mod_id, sid=server_id: app._remove_mod(sid, mid),
        ).grid(row=0, column=6, padx=(2, 8))

