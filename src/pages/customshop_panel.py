"""
CustomShop — Painel de administração da loja in-game.
Permite configurar Settings, Items, Kits, TimedPoints e Database do plugin
CustomShop (ArkApi) sem editar o JSON manualmente.
Inclui aba Web Store para gerenciar o arkshop_web (status, endereço público,
controle do processo Flask, admins SteamID).
"""
from __future__ import annotations

import json
import socket
import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import messagebox
from typing import TYPE_CHECKING, Any, Dict, Optional

import customtkinter as ctk  # type: ignore[reportMissingImports]

from ..ui_constants import (
    _GREEN, _GREEN_DARK, _GREEN_HOVER,
    _BLUE, _BLUE_HOVER,
    _CARD_BG, _BG,
)

if TYPE_CHECKING:
    from ..app import ARKServerManagerApp

_SEC_BG  = "#0d0d1e"
_HEAD_BG = "#141428"
_INNER   = "#16162a"
_BDR     = "#2a2a45"
_FIELD_BG = "#111128"

_DEFAULT_CONFIG_PATH = Path("arkland/plugin/CustomShop/configs/config.json")


def _load_config(path: Path) -> Dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {
            "Settings": {
                "ShopName": "ARKLAND Shop",
                "UiKey": "F3",
                "StartingPoints": 100,
                "DisableSellButton": True,
                "DisableTradeButton": False,
                "WebsiteUrl": "",
                "DiscordUrl": "",
                "VoteRewards": False,
                "HideBuffIcon": False,
                "OverrideCurrencyIcon": "",
                "UseSteamOverlay": False,
                "OverrideLabels": [],
            },
            "Items": {},
            "Kits": {},
            "TimedPointsReward": {
                "Enabled": True,
                "Interval": 30,
                "StackRewards": True,
                "Groups": {"Default": {"Amount": 25}},
            },
            "Database": {
                "Host": "127.0.0.1",
                "Port": 3306,
                "User": "arkland",
                "Password": "changeme",
                "Database": "arkland_shop",
            },
        }


def _save_config(path: Path, data: Dict[str, Any]) -> bool:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        return True
    except Exception as e:
        messagebox.showerror("Erro ao Salvar", str(e))
        return False


def _head(parent: tk.Widget, text: str, bg: str = _INNER) -> None:
    tk.Label(parent, text=text, bg=bg, fg="#c8c8e8",
             font=ctk.CTkFont(size=12, weight="bold"),
             anchor="w").pack(fill="x", padx=10, pady=(8, 2))
    tk.Frame(parent, bg=_GREEN, height=1).pack(fill="x", padx=10, pady=(0, 6))


def _field_row(parent: tk.Widget, label: str, var: tk.Variable,
               hint: str = "", width: int = 260, bg: str = _INNER,
               is_pass: bool = False) -> None:
    row = tk.Frame(parent, bg=bg)
    row.pack(fill="x", padx=10, pady=2)
    row.columnconfigure(0, weight=1)
    ctk.CTkLabel(row, text=label, anchor="w", text_color="gray65",
                 font=ctk.CTkFont(size=11, weight="bold")).grid(
        row=0, column=0, sticky="w", padx=(0, 8))
    if hint:
        ctk.CTkLabel(row, text=hint, anchor="w", text_color="gray40",
                     font=ctk.CTkFont(size=9)).grid(
            row=1, column=0, sticky="w", padx=(0, 8))
    e = ctk.CTkEntry(row, textvariable=var, width=width, height=26,
                     show="*" if is_pass else "")
    e.grid(row=0, column=1, rowspan=2 if hint else 1, padx=(0, 0), sticky="e")


def _bool_row(parent: tk.Widget, label: str, var: tk.BooleanVar,
              bg: str = _INNER) -> None:
    row = tk.Frame(parent, bg=bg)
    row.pack(fill="x", padx=10, pady=2)
    ctk.CTkCheckBox(row, text=label, variable=var,
                    checkmark_color="white", fg_color=_GREEN_DARK,
                    hover_color=_GREEN_HOVER).pack(anchor="w")


