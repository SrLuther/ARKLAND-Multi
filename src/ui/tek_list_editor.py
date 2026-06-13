"""Editores de listas agregadas (classe + multiplicador, spawn weight, etc.) — Fase 4."""
from __future__ import annotations

import tkinter as tk

import customtkinter as ctk  # type: ignore[reportMissingImports]

from ..ui_constants import get_theme
from .chunked_builder import run_chunked_list

_ROW_CHUNK = 6


def build_class_multiplier_editor(
    parent: ctk.CTkFrame,
    vars_ref: dict,
    store_key: str,
    title: str,
    hint: str,
    initial: list[dict],
    accent: str,
    *,
    class_label: str = "Classe",
    class_placeholder: str = "PrimalItemResource_Stone_C",
) -> None:
    """Editor de linhas (ClassName, Multiplier) — harvest e dino class mults."""
    theme = get_theme("tek")
    card = ctk.CTkFrame(parent, fg_color=theme.get("card_bg", "#0d1b2a"), corner_radius=8)
    card.pack(fill="x", padx=0, pady=(0, 10))
    card.grid_columnconfigure(0, weight=1)

    ctk.CTkLabel(
        card, text=title, font=ctk.CTkFont(size=12, weight="bold"),
        text_color=accent, anchor="w",
    ).grid(row=0, column=0, padx=12, pady=(10, 2), sticky="w")
    ctk.CTkLabel(
        card, text=hint, font=ctk.CTkFont(size=10),
        text_color=theme["text_secondary"], wraplength=520, justify="left", anchor="w",
    ).grid(row=1, column=0, padx=12, pady=(0, 6), sticky="w")

    rows = ctk.CTkFrame(card, fg_color="transparent")
    rows.grid(row=2, column=0, sticky="ew", padx=12, pady=(0, 4))
    rows.grid_columnconfigure(0, weight=1)

    row_list: list[dict] = []
    vars_ref[store_key] = row_list

    def _add_row(class_name: str = "", mult: float = 1.0) -> None:
        idx = len(row_list)
        rf = ctk.CTkFrame(rows, fg_color="#07101c", corner_radius=4)
        rf.grid(row=idx, column=0, sticky="ew", pady=2)
        rf.grid_columnconfigure(1, weight=1)

        cn_var = tk.StringVar(value=class_name)
        mt_var = tk.StringVar(value=str(mult))
        ctk.CTkLabel(rf, text=class_label, width=52, font=ctk.CTkFont(size=10),
                     text_color="#8899aa").grid(row=0, column=0, padx=(6, 4), pady=4)
        ctk.CTkEntry(rf, textvariable=cn_var, height=28,
                     placeholder_text=class_placeholder,
                     font=ctk.CTkFont(family="Consolas", size=10)).grid(
            row=0, column=1, padx=4, pady=4, sticky="ew")
        ctk.CTkLabel(rf, text="Mult.", width=36, font=ctk.CTkFont(size=10),
                     text_color="#8899aa").grid(row=0, column=2, padx=(4, 2), pady=4)
        ctk.CTkEntry(rf, textvariable=mt_var, width=64, height=28).grid(
            row=0, column=3, padx=(0, 4), pady=4)

        rd = {"class_name_var": cn_var, "mult_var": mt_var, "_frame": rf}
        row_list.append(rd)

        def _remove(r=rd, f=rf) -> None:
            if r in row_list:
                row_list.remove(r)
            f.destroy()
            for i, x in enumerate(row_list):
                x["_frame"].grid(row=i, column=0, sticky="ew", pady=2)

        ctk.CTkButton(rf, text="✕", width=26, height=26,
                      fg_color="#5c1a1a", hover_color="#7c2020",
                      command=_remove).grid(row=0, column=4, padx=(0, 6), pady=4)

    ctk.CTkButton(
        card, text="＋ Adicionar", width=120, height=28,
        fg_color="#0e4a6e", hover_color="#0a3550",
        font=ctk.CTkFont(size=11),
        command=lambda: _add_row(),
    ).grid(row=3, column=0, padx=12, pady=(4, 10), sticky="w")

    if initial:
        run_chunked_list(
            card, initial,
            lambda item: _add_row(item.get("class_name", ""), item.get("multiplier", 1.0)),
            chunk_size=_ROW_CHUNK,
        ).run()


