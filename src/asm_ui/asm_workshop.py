"""
asm_workshop.py — Workshop Browser TEK.

Janela para buscar, visualizar e gerenciar mods do Steam Workshop para
um servidor ARK específico. Permite buscar por ID ou nome, adicionar à
lista de mods ativos e baixar via SteamCMD.

Uso:
    from src.asm_ui.asm_workshop import open_asm_workshop
    open_asm_workshop(app, srv)
"""
from __future__ import annotations

import json
import threading
import tkinter as tk
import urllib.parse
import urllib.request
import webbrowser
from typing import TYPE_CHECKING, Optional

import customtkinter as ctk  # type: ignore[reportMissingImports]

from ..asm_engine.asm_server_config import AsmServerConfig
from ..ui_constants import get_theme

if TYPE_CHECKING:
    from ..app_tek import ARKServerManagerApp


_ARK_APP_ID       = "346110"   # Workshop app ID do ARK
_STEAM_API_DETAIL = (
    "https://api.steampowered.com/ISteamRemoteStorage/GetPublishedFileDetails/v1/"
)
_STEAM_WS_URL = "https://steamcommunity.com/sharedfiles/filedetails/?id="
_SEARCH_URL   = (
    "https://api.steampowered.com/IPublishedFileService/QueryFiles/v1/"
    "?key=&query_type=1&page=1&numperpage=20&appid=346110"
    "&search_text={query}&return_details=1"
)


# ─────────────────────────────────────────────────────────────────────────────