def build_customshop_panel(app: "ARKServerManagerApp", parent: tk.Widget) -> None:
    """Constrói o painel CustomShop dentro de `parent`."""
    parent.grid_rowconfigure(0, weight=0)
    parent.grid_rowconfigure(1, weight=1)
    parent.grid_columnconfigure(0, weight=1)

    cfg_path = _DEFAULT_CONFIG_PATH
    data: Dict[str, Any] = _load_config(cfg_path)

    # ── Barra de ações no topo ────────────────────────────────────────────
    top_bar = tk.Frame(parent, bg=_BG, height=52)
    top_bar.grid(row=0, column=0, sticky="ew")
    top_bar.grid_propagate(False)

    def _do_save() -> None:
        _collect_all()
        if _save_config(cfg_path, data):
            try:
                app._show_toast("CustomShop salvo com sucesso!", "success")  # type: ignore[attr-defined]
            except AttributeError:
                messagebox.showinfo("Salvo", "CustomShop salvo com sucesso!")

    ctk.CTkButton(
        top_bar, text="💾  Salvar config.json",
        height=36, font=ctk.CTkFont(size=13, weight="bold"),
        fg_color=_GREEN_DARK, hover_color=_GREEN_HOVER,
        command=_do_save,
    ).pack(side="left", padx=(16, 0), pady=8)

    ctk.CTkButton(
        top_bar, text="🔄  Recarregar do Disco",
        height=36, width=190, fg_color=_BLUE, hover_color=_BLUE_HOVER,
        command=lambda: _reload(),
    ).pack(side="left", padx=(10, 0), pady=8)

    path_var = tk.StringVar(value=str(cfg_path))
    ctk.CTkLabel(top_bar, text="Arquivo:", text_color="gray50",
                 font=ctk.CTkFont(size=10)).pack(side="left", padx=(20, 4), pady=8)
    ctk.CTkEntry(top_bar, textvariable=path_var, width=340, height=28).pack(
        side="left", pady=8)
    ctk.CTkButton(
        top_bar, text="📂", width=36, height=28,
        fg_color="#252540", hover_color="#1a1a35",
        command=lambda: _browse_path(path_var),
    ).pack(side="left", padx=(4, 0), pady=8)

    # ── Tabs ──────────────────────────────────────────────────────────────
    tabs = ctk.CTkTabview(parent, fg_color=_BG,
                          segmented_button_fg_color="#141428",
                          segmented_button_selected_color=_GREEN_DARK,
                          segmented_button_selected_hover_color=_GREEN_HOVER)
    tabs.grid(row=1, column=0, sticky="nsew", padx=4, pady=4)
    tabs.add("⚙️  Configurações")
    tabs.add("🛒  Itens")
    tabs.add("🎁  Kits")
    tabs.add("⏱️  Pontos Temporais")
    tabs.add("🗄️  Database")
    tabs.add("🌐  Web Store")

    # ── Tab: Configurações ────────────────────────────────────────────────
    t_cfg = ctk.CTkScrollableFrame(tabs.tab("⚙️  Configurações"), fg_color=_BG)
    t_cfg.pack(fill="both", expand=True)
    card_cfg = tk.Frame(t_cfg, bg=_INNER, highlightthickness=1,
                        highlightbackground=_BDR)
    card_cfg.pack(fill="x", padx=12, pady=8)

    _head(card_cfg, "⚙️  Configurações Gerais da Loja")

    s = data.get("Settings", {})
    _sv = {
        "ShopName":             tk.StringVar(value=str(s.get("ShopName", "ARKLAND Shop"))),
        "UiKey":                tk.StringVar(value=str(s.get("UiKey", "F3"))),
        "StartingPoints":       tk.StringVar(value=str(s.get("StartingPoints", 100))),
        "WebsiteUrl":           tk.StringVar(value=str(s.get("WebsiteUrl", ""))),
        "DiscordUrl":           tk.StringVar(value=str(s.get("DiscordUrl", ""))),
        "OverrideCurrencyIcon": tk.StringVar(value=str(s.get("OverrideCurrencyIcon", ""))),
        "DisableSellButton":    tk.BooleanVar(value=bool(s.get("DisableSellButton", True))),
        "DisableTradeButton":   tk.BooleanVar(value=bool(s.get("DisableTradeButton", False))),
        "VoteRewards":          tk.BooleanVar(value=bool(s.get("VoteRewards", False))),
        "HideBuffIcon":         tk.BooleanVar(value=bool(s.get("HideBuffIcon", False))),
        "UseSteamOverlay":      tk.BooleanVar(value=bool(s.get("UseSteamOverlay", False))),
    }

    _field_row(card_cfg, "Nome da Loja",        _sv["ShopName"],       bg=_INNER)
    _field_row(card_cfg, "Tecla do Menu (UiKey)", _sv["UiKey"],         bg=_INNER,
               hint="Tecla que abre a loja no jogo (ex: F3)", width=120)
    _field_row(card_cfg, "Pontos Iniciais",      _sv["StartingPoints"], bg=_INNER,
               hint="Pontos dados a novos jogadores", width=120)
    _field_row(card_cfg, "URL do Website",       _sv["WebsiteUrl"],     bg=_INNER)
    _field_row(card_cfg, "URL do Discord",       _sv["DiscordUrl"],     bg=_INNER)
    _field_row(card_cfg, "Ícone de Moeda (Override)", _sv["OverrideCurrencyIcon"], bg=_INNER,
               hint="Blueprint path do ícone customizado (vazio = padrão)")

    tk.Frame(card_cfg, bg=_BDR, height=1).pack(fill="x", padx=10, pady=6)
    _bool_row(card_cfg, "Desativar Botão de Vender",  _sv["DisableSellButton"],  bg=_INNER)
    _bool_row(card_cfg, "Desativar Botão de Trocar",  _sv["DisableTradeButton"], bg=_INNER)
    _bool_row(card_cfg, "Recompensas de Votação",     _sv["VoteRewards"],        bg=_INNER)
    _bool_row(card_cfg, "Ocultar Ícone de Buff",      _sv["HideBuffIcon"],       bg=_INNER)
    _bool_row(card_cfg, "Usar Steam Overlay",         _sv["UseSteamOverlay"],    bg=_INNER)

    # ── Tab: Itens ────────────────────────────────────────────────────────
    t_items = tabs.tab("🛒  Itens")
    _build_items_tab(app, t_items, data)

    # ── Tab: Kits ─────────────────────────────────────────────────────────
    t_kits = tabs.tab("🎁  Kits")
    _build_kits_tab(app, t_kits, data)

    # ── Tab: Pontos Temporais ─────────────────────────────────────────────
    t_timed = ctk.CTkScrollableFrame(tabs.tab("⏱️  Pontos Temporais"), fg_color=_BG)
    t_timed.pack(fill="both", expand=True)
    card_tp = tk.Frame(t_timed, bg=_INNER, highlightthickness=1,
                       highlightbackground=_BDR)
    card_tp.pack(fill="x", padx=12, pady=8)
    _head(card_tp, "⏱️  TimedPointsReward")

    tp = data.get("TimedPointsReward", {})
    _tpv = {
        "Enabled":      tk.BooleanVar(value=bool(tp.get("Enabled", True))),
        "Interval":     tk.StringVar(value=str(tp.get("Interval", 30))),
        "StackRewards": tk.BooleanVar(value=bool(tp.get("StackRewards", True))),
    }
    _bool_row(card_tp, "Ativado", _tpv["Enabled"], bg=_INNER)
    _field_row(card_tp, "Intervalo (minutos)", _tpv["Interval"], bg=_INNER,
               hint="Minutos entre cada distribuição de pontos", width=100)
    _bool_row(card_tp, "Acumular Recompensas (Stack)", _tpv["StackRewards"], bg=_INNER)

    tk.Frame(card_tp, bg=_BDR, height=1).pack(fill="x", padx=10, pady=6)
    tk.Label(card_tp, text="Pontos por Grupo:", bg=_INNER, fg="#c8c8e8",
             font=ctk.CTkFont(size=11, weight="bold"),
             anchor="w").pack(fill="x", padx=10, pady=(4, 2))

    _tp_group_vars: Dict[str, tk.StringVar] = {}
    groups_frame = tk.Frame(card_tp, bg=_INNER)
    groups_frame.pack(fill="x", padx=10, pady=(0, 8))
    groups_frame.columnconfigure(0, weight=1)
    groups_frame.columnconfigure(1, weight=1)

    groups = tp.get("Groups", {})
    for i, (g_name, g_val) in enumerate(groups.items()):
        amt = g_val.get("Amount", 0) if isinstance(g_val, dict) else 0
        v = tk.StringVar(value=str(amt))
        _tp_group_vars[g_name] = v
        col = i % 2
        row = i // 2
        cell = tk.Frame(groups_frame, bg=_INNER)
        cell.grid(row=row, column=col, padx=4, pady=2, sticky="ew")
        ctk.CTkLabel(cell, text=g_name, anchor="w", text_color="gray60",
                     font=ctk.CTkFont(size=10, weight="bold")).pack(side="left", padx=(4, 8))
        ctk.CTkEntry(cell, textvariable=v, width=72, height=24).pack(side="right", padx=4)

    # ── Tab: Database ─────────────────────────────────────────────────────
    t_db = ctk.CTkScrollableFrame(tabs.tab("🗄️  Database"), fg_color=_BG)
    t_db.pack(fill="both", expand=True)
    card_db = tk.Frame(t_db, bg=_INNER, highlightthickness=1,
                       highlightbackground=_BDR)
    card_db.pack(fill="x", padx=12, pady=8)
    _head(card_db, "🗄️  Conexão MySQL (CustomShop)")

    db = data.get("Database", {})
    _dbv = {
        "Host":     tk.StringVar(value=str(db.get("Host", "127.0.0.1"))),
        "Port":     tk.StringVar(value=str(db.get("Port", 3306))),
        "User":     tk.StringVar(value=str(db.get("User", "arkland"))),
        "Password": tk.StringVar(value=str(db.get("Password", ""))),
        "Database": tk.StringVar(value=str(db.get("Database", "arkland_shop"))),
    }
    _field_row(card_db, "Host",     _dbv["Host"],     bg=_INNER)
    _field_row(card_db, "Porta",    _dbv["Port"],     bg=_INNER, width=100)
    _field_row(card_db, "Usuário",  _dbv["User"],     bg=_INNER)
    _field_row(card_db, "Senha",    _dbv["Password"], bg=_INNER, is_pass=True)
    _field_row(card_db, "Database", _dbv["Database"], bg=_INNER)

    tk.Label(card_db,
             text="⚠️  Requer libmysql.dll na mesma pasta do CustomShop.dll",
             bg=_INNER, fg="#ffaa44",
             font=ctk.CTkFont(size=10)).pack(anchor="w", padx=10, pady=(6, 8))

    # ── Funções de suporte ────────────────────────────────────────────────
    def _collect_all() -> None:
        s_out = data.setdefault("Settings", {})
        s_out["ShopName"]             = _sv["ShopName"].get()
        s_out["UiKey"]                = _sv["UiKey"].get()
        s_out["StartingPoints"]       = _safe_int(_sv["StartingPoints"].get(), 100)
        s_out["WebsiteUrl"]           = _sv["WebsiteUrl"].get()
        s_out["DiscordUrl"]           = _sv["DiscordUrl"].get()
        s_out["OverrideCurrencyIcon"] = _sv["OverrideCurrencyIcon"].get()
        s_out["DisableSellButton"]    = _sv["DisableSellButton"].get()
        s_out["DisableTradeButton"]   = _sv["DisableTradeButton"].get()
        s_out["VoteRewards"]          = _sv["VoteRewards"].get()
        s_out["HideBuffIcon"]         = _sv["HideBuffIcon"].get()
        s_out["UseSteamOverlay"]      = _sv["UseSteamOverlay"].get()

        tp_out = data.setdefault("TimedPointsReward", {})
        tp_out["Enabled"]      = _tpv["Enabled"].get()
        tp_out["Interval"]     = _safe_int(_tpv["Interval"].get(), 30)
        tp_out["StackRewards"] = _tpv["StackRewards"].get()
        grps = tp_out.setdefault("Groups", {})
        for g_name, gv in _tp_group_vars.items():
            grps[g_name] = {"Amount": _safe_int(gv.get(), 25)}

        db_out = data.setdefault("Database", {})
        db_out["Host"]     = _dbv["Host"].get()
        db_out["Port"]     = _safe_int(_dbv["Port"].get(), 3306)
        db_out["User"]     = _dbv["User"].get()
        db_out["Password"] = _dbv["Password"].get()
        db_out["Database"] = _dbv["Database"].get()

    def _reload() -> None:
        nonlocal data
        new_path = Path(path_var.get())
        data = _load_config(new_path)
        messagebox.showinfo("Recarregado", f"Config recarregada de:\n{new_path}")

    def _browse_path(var: tk.StringVar) -> None:
        from tkinter import filedialog
        p = filedialog.askopenfilename(
            title="Selecionar config.json",
            filetypes=[("JSON", "*.json"), ("Todos", "*.*")],
        )
        if p:
            var.set(p)

    # ── Tab: Web Store ────────────────────────────────────────────────────
    _build_webstore_tab(app, tabs.tab("🌐  Web Store"))