def build_spawn_weight_editor(
    parent: ctk.CTkFrame,
    vars_ref: dict,
    store_key: str,
    title: str,
    hint: str,
    initial: list[dict],
    accent: str,
) -> None:
    theme = get_theme("tek")
    card = ctk.CTkFrame(parent, fg_color=theme.get("card_bg", "#0d1b2a"), corner_radius=8)
    card.pack(fill="x", padx=0, pady=(0, 10))
    card.grid_columnconfigure(0, weight=1)

    ctk.CTkLabel(card, text=title, font=ctk.CTkFont(size=12, weight="bold"),
                 text_color=accent, anchor="w").grid(
        row=0, column=0, padx=12, pady=(10, 2), sticky="w")
    ctk.CTkLabel(card, text=hint, font=ctk.CTkFont(size=10),
                 text_color=theme["text_secondary"], wraplength=520, justify="left",
                 anchor="w").grid(row=1, column=0, padx=12, pady=(0, 6), sticky="w")

    rows = ctk.CTkFrame(card, fg_color="transparent")
    rows.grid(row=2, column=0, sticky="ew", padx=12, pady=(0, 4))
    rows.grid_columnconfigure(0, weight=1)

    row_list: list[dict] = []
    vars_ref[store_key] = row_list

    def _add_row(
        tag: str = "",
        weight: float = 1.0,
        override: bool = False,
        limit: float = 1.0,
    ) -> None:
        idx = len(row_list)
        rf = ctk.CTkFrame(rows, fg_color="#07101c", corner_radius=4)
        rf.grid(row=idx, column=0, sticky="ew", pady=2)
        rf.grid_columnconfigure(1, weight=1)

        tag_v = tk.StringVar(value=tag)
        w_v = tk.StringVar(value=str(weight))
        lim_v = tk.StringVar(value=str(limit))
        ov_v = tk.BooleanVar(value=override)

        ctk.CTkLabel(rf, text="Dino", width=40, font=ctk.CTkFont(size=10),
                     text_color="#8899aa").grid(row=0, column=0, padx=(6, 4), pady=4)
        ctk.CTkEntry(rf, textvariable=tag_v, height=28,
                     placeholder_text="Rex_Character_BP_C",
                     font=ctk.CTkFont(family="Consolas", size=10)).grid(
            row=0, column=1, columnspan=3, padx=4, pady=4, sticky="ew")
        ctk.CTkLabel(rf, text="Peso", width=36, font=ctk.CTkFont(size=10),
                     text_color="#8899aa").grid(row=1, column=0, padx=(6, 4), pady=2)
        ctk.CTkEntry(rf, textvariable=w_v, width=64, height=28).grid(
            row=1, column=1, padx=4, pady=2, sticky="w")
        ctk.CTkCheckBox(rf, text="Override limite %", variable=ov_v,
                        font=ctk.CTkFont(size=10)).grid(row=1, column=2, padx=4, pady=2, sticky="w")
        ctk.CTkLabel(rf, text="Limite %", width=48, font=ctk.CTkFont(size=10),
                     text_color="#8899aa").grid(row=1, column=3, padx=(4, 2), pady=2)
        ctk.CTkEntry(rf, textvariable=lim_v, width=64, height=28).grid(
            row=1, column=4, padx=(0, 4), pady=2)

        rd = {
            "tag_var": tag_v, "weight_var": w_v, "override_var": ov_v,
            "limit_var": lim_v, "_frame": rf,
        }
        row_list.append(rd)

        def _remove(r=rd, f=rf) -> None:
            if r in row_list:
                row_list.remove(r)
            f.destroy()
            for i, x in enumerate(row_list):
                x["_frame"].grid(row=i, column=0, sticky="ew", pady=2)

        ctk.CTkButton(rf, text="✕", width=26, height=26,
                      fg_color="#5c1a1a", hover_color="#7c2020",
                      command=_remove).grid(row=0, column=4, padx=(0, 6), pady=4)

    ctk.CTkButton(card, text="＋ Adicionar", width=120, height=28,
                  fg_color="#0e4a6e", hover_color="#0a3550",
                  font=ctk.CTkFont(size=11), command=lambda: _add_row()).grid(
        row=3, column=0, padx=12, pady=(4, 10), sticky="w")

    if initial:
        run_chunked_list(
            card, initial,
            lambda item: _add_row(
                item.get("dino_name_tag", ""),
                item.get("spawn_weight_multiplier", 1.0),
                item.get("override_spawn_limit_percentage", False),
                item.get("spawn_limit_percentage", 1.0),
            ),
            chunk_size=_ROW_CHUNK,
        ).run()


