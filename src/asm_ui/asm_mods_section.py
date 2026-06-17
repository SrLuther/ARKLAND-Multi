"""Seção dedicada Mods (Workshop) — painel TEK."""
from __future__ import annotations

import tkinter as tk

import customtkinter as ctk  # type: ignore[reportMissingImports]

from ..asm_engine.asm_server_config import AsmServerConfig


def _section_label(parent, text, row, accent):
    ctk.CTkLabel(parent, text=text,
                 font=ctk.CTkFont(size=12, weight="bold"),
                 text_color=accent).grid(
        row=row, column=0, columnspan=4, padx=8, pady=(10, 2), sticky="w")


def build_mods_workshop_section(
    sf: ctk.CTkScrollableFrame,
    srv: AsmServerConfig,
    vars_ref: dict,
    accent: str,
) -> None:
    """Mods Workshop + atualização automática (aba própria na nav lateral)."""
    app = vars_ref.get("_app")
    if app:
        _au_wrap = ctk.CTkFrame(sf, fg_color="transparent")
        _au_wrap.grid(row=0, column=0, columnspan=2, sticky="ew", padx=8, pady=(8, 4))
        from ..pages.build_tek_mod_auto_update_card import build_tek_mod_auto_update_card
        build_tek_mod_auto_update_card(app, _au_wrap, srv.id)

    ctk.CTkLabel(
        sf,
        text="IDs numéricos do Steam Workshop, na ordem de carregamento do servidor.",
        font=ctk.CTkFont(size=10), text_color="#64748b", anchor="w", wraplength=640,
    ).grid(row=1, column=0, columnspan=2, padx=8, pady=(0, 6), sticky="w")

    _section_label(sf, "Lista de Mods", 2, accent)

    _mod_frame = ctk.CTkFrame(sf, fg_color="#0d1b2a", corner_radius=8)
    _mod_frame.grid(row=3, column=0, columnspan=2, padx=8, pady=(0, 4), sticky="ew")
    _mod_frame.grid_columnconfigure(0, weight=1)

    _mod_cache: dict = vars_ref.setdefault("_mod_info_cache", {})

    _hidden_mods = ctk.CTkTextbox(_mod_frame, height=1,
                                  fg_color="#0d1b2a", text_color="#0d1b2a", border_width=0)
    _hidden_mods.grid(row=99, column=0, sticky="ew")
    _hidden_mods.insert("1.0", "\n".join(srv.active_mods))
    vars_ref["_mods_text"] = _hidden_mods

    _mod_rows: list[dict] = []

    def _sync_hidden():
        ids = [r["id_var"].get().strip() for r in _mod_rows if r["id_var"].get().strip()]
        _hidden_mods.configure(state="normal")
        _hidden_mods.delete("1.0", "end")
        _hidden_mods.insert("1.0", "\n".join(ids))

    def _parse_mod_ids_line(raw: str) -> list[str]:
        import re
        seen: set[str] = set()
        out: list[str] = []
        for part in re.split(r"[,;\s]+", (raw or "").strip()):
            mid = part.strip()
            if mid.isdigit() and mid not in seen:
                seen.add(mid)
                out.append(mid)
        return out

    def _clear_mod_rows() -> None:
        for row in list(_mod_rows):
            row["frame"].destroy()
        _mod_rows.clear()

    def _refresh_mod_labels():
        for r in _mod_rows:
            mid = r["id_var"].get().strip()
            cd = _mod_cache.get(mid)
            if cd:
                r["name_lbl"].configure(text=cd.get("name", "—"))
                r["info_lbl"].configure(text=cd.get("info", "—"))
            elif mid:
                r["name_lbl"].configure(text="(clique em Buscar)")
                r["info_lbl"].configure(text="—")
            else:
                r["name_lbl"].configure(text="")
                r["info_lbl"].configure(text="")

    def _add_mod_row(mod_id: str = "", *, defer_status: bool = False):
        ridx = len(_mod_rows)
        rf = ctk.CTkFrame(_rows_outer, fg_color="#07101c", corner_radius=3)
        rf.grid(row=ridx, column=0, sticky="ew", padx=4, pady=1)
        rf.grid_columnconfigure(1, weight=1)

        id_var = tk.StringVar(value=mod_id)
        ctk.CTkEntry(rf, textvariable=id_var, width=115, height=26,
                     placeholder_text="ID Steam",
                     font=ctk.CTkFont(family="Consolas", size=11),
                     ).grid(row=0, column=0, padx=(4, 4), pady=2)

        name_lbl = ctk.CTkLabel(rf, text="", font=ctk.CTkFont(size=11),
                                text_color="#94a3b8", anchor="w")
        name_lbl.grid(row=0, column=1, padx=(0, 4), sticky="ew")

        info_lbl = ctk.CTkLabel(rf, text="", font=ctk.CTkFont(size=10),
                                text_color="#475569", width=170, anchor="w")
        info_lbl.grid(row=0, column=2, padx=(0, 4))

        status_lbl = ctk.CTkLabel(rf, text="", font=ctk.CTkFont(size=10),
                                  text_color="gray50", width=90, anchor="e")
        status_lbl.grid(row=0, column=3, padx=(0, 4))

        rd = {"id_var": id_var, "name_lbl": name_lbl, "info_lbl": info_lbl,
              "status_lbl": status_lbl, "frame": rf}

        def _check_status(_mid: str, _lbl=status_lbl) -> None:
            import threading as _th
            from pathlib import Path as _Path
            def _worker():
                idir = srv.install_dir
                if not idir or not _mid:
                    sf.after(0, lambda: _lbl.configure(text=""))
                    return
                base = _Path(idir) / "ShooterGame" / "Content" / "Mods"
                has_folder = (base / _mid).exists()
                has_dot_mod = (base / f"{_mid}.mod").exists()
                if has_folder and has_dot_mod:
                    txt, col = "✅ instalado", "#4ade80"
                elif has_folder:
                    txt, col = "⚠ sem .mod", "#facc15"
                else:
                    txt, col = "❌ não instalado", "#f87171"
                try:
                    sf.after(0, lambda t=txt, c=col: _lbl.configure(text=t, text_color=c))
                except Exception:
                    pass
            _th.Thread(target=_worker, daemon=True).start()

        def _del(r=rd, f=rf):
            f.destroy()
            if r in _mod_rows:
                _mod_rows.remove(r)
            for i, x in enumerate(_mod_rows):
                x["frame"].grid(row=i, column=0, sticky="ew", padx=4, pady=1)
            _sync_hidden()

        ctk.CTkButton(rf, text="✕", width=24, height=24,
                      fg_color="#5c1a1a", hover_color="#7c2020",
                      font=ctk.CTkFont(size=10), corner_radius=4,
                      command=_del).grid(row=0, column=4, padx=(0, 4))

        _mod_rows.append(rd)
        id_var.trace_add("write", lambda *_: (_sync_hidden(), _check_status(id_var.get().strip())))

        cd = _mod_cache.get(mod_id.strip())
        if cd:
            name_lbl.configure(text=cd.get("name", "—"))
            info_lbl.configure(text=cd.get("info", "—"))
        elif mod_id.strip():
            name_lbl.configure(text="(clique em Buscar)")

        if mod_id.strip() and not defer_status:
            _check_status(mod_id.strip())

    _bulk_row = ctk.CTkFrame(_mod_frame, fg_color="transparent")
    _bulk_row.grid(row=0, column=0, sticky="ew", padx=8, pady=(8, 2))
    _bulk_row.grid_columnconfigure(1, weight=1)

    _bulk_var = tk.StringVar()
    ctk.CTkLabel(
        _bulk_row, text="Colar IDs:", font=ctk.CTkFont(size=10),
        text_color="#64748b", width=72, anchor="w",
    ).grid(row=0, column=0, padx=(0, 6), sticky="w")
    _bulk_entry = ctk.CTkEntry(
        _bulk_row, textvariable=_bulk_var, height=28,
        placeholder_text="ex: 123456789,987654321,111222333",
        font=ctk.CTkFont(family="Consolas", size=11),
    )
    _bulk_entry.grid(row=0, column=1, sticky="ew", padx=(0, 6))

    def _apply_bulk_mod_line(*_) -> None:
        ids = _parse_mod_ids_line(_bulk_var.get())
        if not ids:
            import tkinter.messagebox as mb
            mb.showinfo(
                "Importar mods",
                "Nenhum ID válido encontrado.\n\n"
                "Cole IDs numéricos do Workshop separados por vírgula.",
                parent=sf,
            )
            return
        _clear_mod_rows()
        for mid in ids:
            _add_mod_row(mid)
        _sync_hidden()
        _bulk_var.set("")

    ctk.CTkButton(
        _bulk_row, text="Aplicar lista", width=110, height=28,
        fg_color="#14532d", hover_color="#166534",
        font=ctk.CTkFont(size=11),
        command=_apply_bulk_mod_line,
    ).grid(row=0, column=2, padx=(0, 0))
    _bulk_entry.bind("<Return>", _apply_bulk_mod_line)

    ctk.CTkLabel(
        _mod_frame,
        text="Substitui a lista atual pela ordem dos IDs colados (vírgula, espaço ou ponto-e-vírgula).",
        font=ctk.CTkFont(size=9), text_color="#475569", anchor="w",
    ).grid(row=1, column=0, sticky="w", padx=8, pady=(0, 4))

    _mods_tb = ctk.CTkFrame(_mod_frame, fg_color="transparent")
    _mods_tb.grid(row=2, column=0, sticky="ew", padx=8, pady=(0, 4))

    ctk.CTkButton(_mods_tb, text="+ Mod", width=82, height=28,
                  fg_color="#14532d", hover_color="#166534",
                  font=ctk.CTkFont(size=11),
                  command=_add_mod_row).pack(side="left", padx=(0, 4))

    def _do_fetch_workshop():
        import threading
        import requests as _rq
        ids = [r["id_var"].get().strip() for r in _mod_rows if r["id_var"].get().strip()]
        if not ids:
            return
        _fetch_btn.configure(state="disabled", text="Buscando...")

        def _worker():
            try:
                data = {"itemcount": len(ids)}
                for i, mid in enumerate(ids):
                    data[f"publishedfileids[{i}]"] = mid
                resp = _rq.post(
                    "https://api.steampowered.com/ISteamRemoteStorage/GetPublishedFileDetails/v1/",
                    data=data, timeout=15,
                )
                for d in resp.json().get("response", {}).get("publishedfiledetails", []):
                    fid = d.get("publishedfileid", "")
                    if d.get("result") == 1:
                        from datetime import datetime as _dt
                        ts = d.get("time_updated", 0)
                        date_str = _dt.fromtimestamp(ts).strftime("%d/%m/%Y") if ts else "—"
                        _mod_cache[fid] = {"name": d.get("title", "—"), "info": f"Atualiz.: {date_str}"}
                    else:
                        _mod_cache[fid] = {"name": "❌ ID inválido", "info": "—"}
            except Exception:
                pass
            sf.after(0, lambda: (
                _fetch_btn.configure(state="normal", text="Buscar Info"),
                _refresh_mod_labels(),
            ))

        threading.Thread(target=_worker, daemon=True).start()

    _fetch_btn = ctk.CTkButton(_mods_tb, text="Buscar Info", width=118, height=28,
                               fg_color="#0e4a6e", hover_color="#0a3550",
                               font=ctk.CTkFont(size=11),
                               command=_do_fetch_workshop)
    _fetch_btn.pack(side="left", padx=(0, 4))

    def _do_redownload_mods():
        from .asm_steamcmd_ui import start_mods_redownload
        from ..asm_engine.asm_mod_utils import collect_mod_ids_for_install
        _app = vars_ref.get("_app")
        _lines = _hidden_mods.get("1.0", "end").strip().splitlines()
        srv.active_mods = [l.strip() for l in _lines if l.strip()]
        _ids = collect_mod_ids_for_install(srv)
        if not _ids:
            import tkinter.messagebox as mb
            mb.showinfo(
                "Sem mods",
                "Nenhum mod para baixar.\n\n"
                "Mapa mod: use /Game/Mods/{id}/{nome} no campo Mapa.",
                parent=_app,
            )
            return
        start_mods_redownload(_app, srv, _ids)

    ctk.CTkButton(_mods_tb, text="Redownload Mods", width=155, height=28,
                  fg_color="#1e3a5f", hover_color="#1e40af",
                  font=ctk.CTkFont(size=11),
                  command=_do_redownload_mods).pack(side="left", padx=(0, 4))

    ctk.CTkButton(_mods_tb, text="Validar IDs", width=105, height=28,
                  fg_color="#1c1917", hover_color="#292524",
                  font=ctk.CTkFont(size=11),
                  command=_do_fetch_workshop).pack(side="left")

    _mods_hdr = ctk.CTkFrame(_mod_frame, fg_color="#0f2030", corner_radius=4, height=24)
    _mods_hdr.grid(row=3, column=0, sticky="ew", padx=8, pady=(0, 2))
    _mods_hdr.grid_columnconfigure(1, weight=1)
    ctk.CTkLabel(_mods_hdr, text="ID Steam", font=ctk.CTkFont(size=9, weight="bold"),
                 text_color="#475569", width=115, anchor="center").grid(row=0, column=0, padx=(4, 4), pady=2)
    ctk.CTkLabel(_mods_hdr, text="Nome do Mod", font=ctk.CTkFont(size=9, weight="bold"),
                 text_color="#475569", anchor="w").grid(row=0, column=1, padx=(0, 4), sticky="w", pady=2)
    ctk.CTkLabel(_mods_hdr, text="Última Atualização", font=ctk.CTkFont(size=9, weight="bold"),
                 text_color="#475569", width=170, anchor="w").grid(row=0, column=2, padx=(0, 4), pady=2)
    ctk.CTkLabel(_mods_hdr, text="", width=28).grid(row=0, column=3)

    _rows_outer = ctk.CTkFrame(_mod_frame, fg_color="#060d14", corner_radius=6)
    _rows_outer.grid(row=4, column=0, sticky="ew", padx=8, pady=(0, 8))
    _rows_outer.grid_columnconfigure(0, weight=1)

    def _run_mod_status_checks() -> None:
        for rd in _mod_rows:
            mid = rd["id_var"].get().strip()
            if mid:
                _check_status(mid)

    _mod_ids_to_load = list(srv.active_mods)

    def _populate_mod_rows_chunk(start: int = 0, chunk: int = 5) -> None:
        for _mid in _mod_ids_to_load[start:start + chunk]:
            _add_mod_row(_mid, defer_status=True)
        next_start = start + chunk
        if next_start < len(_mod_ids_to_load):
            sf.after(0, lambda s=next_start: _populate_mod_rows_chunk(s, chunk))
        else:
            if not _mod_ids_to_load:
                _add_mod_row()
            sf.after(120, _run_mod_status_checks)
    sf.after(0, lambda: _populate_mod_rows_chunk())