def _refresh_items_list(scroll_items, data: Dict[str, Any], on_select) -> None:
    for w in scroll_items.winfo_children():
        w.destroy()
    items = data.get("Items", {})
    for idx, (key, itm) in enumerate(items.items()):
        bg = "#1a1a30" if idx % 2 == 0 else _INNER
        row = tk.Frame(scroll_items, bg=bg, cursor="hand2")
        row.grid(row=idx, column=0, sticky="ew", padx=2, pady=1)
        row.columnconfigure(0, weight=1)
        tk.Label(row, text=f"  {itm.get('Description', key)[:32]}", bg=bg, fg="gray70",
                  font=ctk.CTkFont(size=10, weight="bold"), anchor="w").grid(row=0, column=0, sticky="w")
        tk.Label(row, text=f"{itm.get('Price', 0)} pts  ", bg=bg, fg=_GREEN,
                  font=ctk.CTkFont(size=10)).grid(row=0, column=1)
        row.bind("<Button-1>", lambda e, k=key: on_select(k))
        for ch in row.winfo_children():
            ch.bind("<Button-1>", lambda e, k=key: on_select(k))


def _item_dict_from_vars(item_vars: Dict[str, tk.Variable]) -> dict:
    g = lambda k, d: item_vars.get(k, tk.StringVar(value=str(d))).get()
    return {
        "Type":           g("type", "item"),
        "Price":          _safe_int(g("price", "0"), 0),
        "Description":    g("description", ""),
        "Blueprint":      g("blueprint", ""),
        "Quantity":       _safe_int(g("quantity", "1"), 1),
        "Quality":        _safe_float(g("quality", "0"), 0.0),
        "ForceBlueprint": bool(item_vars.get("force_blueprint", tk.BooleanVar()).get()),
    }