def _fetch_mod_details(mod_ids: list[str]) -> list[dict]:
    """Busca detalhes de mods na Steam API por lista de IDs."""
    if not mod_ids:
        return []
    data = urllib.parse.urlencode(
        [("itemcount", len(mod_ids))]
        + [(f"publishedfileids[{i}]", mid) for i, mid in enumerate(mod_ids)]
    ).encode()
    req = urllib.request.Request(_STEAM_API_DETAIL, data=data, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    with urllib.request.urlopen(req, timeout=15) as resp:
        payload = json.loads(resp.read())
    return payload.get("response", {}).get("publishedfiledetails", [])


def _search_mods(query: str) -> list[dict]:
    """Busca mods por nome no Steam Workshop."""
    url = _SEARCH_URL.format(query=urllib.parse.quote(query))
    req = urllib.request.Request(url)
    req.add_header("User-Agent", "ARKLAND-TEK/1.0")
    with urllib.request.urlopen(req, timeout=15) as resp:
        payload = json.loads(resp.read())
    files = payload.get("response", {}).get("publishedfiledetails", [])
    return files


# ─────────────────────────────────────────────────────────────────────────────


def open_asm_workshop(app: "ARKServerManagerApp", srv: AsmServerConfig) -> None:
    """Abre (ou foca) o Workshop Browser para *srv*."""
    win_attr = f"_asm_workshop_{srv.id}"
    existing: Optional[ctk.CTkToplevel] = getattr(app, win_attr, None)
    if existing and existing.winfo_exists():
        existing.lift()
        existing.focus_force()
        return

    win = _WorkshopWindow(app, srv)
    setattr(app, win_attr, win)
    win.protocol("WM_DELETE_WINDOW", lambda: _on_close(app, win_attr, win))
    win.after(100, win.lift)
    win.after(150, win.focus_force)


def _on_close(app: "ARKServerManagerApp", attr: str, win: ctk.CTkToplevel) -> None:
    setattr(app, attr, None)
    win.destroy()


# ─────────────────────────────────────────────────────────────────────────────


class _WorkshopWindow(ctk.CTkToplevel):
    """Janela de Workshop Browser para gerenciar mods do servidor."""

    def __init__(self, app: "ARKServerManagerApp", srv: AsmServerConfig) -> None:
        super().__init__(app)
        th = get_theme("tek")
        bg      = th["bg"]
        card_bg = th["card_bg"]
        accent  = th["accent"]
        sep     = th.get("separator", "#1e293b")
        t_sec   = th.get("text_secondary", "#94a3b8")
        t_mut   = th.get("text_muted", "#475569")

        self._app = app
        self._srv = srv

        self.title(f"Workshop — {srv.name}")
        self.geometry("900x620")
        self.minsize(700, 480)
        self.configure(fg_color=bg)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        # ── Barra de busca ────────────────────────────────────────────────────
        search_bar = ctk.CTkFrame(self, fg_color=card_bg, corner_radius=0, height=54)
        search_bar.grid(row=0, column=0, sticky="ew")
        search_bar.grid_columnconfigure(1, weight=1)
        search_bar.grid_propagate(False)

        ctk.CTkLabel(
            search_bar, text="🔍  Workshop",
            font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"),
            text_color=accent,
        ).grid(row=0, column=0, padx=14, pady=12)

        self._search_var = tk.StringVar()
        self._search_entry = ctk.CTkEntry(
            search_bar,
            textvariable=self._search_var,
            placeholder_text="Nome do mod ou ID (ex: 731604991) — Enter para buscar",
            font=ctk.CTkFont(size=12),
            height=36,
            corner_radius=6,
        )
        self._search_entry.grid(row=0, column=1, padx=(0, 8), pady=9, sticky="ew")
        self._search_entry.bind("<Return>", lambda _: self._do_search())

        ctk.CTkButton(
            search_bar, text="Buscar", width=80, height=36,
            fg_color="#14532d", hover_color="#166534",
            text_color=accent,
            font=ctk.CTkFont(size=12),
            command=self._do_search,
        ).grid(row=0, column=2, padx=(0, 8), pady=9)

        ctk.CTkButton(
            search_bar, text="🌐 Workshop", width=100, height=36,
            fg_color="#0f172a", hover_color="#1e293b",
            border_width=1, border_color=sep,
            text_color=t_sec,
            font=ctk.CTkFont(size=11),
            command=lambda: webbrowser.open(
                f"https://steamcommunity.com/app/{_ARK_APP_ID}/workshop/"
            ),
        ).grid(row=0, column=3, padx=(0, 12), pady=9)

        # ── Barra de mods ativos ──────────────────────────────────────────────
        active_bar = ctk.CTkFrame(self, fg_color="#0a1520", corner_radius=0, height=42)
        active_bar.grid(row=1, column=0, sticky="ew")
        active_bar.grid_columnconfigure(1, weight=1)
        active_bar.grid_propagate(False)

        ctk.CTkLabel(
            active_bar,
            text="Mods ativos no servidor:",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=t_sec,
        ).grid(row=0, column=0, padx=14, pady=10)

        self._active_lbl = ctk.CTkLabel(
            active_bar, text=self._format_active_mods(),
            font=ctk.CTkFont(family="Consolas", size=10),
            text_color=t_mut, anchor="w",
        )
        self._active_lbl.grid(row=0, column=1, padx=0, pady=10, sticky="w")

        ctk.CTkButton(
            active_bar, text="📦  Baixar Todos", width=120, height=30,
            fg_color="#1e3a5f", hover_color="#2563eb",
            text_color="#7dd3fc",
            font=ctk.CTkFont(size=11),
            command=self._download_all_mods,
        ).grid(row=0, column=2, padx=12, pady=6)

        # ── Área de resultados ────────────────────────────────────────────────
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.grid(row=2, column=0, sticky="nsew", padx=10, pady=8)
        body.grid_columnconfigure(0, weight=1)
        body.grid_rowconfigure(0, weight=1)

        self._results_scroll = ctk.CTkScrollableFrame(
            body, fg_color="transparent",
            scrollbar_button_color=sep,
            scrollbar_button_hover_color=accent,
        )
        self._results_scroll.grid(row=0, column=0, sticky="nsew")
        self._results_scroll.grid_columnconfigure(0, weight=1)

        self._status_lbl = ctk.CTkLabel(
            self._results_scroll,
            text="Digite um nome ou ID para buscar mods.",
            font=ctk.CTkFont(size=13),
            text_color=t_mut,
        )
        self._status_lbl.grid(row=0, column=0, pady=40)

        # Carrega mods ativos na abertura (se tiver IDs)
        if srv.active_mods:
            self.after(200, self._load_active_mods)

    # ── Busca ─────────────────────────────────────────────────────────────────

    def _do_search(self) -> None:
        query = self._search_var.get().strip()
        if not query:
            return
        self._clear_results()
        self._set_status("Buscando…")

        # Detecta se é ID numérico
        raw_ids = [p.strip() for p in query.split(",") if p.strip().isdigit()]
        if raw_ids:
            threading.Thread(
                target=self._fetch_by_ids, args=(raw_ids,), daemon=True
            ).start()
        else:
            threading.Thread(
                target=self._fetch_by_name, args=(query,), daemon=True
            ).start()

    def _fetch_by_ids(self, mod_ids: list[str]) -> None:
        try:
            details = _fetch_mod_details(mod_ids)
            self.after(0, lambda d=details: self._render_results(d))
        except Exception as exc:
            self.after(0, lambda e=exc: self._set_status(f"Erro: {e}", error=True))

    def _fetch_by_name(self, query: str) -> None:
        try:
            details = _search_mods(query)
            self.after(0, lambda d=details: self._render_results(d))
        except Exception as exc:
            self.after(0, lambda e=exc: self._set_status(f"Erro: {e}", error=True))

    def _load_active_mods(self) -> None:
        """Carrega os detalhes dos mods já ativos ao abrir."""
        mod_ids = [
            m.strip() for m in (self._srv.active_mods or "").split(",")
            if m.strip().isdigit()
        ]
        if mod_ids:
            self._set_status("Carregando mods ativos…")
            threading.Thread(
                target=self._fetch_by_ids, args=(mod_ids,), daemon=True
            ).start()

    # ── Renderização ──────────────────────────────────────────────────────────

    def _render_results(self, mods: list[dict]) -> None:
        if not self.winfo_exists():
            return
        th = get_theme("tek")
        card_bg = th["card_bg"]
        t_sec   = th.get("text_secondary", "#94a3b8")
        t_mut   = th.get("text_muted", "#475569")
        accent  = th["accent"]
        sep     = th.get("separator", "#1e293b")

        self._clear_results()

        if not mods:
            self._set_status("Nenhum resultado encontrado.")
            return

        active_ids = set(
            m.strip()
            for m in (self._srv.active_mods or "").split(",")
            if m.strip()
        )

        for i, mod in enumerate(mods):
            file_id   = mod.get("publishedfileid", "")
            title     = mod.get("title", f"Mod {file_id}")
            desc      = (mod.get("short_description") or mod.get("file_description") or "")[:100]
            is_active = file_id in active_ids

            row_bg = card_bg if i % 2 == 0 else "#0a1520"
            row = ctk.CTkFrame(
                self._results_scroll,
                fg_color=row_bg,
                corner_radius=6,
            )
            row.grid(row=i, column=0, sticky="ew", pady=2)
            row.grid_columnconfigure(1, weight=1)

            # ID
            ctk.CTkLabel(
                row, text=file_id, width=100, anchor="w",
                font=ctk.CTkFont(family="Consolas", size=10),
                text_color=t_mut,
            ).grid(row=0, column=0, padx=(10, 6), pady=(8, 0), sticky="w")

            # Título + descrição
            info_frame = ctk.CTkFrame(row, fg_color="transparent")
            info_frame.grid(row=0, column=1, padx=4, pady=6, sticky="ew", rowspan=2)
            info_frame.grid_columnconfigure(0, weight=1)

            ctk.CTkLabel(
                info_frame, text=title, anchor="w",
                font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
                text_color=t_sec,
            ).grid(row=0, column=0, sticky="ew")

            if desc:
                ctk.CTkLabel(
                    info_frame, text=desc, anchor="w",
                    font=ctk.CTkFont(size=10),
                    text_color=t_mut,
                ).grid(row=1, column=0, sticky="ew")

            # Botões
            btn_cell = ctk.CTkFrame(row, fg_color="transparent")
            btn_cell.grid(row=0, column=2, padx=(6, 10), pady=8, sticky="e")

            # Link Steam
            ctk.CTkButton(
                btn_cell, text="🌐", width=32, height=28,
                fg_color="#0f172a", hover_color="#1e293b",
                border_width=1, border_color=sep,
                text_color=t_sec,
                font=ctk.CTkFont(size=11),
                corner_radius=4,
                command=lambda fid=file_id: webbrowser.open(f"{_STEAM_WS_URL}{fid}"),
            ).pack(side="left", padx=(0, 4))

            # Adicionar / Remover
            if is_active:
                ctk.CTkButton(
                    btn_cell, text="✓ Ativo", width=72, height=28,
                    fg_color="#14532d", hover_color="#166534",
                    text_color=accent,
                    font=ctk.CTkFont(size=10),
                    corner_radius=4,
                    command=lambda fid=file_id: self._remove_mod(fid),
                ).pack(side="left", padx=(0, 4))
            else:
                ctk.CTkButton(
                    btn_cell, text="+ Adicionar", width=82, height=28,
                    fg_color="#1e3a5f", hover_color="#2563eb",
                    text_color="#7dd3fc",
                    font=ctk.CTkFont(size=10),
                    corner_radius=4,
                    command=lambda fid=file_id, ttl=title: self._add_mod(fid, ttl),
                ).pack(side="left", padx=(0, 4))

            # Baixar
            ctk.CTkButton(
                btn_cell, text="📦", width=32, height=28,
                fg_color="#0f172a", hover_color="#1e3a5f",
                border_width=1, border_color=sep,
                text_color=t_sec,
                font=ctk.CTkFont(size=11),
                corner_radius=4,
                command=lambda fid=file_id: self._download_mod(fid),
            ).pack(side="left")

        n = len(mods)
        self._set_status(f"{n} resultado{'s' if n != 1 else ''} encontrado{'s' if n != 1 else ''}")

    # ── Gestão de mods ativos ─────────────────────────────────────────────────

    def _add_mod(self, mod_id: str, title: str = "") -> None:
        srv = self._srv
        existing = [m.strip() for m in (srv.active_mods or "").split(",") if m.strip()]
        if mod_id not in existing:
            existing.append(mod_id)
            srv.active_mods = ",".join(existing)
            self._app.asm_config_manager.update_server(srv)
            self._app.asm_config_manager.save()
            self._active_lbl.configure(text=self._format_active_mods())
            # Re-renderiza para atualizar botões
            self._do_search()

    def _remove_mod(self, mod_id: str) -> None:
        srv = self._srv
        existing = [m.strip() for m in (srv.active_mods or "").split(",") if m.strip()]
        if mod_id in existing:
            existing.remove(mod_id)
            srv.active_mods = ",".join(existing)
            self._app.asm_config_manager.update_server(srv)
            self._app.asm_config_manager.save()
            self._active_lbl.configure(text=self._format_active_mods())
            self._do_search()

    # ── Download ──────────────────────────────────────────────────────────────

    def _download_mod(self, mod_id: str) -> None:
        """Baixa um único mod via SteamCMD em janela de log."""
        self._open_download_window([mod_id])

    def _download_all_mods(self) -> None:
        """Baixa todos os mods ativos via SteamCMD."""
        srv = self._srv
        mod_ids = [m.strip() for m in (srv.active_mods or "").split(",") if m.strip()]
        if not mod_ids:
            return
        self._open_download_window(mod_ids)

    def _open_download_window(self, mod_ids: list[str]) -> None:
        th = get_theme("tek")
        bg  = th["bg"]
        sep = th.get("separator", "#1e293b")

        log_win = ctk.CTkToplevel(self)
        log_win.title(f"Download — {len(mod_ids)} mod(s)")
        log_win.geometry("600x400")
        log_win.configure(fg_color=bg)
        log_win.grab_set()

        log_box = ctk.CTkTextbox(
            log_win, state="disabled",
            font=ctk.CTkFont(family="Consolas", size=11),
            fg_color="#04090f", text_color="#d1fae5",
            border_width=1, border_color=sep,
            corner_radius=6,
        )
        log_box.pack(fill="both", expand=True, padx=10, pady=(10, 6))

        def _log(msg: str) -> None:
            if not log_win.winfo_exists():
                return
            log_box.configure(state="normal")
            log_box.insert("end", msg + "\n")
            log_box.see("end")
            log_box.configure(state="disabled")

        ctk.CTkButton(
            log_win, text="Fechar", width=80,
            fg_color="#0f172a", hover_color="#1e293b",
            command=log_win.destroy,
        ).pack(pady=(0, 10))

        def _worker():
            srv = self._srv
            try:
                from ..asm_engine.asm_steamcmd import AsmSteamCmd  # noqa: PLC0415
                scmd_path = (
                    getattr(getattr(self._app.config_manager, "config", None), "steamcmd_path", None)
                    or AsmSteamCmd.find_steamcmd()
                )
                if not scmd_path:
                    log_win.after(0, lambda: _log(
                        "✘ SteamCMD não encontrado. Configure o caminho nas configurações."
                    ))
                    return
                sc = AsmSteamCmd(scmd_path, on_log=lambda m: log_win.after(0, lambda msg=m: _log(msg)))
                sc.download_mods(
                    mod_ids=mod_ids,
                    install_dir=srv.install_dir,
                    on_done=lambda ok, msg: log_win.after(
                        0, lambda o=ok, m=msg: _log(f"{'✔' if o else '✘'} {m}")
                    ),
                )
            except Exception as exc:
                log_win.after(0, lambda e=exc: _log(f"✘ {e}"))

        threading.Thread(target=_worker, daemon=True).start()

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _format_active_mods(self) -> str:
        mods = [m.strip() for m in (self._srv.active_mods or "").split(",") if m.strip()]
        if not mods:
            return "Nenhum mod ativo."
        if len(mods) <= 5:
            return ", ".join(mods)
        return ", ".join(mods[:5]) + f"  (+{len(mods) - 5} mais)"

    def _clear_results(self) -> None:
        for w in self._results_scroll.winfo_children():
            w.destroy()

    def _set_status(self, text: str, error: bool = False) -> None:
        if not self.winfo_exists():
            return
        th = get_theme("tek")
        color = "#f87171" if error else th.get("text_muted", "#475569")
        lbl = ctk.CTkLabel(
            self._results_scroll, text=text,
            font=ctk.CTkFont(size=12), text_color=color,
        )
        lbl.grid(row=0, column=0, pady=30)
