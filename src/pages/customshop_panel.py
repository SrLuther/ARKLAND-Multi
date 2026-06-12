"""
CustomShop — Painel de administração da loja (catálogo + loja central LAN).

Suporta modo host (esta máquina hospeda arkshop_web) e cliente (aponta para
loja central em outra máquina da rede). Sincroniza config dos plugins em todos
os servidores do app para cross-cluster multi-máquina.
"""
from __future__ import annotations

import json
import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import messagebox
from typing import TYPE_CHECKING, Any, Dict, Optional

import customtkinter as ctk  # type: ignore[reportMissingImports]

from ..shop_integration import (
    default_catalog_path,
    default_customshop_path,
    get_local_ip,
    get_shop_subprocess_env,
    install_customshop_all,
    is_customshop_installed,
    iter_shop_servers,
    resolve_central_url,
    slugify_server_id,
    sync_all_plugins,
    test_shop_connection,
)
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

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_DEFAULT_CONFIG_PATH = _PROJECT_ROOT / "plugin" / "CustomShop" / "configs" / "config.json"


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

    shop_cfg = app.config_manager.config.shop
    cfg_path = default_catalog_path(shop_cfg)
    if not cfg_path.exists() and _DEFAULT_CONFIG_PATH.exists():
        cfg_path = _DEFAULT_CONFIG_PATH
    data: Dict[str, Any] = _load_config(cfg_path)

    # ── Barra de ações no topo ────────────────────────────────────────────
    top_bar = tk.Frame(parent, bg=_BG, height=52)
    top_bar.grid(row=0, column=0, sticky="ew")
    top_bar.grid_propagate(False)

    def _persist_shop_globals() -> None:
        shop_cfg.catalog_config_path = str(cfg_path)
        app.config_manager.save()

    def _do_save() -> None:
        _collect_all()
        _persist_shop_globals()
        if not _save_config(cfg_path, data):
            return
        msgs: list[str] = []
        if shop_cfg.auto_sync_on_save:
            ok, errs = sync_all_plugins(
                app.config_manager, shop_cfg, data, Path(cfg_path),
                asm_cm=getattr(app, "asm_config_manager", None),
            )
            if ok:
                msgs.append(f"{len(ok)} plugin(s) sincronizado(s)")
            if errs:
                msgs.append("Erros: " + "; ".join(errs[:3]))
        try:
            detail = (" — " + ", ".join(msgs)) if msgs else ""
            app._show_toast(f"Catálogo salvo{detail}", "success")  # type: ignore[attr-defined]
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
               hint="Legado MX-E — jogadores usam /shop ou a loja web", width=120)
    _field_row(card_cfg, "Pontos Iniciais",      _sv["StartingPoints"], bg=_INNER,
               hint="Pontos dados a novos jogadores", width=120)
    _field_row(card_cfg, "URL do Website",       _sv["WebsiteUrl"],     bg=_INNER,
               hint="Preenchida automaticamente ao sincronizar plugins", width=260)
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

    grp_header = tk.Frame(card_tp, bg=_INNER)
    grp_header.pack(fill="x", padx=10, pady=(4, 2))
    tk.Label(grp_header, text="Pontos por Grupo:", bg=_INNER, fg="#c8c8e8",
             font=ctk.CTkFont(size=11, weight="bold"), anchor="w").pack(side="left")

    _tp_group_vars: Dict[str, tk.StringVar] = {}
    groups_frame = tk.Frame(card_tp, bg=_INNER)
    groups_frame.pack(fill="x", padx=10, pady=(0, 4))

    def _rebuild_groups_ui() -> None:
        for w in groups_frame.winfo_children():
            w.destroy()
        for g_name, v in list(_tp_group_vars.items()):
            row = tk.Frame(groups_frame, bg=_INNER)
            row.pack(fill="x", pady=2)
            ctk.CTkLabel(row, text=g_name, anchor="w", text_color="gray60",
                         width=120, font=ctk.CTkFont(size=10, weight="bold")).pack(side="left", padx=(4, 8))
            ctk.CTkEntry(row, textvariable=v, width=80, height=24).pack(side="left")
            ctk.CTkButton(row, text="✕", width=26, height=24,
                          fg_color="#6a2020", hover_color="#8a3030",
                          command=lambda k=g_name: _remove_group(k)).pack(side="left", padx=(6, 0))

    def _remove_group(name: str) -> None:
        _tp_group_vars.pop(name, None)
        _rebuild_groups_ui()

    groups = tp.get("Groups", {})
    for g_name, g_val in groups.items():
        amt = g_val.get("Amount", 0) if isinstance(g_val, dict) else 0
        _tp_group_vars[g_name] = tk.StringVar(value=str(amt))
    _rebuild_groups_ui()

    add_row = tk.Frame(card_tp, bg=_INNER)
    add_row.pack(fill="x", padx=10, pady=(2, 8))
    new_grp_name = tk.StringVar()
    new_grp_amt  = tk.StringVar(value="25")
    ctk.CTkEntry(add_row, textvariable=new_grp_name, width=120, height=26,
                 placeholder_text="Nome (ex: VIP)").pack(side="left", padx=(0, 6))
    ctk.CTkEntry(add_row, textvariable=new_grp_amt, width=72, height=26,
                 placeholder_text="Pts").pack(side="left", padx=(0, 6))
    def _add_group() -> None:
        name = new_grp_name.get().strip()
        if not name:
            return
        _tp_group_vars[name] = tk.StringVar(value=new_grp_amt.get() or "25")
        new_grp_name.set("")
        _rebuild_groups_ui()
    ctk.CTkButton(add_row, text="＋ Adicionar Grupo", height=26,
                  fg_color=_GREEN_DARK, hover_color=_GREEN_HOVER,
                  command=_add_group).pack(side="left")

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
        central = resolve_central_url(shop_cfg)
        s_out["WebsiteUrl"] = central
        s_out["WebApiUrl"] = central
        s_out["WebApiKey"] = shop_cfg.api_key or s_out.get("WebApiKey", "")

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
    _build_webstore_tab(
        app, tabs.tab("🌐  Web Store"),
        get_catalog=lambda: data,
        get_catalog_path=lambda: Path(cfg_path),
        collect_catalog=_collect_all,
    )


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
    _head(list_fr, "🛒  Itens")
    scroll_items = ctk.CTkScrollableFrame(list_fr, fg_color=_INNER)
    scroll_items.pack(fill="both", expand=True)
    scroll_items.grid_columnconfigure(0, weight=1)
    ctk.CTkButton(list_fr, text="＋ Novo Item", height=30,
                   fg_color=_GREEN_DARK, hover_color=_GREEN_HOVER,
                   command=lambda: _new_item()).pack(fill="x", padx=8, pady=6)
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