def _build_item_edit_form(detail_fr, data: Dict[str, Any], key: str,
                           item_vars: dict, save_cb, remove_cb) -> None:
    for w in detail_fr.winfo_children():
        w.destroy()
    item_vars.clear()
    itm = data.get("Items", {}).get(key, {})
    _head(detail_fr, f"Editar: {key}")
    scr = ctk.CTkScrollableFrame(detail_fr, fg_color=_INNER)
    scr.pack(fill="both", expand=True)
    for lbl, dflt, fk in [
        ("ID (chave)", key,                          "id"),
        ("Tipo",       itm.get("Type", "item"),      "type"),
        ("Preço (pts)",str(itm.get("Price", 0)),     "price"),
        ("Descrição",  itm.get("Description", ""),   "description"),
        ("Blueprint",  itm.get("Blueprint", ""),     "blueprint"),
        ("Quantidade", str(itm.get("Quantity", 1)),  "quantity"),
        ("Qualidade",  str(itm.get("Quality", 0)),   "quality"),
    ]:
        v = tk.StringVar(value=dflt)
        item_vars[fk] = v
        _field_row(scr, lbl, v, bg=_INNER)
    fbv = tk.BooleanVar(value=bool(itm.get("ForceBlueprint", False)))
    item_vars["force_blueprint"] = fbv  # type: ignore[assignment]
    _bool_row(scr, "Force Blueprint", fbv, bg=_INNER)
    btn_row = tk.Frame(detail_fr, bg=_INNER)
    btn_row.pack(fill="x", padx=8, pady=6)
    ctk.CTkButton(btn_row, text="💾 Salvar Item", fg_color=_GREEN_DARK,
                   hover_color=_GREEN_HOVER,
                   command=lambda k=key: save_cb(k)).pack(side="left", padx=(0, 6))
    ctk.CTkButton(btn_row, text="🗑️ Remover", fg_color="#6a2020",
                   hover_color="#8a3030",
                   command=lambda k=key: remove_cb(k)).pack(side="left")