def build_class_name_list_editor(
    parent: ctk.CTkFrame,
    vars_ref: dict,
    store_key: str,
    title: str,
    hint: str,
    initial: list[str],
    accent: str,
) -> None:
    theme = get_theme("tek")
    card = ctk.CTkFrame(parent, fg_color=theme.get("card_bg", "#0d1b2a"), corner_radius=8)
    card.pack(fill="x", padx=0, pady=(0, 10))
    card.grid_columnconfigure(0, weight=1)

    ctk.CTkLabel(card, text=title, font=ctk.CTkFont(size=12, weight="bold"),
                 text_color=accent, anchor="w").grid(row=0, column=0, padx=12, pady=(10, 2), sticky="w")
    ctk.CTkLabel(card, text=hint, font=ctk.CTkFont(size=10),
                 text_color=theme["text_secondary"], wraplength=520, justify="left",
                 anchor="w").grid(row=1, column=0, padx=12, pady=(0, 6), sticky="w")

    rows = ctk.CTkFrame(card, fg_color="transparent")
    rows.grid(row=2, column=0, sticky="ew", padx=12, pady=(0, 4))
    rows.grid_columnconfigure(0, weight=1)

    row_list: list[dict] = []
    vars_ref[store_key] = row_list

    def _add_row(class_name: str = "") -> None:
        idx = len(row_list)
        rf = ctk.CTkFrame(rows, fg_color="#07101c", corner_radius=4)
        rf.grid(row=idx, column=0, sticky="ew", pady=2)
        rf.grid_columnconfigure(1, weight=1)
        cn_var = tk.StringVar(value=class_name)
        ctk.CTkLabel(rf, text="Classe", width=52, font=ctk.CTkFont(size=10),
                     text_color="#8899aa").grid(row=0, column=0, padx=(6, 4), pady=4)
        ctk.CTkEntry(rf, textvariable=cn_var, height=28,
                     placeholder_text="Rex_Character_BP_C",
                     font=ctk.CTkFont(family="Consolas", size=10)).grid(
            row=0, column=1, padx=4, pady=4, sticky="ew")
        rd = {"class_name_var": cn_var, "_frame": rf}
        row_list.append(rd)

        def _remove(r=rd, f=rf) -> None:
            if r in row_list:
                row_list.remove(r)
            f.destroy()
            for i, x in enumerate(row_list):
                x["_frame"].grid(row=i, column=0, sticky="ew", pady=2)

        ctk.CTkButton(rf, text="✕", width=26, height=26,
                      fg_color="#5c1a1a", hover_color="#7c2020",
                      command=_remove).grid(row=0, column=2, padx=(0, 6), pady=4)

    ctk.CTkButton(card, text="＋ Adicionar", width=120, height=28,
                  fg_color="#0e4a6e", hover_color="#0a3550",
                  font=ctk.CTkFont(size=11), command=lambda: _add_row()).grid(
        row=3, column=0, padx=12, pady=(4, 10), sticky="w")

    if initial:
        run_chunked_list(card, initial, lambda name: _add_row(name), chunk_size=_ROW_CHUNK).run()


def collect_class_multiplier_list(row_list: list[dict]) -> list[dict]:
    out: list[dict] = []
    for rd in row_list:
        cn = rd.get("class_name_var", tk.StringVar()).get().strip()
        if not cn:
            continue
        try:
            mult = float(rd.get("mult_var", tk.StringVar(value="1.0")).get())
        except ValueError:
            mult = 1.0
        out.append({"class_name": cn, "multiplier": mult})
    return out


def collect_spawn_weight_list(row_list: list[dict]) -> list[dict]:
    out: list[dict] = []
    for rd in row_list:
        tag = rd.get("tag_var", tk.StringVar()).get().strip()
        if not tag:
            continue
        try:
            weight = float(rd.get("weight_var", tk.StringVar(value="1.0")).get())
        except ValueError:
            weight = 1.0
        try:
            limit = float(rd.get("limit_var", tk.StringVar(value="1.0")).get())
        except ValueError:
            limit = 1.0
        out.append({
            "dino_name_tag": tag,
            "spawn_weight_multiplier": weight,
            "override_spawn_limit_percentage": bool(
                rd.get("override_var", tk.BooleanVar()).get()
            ),
            "spawn_limit_percentage": limit,
        })
    return out


def collect_class_name_list(row_list: list[dict]) -> list[str]:
    out: list[str] = []
    for rd in row_list:
        cn = rd.get("class_name_var", tk.StringVar()).get().strip()
        if cn:
            out.append(cn)
    return out