_RCON_CHEATSHEET = [
    ("Broadcast",         "broadcast Mensagem aqui"),
    ("Salvar mundo",      "saveworld"),
    ("Destruir dinos",    "destroywilddinos"),
    ("Ban jogador",       "ban {steamid}"),
    ("Kick jogador",      "kick {steamid}"),
    ("Dar item",          "giveitemtoplayer {steamid} <Blueprint> <Qty> <Qual> <Force>"),
    ("Teleportar",        "teleporttoplayer {steamid}"),
    ("God mode",          "god"),
    ("Infinite stats",    "infinitestats"),
    ("Add XP",            "addexperience {xp} 0 0"),
    ("Dar dino",          "spawnexactdino <Blueprint> {level} 0 0"),
    ("Pontos (add)",      "Shop.AddPoints {steamid} {amount}"),
    ("Pontos (set)",      "Shop.SetPoints {steamid} {amount}"),
    ("Recarregar loja",   "Shop.Reload"),
]


def _build_kit_entry_section(scr: tk.Widget, kit_vars: dict, entries: list) -> None:
    """Constrói a seção de entradas (Dinos/Itens) do kit com adição/remoção dinâmica."""
    _kit_entry_vars: list = kit_vars.setdefault("_entry_vars", [])
    _kit_entry_vars.clear()
    for e in entries:
        _kit_entry_vars.append({k: tk.StringVar(value=str(v)) for k, v in e.items()})

    sep = tk.Frame(scr, bg=_BDR, height=1)
    sep.pack(fill="x", padx=10, pady=6)

    def _rebuild_entries_ui() -> None:
        for w in entries_frame.winfo_children():
            w.destroy()
        for idx, ev in enumerate(_kit_entry_vars):
            card = tk.Frame(entries_frame, bg="#0e0e20", highlightthickness=1,
                            highlightbackground=_BDR)
            card.pack(fill="x", padx=4, pady=3)
            hdr = tk.Frame(card, bg="#0e0e20")
            hdr.pack(fill="x", padx=6, pady=(4, 2))
            type_val = ev.get("Type", tk.StringVar(value="item")).get()
            icon = "🦕" if type_val == "dino" else "📦"
            tk.Label(hdr, text=f"{icon} Entrada {idx + 1}", bg="#0e0e20",
                     fg="#c8c8e8", font=ctk.CTkFont(size=10, weight="bold")).pack(side="left")
            ctk.CTkButton(hdr, text="✕ Remover", width=80, height=20,
                          fg_color="#6a2020", hover_color="#8a3030",
                          command=lambda i=idx: _remove_entry(i)).pack(side="right")
            # Blueprint
            bp_row = tk.Frame(card, bg="#0e0e20")
            bp_row.pack(fill="x", padx=6, pady=1)
            ctk.CTkLabel(bp_row, text="Blueprint:", anchor="w", text_color="gray55",
                         width=90, font=ctk.CTkFont(size=10)).pack(side="left")
            ctk.CTkEntry(bp_row, textvariable=ev.get("Blueprint", tk.StringVar()),
                         height=24, width=320).pack(side="left", padx=(0, 4))
            # Campos específicos por tipo
            if type_val == "dino":
                for lbl, fk in [("Nível", "Level"), ("Sexo (M/F/R)", "Gender")]:
                    r = tk.Frame(card, bg="#0e0e20")
                    r.pack(fill="x", padx=6, pady=1)
                    ctk.CTkLabel(r, text=f"{lbl}:", anchor="w", text_color="gray55",
                                 width=90, font=ctk.CTkFont(size=10)).pack(side="left")
                    ctk.CTkEntry(r, textvariable=ev.get(fk, tk.StringVar()),
                                 height=24, width=100).pack(side="left")
            else:
                for lbl, fk in [("Quantidade", "Quantity"), ("Qualidade", "Quality"),
                                 ("Dano %", "Damage"), ("Durabilidade %", "Durability")]:
                    r = tk.Frame(card, bg="#0e0e20")
                    r.pack(fill="x", padx=6, pady=1)
                    ctk.CTkLabel(r, text=f"{lbl}:", anchor="w", text_color="gray55",
                                 width=90, font=ctk.CTkFont(size=10)).pack(side="left")
                    ctk.CTkEntry(r, textvariable=ev.get(fk, tk.StringVar()),
                                 height=24, width=100).pack(side="left")
                # Force Blueprint checkbox
                fb_var = ev.get("ForceBlueprint", tk.BooleanVar())
                fb_row = tk.Frame(card, bg="#0e0e20")
                fb_row.pack(fill="x", padx=6, pady=(2, 4))
                ctk.CTkCheckBox(fb_row, text="Force Blueprint", variable=fb_var,
                                checkmark_color="white", fg_color=_GREEN_DARK,
                                hover_color=_GREEN_HOVER).pack(anchor="w")

    def _remove_entry(idx: int) -> None:
        _kit_entry_vars.pop(idx)
        _rebuild_entries_ui()

    def _add_entry(entry_type: str) -> None:
        if entry_type == "dino":
            _kit_entry_vars.append({
                "Type": tk.StringVar(value="dino"),
                "Blueprint": tk.StringVar(),
                "Level": tk.StringVar(value="1"),
                "Gender": tk.StringVar(value="R"),
            })
        else:
            _kit_entry_vars.append({
                "Type": tk.StringVar(value="item"),
                "Blueprint": tk.StringVar(),
                "Quantity": tk.StringVar(value="1"),
                "Quality": tk.StringVar(value="0"),
                "Damage": tk.StringVar(value="0"),
                "Durability": tk.StringVar(value="0"),
                "ForceBlueprint": tk.BooleanVar(value=False),
            })
        _rebuild_entries_ui()

    hdr_entries = tk.Frame(scr, bg=_INNER)
    hdr_entries.pack(fill="x", padx=10, pady=(0, 2))
    tk.Label(hdr_entries, text="Itens / Dinos do Kit:", bg=_INNER, fg="#c8c8e8",
             font=ctk.CTkFont(size=11, weight="bold")).pack(side="left")
    ctk.CTkButton(hdr_entries, text="＋ Item", width=70, height=24,
                  fg_color=_GREEN_DARK, hover_color=_GREEN_HOVER,
                  command=lambda: _add_entry("item")).pack(side="right", padx=(4, 0))
    ctk.CTkButton(hdr_entries, text="＋ Dino", width=70, height=24,
                  fg_color="#1a4a6a", hover_color="#1a5a8a",
                  command=lambda: _add_entry("dino")).pack(side="right", padx=(4, 0))

    entries_frame = tk.Frame(scr, bg=_INNER)
    entries_frame.pack(fill="x", padx=4, pady=(0, 6))
    _rebuild_entries_ui()