def _build_items_tab(app: "ARKServerManagerApp", parent: tk.Widget,
                     data: Dict[str, Any]) -> None:
    frame = tk.Frame(parent, bg=_BG)
    frame.pack(fill="both", expand=True)
    frame.columnconfigure(0, weight=1)
    frame.columnconfigure(1, weight=2)
    frame.rowconfigure(0, weight=1)
    list_fr = tk.Frame(frame, bg=_INNER, highlightthickness=1, highlightbackground=_BDR)
    list_fr.grid(row=0, column=0, padx=(8, 4), pady=8, sticky="nsew")
    list_fr.rowconfigure(1, weight=1)
    list_fr.columnconfigure(0, weight=1)
    _head(list_fr, "🛒  Itens")
    scroll_items = ctk.CTkScrollableFrame(list_fr, fg_color=_INNER)
    scroll_items.grid(row=1, column=0, sticky="nsew")
    scroll_items.grid_columnconfigure(0, weight=1)
    ctk.CTkButton(list_fr, text="＋ Novo Item", height=30,
                   fg_color=_GREEN_DARK, hover_color=_GREEN_HOVER,
                   command=lambda: _new_item()).grid(row=2, column=0, padx=8, pady=6, sticky="ew")
    detail_fr = tk.Frame(frame, bg=_INNER, highlightthickness=1, highlightbackground=_BDR)
    detail_fr.grid(row=0, column=1, padx=(4, 8), pady=8, sticky="nsew")
    _item_vars: Dict[str, tk.Variable] = {}
    def _select_item(key: str) -> None:
        _build_item_edit_form(detail_fr, data, key, _item_vars, _save_item, _remove_item)
    def _save_item(old_key: str) -> None:
        new_key = _item_vars.get("id", tk.StringVar()).get().strip()
        if not new_key:
            messagebox.showerror("Erro", "ID do item não pode ser vazio."); return
        items = data.setdefault("Items", {})
        if old_key != new_key and old_key in items: del items[old_key]
        items[new_key] = _item_dict_from_vars(_item_vars)
        _refresh_items_list(scroll_items, data, _select_item)
    def _remove_item(key: str) -> None:
        if not messagebox.askyesno("Remover", f"Remover item '{key}'?"): return
        data.get("Items", {}).pop(key, None)
        for w in detail_fr.winfo_children(): w.destroy()
        _refresh_items_list(scroll_items, data, _select_item)
    def _new_item() -> None:
        key = f"novo_item_{len(data.get('Items', {}))}"
        data.setdefault("Items", {})[key] = {
            "Type": "item", "Price": 10, "Description": key,
            "Blueprint": "", "Quantity": 1, "Quality": 0.0, "ForceBlueprint": False,
        }
        _refresh_items_list(scroll_items, data, _select_item)
        _select_item(key)
    _refresh_items_list(scroll_items, data, _select_item)


def _refresh_kits_list(scroll_kits, data: Dict[str, Any], on_select) -> None:
    for w in scroll_kits.winfo_children():
        w.destroy()
    kits = data.get("Kits", {})
    for idx, (key, kt) in enumerate(kits.items()):
        bg = "#1a1a30" if idx % 2 == 0 else _INNER
        row = tk.Frame(scroll_kits, bg=bg, cursor="hand2")
        row.grid(row=idx, column=0, sticky="ew", padx=2, pady=1)
        row.columnconfigure(0, weight=1)
        tk.Label(row, text=f"  {kt.get('Description', key)[:32]}", bg=bg, fg="gray70",
                  font=ctk.CTkFont(size=10, weight="bold"), anchor="w").grid(row=0, column=0, sticky="w")
        tk.Label(row, text=f"{kt.get('Price', 0)} pts  ", bg=bg, fg=_GREEN,
                  font=ctk.CTkFont(size=10)).grid(row=0, column=1)
        row.bind("<Button-1>", lambda e, k=key: on_select(k))
        for ch in row.winfo_children():
            ch.bind("<Button-1>", lambda e, k=key: on_select(k))


