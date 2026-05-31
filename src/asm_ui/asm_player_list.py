"""
asm_player_list.py — Lista de Jogadores TEK via RCON.

Janela que mostra os jogadores conectados ao servidor em tempo real,
com ações individuais: Kick, Ban, Whitelist, Admin.

Uso:
    from src.asm_ui.asm_player_list import open_asm_player_list
    open_asm_player_list(app, srv)
"""
from __future__ import annotations

import re
import threading
import time
import tkinter as tk
from typing import TYPE_CHECKING, NamedTuple, Optional

import customtkinter as ctk  # type: ignore[reportMissingImports]

from ..rcon_client import RconClient
from ..asm_engine.asm_server_config import AsmServerConfig
from ..ui_constants import get_theme

if TYPE_CHECKING:
    from ..app_tek import ARKServerManagerApp


_AUTO_REFRESH_MS = 30_000   # 30 s


class _Player(NamedTuple):
    index: int
    name: str
    steam_id: str


def _parse_listplayers(raw: str) -> list[_Player]:
    """Analisa a saída do RCON 'ListPlayers'.

    Formato esperado (uma linha por jogador):
        0. NomeDoJogador, 76561198012345678
    Retorna lista de _Player.
    """
    players: list[_Player] = []
    for line in raw.splitlines():
        line = line.strip()
        m = re.match(r"^(\d+)\.\s+(.+),\s*(\d{15,17})$", line)
        if m:
            players.append(_Player(int(m.group(1)), m.group(2).strip(), m.group(3)))
    return players


# ─────────────────────────────────────────────────────────────────────────────


def open_asm_player_list(app: "ARKServerManagerApp", srv: AsmServerConfig) -> None:
    """Abre (ou foca) a janela de lista de jogadores para *srv*."""
    win_attr = f"_asm_player_list_{srv.id}"
    existing: Optional[ctk.CTkToplevel] = getattr(app, win_attr, None)
    if existing and existing.winfo_exists():
        existing.lift()
        existing.focus_force()
        return

    win = _PlayerListWindow(app, srv)
    setattr(app, win_attr, win)
    win.protocol("WM_DELETE_WINDOW", lambda: _on_close(app, win_attr, win))
    win.after(100, win.lift)
    win.after(150, win.focus_force)


def _on_close(app: "ARKServerManagerApp", attr: str, win: ctk.CTkToplevel) -> None:
    win._cancel_refresh()  # type: ignore[attr-defined]
    setattr(app, attr, None)
    win.destroy()


# ─────────────────────────────────────────────────────────────────────────────


