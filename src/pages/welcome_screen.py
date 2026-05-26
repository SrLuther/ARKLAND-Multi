"""Tela inicial de seleção de modo — PRIMITIVO ou TEK.

Exibida ao iniciar o app, antes da UI principal ser construída.
"""
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

import customtkinter as ctk  # type: ignore[reportMissingImports]

if TYPE_CHECKING:
    from ..app import ARKServerManagerApp

_BG       = "#090d14"
_TEXT     = "#c8d8e0"
_TEXT_DIM = "#3a5060"

# PRIMITIVO
_ACCENT_P = "#4CAF50"
_HOVER_P  = "#2E7D32"
_CARD_P   = "#0b1510"
_BORDER_P = "#1a3a1e"

# TEK
_ACCENT_T = "#00BCD4"
_HOVER_T  = "#00838F"
_CARD_T   = "#080f1c"
_BORDER_T = "#0a2a36"

_DIAS  = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"]
_MESES = [
    "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
    "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro",
]


def build_welcome_screen(app: "ARKServerManagerApp") -> None:
    """Constrói a tela de boas-vindas que cobre toda a janela."""
    frame = ctk.CTkFrame(app, corner_radius=0, fg_color=_BG)
    frame.grid(row=0, column=0, columnspan=2, sticky="nsew")
    frame.grid_columnconfigure(0, weight=1)
    frame.grid_rowconfigure(0, weight=1)   # espaço topo
    frame.grid_rowconfigure(1, weight=0)   # logo
    frame.grid_rowconfigure(2, weight=0)   # clock
    frame.grid_rowconfigure(3, weight=0)   # prompt
    frame.grid_rowconfigure(4, weight=2)   # cards
    frame.grid_rowconfigure(5, weight=0)   # update
    frame.grid_rowconfigure(6, weight=0)   # versão
    frame.grid_rowconfigure(7, weight=1)   # espaço rodapé
    app._welcome_frame = frame

    # ── Logo / Título ─────────────────────────────────────────────────────────
    logo_f = ctk.CTkFrame(frame, fg_color="transparent")
    logo_f.grid(row=1, column=0, pady=(0, 20))

    ctk.CTkLabel(logo_f, text="ARKLAND",
                 font=ctk.CTkFont(size=48, weight="bold"),
                 text_color=_TEXT).pack()
    ctk.CTkLabel(logo_f, text="Server Manager",
                 font=ctk.CTkFont(size=15),
                 text_color=_TEXT_DIM).pack()

    # ── Relógio ───────────────────────────────────────────────────────────────
    clock_f = ctk.CTkFrame(frame, fg_color="transparent")
    clock_f.grid(row=2, column=0, pady=(0, 30))

    date_lbl = ctk.CTkLabel(clock_f, text="",
                             font=ctk.CTkFont(size=12),
                             text_color=_TEXT_DIM)
    date_lbl.pack()
    time_lbl = ctk.CTkLabel(clock_f, text="",
                             font=ctk.CTkFont(size=32, weight="bold"),
                             text_color="#6aa8b8")
    time_lbl.pack()

    def _tick() -> None:
        if not frame.winfo_exists():
            return
        now = datetime.now()
        d = f"{_DIAS[now.weekday()]}, {now.day} de {_MESES[now.month - 1]} de {now.year}"
        try:
            date_lbl.configure(text=d)
            time_lbl.configure(text=now.strftime("%H:%M:%S"))
            frame.after(1000, _tick)
        except Exception:
            pass

    _tick()

    # ── Subtítulo ─────────────────────────────────────────────────────────────
    ctk.CTkLabel(frame,
                 text="Selecione o tipo de gerenciamento de servidor:",
                 font=ctk.CTkFont(size=13),
                 text_color="#3a5060").grid(row=3, column=0, pady=(0, 24))

    # ── Cards de modo ─────────────────────────────────────────────────────────
    cards_host = ctk.CTkFrame(frame, fg_color="transparent")
    cards_host.grid(row=4, column=0, sticky="n")
    cards_host.grid_columnconfigure((0, 1), weight=1)

    _mode_card(
        app, cards_host, col=0,
        title="PRIMITIVO",
        icon="🌿",
        subtitle="ARK: Survival Evolved — Modo Simplificado",
        accent=_ACCENT_P,
        hover=_HOVER_P,
        card_bg=_CARD_P,
        border=_BORDER_P,
        desc=[
            "Sistema próprio do ARKLAND",
            "Configuração rápida e direta",
            "GameUserSettings.ini + Game.ini",
            "Clusters e sincronização multi-servidor",
        ],
        mode="primitive",
    )

    _mode_card(
        app, cards_host, col=1,
        title="TEK",
        icon="⚡",
        subtitle="ARK: Survival Evolved — Compatível com ASM",
        accent=_ACCENT_T,
        hover=_HOVER_T,
        card_bg=_CARD_T,
        border=_BORDER_T,
        desc=[
            "Motor fiel ao ArkServerManager (ASM)",
            "300+ parâmetros de ServerProfile",
            "INI gerado via mapeamento declarativo",
            "Perfis completos por servidor",
        ],
        mode="tek",
    )

    # ── Verificação de atualização ──────────────────────────────────────────
    upd_row = ctk.CTkFrame(frame, fg_color="transparent")
    upd_row.grid(row=5, column=0, pady=(18, 0))

    app._welcome_update_status = ctk.CTkLabel(
        upd_row, text="● Não verificado",
        font=ctk.CTkFont(size=11), text_color="#3a5060")
    app._welcome_update_status.pack(side="right", padx=(12, 0))

    def _do_welcome_check() -> None:
        url = app.config_manager.config.update_url
        if not url:
            app._welcome_update_status.configure(
                text="● URL não configurada", text_color="#ff6666")
            return
        app._welcome_update_btn.configure(state="disabled", text="🔍  Verificando...")
        app._welcome_update_status.configure(text="Verificando...", text_color="#aaaaaa")
        app.update_checker.check_async(
            url,
            on_result=lambda info: app.after(0, lambda: _welcome_update_result(info))
        )

    def _welcome_update_result(info) -> None:  # type: ignore[type-arg]
        if not frame.winfo_exists():
            return
        try:
            from ..version import APP_VERSION as _VER  # noqa: PLC0415
            app._welcome_update_btn.configure(state="normal", text="🔍  Verificar Atualização")
            if info is None:
                app._welcome_update_status.configure(
                    text="❌  Falha ao verificar", text_color="#ff6666")
            elif info.is_newer_than(_VER):
                app._welcome_update_status.configure(
                    text=f"🔔  v{info.version} disponível!", text_color="#ffaa44")
            else:
                app._welcome_update_status.configure(
                    text="✅  Versão mais recente", text_color="#4CAF50")
        except Exception:
            pass

    app._welcome_update_btn = ctk.CTkButton(
        upd_row, text="🔍  Verificar Atualização",
        width=185, height=30,
        fg_color="#111b24", hover_color="#1c2d3d",
        text_color="#6aa8b8", border_width=1, border_color="#0a2a36",
        font=ctk.CTkFont(size=11),
        command=_do_welcome_check,
    )
    app._welcome_update_btn.pack(side="left")

    # ── Versão ────────────────────────────────────────────────────────────────
    from ..version import APP_VERSION  # noqa: PLC0415
    ctk.CTkLabel(frame, text=f"v{APP_VERSION}",
                 font=ctk.CTkFont(size=10),
                 text_color="#1e2e38").grid(row=6, column=0, pady=(8, 0))