def _build_kit_edit_form(detail_fr, data: Dict[str, Any], key: str,
                          kit_vars: dict, save_cb, remove_cb) -> None:
    for w in detail_fr.winfo_children():
        w.destroy()
    kit_vars.clear()
    kt = data.get("Kits", {}).get(key, {})
    _head(detail_fr, f"Kit: {key}")
    scr = ctk.CTkScrollableFrame(detail_fr, fg_color=_INNER)
    scr.pack(fill="both", expand=True)
    for lbl, fk, dflt in [
        ("ID (chave)",  "id",          key),
        ("Preço (pts)", "price",       str(kt.get("Price", 0))),
        ("Descrição",   "description", kt.get("Description", "")),
        ("Permissões",  "permissions", kt.get("Permissions", "")),
        ("Usos Padrão", "default_amt", str(kt.get("DefaultAmount", 999))),
    ]:
        v = tk.StringVar(value=dflt)
        kit_vars[fk] = v
        _field_row(scr, lbl, v, bg=_INNER)
    tk.Label(scr, text="Comandos (1 por linha):",
              bg=_INNER, fg="gray60", font=ctk.CTkFont(size=10)).pack(anchor="w", padx=10, pady=(6, 2))
    cmds_txt = tk.Text(scr, bg="#0a0a18", fg="gray70", height=4, width=40,
                        insertbackground="white", font=ctk.CTkFont(size=10))
    cmds_txt.insert("1.0", "\n".join(kt.get("Commands", [])))
    cmds_txt.pack(fill="x", padx=10, pady=(0, 6))
    kit_vars["_commands_widget"] = cmds_txt  # type: ignore[assignment]
    btn_row = tk.Frame(detail_fr, bg=_INNER)
    btn_row.pack(fill="x", padx=8, pady=6)
    ctk.CTkButton(btn_row, text="💾 Salvar Kit", fg_color=_GREEN_DARK,
                   hover_color=_GREEN_HOVER,
                   command=lambda k=key, t=cmds_txt: save_cb(k, t)).pack(side="left", padx=(0, 6))
    ctk.CTkButton(btn_row, text="🗑️ Remover", fg_color="#6a2020",
                   hover_color="#8a3030",
                   command=lambda k=key: remove_cb(k)).pack(side="left")


def _kit_dict_from_vars(kit_vars: dict, cmds_widget: tk.Text, existing_items: list) -> dict:
    g = lambda k, d: kit_vars.get(k, tk.StringVar(value=str(d))).get()
    return {
        "Price":         _safe_int(g("price", "0"), 0),
        "Description":   g("description", ""),
        "DefaultAmount": _safe_int(g("default_amt", "999"), 999),
        "Items":         existing_items,
        "Commands":      [ln for ln in cmds_widget.get("1.0", "end").splitlines() if ln.strip()],
    }


def _build_kits_tab(app: "ARKServerManagerApp", parent: tk.Widget,
                    data: Dict[str, Any]) -> None:
    frame = tk.Frame(parent, bg=_BG)
    frame.pack(fill="both", expand=True)
    frame.columnconfigure(0, weight=1)
    frame.columnconfigure(1, weight=2)
    frame.rowconfigure(0, weight=1)
    list_fr = tk.Frame(frame, bg=_INNER, highlightthickness=1, highlightbackground=_BDR)
    list_fr.grid(row=0, column=0, padx=(8, 4), pady=8, sticky="nsew")
    list_fr.rowconfigure(1, weight=1)
    list_fr.columnconfigure(0, weight=1)
    _head(list_fr, "🎁  Kits")
    scroll_kits = ctk.CTkScrollableFrame(list_fr, fg_color=_INNER)
    scroll_kits.grid(row=1, column=0, sticky="nsew")
    scroll_kits.grid_columnconfigure(0, weight=1)
    ctk.CTkButton(list_fr, text="＋ Novo Kit", height=30,
                   fg_color=_GREEN_DARK, hover_color=_GREEN_HOVER,
                   command=lambda: _new_kit()).grid(row=2, column=0, padx=8, pady=6, sticky="ew")
    detail_fr = tk.Frame(frame, bg=_INNER, highlightthickness=1, highlightbackground=_BDR)
    detail_fr.grid(row=0, column=1, padx=(4, 8), pady=8, sticky="nsew")
    _kit_vars: Dict[str, tk.Variable] = {}
    def _select(key: str) -> None:
        _build_kit_edit_form(detail_fr, data, key, _kit_vars, _save_kit, _remove)
    def _save_kit(old_key: str, cmds_widget: tk.Text) -> None:
        new_key = _kit_vars.get("id", tk.StringVar()).get().strip()
        if not new_key:
            messagebox.showerror("Erro", "ID do kit não pode ser vazio."); return
        kits = data.setdefault("Kits", {})
        if old_key != new_key and old_key in kits: del kits[old_key]
        perms = _kit_vars.get("permissions", tk.StringVar()).get().strip()
        kits[new_key] = _kit_dict_from_vars(_kit_vars, cmds_widget, kits.get(new_key, {}).get("Items", []))
        if perms: kits[new_key]["Permissions"] = perms
        _refresh_kits_list(scroll_kits, data, _select)
    def _remove(key: str) -> None:
        if not messagebox.askyesno("Remover", f"Remover kit '{key}'?"): return
        data.get("Kits", {}).pop(key, None)
        for w in detail_fr.winfo_children(): w.destroy()
        _refresh_kits_list(scroll_kits, data, _select)
    def _new_kit() -> None:
        key = f"novo_kit_{len(data.get('Kits', {}))}"
        data.setdefault("Kits", {})[key] = {
            "Price": 0, "Description": key, "DefaultAmount": 1, "Items": [], "Commands": [],
        }
        _refresh_kits_list(scroll_kits, data, _select)
        _select(key)
    _refresh_kits_list(scroll_kits, data, _select)


_WEBSTORE_DIR = Path(__file__).parent.parent.parent / "plugin" / "arkshop_web"
_ADMIN_FILE   = _WEBSTORE_DIR / "admin_steamids.json"
_SETTINGS_FILE = _WEBSTORE_DIR / "settings.json"

_web_process: Optional[subprocess.Popen] = None  # type: ignore[type-arg]