def _build_kit_edit_form(detail_fr, data: Dict[str, Any], key: str,
                          kit_vars: dict, save_cb, remove_cb) -> None:
    for w in detail_fr.winfo_children():
        w.destroy()
    kit_vars.clear()
    kt = data.get("Kits", {}).get(key, {})
    _head(detail_fr, f"Kit: {key}")

    scr = ctk.CTkScrollableFrame(detail_fr, fg_color=_INNER)
    scr.pack(fill="both", expand=True)

    # ── Campos básicos ────────────────────────────────────────────────────
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

    # ── Seção de entradas (Itens/Dinos) ───────────────────────────────────
    entries_raw = kt.get("Items", [])
    entries: list = []
    for e in entries_raw if isinstance(entries_raw, list) else []:
        if not isinstance(e, dict):
            continue
        entries.append(e)
    _build_kit_entry_section(scr, kit_vars, entries)

    # ── Comandos RCON ─────────────────────────────────────────────────────
    sep2 = tk.Frame(scr, bg=_BDR, height=1)
    sep2.pack(fill="x", padx=10, pady=6)

    cmd_hdr = tk.Frame(scr, bg=_INNER)
    cmd_hdr.pack(fill="x", padx=10, pady=(0, 2))
    tk.Label(cmd_hdr, text="Comandos RCON (1 por linha):", bg=_INNER, fg="#c8c8e8",
             font=ctk.CTkFont(size=11, weight="bold")).pack(side="left")

    # Colinha dropdown
    cheat_var = tk.StringVar(value="— Colinha de comandos —")
    cheat_menu = ctk.CTkOptionMenu(
        cmd_hdr,
        values=["— Colinha de comandos —"] + [f"{n}  →  {c}" for n, c in _RCON_CHEATSHEET],
        variable=cheat_var, width=260, height=24,
        fg_color="#1a1a35", button_color="#252545",
        button_hover_color=_GREEN_DARK,
    )
    cheat_menu.pack(side="right")

    cmds_txt = tk.Text(scr, bg="#0a0a18", fg="gray70", height=5, width=40,
                       insertbackground="white", font=ctk.CTkFont(size=10),
                       relief="flat", padx=6, pady=4)
    cmds_txt.insert("1.0", "\n".join(kt.get("Commands", [])))
    cmds_txt.pack(fill="x", padx=10, pady=(0, 2))

    def _insert_cheat(*_) -> None:
        val = cheat_var.get()
        if "→" not in val:
            return
        cmd = val.split("→", 1)[1].strip()
        cmds_txt.insert("end", ("\n" if cmds_txt.get("1.0", "end").strip() else "") + cmd)
        cheat_var.set("— Colinha de comandos —")

    cheat_var.trace_add("write", _insert_cheat)

    tk.Label(scr, text="Use {steamid} como placeholder do jogador",
             bg=_INNER, fg="gray40", font=ctk.CTkFont(size=9)).pack(anchor="w", padx=10, pady=(0, 8))

    kit_vars["_commands_widget"] = cmds_txt  # type: ignore[assignment]

    # ── Botões ────────────────────────────────────────────────────────────
    btn_row = tk.Frame(detail_fr, bg=_INNER)
    btn_row.pack(fill="x", padx=8, pady=6)
    ctk.CTkButton(btn_row, text="💾 Salvar Kit", fg_color=_GREEN_DARK,
                   hover_color=_GREEN_HOVER,
                   command=lambda k=key, t=cmds_txt: save_cb(k, t)).pack(side="left", padx=(0, 6))
    ctk.CTkButton(btn_row, text="🗑️ Remover", fg_color="#6a2020",
                   hover_color="#8a3030",
                   command=lambda k=key: remove_cb(k)).pack(side="left")


