from __future__ import annotations

import os
from typing import TYPE_CHECKING, Dict

import customtkinter as ctk  # type: ignore[reportMissingImports]

from ..ui_constants import _GREEN, _GREEN_DARK, _GREEN_HOVER, _SIDEBAR_BG, _resource_path
from ..version import APP_VERSION

if TYPE_CHECKING:
    from ..app import ARKServerManagerApp


def build_sidebar(app: "ARKServerManagerApp") -> None:
    sb = ctk.CTkFrame(app, width=210, corner_radius=0, fg_color=_SIDEBAR_BG)
    sb.grid(row=0, column=0, sticky="nsew")
    sb.grid_propagate(False)
    sb.grid_columnconfigure(0, weight=1)
    app._sidebar = sb

    # Logo
    try:
        from PIL import Image  # type: ignore[reportMissingImports]
        _logo = Image.open(_resource_path(os.path.join("ig", "ArkLandBR.png")))
        app._logo_img = ctk.CTkImage(light_image=_logo, dark_image=_logo, size=(120, 120))
        ctk.CTkLabel(sb, image=app._logo_img, text="").grid(
            row=0, column=0, padx=20, pady=(16, 0))
    except Exception:
        ctk.CTkLabel(
            sb, text="⚡ ARKLAND",
            font=ctk.CTkFont(size=20, weight="bold"), text_color=_GREEN,
        ).grid(row=0, column=0, padx=20, pady=(24, 0))

    ctk.CTkLabel(sb, text="Server Manager",
                 font=ctk.CTkFont(size=12), text_color="#88d4a0").grid(row=1, column=0)
    ver_clock = ctk.CTkFrame(sb, fg_color="transparent")
    ver_clock.grid(row=2, column=0, pady=(0, 6))
    ctk.CTkLabel(ver_clock, text=f"v{APP_VERSION}",
                 font=ctk.CTkFont(size=10), text_color="gray50").pack()
    app._sidebar_clock_lbl = ctk.CTkLabel(
        ver_clock, text="",
        font=ctk.CTkFont(size=11), text_color="#88d4a0",
    )
    app._sidebar_clock_lbl.pack(pady=(2, 0))
    app.after(100, app._sidebar_clock_tick)

    ctk.CTkFrame(sb, height=1, fg_color="#2a2a44").grid(
        row=3, column=0, sticky="ew", padx=12, pady=4)

    app._nav_buttons: Dict[str, ctk.CTkButton] = {}
    for i, (label, key) in enumerate([
        ("🏠  Dashboard",      "dashboard"),
        ("🔄  Sincronização",  "sync"),
        ("⚡  BUFFs",          "buffs"),
        ("📊  Desempenho",     "desempenho"),
        ("🔗  Clusters",       "clusters"),
        ("🖥️  Remoto",         "remoto"),
        ("⚙️  Configurações",  "config"),
        ("ℹ️  Sobre",           "sobre"),
    ]):
        btn = ctk.CTkButton(
            sb, text=label, anchor="w", width=185, height=38,
            fg_color="transparent", text_color="#d8d8e8",
            hover_color="#252540", corner_radius=8,
            command=lambda k=key: app._show_frame(k),
        )
        btn.grid(row=i + 4, column=0, padx=12, pady=2, sticky="ew")
        app._nav_buttons[key] = btn

    ctk.CTkFrame(sb, height=1, fg_color="#2a2a44").grid(
        row=12, column=0, sticky="ew", padx=12, pady=8)

    # Título "Servidores" + botão "+"
    srv_hdr = ctk.CTkFrame(sb, fg_color="transparent")
    srv_hdr.grid(row=13, column=0, padx=12, pady=(0, 4), sticky="ew")
    srv_hdr.grid_columnconfigure(0, weight=1)
    ctk.CTkLabel(srv_hdr, text="SERVIDORES",
                 font=ctk.CTkFont(size=10, weight="bold"), text_color="gray50").grid(
        row=0, column=0, sticky="w", padx=4)
    ctk.CTkButton(
        srv_hdr, text="＋", width=28, height=24,
        fg_color=_GREEN_DARK, hover_color=_GREEN_HOVER,
        font=ctk.CTkFont(size=14, weight="bold"),
        command=app._dialog_add_server,
    ).grid(row=0, column=1)

    # Frame scrollable para lista de servidores
    app._servers_list_sb = ctk.CTkScrollableFrame(
        sb, fg_color="transparent", height=280)
    app._servers_list_sb.grid(row=14, column=0, sticky="ew", padx=6)
    app._servers_list_sb.grid_columnconfigure(0, weight=1)

    app._sidebar_update_lbl = ctk.CTkLabel(
        sb, text="", font=ctk.CTkFont(size=10), text_color="#ffaa44", wraplength=180)
    app._sidebar_update_lbl.grid(row=15, column=0, padx=10, pady=4)

    # ── Botões de Perfil ──────────────────────────────────────────────────
    ctk.CTkFrame(sb, height=1, fg_color="#2a2a44").grid(
        row=16, column=0, sticky="ew", padx=12, pady=(2, 4))
    ctk.CTkLabel(sb, text="PERFIL",
                 font=ctk.CTkFont(size=10, weight="bold"), text_color="gray50").grid(
        row=17, column=0, padx=16, pady=(0, 2), sticky="w")
    profile_fr = ctk.CTkFrame(sb, fg_color="transparent")
    profile_fr.grid(row=18, column=0, padx=10, pady=(0, 10), sticky="ew")
    profile_fr.grid_columnconfigure(0, weight=1)
    profile_fr.grid_columnconfigure(1, weight=1)
    ctk.CTkButton(
        profile_fr, text="💾 Exportar", height=28,
        fg_color="#252540", hover_color="#1a1a35",
        font=ctk.CTkFont(size=11),
        command=app._export_profile,
    ).grid(row=0, column=0, padx=(0, 2), sticky="ew")
    ctk.CTkButton(
        profile_fr, text="📂 Importar", height=28,
        fg_color="#252540", hover_color="#1a1a35",
        font=ctk.CTkFont(size=11),
        command=app._import_profile,
    ).grid(row=0, column=1, padx=(2, 0), sticky="ew")