def _get_local_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def _load_webstore_settings() -> Dict[str, Any]:
    try:
        return json.loads(_SETTINGS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_webstore_settings(data: Dict[str, Any]) -> None:
    _SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    _SETTINGS_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _load_admin_ids() -> list[str]:
    try:
        raw = json.loads(_ADMIN_FILE.read_text(encoding="utf-8"))
        return raw if isinstance(raw, list) else []
    except Exception:
        return []


def _save_admin_ids(ids: list[str]) -> None:
    _ADMIN_FILE.parent.mkdir(parents=True, exist_ok=True)
    _ADMIN_FILE.write_text(json.dumps(sorted(set(ids)), indent=2, ensure_ascii=False), encoding="utf-8")


def _is_web_running() -> bool:
    global _web_process
    return _web_process is not None and _web_process.poll() is None


def _build_webstore_tab(app: "ARKServerManagerApp", parent: tk.Widget) -> None:
    scr = ctk.CTkScrollableFrame(parent, fg_color=_BG)
    scr.pack(fill="both", expand=True)

    ws = _load_webstore_settings()
    port = int(ws.get("port", ws.get("rcon_port", 5177)) if "port" in ws else 5177)

    # ── Card: Status & Controle ───────────────────────────────────────────
    card_status = tk.Frame(scr, bg=_INNER, highlightthickness=1, highlightbackground=_BDR)
    card_status.pack(fill="x", padx=12, pady=(12, 6))
    _head(card_status, "🌐  Status da Web Store")

    status_row = tk.Frame(card_status, bg=_INNER)
    status_row.pack(fill="x", padx=10, pady=(4, 0))

    status_dot = tk.Label(status_row, text="●", bg=_INNER,
                          font=ctk.CTkFont(size=18))
    status_dot.pack(side="left", padx=(0, 8))

    status_lbl = tk.Label(status_row, bg=_INNER,
                          font=ctk.CTkFont(size=12, weight="bold"))
    status_lbl.pack(side="left")

    def _refresh_status() -> None:
        running = _is_web_running()
        status_dot.config(fg="#22c55e" if running else "#ef4444")
        status_lbl.config(
            text="Online" if running else "Offline",
            fg="#22c55e" if running else "#ef4444",
        )
        btn_start.configure(state="disabled" if running else "normal")
        btn_stop.configure(state="normal" if running else "disabled")
        addr_lbl.config(fg="#94a3b8" if not running else _GREEN)

    # ── Endereço público ──────────────────────────────────────────────────
    addr_frame = tk.Frame(card_status, bg=_INNER)
    addr_frame.pack(fill="x", padx=10, pady=6)

    local_ip = _get_local_ip()
    port_var = tk.StringVar(value=str(port))
    public_url = f"http://{local_ip}:{port}"

    tk.Label(addr_frame, text="Endereço de acesso (rede local):",
             bg=_INNER, fg="gray50", font=ctk.CTkFont(size=10)).pack(anchor="w")

    url_row = tk.Frame(addr_frame, bg=_INNER)
    url_row.pack(fill="x", pady=(2, 0))

    addr_lbl = tk.Label(url_row, text=public_url,
                        bg=_INNER, fg="#94a3b8",
                        font=ctk.CTkFont(size=13, weight="bold"),
                        cursor="hand2")
    addr_lbl.pack(side="left")

    def _copy_url() -> None:
        url = f"http://{local_ip}:{port_var.get()}"
        parent.clipboard_clear()
        parent.clipboard_append(url)
        try:
            app._show_toast("URL copiada!", "success")  # type: ignore[attr-defined]
        except AttributeError:
            pass

    ctk.CTkButton(url_row, text="📋 Copiar", width=80, height=24,
                  fg_color="#252540", hover_color="#1a1a35",
                  command=_copy_url).pack(side="left", padx=(10, 0))

    # ── Porta ─────────────────────────────────────────────────────────────
    port_row = tk.Frame(card_status, bg=_INNER)
    port_row.pack(fill="x", padx=10, pady=(0, 6))
    tk.Label(port_row, text="Porta:", bg=_INNER, fg="gray50",
             font=ctk.CTkFont(size=10)).pack(side="left", padx=(0, 8))
    ctk.CTkEntry(port_row, textvariable=port_var, width=90, height=26).pack(side="left")
    tk.Label(port_row,
             text="  ⚠  Alterar porta requer reiniciar a Web Store",
             bg=_INNER, fg="#f59e0b", font=ctk.CTkFont(size=9)).pack(side="left", padx=(8, 0))

    def _update_addr_label(*_) -> None:
        addr_lbl.config(text=f"http://{local_ip}:{port_var.get()}")

    port_var.trace_add("write", _update_addr_label)

    # ── Botões Start / Stop ───────────────────────────────────────────────
    btn_row = tk.Frame(card_status, bg=_INNER)
    btn_row.pack(fill="x", padx=10, pady=(0, 10))

    def _start_web() -> None:
        global _web_process
        if _is_web_running():
            return
        web_dir = _WEBSTORE_DIR
        py_exe = sys.executable
        env = {**__import__("os").environ, "PORT": port_var.get()}

        # Salvar porta nas settings
        s = _load_webstore_settings()
        s["port"] = _safe_int(port_var.get(), 5177)
        _save_webstore_settings(s)

        _web_process = subprocess.Popen(
            [py_exe, str(web_dir / "app.py")],
            cwd=str(web_dir),
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        parent.after(800, _refresh_status)

    def _stop_web() -> None:
        global _web_process
        if _web_process and _web_process.poll() is None:
            _web_process.terminate()
            try:
                _web_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                _web_process.kill()
        _web_process = None
        parent.after(300, _refresh_status)

    btn_start = ctk.CTkButton(btn_row, text="▶  Iniciar Web Store",
                               height=34, fg_color=_GREEN_DARK, hover_color=_GREEN_HOVER,
                               command=_start_web)
    btn_start.pack(side="left", padx=(0, 8))

    btn_stop = ctk.CTkButton(btn_row, text="■  Parar",
                              height=34, fg_color="#7f1d1d", hover_color="#991b1b",
                              command=_stop_web)
    btn_stop.pack(side="left")

    _refresh_status()

    # ── Card: Admins SteamID ──────────────────────────────────────────────
    card_admins = tk.Frame(scr, bg=_INNER, highlightthickness=1, highlightbackground=_BDR)
    card_admins.pack(fill="x", padx=12, pady=6)
    _head(card_admins, "🔑  Admins da Web Store (SteamID64)")

    tk.Label(card_admins,
             text="SteamIDs com acesso total à interface admin da loja web (um por linha):",
             bg=_INNER, fg="gray50", font=ctk.CTkFont(size=10)).pack(anchor="w", padx=10, pady=(0, 4))

    admins_txt = tk.Text(card_admins, bg="#0a0a18", fg="#c8c8e8", height=8,
                         insertbackground="white", font=ctk.CTkFont(size=11),
                         relief="flat", padx=8, pady=6)
    admins_txt.pack(fill="x", padx=10, pady=(0, 6))
    admins_txt.insert("1.0", "\n".join(_load_admin_ids()))

    def _save_admins() -> None:
        raw = admins_txt.get("1.0", "end").strip()
        ids = [ln.strip() for ln in raw.splitlines() if ln.strip()]
        invalid = [i for i in ids if not (i.startswith("7656119") and len(i) == 17 and i.isdigit())]
        if invalid:
            messagebox.showerror("SteamID inválido",
                                 "Os seguintes IDs são inválidos:\n" + "\n".join(invalid))
            return
        _save_admin_ids(ids)
        try:
            app._show_toast("Admins salvos!", "success")  # type: ignore[attr-defined]
        except AttributeError:
            messagebox.showinfo("Salvo", "Admins salvos com sucesso!")

    ctk.CTkButton(card_admins, text="💾  Salvar Admins",
                  height=32, fg_color=_GREEN_DARK, hover_color=_GREEN_HOVER,
                  command=_save_admins).pack(anchor="w", padx=10, pady=(0, 10))

    # ── Card: Configurações da Web Store ──────────────────────────────────
    card_ws = tk.Frame(scr, bg=_INNER, highlightthickness=1, highlightbackground=_BDR)
    card_ws.pack(fill="x", padx=12, pady=6)
    _head(card_ws, "⚙️  Configurações do Servidor Web")

    ws_reloaded = _load_webstore_settings()
    _wsv = {
        "rcon_host":     tk.StringVar(value=str(ws_reloaded.get("rcon_host", "127.0.0.1"))),
        "rcon_port":     tk.StringVar(value=str(ws_reloaded.get("rcon_port", 27020))),
        "rcon_password": tk.StringVar(value=str(ws_reloaded.get("rcon_password", ""))),
        "server_id":     tk.StringVar(value=str(ws_reloaded.get("server_id", "default"))),
    }
    _field_row(card_ws, "Host RCON",    _wsv["rcon_host"],     bg=_INNER)
    _field_row(card_ws, "Porta RCON",   _wsv["rcon_port"],     bg=_INNER, width=100)
    _field_row(card_ws, "Senha RCON",   _wsv["rcon_password"], bg=_INNER, is_pass=True)
    _field_row(card_ws, "Server ID",    _wsv["server_id"],     bg=_INNER,
               hint="Identificador deste servidor (ex: pvp1, pve2)")

    def _save_ws_settings() -> None:
        s = _load_webstore_settings()
        s["rcon_host"]     = _wsv["rcon_host"].get().strip()
        s["rcon_port"]     = _safe_int(_wsv["rcon_port"].get(), 27020)
        s["rcon_password"] = _wsv["rcon_password"].get()
        s["server_id"]     = _wsv["server_id"].get().strip() or "default"
        _save_webstore_settings(s)
        try:
            app._show_toast("Configurações salvas!", "success")  # type: ignore[attr-defined]
        except AttributeError:
            messagebox.showinfo("Salvo", "Configurações salvas!")

    ctk.CTkButton(card_ws, text="💾  Salvar Configurações",
                  height=32, fg_color=_GREEN_DARK, hover_color=_GREEN_HOVER,
                  command=_save_ws_settings).pack(anchor="w", padx=10, pady=(4, 10))


def _safe_int(v: str, default: int = 0) -> int:
    try:
        return int(float(v))
    except (ValueError, TypeError):
        return default


def _safe_float(v: str, default: float = 0.0) -> float:
    try:
        return float(v)
    except (ValueError, TypeError):
        return default