class _PlayerListWindow(ctk.CTkToplevel):
    """Janela de lista de jogadores em tempo real."""

    def __init__(self, app: "ARKServerManagerApp", srv: AsmServerConfig) -> None:
        super().__init__(app)
        th = get_theme("tek")
        bg      = th["bg"]
        card_bg = th["card_bg"]
        accent  = th["accent"]
        sep     = th.get("separator", "#1e293b")
        t_sec   = th.get("text_secondary", "#94a3b8")
        t_mut   = th.get("text_muted", "#475569")

        self._app    = app
        self._srv    = srv
        self._players: list[_Player] = []
        self._selected: Optional[_Player] = None
        self._refresh_id: Optional[str] = None
        self._lock = threading.Lock()

        # ── Janela ───────────────────────────────────────────────────────────
        self.title(f"Jogadores — {srv.name}")
        self.geometry("680x480")
        self.minsize(520, 360)
        self.configure(fg_color=bg)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # ── TopBar ───────────────────────────────────────────────────────────
        top = ctk.CTkFrame(self, fg_color=card_bg, corner_radius=0, height=44)
        top.grid(row=0, column=0, sticky="ew")
        top.grid_columnconfigure(1, weight=1)
        top.grid_propagate(False)

        self._count_lbl = ctk.CTkLabel(
            top, text="0 jogadores online",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            text_color=accent,
        )
        self._count_lbl.grid(row=0, column=0, padx=14, pady=10, sticky="w")

        self._status_lbl = ctk.CTkLabel(
            top, text="Aguardando…",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=t_mut,
        )
        self._status_lbl.grid(row=0, column=1, padx=0, pady=10, sticky="w")

        right_bar = ctk.CTkFrame(top, fg_color="transparent")
        right_bar.grid(row=0, column=2, padx=12, pady=6, sticky="e")

        ctk.CTkButton(
            right_bar, text="↺ Atualizar", width=90, height=30,
            fg_color="#0f172a", hover_color="#1e293b",
            border_width=1, border_color=sep,
            text_color=t_sec,
            font=ctk.CTkFont(size=11),
            command=self._do_refresh,
        ).pack(side="left", padx=(0, 6))

        ctk.CTkLabel(
            right_bar,
            text="Auto-atualiza a cada 30s",
            font=ctk.CTkFont(size=10),
            text_color=t_mut,
        ).pack(side="left")

        # ── Corpo: lista + painel de ações ───────────────────────────────────
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.grid(row=1, column=0, sticky="nsew", padx=10, pady=8)
        body.grid_columnconfigure(0, weight=1)
        body.grid_rowconfigure(0, weight=1)

        # Header da tabela
        hdr = ctk.CTkFrame(body, fg_color=card_bg, corner_radius=6, height=30)
        hdr.grid(row=0, column=0, sticky="ew", pady=(0, 2))
        hdr.grid_propagate(False)
        for col, (txt, w) in enumerate(
            [("#", 34), ("Nome", 300), ("SteamID", 180), ("Ações", 120)]
        ):
            ctk.CTkLabel(
                hdr, text=txt, width=w,
                font=ctk.CTkFont(size=11, weight="bold"),
                text_color=t_sec, anchor="w",
            ).grid(row=0, column=col, padx=(8 if col == 0 else 4, 0), pady=4, sticky="w")

        # Área rolável de jogadores
        self._scroll = ctk.CTkScrollableFrame(
            body, fg_color="transparent",
            scrollbar_button_color=sep,
            scrollbar_button_hover_color=accent,
        )
        self._scroll.grid(row=1, column=0, sticky="nsew")
        self._scroll.grid_columnconfigure(0, weight=1)
        body.grid_rowconfigure(1, weight=1)

        # Mensagem de placeholder
        self._placeholder = ctk.CTkLabel(
            self._scroll,
            text="Buscando jogadores…",
            font=ctk.CTkFont(size=13),
            text_color=t_mut,
        )
        self._placeholder.grid(row=0, column=0, pady=40)

        # Inicia refresh
        self._do_refresh()

    # ── Refresh ───────────────────────────────────────────────────────────────

    def _do_refresh(self) -> None:
        self._cancel_refresh()
        self._status_lbl.configure(text="Atualizando…")
        threading.Thread(target=self._fetch_worker, daemon=True).start()
        self._refresh_id = self.after(_AUTO_REFRESH_MS, self._do_refresh)

    def _cancel_refresh(self) -> None:
        if self._refresh_id:
            try:
                self.after_cancel(self._refresh_id)
            except Exception:
                pass
            self._refresh_id = None

    def _fetch_worker(self) -> None:
        srv = self._srv
        host = srv.server_ip or "127.0.0.1"
        try:
            rc = RconClient(host, srv.rcon_port, srv.admin_password)
            rc.connect()
            ok, resp = rc.send_command_safe("listplayers")
            rc.disconnect()
            if ok:
                players = _parse_listplayers(resp or "")
                self.after(0, lambda p=players: self._render(p))
            else:
                self.after(0, lambda: self._set_status(f"Erro RCON: {resp}", error=True))
        except Exception as exc:
            self.after(0, lambda e=exc: self._set_status(str(e), error=True))

    def _render(self, players: list[_Player]) -> None:
        if not self.winfo_exists():
            return
        th = get_theme("tek")
        t_sec = th.get("text_secondary", "#94a3b8")
        t_mut = th.get("text_muted", "#475569")
        sep   = th.get("separator", "#1e293b")
        card  = th["card_bg"]
        accent = th["accent"]

        # Destroi linhas antigas
        for widget in self._scroll.winfo_children():
            widget.destroy()

        self._players = players
        n = len(players)
        self._count_lbl.configure(text=f"{n} jogador{'es' if n != 1 else ''} online")
        self._set_status(time.strftime("Atualizado às %H:%M:%S"))

        if not players:
            ctk.CTkLabel(
                self._scroll,
                text="Nenhum jogador conectado.",
                font=ctk.CTkFont(size=13),
                text_color=t_mut,
            ).grid(row=0, column=0, pady=40)
            return

        for i, p in enumerate(players):
            row_bg = card if i % 2 == 0 else "#0a1520"
            row_frame = ctk.CTkFrame(
                self._scroll,
                fg_color=row_bg,
                corner_radius=4,
                height=38,
            )
            row_frame.grid(row=i, column=0, sticky="ew", pady=1)
            row_frame.grid_propagate(False)
            row_frame.grid_columnconfigure(1, weight=1)

            # # index
            ctk.CTkLabel(
                row_frame, text=str(p.index), width=34,
                font=ctk.CTkFont(family="Consolas", size=11),
                text_color=t_mut,
            ).grid(row=0, column=0, padx=(8, 4), pady=8, sticky="w")

            # Nome
            ctk.CTkLabel(
                row_frame, text=p.name, anchor="w",
                font=ctk.CTkFont(family="Segoe UI", size=12),
                text_color=t_sec,
            ).grid(row=0, column=1, padx=4, pady=8, sticky="w")

            # SteamID
            ctk.CTkLabel(
                row_frame, text=p.steam_id, width=180, anchor="w",
                font=ctk.CTkFont(family="Consolas", size=10),
                text_color=t_mut,
            ).grid(row=0, column=2, padx=4, pady=8, sticky="w")

            # Botões de ação
            btn_cell = ctk.CTkFrame(row_frame, fg_color="transparent", width=120)
            btn_cell.grid(row=0, column=3, padx=(4, 8), pady=6, sticky="e")

            for label, cmd_fn, color, hover in [
                ("Kick", lambda pl=p: self._action_kick(pl), "#7f1d1d", "#991b1b"),
                ("Ban",  lambda pl=p: self._action_ban(pl),  "#451a03", "#78350f"),
                ("WL",   lambda pl=p: self._action_whitelist(pl), "#0f172a", "#1e293b"),
            ]:
                ctk.CTkButton(
                    btn_cell, text=label, width=36, height=26,
                    fg_color=color, hover_color=hover,
                    text_color="#fca5a5" if "d" in color else t_sec,
                    font=ctk.CTkFont(size=10),
                    corner_radius=4,
                    command=cmd_fn,
                ).pack(side="left", padx=(0, 2))

    # ── Ações por jogador ─────────────────────────────────────────────────────

    def _rcon_cmd(self, cmd: str, on_done: None = None) -> None:
        """Envia um comando RCON em background e recarrega a lista."""
        def _worker():
            srv = self._srv
            host = srv.server_ip or "127.0.0.1"
            try:
                rc = RconClient(host, srv.rcon_port, srv.admin_password)
                rc.connect()
                rc.send_command_safe(cmd)
                rc.disconnect()
            except Exception:
                pass
            self.after(500, self._do_refresh)
        threading.Thread(target=_worker, daemon=True).start()

    def _action_kick(self, p: _Player) -> None:
        self._rcon_cmd(f"kickplayer {p.steam_id}")

    def _action_ban(self, p: _Player) -> None:
        self._rcon_cmd(f"ban {p.name}")

    def _action_whitelist(self, p: _Player) -> None:
        self._rcon_cmd(f"cheat AllowPlayerToJoinNoCheck {p.steam_id}")

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _set_status(self, text: str, error: bool = False) -> None:
        if self.winfo_exists():
            th = get_theme("tek")
            color = "#f87171" if error else th.get("text_muted", "#475569")
            self._status_lbl.configure(text=text, text_color=color)