def _mode_card(
    app: "ARKServerManagerApp",
    parent,
    col: int,
    title: str,
    icon: str,
    subtitle: str,
    accent: str,
    hover: str,
    card_bg: str,
    border: str,
    desc: list,
    mode: str,
) -> None:
    card = ctk.CTkFrame(parent, corner_radius=18,
                        fg_color=card_bg,
                        border_width=2, border_color=border)
    card.grid(row=0, column=col, padx=24, pady=0, sticky="n")
    card.grid_columnconfigure(0, weight=1)

    # Ícone + título
    ctk.CTkLabel(card, text=f"{icon}  {title}",
                 font=ctk.CTkFont(size=34, weight="bold"),
                 text_color=accent).pack(padx=36, pady=(28, 2), anchor="w")

    ctk.CTkLabel(card, text=subtitle,
                 font=ctk.CTkFont(size=12),
                 text_color="#607080").pack(padx=36, pady=(0, 14), anchor="w")

    # Separador
    ctk.CTkFrame(card, height=1, fg_color=border).pack(fill="x", padx=28)

    # Descrição
    for line in desc:
        ctk.CTkLabel(card, text=f"  •  {line}",
                     font=ctk.CTkFont(size=11),
                     text_color="#4a6878",
                     justify="left",
                     anchor="w").pack(padx=28, pady=(8, 0), fill="x")

    # Botão de seleção
    ctk.CTkButton(
        card,
        text=f"▶  Iniciar como {title}",
        height=42,
        corner_radius=10,
        fg_color=accent,
        hover_color=hover,
        text_color="#ffffff",
        font=ctk.CTkFont(size=13, weight="bold"),
        command=lambda m=mode: app._launch_mode(m),
    ).pack(padx=28, pady=(20, 28), fill="x")