def _kit_dict_from_vars(kit_vars: dict, cmds_widget: tk.Text, _ignored: list) -> dict:
    g = lambda k, d: kit_vars.get(k, tk.StringVar(value=str(d))).get()

    entry_vars: list = kit_vars.get("_entry_vars", [])
    items_out = []
    for ev in entry_vars:
        gv = lambda k, d, ev=ev: ev.get(k, tk.StringVar(value=str(d))).get() if isinstance(ev.get(k), tk.Variable) else str(ev.get(k, d))
        t = gv("Type", "item")
        if t == "dino":
            items_out.append({
                "Type":      "dino",
                "Blueprint": gv("Blueprint", ""),
                "Level":     _safe_int(gv("Level", "1"), 1),
                "Gender":    gv("Gender", "R"),
            })
        else:
            fb = ev.get("ForceBlueprint")
            items_out.append({
                "Type":          "item",
                "Blueprint":     gv("Blueprint", ""),
                "Quantity":      _safe_int(gv("Quantity", "1"), 1),
                "Quality":       _safe_float(gv("Quality", "0"), 0.0),
                "Damage":        _safe_float(gv("Damage", "0"), 0.0),
                "Durability":    _safe_float(gv("Durability", "0"), 0.0),
                "ForceBlueprint": bool(fb.get()) if isinstance(fb, tk.BooleanVar) else False,
            })

    return {
        "Price":         _safe_int(g("price", "0"), 0),
        "Description":   g("description", ""),
        "DefaultAmount": _safe_int(g("default_amt", "999"), 999),
        "Items":         items_out,
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
    _head(list_fr, "🎁  Kits")
    scroll_kits = ctk.CTkScrollableFrame(list_fr, fg_color=_INNER)
    scroll_kits.pack(fill="both", expand=True)
    scroll_kits.grid_columnconfigure(0, weight=1)
    ctk.CTkButton(list_fr, text="＋ Novo Kit", height=30,
                   fg_color=_GREEN_DARK, hover_color=_GREEN_HOVER,
                   command=lambda: _new_kit()).pack(fill="x", padx=8, pady=6)
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
_web_log_fh: Optional[Any] = None  # mantido em módulo para evitar GC prematuro


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


def _ensure_mariadb_running(timeout: int = 45) -> bool:
    """Garante que o MariaDB local está rodando. Retorna True se online ao final."""
    import socket as _socket
    import time as _time

    def _port_up() -> bool:
        try:
            with _socket.create_connection(("127.0.0.1", 3306), timeout=1):
                return True
        except OSError:
            return False

    # Se a porta já está respondendo, não precisa fazer nada
    if _port_up():
        return True

    # Tenta iniciar o servidor MariaDB portable
    try:
        from src.pages.db_local_server import DbLocalServer
        srv = DbLocalServer()
        if not srv.is_installed():
            # MariaDB não está instalado — a loja usará SQLite
            return False
        if not srv.is_running():
            import logging as _log2
            _log2.getLogger(__name__).info("auto_start_webstore: MariaDB não está rodando, iniciando…")
            ok, msg = srv.start()
            _log2.getLogger(__name__).info("auto_start_webstore: MariaDB start → %s (%s)", ok, msg)
    except Exception as exc:
        import logging as _log2
        _log2.getLogger(__name__).warning("auto_start_webstore: não foi possível iniciar MariaDB: %s", exc)
        return False

    # Aguarda a porta subir (até `timeout` segundos)
    deadline = _time.time() + timeout
    while _time.time() < deadline:
        if _port_up():
            return True
        _time.sleep(0.8)
    return False


def auto_start_webstore(app: "ARKServerManagerApp") -> None:
    """Inicia a Web Store automaticamente no boot do app, sem precisar abrir a aba da Loja."""
    global _web_process, _web_log_fh
    if _is_web_running():
        return
    shop = app.config_manager.config.shop
    if (shop.mode or "host") != "host":
        return

    def _launch() -> None:
        global _web_process, _web_log_fh
        # Passo 1: garante que o MariaDB está rodando antes de iniciar o Flask
        _ensure_mariadb_running(timeout=45)
        # Passo 2: inicia o processo Flask
        env = get_shop_subprocess_env(shop)
        _log_path = _WEBSTORE_DIR / "webstore.log"
        _WEBSTORE_DIR.mkdir(parents=True, exist_ok=True)
        _web_log_fh = open(_log_path, "a", encoding="utf-8")  # noqa: WPS515
        _web_process = subprocess.Popen(
            [sys.executable, str(_WEBSTORE_DIR / "app.py")],
            cwd=str(_WEBSTORE_DIR),
            env=env,
            stdout=_web_log_fh,
            stderr=_web_log_fh,
        )

    # Roda em thread para não bloquear a UI durante o wait do MariaDB
    threading.Thread(target=_launch, daemon=True, name="WebStoreLauncher").start()


def _build_webstore_tab(
    app: "ARKServerManagerApp",
    parent: tk.Widget,
    *,
    get_catalog,
    get_catalog_path,
    collect_catalog,
) -> None:
    scr = ctk.CTkScrollableFrame(parent, fg_color=_BG)
    scr.pack(fill="both", expand=True)

    shop = app.config_manager.config.shop
    local_ip = get_local_ip()

    def _save_shop_from_ui() -> None:
        shop.mode = _mode_var.get()
        shop.central_url = _central_url_var.get().strip()
        shop.host_ip = _host_ip_var.get().strip()
        shop.port = _safe_int(_port_var.get(), 5177)
        shop.api_key = _api_key_var.get().strip()
        shop.machine_label = _machine_var.get().strip()
        shop.delivery_mode = _delivery_var.get()
        shop.auto_sync_on_save = _auto_sync_var.get()
        shop.orders_db_url = _orders_url_var.get().strip()
        shop.orders_db_host = _odb_host.get().strip()
        shop.orders_db_port = _safe_int(_odb_port.get(), 3306)
        shop.orders_db_name = _odb_name.get().strip()
        shop.orders_db_user = _odb_user.get().strip()
        shop.orders_db_password = _odb_pass.get()
        app.config_manager.save()

    def _refresh_central_label() -> None:
        _save_shop_from_ui()
        url = resolve_central_url(shop)
        _central_url_lbl.config(text=url)

    # ── Modo Host / Cliente ───────────────────────────────────────────────
    card_mode = tk.Frame(scr, bg=_INNER, highlightthickness=1, highlightbackground=_BDR)
    card_mode.pack(fill="x", padx=12, pady=(12, 6))
    _head(card_mode, "🌐  Loja Central (cross / multi-máquina)")

    tk.Label(
        card_mode,
        text="Host: esta máquina hospeda a loja. Cliente: aponta para a loja de outra máquina na LAN.",
        bg=_INNER, fg="gray50", font=ctk.CTkFont(size=10), wraplength=720, justify="left",
    ).pack(anchor="w", padx=10, pady=(0, 6))

    _mode_var = tk.StringVar(value=shop.mode or "host")
    mode_row = tk.Frame(card_mode, bg=_INNER)
    mode_row.pack(fill="x", padx=10, pady=4)
    ctk.CTkRadioButton(mode_row, text="Host (hospedar loja aqui)", variable=_mode_var,
                       value="host", command=_refresh_central_label).pack(side="left", padx=(0, 16))
    ctk.CTkRadioButton(mode_row, text="Cliente (usar loja remota)", variable=_mode_var,
                       value="client", command=_refresh_central_label).pack(side="left")

    _machine_var = tk.StringVar(value=shop.machine_label or "")
    _field_row(card_mode, "Rótulo desta máquina", _machine_var, bg=_INNER,
               hint="ex: Maquina-A — aparece no registro de servidores", width=200)

    _host_ip_var = tk.StringVar(value=shop.host_ip or local_ip)
    _field_row(card_mode, "IP LAN (host)", _host_ip_var, bg=_INNER,
               hint="IP desta máquina na rede — usado para montar a URL central", width=200)

    _central_url_var = tk.StringVar(value=shop.central_url or "")
    _field_row(card_mode, "URL central (cliente)", _central_url_var, bg=_INNER,
               hint="ex: http://192.168.1.10:5177 — obrigatório no modo cliente", width=320)

    _central_url_lbl = tk.Label(card_mode, bg=_INNER, fg=_GREEN,
                                font=ctk.CTkFont(size=12, weight="bold"), anchor="w")
    _central_url_lbl.pack(anchor="w", padx=10, pady=(4, 8))
    # Valor inicial direto do shop já carregado (não chama _save_shop_from_ui
    # aqui pois as demais variáveis ainda não foram criadas neste ponto)
    _central_url_lbl.config(text=resolve_central_url(shop))

    # ── Status & processo (somente host) ──────────────────────────────────
    card_status = tk.Frame(scr, bg=_INNER, highlightthickness=1, highlightbackground=_BDR)
    card_status.pack(fill="x", padx=12, pady=6)
    _head(card_status, "▶  Processo da Web Store (modo Host)")

    status_row = tk.Frame(card_status, bg=_INNER)
    status_row.pack(fill="x", padx=10, pady=4)
    status_dot = tk.Label(status_row, text="●", bg=_INNER, font=ctk.CTkFont(size=18))
    status_dot.pack(side="left", padx=(0, 8))
    status_lbl = tk.Label(status_row, bg=_INNER, font=ctk.CTkFont(size=12, weight="bold"))
    status_lbl.pack(side="left")
    conn_lbl = tk.Label(card_status, bg=_INNER, fg="gray50", font=ctk.CTkFont(size=10), anchor="w")
    conn_lbl.pack(fill="x", padx=10, pady=(0, 6))

    _port_var = tk.StringVar(value=str(shop.port or 5177))
    port_row = tk.Frame(card_status, bg=_INNER)
    port_row.pack(fill="x", padx=10, pady=2)
    tk.Label(port_row, text="Porta:", bg=_INNER, fg="gray50",
             font=ctk.CTkFont(size=10)).pack(side="left", padx=(0, 8))
    ctk.CTkEntry(port_row, textvariable=_port_var, width=90, height=26).pack(side="left")
    port_var_trace = _port_var.trace_add("write", lambda *_: _refresh_central_label())

    _api_key_var = tk.StringVar(value=shop.api_key or "")
    _field_row(card_status, "API Key (ARKSHOP_API_KEY)", _api_key_var, bg=_INNER, is_pass=True,
               hint="Mesma chave em todos os plugins CustomShop da rede", width=280)

    _delivery_var = tk.StringVar(value=shop.delivery_mode or "plugin")
    del_row = tk.Frame(card_status, bg=_INNER)
    del_row.pack(fill="x", padx=10, pady=4)
    tk.Label(del_row, text="Entrega:", bg=_INNER, fg="gray65",
             font=ctk.CTkFont(size=11, weight="bold")).pack(side="left", padx=(0, 12))
    ctk.CTkRadioButton(del_row, text="Plugin (recomendado)", variable=_delivery_var,
                       value="plugin").pack(side="left", padx=(0, 12))
    ctk.CTkRadioButton(del_row, text="RCON (legado)", variable=_delivery_var,
                       value="rcon").pack(side="left")

    btn_row = tk.Frame(card_status, bg=_INNER)
    btn_row.pack(fill="x", padx=10, pady=(4, 10))

    def _refresh_status() -> None:
        is_host = _mode_var.get() == "host"
        running = _is_web_running() if is_host else False
        _save_shop_from_ui()
        url = resolve_central_url(shop)
        if is_host:
            status_dot.config(fg="#22c55e" if running else "#ef4444")
            status_lbl.config(
                text="Online" if running else "Offline",
                fg="#22c55e" if running else "#ef4444",
            )
            btn_start.configure(state="disabled" if running else "normal")
            btn_stop.configure(state="normal" if running else "disabled")
        else:
            status_dot.config(fg="#3b82f6")
            status_lbl.config(text="Modo cliente", fg="#3b82f6")
            btn_start.configure(state="disabled")
            btn_stop.configure(state="disabled")
        ok, msg = test_shop_connection(url)
        conn_lbl.config(
            text=f"Teste HTTP: {'✓' if ok else '✗'} {msg} — {url}",
            fg="#22c55e" if ok else "#f59e0b",
        )

    def _start_web() -> None:
        global _web_process, _web_log_fh
        if _mode_var.get() != "host" or _is_web_running():
            return
        _save_shop_from_ui()
        collect_catalog()
        env = get_shop_subprocess_env(shop)
        _log_path = _WEBSTORE_DIR / "webstore.log"
        _WEBSTORE_DIR.mkdir(parents=True, exist_ok=True)
        _web_log_fh = open(_log_path, "a", encoding="utf-8")  # noqa: WPS515
        _web_process = subprocess.Popen(
            [sys.executable, str(_WEBSTORE_DIR / "app.py")],
            cwd=str(_WEBSTORE_DIR),
            env=env,
            stdout=_web_log_fh,
            stderr=_web_log_fh,
        )
        parent.after(900, _refresh_status)

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
    btn_stop = ctk.CTkButton(btn_row, text="■  Parar", height=34,
                             fg_color="#7f1d1d", hover_color="#991b1b",
                             command=_stop_web)
    btn_stop.pack(side="left", padx=(0, 8))
    ctk.CTkButton(btn_row, text="🔍  Testar conexão", height=34,
                  fg_color=_BLUE, hover_color=_BLUE_HOVER,
                  command=_refresh_status).pack(side="left")

    # ── Banco de pedidos ──────────────────────────────────────────────────
    card_db = tk.Frame(scr, bg=_INNER, highlightthickness=1, highlightbackground=_BDR)
    card_db.pack(fill="x", padx=12, pady=6)
    _head(card_db, "🗄️  Banco de Pedidos (arkshop_web)")

    # Fallback: pré-preenche com credenciais do DB Manager se os campos estiverem vazios
    from src.shop_integration import _db_manager_prefs
    _dbm = _db_manager_prefs() if not shop.orders_db_user else {}

    _orders_url_var = tk.StringVar(value=shop.orders_db_url or "")
    _field_row(card_db, "URL completa (opcional)", _orders_url_var, bg=_INNER,
               hint="sqlite:///... ou mysql+pymysql://user:pass@host/db", width=360)
    _odb_host = tk.StringVar(value=shop.orders_db_host or _dbm.get("host", "127.0.0.1"))
    _odb_port = tk.StringVar(value=str(shop.orders_db_port or _dbm.get("port", 3306)))
    _odb_name = tk.StringVar(value=shop.orders_db_name or _dbm.get("database", "arkland_shop"))
    _odb_user = tk.StringVar(value=shop.orders_db_user or _dbm.get("user", ""))
    _odb_pass = tk.StringVar(value=shop.orders_db_password or _dbm.get("password", ""))
    _field_row(card_db, "MySQL Host (LAN)", _odb_host, bg=_INNER,
               hint="Use o IP da máquina host para clientes na rede", width=200)
    _field_row(card_db, "Porta", _odb_port, bg=_INNER, width=80)
    _field_row(card_db, "Database", _odb_name, bg=_INNER, width=160)
    _field_row(card_db, "Usuário", _odb_user, bg=_INNER, width=160)
    _field_row(card_db, "Senha", _odb_pass, bg=_INNER, is_pass=True, width=200)

    tk.Label(card_db,
             text="Vazio = SQLite local em plugin/arkshop_web/orders.db (apenas host único).",
             bg=_INNER, fg="gray45", font=ctk.CTkFont(size=9)).pack(anchor="w", padx=10, pady=(0, 6))

    # ── Servidores deste app ──────────────────────────────────────────────
    card_srv = tk.Frame(scr, bg=_INNER, highlightthickness=1, highlightbackground=_BDR)
    card_srv.pack(fill="x", padx=12, pady=6)
    _head(card_srv, "🖧  Servidores ARK deste app")

    tk.Label(
        card_srv,
        text="Cada servidor do cross recebe o mesmo catálogo e aponta para a loja central.",
        bg=_INNER, fg="gray50", font=ctk.CTkFont(size=10),
    ).pack(anchor="w", padx=10, pady=(0, 4))

    srv_frame = tk.Frame(card_srv, bg=_INNER)
    srv_frame.pack(fill="x", padx=10, pady=4)

    _server_rows: list = []

    def _rebuild_server_rows() -> None:
        for w in srv_frame.winfo_children():
            w.destroy()
        _server_rows.clear()
        asm_cm = getattr(app, "asm_config_manager", None)
        for kind, srv in iter_shop_servers(app.config_manager, asm_cm):
            row = tk.Frame(srv_frame, bg="#1a1a30")
            row.pack(fill="x", pady=2)
            sid_var = tk.StringVar(
                value=srv.shop_server_id or slugify_server_id(srv.name, srv.id),
            )
            path_var = tk.StringVar(
                value=srv.customshop_config_path or default_customshop_path(srv.install_dir),
            )
            prefix = "TEK" if kind == "tek" else "PRIM"
            installed = is_customshop_installed(srv.install_dir)
            status = "✓" if installed else "○"
            tk.Label(
                row, text=f"{status} [{prefix}] {srv.name[:22]}", bg="#1a1a30", fg="gray70",
                font=ctk.CTkFont(size=10, weight="bold"), width=168, anchor="w",
            ).pack(side="left", padx=(4, 6))
            ctk.CTkEntry(row, textvariable=sid_var, width=110, height=24,
                         placeholder_text="shop id").pack(side="left", padx=2)
            ctk.CTkEntry(row, textvariable=path_var, width=360, height=24).pack(
                side="left", padx=2)
            _server_rows.append((kind, srv, sid_var, path_var))

    _rebuild_server_rows()

    _auto_sync_var = tk.BooleanVar(value=bool(shop.auto_sync_on_save))

    def _apply_plugins() -> None:
        _save_shop_from_ui()
        collect_catalog()
        for _kind, srv, sid_var, path_var in _server_rows:
            srv.shop_server_id = sid_var.get().strip() or slugify_server_id(srv.name, srv.id)
            srv.customshop_config_path = path_var.get().strip()
        app.config_manager.save_servers()
        asm_cm = getattr(app, "asm_config_manager", None)
        if asm_cm:
            asm_cm.save()
        catalog = get_catalog()
        ok, errs = sync_all_plugins(
            app.config_manager, shop, catalog, get_catalog_path(),
            asm_cm=asm_cm,
        )
        msg = f"{len(ok)} plugin(s) atualizado(s)."
        if errs:
            msg += "\n" + "\n".join(errs[:5])
        try:
            app._show_toast(msg[:120], "success" if ok else "warning")  # type: ignore[attr-defined]
        except AttributeError:
            messagebox.showinfo("Sincronizar", msg)

    def _install_customshop() -> None:
        asm_cm = getattr(app, "asm_config_manager", None)
        targets = iter_shop_servers(app.config_manager, asm_cm)
        if not targets:
            messagebox.showwarning("Instalar", "Nenhum servidor cadastrado no app.")
            return
        if not messagebox.askyesno(
            "Instalar CustomShop",
            f"Copiar CustomShop.dll e dependências para {len(targets)} servidor(es)?\n\n"
            "config.json existente não será sobrescrito.",
        ):
            return
        ok, errs = install_customshop_all(
            app.config_manager, asm_cm, overwrite_dlls=True,
        )
        _rebuild_server_rows()
        msg = f"{len(ok)} servidor(es) com plugin instalado."
        if errs:
            msg += "\n" + "\n".join(errs[:5])
        try:
            app._show_toast(msg[:120], "success" if ok else "warning")  # type: ignore[attr-defined]
        except AttributeError:
            messagebox.showinfo("Instalar CustomShop", msg)

    act_row = tk.Frame(card_srv, bg=_INNER)
    act_row.pack(fill="x", padx=10, pady=(6, 10))
    ctk.CTkButton(act_row, text="📦  Instalar CustomShop",
                  height=34, fg_color="#1a4a6a", hover_color="#1a5a8a",
                  command=_install_customshop).pack(side="left", padx=(0, 10))
    ctk.CTkButton(act_row, text="🔄  Aplicar em todos os plugins",
                  height=34, fg_color=_GREEN_DARK, hover_color=_GREEN_HOVER,
                  command=_apply_plugins).pack(side="left", padx=(0, 10))
    ctk.CTkCheckBox(act_row, text="Auto-sync ao salvar catálogo",
                    variable=_auto_sync_var).pack(side="left")
    ctk.CTkButton(act_row, text="↻  Atualizar lista",
                  height=30, width=120, fg_color="#252540",
                  command=_rebuild_server_rows).pack(side="left", padx=(10, 0))

    # ── Admins SteamID ────────────────────────────────────────────────────
    card_admins = tk.Frame(scr, bg=_INNER, highlightthickness=1, highlightbackground=_BDR)
    card_admins.pack(fill="x", padx=12, pady=6)
    _head(card_admins, "🔑  Admins da Web Store (SteamID64)")

    admins_txt = tk.Text(card_admins, bg="#0a0a18", fg="#c8c8e8", height=6,
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
                                 "IDs inválidos:\n" + "\n".join(invalid))
            return
        _save_admin_ids(ids)
        try:
            app._show_toast("Admins salvos!", "success")  # type: ignore[attr-defined]
        except AttributeError:
            messagebox.showinfo("Salvo", "Admins salvos!")

    ctk.CTkButton(card_admins, text="💾  Salvar Admins",
                  height=32, fg_color=_GREEN_DARK, hover_color=_GREEN_HOVER,
                  command=_save_admins).pack(anchor="w", padx=10, pady=(0, 10))

    # ── Links de Download ──────────────────────────────────────────────────
    card_dl = tk.Frame(scr, bg=_INNER, highlightthickness=1, highlightbackground=_BDR)
    card_dl.pack(fill="x", padx=12, pady=6)
    _head(card_dl, "⬇️  Links de Download (visíveis na web store)")

    tk.Label(card_dl,
             text="Adicione links que aparecem na aba 'Downloads' da loja web para os jogadores.",
             bg=_INNER, fg="gray55", font=ctk.CTkFont(size=10)).pack(anchor="w", padx=10, pady=(0, 4))

    dl_list_frame = tk.Frame(card_dl, bg=_INNER)
    dl_list_frame.pack(fill="x", padx=10, pady=(0, 4))

    _dl_rows: list[dict] = []

    def _load_dl_from_config() -> None:
        """Lê Downloads do config.json."""
        try:
            import json as _json
            p = Path(_CONFIG_PATH())
            if p.exists():
                d = _json.loads(p.read_text(encoding="utf-8-sig"))
                return d.get("Downloads") or []
        except Exception:
            pass
        return []

    def _CONFIG_PATH() -> str:
        from src.shop_integration import default_customshop_path
        return default_customshop_path(None)

    def _refresh_dl_list() -> None:
        for w in dl_list_frame.winfo_children():
            w.destroy()
        for i, dl in enumerate(_dl_rows):
            row = tk.Frame(dl_list_frame, bg=_INNER)
            row.pack(fill="x", pady=2)
            tk.Label(row, text=dl.get("label", "—"), bg=_INNER, fg="#d4c8a8",
                     font=ctk.CTkFont(size=11, weight="bold"), width=20, anchor="w").pack(side="left")
            tk.Label(row, text=dl.get("category", ""), bg=_INNER, fg="gray50",
                     font=ctk.CTkFont(size=10), width=12, anchor="w").pack(side="left")
            tk.Label(row, text=dl.get("url", "")[:50], bg=_INNER, fg="#7a6848",
                     font=ctk.CTkFont(family="Courier New", size=9), anchor="w").pack(side="left", fill="x", expand=True)
            ctk.CTkButton(row, text="✏️", width=28, height=22,
                          fg_color="transparent", hover_color="#1a1508",
                          command=lambda idx=i: _edit_dl(idx)).pack(side="right", padx=2)
            ctk.CTkButton(row, text="🗑", width=28, height=22,
                          fg_color="transparent", hover_color="#2a0a0a",
                          command=lambda idx=i: _del_dl(idx)).pack(side="right")

    def _save_downloads_to_config() -> None:
        try:
            import json as _json
            p = Path(_CONFIG_PATH())
            if not p.exists():
                return
            d = _json.loads(p.read_text(encoding="utf-8-sig"))
            d["Downloads"] = _dl_rows
            p.write_text(_json.dumps(d, indent=2, ensure_ascii=False), encoding="utf-8")
        except Exception as exc:
            messagebox.showerror("Erro", f"Não foi possível salvar downloads:\n{exc}")

    def _del_dl(idx: int) -> None:
        _dl_rows.pop(idx)
        _refresh_dl_list()
        _save_downloads_to_config()

    def _edit_dl(idx: int) -> None:
        _open_dl_dialog(idx)

    def _open_dl_dialog(idx: int | None = None) -> None:
        dl = _dl_rows[idx] if idx is not None else {}
        dlg = tk.Toplevel(card_dl)
        dlg.title("Link de Download")
        dlg.configure(bg="#0d0a06")
        dlg.resizable(False, False)
        dlg.grab_set()

        fields = {}
        for label, key, default, w in [
            ("Label *", "label", "", 280),
            ("URL *", "url", "https://", 360),
            ("Descrição", "description", "", 360),
            ("Categoria", "category", "Geral", 160),
            ("Ícone", "icon", "link", 120),
        ]:
            r = tk.Frame(dlg, bg="#0d0a06")
            r.pack(fill="x", padx=16, pady=4)
            tk.Label(r, text=label, bg="#0d0a06", fg="#d4c8a8",
                     font=ctk.CTkFont(size=11), width=12, anchor="w").pack(side="left")
            var = tk.StringVar(value=dl.get(key, default))
            fields[key] = var
            tk.Entry(r, textvariable=var, bg="#131008", fg="#d4c8a8",
                     insertbackground="white", relief="flat",
                     font=ctk.CTkFont(size=11), width=w // 8).pack(side="left", padx=4)

        tk.Label(dlg, text="Ícones: discord, steam, download, link, youtube, twitch, mod, tool, map, patch, website",
                 bg="#0d0a06", fg="gray45", font=ctk.CTkFont(size=9)).pack(padx=16, pady=(0, 8))

        def _confirm():
            label_v = fields["label"].get().strip()
            url_v   = fields["url"].get().strip()
            if not label_v or not url_v:
                messagebox.showwarning("Atenção", "Label e URL são obrigatórios.", parent=dlg)
                return
            import uuid as _uuid
            entry = {
                "id":          dl.get("id") or _uuid.uuid4().hex[:8],
                "label":       label_v,
                "url":         url_v,
                "description": fields["description"].get().strip(),
                "category":    fields["category"].get().strip() or "Geral",
                "icon":        fields["icon"].get().strip() or "link",
            }
            if idx is not None:
                _dl_rows[idx] = entry
            else:
                _dl_rows.append(entry)
            _refresh_dl_list()
            _save_downloads_to_config()
            dlg.destroy()

        btn_row = tk.Frame(dlg, bg="#0d0a06")
        btn_row.pack(fill="x", padx=16, pady=10)
        ctk.CTkButton(btn_row, text="Salvar", fg_color="#923c0a", hover_color="#e87820",
                      command=_confirm).pack(side="right", padx=4)
        ctk.CTkButton(btn_row, text="Cancelar", fg_color="transparent",
                      command=dlg.destroy).pack(side="right")

    # Carrega downloads do config
    _dl_rows.extend(_load_dl_from_config())
    _refresh_dl_list()

    btn_dl_row = tk.Frame(card_dl, bg=_INNER)
    btn_dl_row.pack(fill="x", padx=10, pady=(4, 10))
    ctk.CTkButton(btn_dl_row, text="➕  Novo Link",
                  height=30, fg_color="#923c0a", hover_color="#e87820",
                  command=lambda: _open_dl_dialog()).pack(side="left")

    _refresh_status()


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
