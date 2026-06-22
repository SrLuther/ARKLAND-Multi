from __future__ import annotations

import tkinter as tk
from typing import TYPE_CHECKING

import customtkinter as ctk  # type: ignore[reportMissingImports]

from ..cluster_probe import ClusterTravelTestResult
from ..ui_constants import _BG, _CARD_BG

if TYPE_CHECKING:
    from ..app import ARKServerManagerApp

_ICON = {"ok": "✅", "warn": "⚠️", "error": "❌"}
_COLOR = {"ok": "#5aaa5a", "warn": "#e0a020", "error": "#cc4444"}


def show_cluster_travel_dialog(
    app: "ARKServerManagerApp", result: ClusterTravelTestResult
) -> None:
    dlg = tk.Toplevel(app)
    dlg.title(f"Teste de Viagem — {result.profile_name}")
    dlg.configure(bg=_BG)
    dlg.resizable(True, True)
    dlg.grab_set()
    dlg.minsize(620, 520)

    hdr = ctk.CTkFrame(dlg, fg_color=_CARD_BG, corner_radius=0)
    hdr.pack(fill="x")
    ctk.CTkLabel(
        hdr,
        text=f"🧭  Simulação do terminal de viagem — {result.profile_name}",
        font=ctk.CTkFont(size=14, weight="bold"),
    ).pack(anchor="w", padx=16, pady=10)
    ctk.CTkLabel(
        hdr,
        text=(
            "Verifica se os mapas se enxergam pelo cluster (config, pasta compartilhada e uploads). "
            "No jogo, servidores offline não aparecem na lista — apenas dados já enviados."
        ),
        text_color="gray55",
        font=ctk.CTkFont(size=10),
        justify="left",
        wraplength=580,
    ).pack(anchor="w", padx=16, pady=(0, 10))

    body = ctk.CTkScrollableFrame(dlg, fg_color="transparent", width=600, height=480)
    body.pack(fill="both", expand=True, padx=12, pady=8)

    def _section(title: str) -> None:
        ctk.CTkLabel(
            body, text=title, font=ctk.CTkFont(size=12, weight="bold"), anchor="w",
        ).pack(anchor="w", pady=(12, 4))

    _section("Verificações gerais")
    for status, title, detail in result.checks:
        fr = ctk.CTkFrame(body, fg_color=_CARD_BG, corner_radius=8)
        fr.pack(fill="x", pady=3)
        ctk.CTkLabel(
            fr,
            text=f"{_ICON.get(status, '•')}  {title}",
            text_color=_COLOR.get(status, "gray70"),
            font=ctk.CTkFont(size=11, weight="bold"),
            anchor="w",
        ).pack(anchor="w", padx=12, pady=(8, 0))
        if detail:
            ctk.CTkLabel(
                fr, text=detail, text_color="gray55", font=ctk.CTkFont(size=10),
                anchor="w", justify="left", wraplength=560,
            ).pack(anchor="w", padx=12, pady=(2, 8))

    _section("Mapas vinculados")
    for m in result.members:
        st = "ok" if m.launch_ok and m.path_ok else ("warn" if m.path_ok else "error")
        run_tag = "🟢 online" if m.running else "⚫ offline"
        fr = ctk.CTkFrame(body, fg_color=_CARD_BG, corner_radius=8)
        fr.pack(fill="x", pady=3)
        ctk.CTkLabel(
            fr,
            text=f"{_ICON[st]}  {m.name} — {m.map_label}  :{m.port}  {run_tag}",
            text_color=_COLOR[st],
            font=ctk.CTkFont(size=11, weight="bold"),
            anchor="w",
        ).pack(anchor="w", padx=12, pady=(8, 0))
        lines = [
            f"Cluster ID: {m.launch_cluster_id or '(vazio)'}",
            f"Pasta ARK: {m.cluster_dir or '(vazio)'}",
            f"Pasta compartilhada: {m.shared_dir or '(vazio)'}",
            f"Acesso: {m.path_note}",
        ]
        if m.launch_notes:
            lines.append("Problemas: " + "; ".join(m.launch_notes))
        ctk.CTkLabel(
            fr, text="\n".join(lines), text_color="gray55", font=ctk.CTkFont(size=10),
            anchor="w", justify="left",
        ).pack(anchor="w", padx=12, pady=(2, 8))

    if result.simulated_listings:
        _section("Como apareceria no obelisco / terminal (por mapa)")
        for map_name, lines in result.simulated_listings.items():
            fr = ctk.CTkFrame(body, fg_color=_CARD_BG, corner_radius=8)
            fr.pack(fill="x", pady=3)
            ctk.CTkLabel(
                fr, text=f"📍 {map_name}", font=ctk.CTkFont(size=11, weight="bold"),
                anchor="w",
            ).pack(anchor="w", padx=12, pady=(8, 0))
            ctk.CTkLabel(
                fr, text="\n".join(lines), text_color="gray60", font=ctk.CTkFont(size=10),
                anchor="w", justify="left",
            ).pack(anchor="w", padx=12, pady=(2, 8))

    errors = sum(1 for s, _, _ in result.checks if s == "error")
    errors += sum(1 for m in result.members if not m.launch_ok or not m.path_ok)
    warns = sum(1 for s, _, _ in result.checks if s == "warn")
    warns += sum(1 for e in result.visibility if e.status == "warn")

    if errors:
        summary = f"❌  {errors} problema(s) — corrija antes de confiar na viagem entre mapas."
        summary_color = "#cc4444"
    elif warns:
        summary = f"⚠️  {warns} aviso(s) — revise, mas a configuração pode funcionar."
        summary_color = "#e0a020"
    else:
        summary = "✅  Mapas configurados para se enxergar no cluster."
        summary_color = "#5aaa5a"

    ctk.CTkLabel(
        dlg, text=summary, text_color=summary_color,
        font=ctk.CTkFont(size=12, weight="bold"),
    ).pack(pady=(0, 6))

    ctk.CTkButton(dlg, text="Fechar", width=100, height=32, command=dlg.destroy).pack(
        pady=(0, 12)
    )

    dlg.update_idletasks()
    w, h = dlg.winfo_reqwidth(), dlg.winfo_reqheight()
    x = app.winfo_x() + (app.winfo_width() - w) // 2
    y = app.winfo_y() + (app.winfo_height() - h) // 2
    dlg.geometry(f"+{x}+{y}")
