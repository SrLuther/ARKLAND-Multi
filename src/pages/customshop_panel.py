"""
CustomShop — Painel de administração da loja (catálogo + loja central LAN).

Suporta modo host (esta máquina hospeda arkshop_web) e cliente (aponta para
loja central em outra máquina da rede). Sincroniza config dos plugins em todos
os servidores do app para cross-cluster multi-máquina.
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

from ..rcon_client import RconClient
from ..rcon_util import CUSTOMSHOP_RELOAD_COMMANDS, sanitize_rcon_password
from ..shop_catalog_import import import_catalog_from_file
from ..shop_integration import (
    DEFAULT_REMOTE_SHOP_HOST,
    DEFAULT_REMOTE_SHOP_PUBLIC_IP,
    DEFAULT_SHOP_PORT,
    DEFAULT_SHOP_PUBLIC_URL,
    build_webstore_launch,
    check_webstore_firewall_rule,
    collect_groups_from_catalog,
    create_webstore_firewall_rule,
    default_catalog_path,
    default_customshop_path,
    diagnose_shop_connectivity,
    diagnose_webstore_access,
    fetch_public_ip,
    get_local_ip,
    get_shop_subprocess_env,
    install_customshop_all,
    is_customshop_installed,
    iter_shop_servers,
    provision_permission_groups_for_servers,
    read_webstore_log_tail,
    resolve_central_url,
    resolve_plugin_api_url,
    resolve_plugin_website_url,
    resolve_public_shop_url,
    resolve_website_url,
    resolve_webstore_executable,
    shop_access_urls,
    slugify_server_id,
    sync_all_plugins,
    test_shop_connection,
    webstore_data_dir,
    resolve_shop_db_password,
    _is_placeholder_db_password,
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
        data = json.loads(path.read_text(encoding="utf-8"))
        _strip_catalog_db_password(data)
        return data
    except Exception:
        return {
            "Settings": {
                "ShopName": "ARKLAND Donations",
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
                "Enabled": False,
                "Interval": 30,
                "StackRewards": True,
                "Groups": {
                    "Default": {"Amount": 25},
                    "VIPBronze": {"Amount": 20},
                    "VIPPrata": {"Amount": 30},
                    "VIPOuro": {"Amount": 50},
                    "VIPDiamante": {"Amount": 75},
                },
            },
            "Database": {
                "Host": "127.0.0.1",
                "Port": 3306,
                "User": "arkland",
                "Database": "arkland_shop",
            },
        }


def _strip_catalog_db_password(data: Dict[str, Any]) -> None:
    """Senha MySQL não fica no catálogo — só no DB Manager / Web Store."""
    db = data.get("Database")
    if isinstance(db, dict):
        db.pop("Password", None)


def _save_config(path: Path, data: Dict[str, Any]) -> bool:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.loads(json.dumps(data))  # cópia para não mutar o estado da UI
        _strip_catalog_db_password(payload)
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
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

    def _import_catalog() -> None:
        from tkinter import filedialog
        src = filedialog.askopenfilename(
            title="Importar catálogo (ArkShop / CustomShop)",
            filetypes=[("JSON", "*.json"), ("Todos", "*.*")],
            initialfile="loja.json",
        )
        if not src:
            return
        merge = messagebox.askyesno(
            "Modo de importação",
            "Mesclar com o catálogo atual?\n\n"
            "Sim = mantém itens/kits existentes e sobrescreve chaves iguais\n"
            "Não = substitui todo o catálogo (Itens + Kits)",
            parent=parent.winfo_toplevel(),
        )
        import_timed = messagebox.askyesno(
            "Pontos temporais",
            "Importar também TimedPointsReward (grupos VIP, intervalo, etc.)?\n\n"
            "Não altera Database nem credenciais.",
            parent=parent.winfo_toplevel(),
        )
        try:
            result = import_catalog_from_file(
                src, data, merge=merge, import_timed=import_timed,
            )
        except Exception as exc:
            messagebox.showerror("Erro na importação", str(exc), parent=parent.winfo_toplevel())
            return

        if import_timed and _tpv and data.get("TimedPointsReward"):
            tp = data["TimedPointsReward"]
            _tpv["Enabled"].set(bool(tp.get("Enabled", True)))
            _tpv["Interval"].set(str(tp.get("Interval", 30)))
            _tpv["StackRewards"].set(bool(tp.get("StackRewards", True)))
            _tp_group_vars.clear()
            for g_name, g_data in (tp.get("Groups") or {}).items():
                amt = g_data.get("Amount", 25) if isinstance(g_data, dict) else 25
                _tp_group_vars[g_name] = tk.StringVar(value=str(amt))

        _reset_shop_tab("🛒  Itens")
        _reset_shop_tab("🎁  Kits")
        if import_timed:
            _reset_shop_tab("⏱️  Pontos Temporais")
        if tabs.get() in ("🛒  Itens", "🎁  Kits", "⏱️  Pontos Temporais"):
            _rebuild_shop_tab(tabs.get())

        msg = (
            f"Formato: {result['format']}\n"
            f"Arquivo: {result['source']}\n\n"
            f"Itens: {result['items_total']} ({result['items_added']} aplicados"
        )
        if result.get("items_skipped"):
            msg += f", {result['items_skipped']} sobrescritos"
        msg += (
            f")\nKits: {result['kits_total']} ({result['kits_added']} aplicados"
        )
        if result.get("kits_skipped"):
            msg += f", {result['kits_skipped']} sobrescritos"
        msg += ")\n\nUse «Salvar config.json» para gravar no disco."
        messagebox.showinfo("Importação concluída", msg, parent=parent.winfo_toplevel())

    ctk.CTkButton(
        top_bar, text="📥  Importar JSON",
        height=36, width=160, fg_color="#3a3a6a", hover_color="#4a4a8a",
        command=_import_catalog,
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
    tabs.add("💬  Chat Cluster")
    tabs.add("🗄️  Database")
    tabs.add("🌐  Web Store")

    _built_shop_tabs: set[str] = set()

    def _clear_tab_frame(frame: tk.Widget) -> None:
        for w in list(frame.winfo_children()):
            try:
                w.destroy()
            except Exception:
                pass

    def _reset_shop_tab(tab_name: str) -> None:
        """Remove UI antiga para evitar painéis duplicados ao remontar a aba."""
        _built_shop_tabs.discard(tab_name)
        try:
            _clear_tab_frame(tabs.tab(tab_name))
        except Exception:
            pass

    def _rebuild_shop_tab(tab_name: str) -> None:
        _reset_shop_tab(tab_name)
        builder = _TAB_BUILDERS.get(tab_name)
        if not builder:
            return
        _built_shop_tabs.add(tab_name)
        builder()
    _sv: Dict[str, tk.Variable] = {}
    _tpv: Dict[str, tk.Variable] = {}
    _ccv: Dict[str, tk.Variable] = {}
    _dbv: Dict[str, tk.Variable] = {}
    _tp_group_vars: Dict[str, tk.StringVar] = {}

    def _build_tab_cfg() -> None:
        t_cfg = ctk.CTkScrollableFrame(tabs.tab("⚙️  Configurações"), fg_color=_BG)
        t_cfg.pack(fill="both", expand=True)
        card_cfg = tk.Frame(t_cfg, bg=_INNER, highlightthickness=1,
                            highlightbackground=_BDR)
        card_cfg.pack(fill="x", padx=12, pady=8)

        _head(card_cfg, "⚙️  Configurações Gerais da Loja")

        s = data.get("Settings", {})
        _sv.clear()
        _sv.update({
            "ShopName":             tk.StringVar(value=str(s.get("ShopName", "ARKLAND Donations"))),
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
            "MarketCryoRequireMinDays": tk.BooleanVar(
                value=bool(s.get("MarketCryoRequireMinDays", False))),
            "MarketCryoMinDaysRemaining": tk.StringVar(
                value=str(s.get("MarketCryoMinDaysRemaining", 20))),
            "MarketCryoDebug":      tk.BooleanVar(value=bool(s.get("MarketCryoDebug", False))),
        })

        _field_row(card_cfg, "Nome exibido (portal)", _sv["ShopName"],       bg=_INNER)
        _field_row(card_cfg, "Tecla do Menu (UiKey)", _sv["UiKey"],         bg=_INNER,
                   hint="Legado MX-E — jogadores usam /shop ou a loja web", width=120)
        _field_row(card_cfg, "Pontos Iniciais",      _sv["StartingPoints"], bg=_INNER,
                   hint="Pontos dados a novos jogadores", width=120)
        _field_row(card_cfg, "URL do Website",       _sv["WebsiteUrl"],     bg=_INNER,
                   hint="Preenchida ao salvar — usa domínio público configurado na Web Store", width=260)
        _field_row(card_cfg, "URL do Discord",       _sv["DiscordUrl"],     bg=_INNER)
        _field_row(card_cfg, "Ícone de Moeda (Override)", _sv["OverrideCurrencyIcon"], bg=_INNER,
                   hint="Blueprint path do ícone customizado (vazio = padrão)")

        tk.Frame(card_cfg, bg=_BDR, height=1).pack(fill="x", padx=10, pady=6)
        _bool_row(card_cfg, "Desativar Botão de Vender",  _sv["DisableSellButton"],  bg=_INNER)
        _bool_row(card_cfg, "Desativar Botão de Trocar",  _sv["DisableTradeButton"], bg=_INNER)
        _bool_row(card_cfg, "Recompensas de Votação",     _sv["VoteRewards"],        bg=_INNER)
        _bool_row(card_cfg, "Ocultar Ícone de Buff",      _sv["HideBuffIcon"],       bg=_INNER)
        _bool_row(card_cfg, "Usar Steam Overlay",         _sv["UseSteamOverlay"],    bg=_INNER)

        tk.Frame(card_cfg, bg=_BDR, height=1).pack(fill="x", padx=10, pady=6)
        _head(card_cfg, "🛒  Comércio P2P — Cryopod (/enviar)")

        tk.Label(
            card_cfg,
            text=(
                "Controla se o servidor exige timer mínimo na cryopod antes de enviar dino "
                "ao mercado. Desligado = ignora a leitura de dias (útil se a API do ARK "
                "mostrar 0 dias com timer visível no jogo)."
            ),
            bg=_INNER, fg="gray55", font=ctk.CTkFont(size=10),
            anchor="w", justify="left", wraplength=720,
        ).pack(fill="x", padx=10, pady=(0, 6))

        _bool_row(
            card_cfg,
            "Exigir timer mínimo no /enviar e /confirmar",
            _sv["MarketCryoRequireMinDays"],
            bg=_INNER,
        )
        _field_row(
            card_cfg,
            "Dias mínimos de timer",
            _sv["MarketCryoMinDaysRemaining"],
            bg=_INNER,
            hint="Só aplica com a opção acima ligada (padrão: 20)",
            width=80,
        )
        _bool_row(
            card_cfg,
            "Diagnóstico cryopod (log + /enviardebug)",
            _sv["MarketCryoDebug"],
            bg=_INNER,
        )

    def _build_tab_timed() -> None:
        t_timed = ctk.CTkScrollableFrame(tabs.tab("⏱️  Pontos Temporais"), fg_color=_BG)
        t_timed.pack(fill="both", expand=True)
        card_tp = tk.Frame(t_timed, bg=_INNER, highlightthickness=1,
                           highlightbackground=_BDR)
        card_tp.pack(fill="x", padx=12, pady=8)
        _head(card_tp, "⏱️  TimedPointsReward")
        tk.Label(
            card_tp,
            text=(
                "Default: pontos base para quem está conectado no servidor. "
                "Grupos VIP: bônus com licença resgatada na loja web ou permissão no jogo. "
                "Sem pontos offline."
            ),
            bg=_INNER, fg="gray55", font=ctk.CTkFont(size=10),
            anchor="w", justify="left", wraplength=720,
        ).pack(fill="x", padx=10, pady=(0, 6))

        tp = data.get("TimedPointsReward", {})
        _tpv.clear()
        _tpv.update({
            "Enabled":      tk.BooleanVar(value=bool(tp.get("Enabled", True))),
            "Interval":     tk.StringVar(value=str(tp.get("Interval", 30))),
            "StackRewards": tk.BooleanVar(value=bool(tp.get("StackRewards", True))),
        })
        _bool_row(card_tp, "Ativado", _tpv["Enabled"], bg=_INNER)
        _field_row(card_tp, "Intervalo (minutos)", _tpv["Interval"], bg=_INNER,
                   hint="Minutos entre cada distribuição — só jogadores conectados", width=100)
        _bool_row(card_tp, "Acumular Recompensas (Stack)", _tpv["StackRewards"], bg=_INNER)

        tk.Frame(card_tp, bg=_BDR, height=1).pack(fill="x", padx=10, pady=6)

        grp_header = tk.Frame(card_tp, bg=_INNER)
        grp_header.pack(fill="x", padx=10, pady=(4, 2))
        tk.Label(grp_header, text="Pontos por Grupo:", bg=_INNER, fg="#c8c8e8",
                 font=ctk.CTkFont(size=11, weight="bold"), anchor="w").pack(side="left")

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

        _tp_group_vars.clear()
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

    def _build_tab_cross_chat() -> None:
        t_cc = ctk.CTkScrollableFrame(tabs.tab("💬  Chat Cluster"), fg_color=_BG)
        t_cc.pack(fill="both", expand=True)
        card_cc = tk.Frame(t_cc, bg=_INNER, highlightthickness=1,
                           highlightbackground=_BDR)
        card_cc.pack(fill="x", padx=12, pady=8)
        _head(card_cc, "💬  Chat Cluster (Cross-ARK)")
        tk.Label(
            card_cc,
            text=(
                "Jogadores usam /c mensagem no chat do jogo para falar com outros mapas do cluster. "
                "Cada servidor recebe um ServerId único ao sincronizar o plugin (nome do servidor). "
                "Requer MySQL compartilhado e CustomShop.dll nos mapas."
            ),
            bg=_INNER, fg="gray55", font=ctk.CTkFont(size=10),
            anchor="w", justify="left", wraplength=720,
        ).pack(fill="x", padx=10, pady=(0, 8))

        cc = data.get("CrossChat", {})
        _ccv.clear()
        _ccv.update({
            "Enabled":             tk.BooleanVar(value=bool(cc.get("Enabled", True))),
            "Command":             tk.StringVar(value=str(cc.get("Command", "/c"))),
            "PollIntervalSeconds": tk.StringVar(value=str(cc.get("PollIntervalSeconds", 2))),
            "MaxMessageLength":    tk.StringVar(value=str(cc.get("MaxMessageLength", 200))),
            "RateLimitSeconds":    tk.StringVar(value=str(cc.get("RateLimitSeconds", 2))),
            "UseWebApi":           tk.BooleanVar(value=bool(cc.get("UseWebApi", False))),
        })
        _bool_row(card_cc, "Ativado no catálogo", _ccv["Enabled"], bg=_INNER)
        _field_row(card_cc, "Comando", _ccv["Command"], bg=_INNER,
                   hint="Padrão: /c — jogador digita /c olá cluster", width=100)
        _field_row(card_cc, "Intervalo de poll (s)", _ccv["PollIntervalSeconds"], bg=_INNER,
                   hint="Frequência de busca de mensagens de outros mapas", width=80)
        _field_row(card_cc, "Tamanho máx. mensagem", _ccv["MaxMessageLength"], bg=_INNER, width=80)
        _field_row(card_cc, "Rate limit (s)", _ccv["RateLimitSeconds"], bg=_INNER,
                   hint="Segundos entre mensagens por jogador (0 = desligado)", width=80)
        _bool_row(card_cc, "Usar API Web (fallback MySQL)", _ccv["UseWebApi"], bg=_INNER)

        tk.Label(
            card_cc,
            text=(
                "💡 Ative também «Chat cluster entre mapas» na aba Web Store. "
                "Ao salvar, cada servidor recebe ServerId = nome do mapa."
            ),
            bg=_INNER, fg="#88cc88", font=ctk.CTkFont(size=10),
            anchor="w", justify="left", wraplength=720,
        ).pack(fill="x", padx=10, pady=(8, 10))

    def _build_tab_db() -> None:
        t_db = ctk.CTkScrollableFrame(tabs.tab("🗄️  Database"), fg_color=_BG)
        t_db.pack(fill="both", expand=True)
        card_db = tk.Frame(t_db, bg=_INNER, highlightthickness=1,
                           highlightbackground=_BDR)
        card_db.pack(fill="x", padx=12, pady=8)
        _head(card_db, "🗄️  Conexão MySQL (CustomShop)")

        db = data.get("Database", {})
        _dbv.clear()
        resolved_pw = resolve_shop_db_password(shop_cfg)
        _dbv.update({
            "Host":     tk.StringVar(value=str(db.get("Host", "127.0.0.1"))),
            "Port":     tk.StringVar(value=str(db.get("Port", 3306))),
            "User":     tk.StringVar(value=str(db.get("User", "arkland"))),
            "Password": tk.StringVar(value=resolved_pw),
            "Database": tk.StringVar(value=str(db.get("Database", "arkland_shop"))),
        })
        tk.Label(card_db,
                 text="A senha é lida do Banco de Pedidos (Web Store) ou do DB Manager — "
                      "não é salva neste catálogo.",
                 bg=_INNER, fg="gray55",
                 font=ctk.CTkFont(size=10), wraplength=680).pack(anchor="w", padx=10, pady=(0, 4))
        _field_row(card_db, "Host",     _dbv["Host"],     bg=_INNER)
        _field_row(card_db, "Porta",    _dbv["Port"],     bg=_INNER, width=100)
        _field_row(card_db, "Usuário",  _dbv["User"],     bg=_INNER)
        _field_row(card_db, "Senha",    _dbv["Password"], bg=_INNER, is_pass=True)
        _field_row(card_db, "Database", _dbv["Database"], bg=_INNER)

        tk.Label(card_db,
                 text="⚠️  Requer libmysql.dll na mesma pasta do CustomShop.dll",
                 bg=_INNER, fg="#ffaa44",
                 font=ctk.CTkFont(size=10)).pack(anchor="w", padx=10, pady=(6, 8))

    def _collect_all() -> None:
        if _sv:
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
            s_out["MarketCryoRequireMinDays"] = _sv["MarketCryoRequireMinDays"].get()
            s_out["MarketCryoMinDaysRemaining"] = _safe_int(
                _sv["MarketCryoMinDaysRemaining"].get(), 20)
            s_out["MarketCryoDebug"]      = _sv["MarketCryoDebug"].get()
            central = resolve_plugin_website_url(shop_cfg)
            s_out["WebsiteUrl"] = central
            s_out["WebApiUrl"] = resolve_plugin_api_url(shop_cfg)
            s_out["WebApiKey"] = shop_cfg.api_key or s_out.get("WebApiKey", "")

        if _tpv:
            tp_out = data.setdefault("TimedPointsReward", {})
            tp_out["Enabled"]      = _tpv["Enabled"].get()
            tp_out["Interval"]     = _safe_int(_tpv["Interval"].get(), 30)
            tp_out["StackRewards"] = _tpv["StackRewards"].get()
            tp_out["Groups"] = {
                g_name: {"Amount": _safe_int(gv.get(), 25)}
                for g_name, gv in _tp_group_vars.items()
            }

        if _ccv:
            cc_out = data.setdefault("CrossChat", {})
            cc_out["Enabled"] = _ccv["Enabled"].get()
            cc_out["Command"] = (_ccv["Command"].get() or "/c").strip() or "/c"
            cc_out["PollIntervalSeconds"] = max(1, _safe_int(_ccv["PollIntervalSeconds"].get(), 2))
            cc_out["MaxMessageLength"] = max(1, min(500, _safe_int(_ccv["MaxMessageLength"].get(), 200)))
            cc_out["RateLimitSeconds"] = max(0, _safe_int(_ccv["RateLimitSeconds"].get(), 2))
            cc_out["UseWebApi"] = _ccv["UseWebApi"].get()
            cc_out["_comment"] = (
                "Chat entre mapas do cluster via MySQL (comando /c). "
                "ServerId unico por mapa — definido ao sincronizar."
            )

        if _dbv:
            db_out = data.setdefault("Database", {})
            db_out["Host"]     = _dbv["Host"].get()
            db_out["Port"]     = _safe_int(_dbv["Port"].get(), 3306)
            db_out["User"]     = _dbv["User"].get()
            db_out["Database"] = _dbv["Database"].get()
            db_out.pop("Password", None)
            pw = (_dbv["Password"].get() or "").strip()
            if pw and not _is_placeholder_db_password(pw):
                shop_cfg.orders_db_password = pw
                from ..db_setup_resources import save_shop_connection_prefs
                save_shop_connection_prefs(
                    host=db_out["Host"],
                    port=int(db_out["Port"]),
                    user=db_out["User"],
                    password=pw,
                    database=db_out["Database"],
                )
                app.config_manager.save()

    _TAB_BUILDERS = {
        "⚙️  Configurações": _build_tab_cfg,
        "🛒  Itens": lambda: _build_items_tab(app, tabs.tab("🛒  Itens"), data),
        "🎁  Kits": lambda: _build_kits_tab(app, tabs.tab("🎁  Kits"), data),
        "⏱️  Pontos Temporais": _build_tab_timed,
        "💬  Chat Cluster": _build_tab_cross_chat,
        "🗄️  Database": _build_tab_db,
        "🌐  Web Store": lambda: _build_webstore_tab(
            app, tabs.tab("🌐  Web Store"),
            get_catalog=lambda: data,
            get_catalog_path=lambda: Path(cfg_path),
            collect_catalog=_collect_all,
        ),
    }

    def _on_shop_tab_change() -> None:
        tab = tabs.get()
        if tab in _built_shop_tabs:
            return
        frame = tabs.tab(tab)
        loading = ctk.CTkLabel(frame, text="⏳  Carregando…", text_color="gray50",
                               font=ctk.CTkFont(size=13))
        loading.place(relx=0.5, rely=0.5, anchor="center")
        frame.update_idletasks()
        _built_shop_tabs.add(tab)

        def _do_build() -> None:
            try:
                loading.destroy()
            except Exception:
                pass
            _clear_tab_frame(frame)
            builder = _TAB_BUILDERS.get(tab)
            if builder:
                builder()

        parent.after(0, _do_build)

    tabs.configure(command=_on_shop_tab_change)
    _built_shop_tabs.add("⚙️  Configurações")
    _build_tab_cfg()

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


_WEBSTORE_DIR = webstore_data_dir()
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


def _is_web_running(port: int = 0) -> bool:
    global _web_process
    if _web_process is not None and _web_process.poll() is None:
        return True
    if port > 0:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.4):
                return True
        except OSError:
            pass
    return False


def _reload_customshop_rcon_all(app: "ARKServerManagerApp") -> tuple[list[str], list[str], list[str]]:
    """Envia comando de reload do CustomShop via RCON para todos os servidores elegíveis."""
    asm_cm = getattr(app, "asm_config_manager", None)
    servers = iter_shop_servers(app.config_manager, asm_cm)
    ok: list[str] = []
    failed: list[str] = []
    skipped: list[str] = []
    commands = list(CUSTOMSHOP_RELOAD_COMMANDS)

    for _kind, srv in servers:
        name = getattr(srv, "name", "") or getattr(srv, "id", "") or "Servidor"
        if not getattr(srv, "rcon_enabled", False):
            skipped.append(f"{name}: RCON desativado")
            continue
        rcon_pass = sanitize_rcon_password(
            getattr(srv, "rcon_password", "") or getattr(srv, "admin_password", "") or ""
        )
        if not rcon_pass:
            skipped.append(f"{name}: senha RCON/admin não definida")
            continue

        host = (getattr(srv, "server_ip", "") or "127.0.0.1").strip() or "127.0.0.1"
        port = int(getattr(srv, "rcon_port", None) or 27020)

        inst = app.server_manager.get_instance(getattr(srv, "id", ""))
        if inst is not None and getattr(inst, "status", "") != "running":
            skipped.append(f"{name}: servidor não está em execução")
            continue

        client = RconClient(host, port, rcon_pass)
        last_err = ""
        success = False
        try:
            client.connect()
            for cmd in commands:
                cmd_ok, result = client.send_command_with_retry(cmd, retries=2)
                if cmd_ok:
                    ok.append(f"{name}: {cmd}")
                    success = True
                    break
                last_err = result
        except Exception as exc:
            last_err = str(exc)
        finally:
            try:
                client.disconnect()
            except Exception:
                pass

        if not success:
            failed.append(f"{name}: {last_err or 'falha no comando RCON'}")

    return ok, failed, skipped


def _launch_webstore_process(shop) -> tuple[bool, str]:
    """Inicia o processo Flask da Web Store. Retorna (ok, mensagem)."""
    global _web_process, _web_log_fh

    if getattr(sys, "frozen", False) and resolve_webstore_executable() is None:
        return False, "ARKLAND-WebStore.exe não encontrado na pasta de instalação."

    _ensure_mariadb_running(timeout=30)
    env = get_shop_subprocess_env(shop)
    cmd, cwd, log_path = build_webstore_launch(shop)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    if _web_log_fh:
        try:
            _web_log_fh.close()
        except Exception:
            pass
    _web_log_fh = open(log_path, "a", encoding="utf-8")  # noqa: WPS515
    try:
        _web_process = subprocess.Popen(
            cmd,
            cwd=cwd,
            env=env,
            stdout=_web_log_fh,
            stderr=_web_log_fh,
        )
    except Exception as exc:
        return False, str(exc)

    import time as _time
    port = max(1, int(shop.port or DEFAULT_SHOP_PORT))
    deadline = _time.time() + 12
    while _time.time() < deadline:
        if _web_process.poll() is not None:
            tail = read_webstore_log_tail(8)
            return False, tail or "Processo encerrou antes de abrir a porta."
        if _is_web_running(port):
            return True, f"Rodando na porta {port}"
        _time.sleep(0.5)
    if _web_process.poll() is None:
        return True, f"Iniciando (porta {port} ainda não respondeu)"
    tail = read_webstore_log_tail(8)
    return False, tail or "Falha ao iniciar a Web Store."


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
    shop = app.config_manager.config.shop
    if (shop.mode or "client") != "host":
        return
    if _is_web_running(max(1, int(shop.port or DEFAULT_SHOP_PORT))):
        return

    def _launch() -> None:
        ok, msg = _launch_webstore_process(shop)
        if not ok:
            import logging as _log2
            _log2.getLogger(__name__).warning("auto_start_webstore: %s", msg)
            return
        import time as _t
        _t.sleep(4)

    # Roda em thread para não bloquear a UI durante o wait do MariaDB
    threading.Thread(target=_launch, daemon=True, name="WebStoreLauncher").start()


def stop_webstore() -> None:
    """Encerra a Web Store — necessário antes de atualizar o app (libera o .exe)."""
    global _web_process, _web_log_fh
    if _web_process is not None and _web_process.poll() is None:
        try:
            _web_process.terminate()
            try:
                _web_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                _web_process.kill()
        except Exception:
            pass
    _web_process = None
    if _web_log_fh:
        try:
            _web_log_fh.close()
        except Exception:
            pass
        _web_log_fh = None
    if sys.platform == "win32":
        try:
            subprocess.run(
                ["taskkill", "/F", "/IM", "ARKLAND-WebStore.exe"],
                capture_output=True,
            )
        except Exception:
            pass


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
    _port_var = tk.StringVar(value=str(shop.port or DEFAULT_SHOP_PORT))

    from src.shop_integration import _db_manager_prefs

    _dbm = _db_manager_prefs() if not shop.orders_db_user else {}
    _orders_url_var = tk.StringVar(value=shop.orders_db_url or "")
    _odb_host = tk.StringVar(value=shop.orders_db_host or _dbm.get("host", DEFAULT_REMOTE_SHOP_HOST))
    _odb_port = tk.StringVar(value=str(shop.orders_db_port or _dbm.get("port", 3306)))
    _odb_name = tk.StringVar(value=shop.orders_db_name or _dbm.get("database", "arkland_shop"))
    _odb_user = tk.StringVar(value=shop.orders_db_user or _dbm.get("user", ""))
    _odb_pass = tk.StringVar(value=resolve_shop_db_password(shop) or _dbm.get("password", ""))
    _auto_sync_var = tk.BooleanVar(value=bool(shop.auto_sync_on_save))
    _cross_chat_var = tk.BooleanVar(value=bool(getattr(shop, "cross_chat_enabled", True)))

    def _save_shop_from_ui() -> None:
        shop.mode = _mode_var.get()
        shop.central_url = _central_url_var.get().strip()
        shop.public_url = _public_shop_url_var.get().strip()
        shop.host_ip = _host_ip_var.get().strip()
        shop.public_ip = _public_ip_var.get().strip()
        shop.port = _safe_int(_port_var.get(), DEFAULT_SHOP_PORT)
        shop.api_key = _api_key_var.get().strip()
        shop.machine_label = _machine_var.get().strip()
        shop.delivery_mode = _delivery_var.get()
        shop.auto_sync_on_save = _auto_sync_var.get()
        shop.cross_chat_enabled = bool(_cross_chat_var.get())
        shop.orders_db_url = _orders_url_var.get().strip()
        shop.orders_db_host = _odb_host.get().strip()
        shop.orders_db_port = _safe_int(_odb_port.get(), 3306)
        shop.orders_db_name = _odb_name.get().strip()
        shop.orders_db_user = _odb_user.get().strip()
        raw_pass = _odb_pass.get()
        if not _is_placeholder_db_password(raw_pass):
            shop.orders_db_password = raw_pass
        app.config_manager.save()
        host = shop.orders_db_host.strip()
        user = shop.orders_db_user.strip()
        if host and user:
            from ..db_setup_resources import save_shop_connection_prefs
            pw = shop.orders_db_password or ""
            if pw and not _is_placeholder_db_password(pw):
                save_shop_connection_prefs(
                    host=host,
                    port=int(shop.orders_db_port or 3306),
                    user=user,
                    password=pw,
                    database=shop.orders_db_name.strip() or "arkland_shop",
                )

    def _validate_shared_shop_requirements() -> bool:
        is_client = (_mode_var.get() == "client")
        central = _central_url_var.get().strip()
        db_url = _orders_url_var.get().strip().lower()
        using_sqlite = db_url.startswith("sqlite:///") or (
            not db_url and not _odb_user.get().strip()
        )
        if is_client and not central:
            messagebox.showerror(
                "Loja remota",
                "No modo Cliente, defina a URL da loja (ex: https://arkland.com.br).",
                parent=parent.winfo_toplevel(),
            )
            return False
        if is_client and using_sqlite:
            messagebox.showerror(
                "Banco compartilhado obrigatório",
                "Para rodar em 2 máquinas/instâncias com a mesma loja, use o mesmo banco MySQL compartilhado.\n"
                "SQLite local não mantém sincronização entre instâncias.",
                parent=parent.winfo_toplevel(),
            )
            return False
        return True

    def _refresh_access_labels() -> None:
        shop.mode = _mode_var.get()
        shop.host_ip = _host_ip_var.get().strip()
        shop.public_ip = _public_ip_var.get().strip()
        shop.public_url = _public_shop_url_var.get().strip()
        shop.port = _safe_int(_port_var.get(), DEFAULT_SHOP_PORT)
        shop.central_url = _central_url_var.get().strip()
        urls = shop_access_urls(shop)
        is_remote = shop.mode == "client"
        api_hint = " (loja remota)" if is_remote else " (LAN — entrega in-game)"
        _central_url_lbl.config(
            text=f"🔌  API plugins → {urls['plugin_api']}{api_hint}",
        )
        if is_remote:
            if urls["lan_url"]:
                _lan_url_lbl.config(
                    text=f"🏠  Servidor remoto (LAN): {urls['lan_url']}",
                    fg=_GREEN,
                )
            else:
                _lan_url_lbl.config(
                    text="🏠  Servidor remoto (LAN): defina IP LAN do host acima",
                    fg="gray45",
                )
            rp = urls.get("remote_public_url") or ""
            if rp:
                _remote_inet_lbl.config(text=f"🌍  Internet (IP público): {rp}", fg="#38bdf8")
                _remote_inet_lbl.pack(anchor="w", padx=10, pady=(0, 2), after=_lan_url_lbl)
            else:
                _remote_inet_lbl.pack_forget()
        elif urls["lan_url"]:
            _remote_inet_lbl.pack_forget()
            _lan_url_lbl.config(text=f"🏠  Rede local (host): {urls['lan_url']}", fg=_GREEN)
        else:
            _remote_inet_lbl.pack_forget()
            _lan_url_lbl.config(
                text="🏠  IP LAN do host não definido (opcional se usar só domínio)",
                fg="gray45",
            )
        shop_pub = urls.get("shop_url") or urls.get("public_url") or ""
        plugin_shop = urls.get("plugin_website") or ""
        if shop_pub:
            _public_url_lbl.config(
                text=f"🛒  Loja (jogadores): {shop_pub}"
                + (f"  ·  /shop → {plugin_shop}" if plugin_shop and plugin_shop != shop_pub else ""),
                fg="#a78bfa",
            )
        else:
            _public_url_lbl.config(
                text="🛒  Loja pública: defina arkland.com.br acima",
                fg="gray45",
            )
        if _host_only_widgets:
            _toggle_host_only_widgets(is_remote)

    _host_only_widgets: list[tk.Widget] = []

    def _toggle_host_only_widgets(is_remote: bool) -> None:
        for w in _host_only_widgets:
            try:
                w.pack_forget() if is_remote else w.pack()
            except Exception:
                pass

    _refresh_central_label = _refresh_access_labels

    # ── Modo Host / Cliente ───────────────────────────────────────────────
    card_mode = tk.Frame(scr, bg=_INNER, highlightthickness=1, highlightbackground=_BDR)
    card_mode.pack(fill="x", padx=12, pady=(12, 6))
    _head(card_mode, "🌐  Loja Central (cross / multi-máquina)")

    tk.Label(
        card_mode,
        text="Cliente (padrão): esta máquina só gerencia servidores — a loja roda em outro servidor (arkland.com.br). "
             "Host: use apenas na máquina que hospeda a web store.",
        bg=_INNER, fg="gray50", font=ctk.CTkFont(size=10), wraplength=720, justify="left",
    ).pack(anchor="w", padx=10, pady=(0, 6))

    _mode_var = tk.StringVar(value=shop.mode or "client")
    mode_row = tk.Frame(card_mode, bg=_INNER)
    mode_row.pack(fill="x", padx=10, pady=4)
    ctk.CTkRadioButton(mode_row, text="Cliente (loja remota — recomendado)", variable=_mode_var,
                       value="client", command=_refresh_central_label).pack(side="left", padx=(0, 16))
    ctk.CTkRadioButton(mode_row, text="Host (loja nesta máquina)", variable=_mode_var,
                       value="host", command=_refresh_central_label).pack(side="left")

    _machine_var = tk.StringVar(value=shop.machine_label or "")
    _field_row(card_mode, "Rótulo desta máquina", _machine_var, bg=_INNER,
               hint="Obrigatório no cluster: nome único por PC (ex: Maquina-B) — servidores aparecem no site após Sincronizar", width=200)

    _host_ip_var = tk.StringVar(value=shop.host_ip or DEFAULT_REMOTE_SHOP_HOST)
    _field_row(card_mode, "IP LAN (servidor remoto)", _host_ip_var, bg=_INNER,
               hint="Máquina onde banco/loja rodam — ex: 192.168.15.51", width=200)

    _public_shop_url_var = tk.StringVar(
        value=getattr(shop, "public_url", "") or DEFAULT_SHOP_PUBLIC_URL,
    )
    pub_shop_row = tk.Frame(card_mode, bg=_INNER)
    pub_shop_row.pack(fill="x", padx=10, pady=(6, 2))
    pub_shop_row.columnconfigure(0, weight=1)
    ctk.CTkLabel(pub_shop_row, text="Domínio público da loja", anchor="w", text_color="gray65",
                 font=ctk.CTkFont(size=11, weight="bold")).grid(row=0, column=0, sticky="w")
    ctk.CTkLabel(
        pub_shop_row,
        text="Endereço que os jogadores verão — padrão: arkland.com.br. "
             "Aponte o DNS para seu servidor e use reverse proxy (443) → porta da loja.",
        anchor="w", text_color="gray40", font=ctk.CTkFont(size=9), wraplength=680,
    ).grid(row=1, column=0, sticky="w")
    ctk.CTkEntry(pub_shop_row, textvariable=_public_shop_url_var, width=360, height=26).grid(
        row=0, column=1, rowspan=2, sticky="e", padx=(0, 6))
    _shop_url_copy_btn = ctk.CTkButton(
        pub_shop_row, text="📋", width=36, height=26,
        fg_color="#2a2a2a", hover_color="#404040",
        font=ctk.CTkFont(size=11),
    )
    _shop_url_copy_btn.grid(row=0, column=2, rowspan=2)

    _public_ip_var = tk.StringVar(
        value=getattr(shop, "public_ip", "") or DEFAULT_REMOTE_SHOP_PUBLIC_IP,
    )
    pub_row = tk.Frame(card_mode, bg=_INNER)
    pub_row.pack(fill="x", padx=10, pady=2)
    pub_row.columnconfigure(0, weight=1)
    ctk.CTkLabel(pub_row, text="IP público desta máquina", anchor="w", text_color="gray65",
                 font=ctk.CTkFont(size=11, weight="bold")).grid(row=0, column=0, sticky="w")
    ctk.CTkLabel(
        pub_row,
        text="Deve ser igual ao registro A do domínio (botão Detectar). Usado no diagnóstico.",
        anchor="w", text_color="gray40", font=ctk.CTkFont(size=9),
    ).grid(row=1, column=0, sticky="w")
    ctk.CTkEntry(pub_row, textvariable=_public_ip_var, width=200, height=26).grid(
        row=0, column=1, rowspan=2, sticky="e", padx=(0, 6))
    _pub_detect_btn = ctk.CTkButton(
        pub_row, text="🔄 Detectar", width=90, height=26,
        fg_color="#2a3050", hover_color="#3a4060",
        font=ctk.CTkFont(size=10),
    )
    _pub_detect_btn.grid(row=0, column=2, rowspan=2, padx=(0, 4))
    _pub_copy_btn = ctk.CTkButton(
        pub_row, text="📋", width=36, height=26,
        fg_color="#2a2a2a", hover_color="#404040",
        font=ctk.CTkFont(size=11),
    )
    _pub_copy_btn.grid(row=0, column=3, rowspan=2)
    _host_only_widgets.extend([pub_row])

    def _detect_public_ip() -> None:
        _pub_detect_btn.configure(state="disabled", text="⏳")

        def _worker() -> None:
            ok, result = fetch_public_ip()
            def _done() -> None:
                if ok:
                    _public_ip_var.set(result)
                    _refresh_access_labels()
                else:
                    messagebox.showwarning("IP público", result, parent=parent.winfo_toplevel())
                _pub_detect_btn.configure(state="normal", text="🔄 Detectar")
            parent.after(0, _done)

        threading.Thread(target=_worker, daemon=True).start()

    def _copy_public_url() -> None:
        _save_shop_from_ui()
        url = resolve_public_shop_url(shop) or resolve_website_url(shop)
        if not url:
            messagebox.showinfo(
                "Copiar URL",
                "Defina o domínio público da loja primeiro.",
                parent=parent.winfo_toplevel(),
            )
            return
        try:
            parent.winfo_toplevel().clipboard_clear()
            parent.winfo_toplevel().clipboard_append(url)
            toast_msg = f"URL copiada: {url}"
            try:
                app._show_toast(toast_msg, "success")  # type: ignore[attr-defined]
            except AttributeError:
                messagebox.showinfo("Copiar URL", toast_msg, parent=parent.winfo_toplevel())
        except Exception:
            pass

    def _copy_shop_url() -> None:
        _copy_public_url()

    _pub_detect_btn.configure(command=_detect_public_ip)
    _pub_copy_btn.configure(command=_copy_public_url)
    _shop_url_copy_btn.configure(command=_copy_shop_url)
    _public_ip_var.trace_add("write", lambda *_: _refresh_access_labels())
    _public_shop_url_var.trace_add("write", lambda *_: _refresh_access_labels())

    _central_url_var = tk.StringVar(
        value=shop.central_url or DEFAULT_SHOP_PUBLIC_URL,
    )
    _field_row(card_mode, "URL da loja remota", _central_url_var, bg=_INNER,
               hint="https://arkland.com.br — servidor onde a web store está instalada", width=320)

    _central_url_lbl = tk.Label(card_mode, bg=_INNER, fg=_GREEN,
                                font=ctk.CTkFont(size=11, weight="bold"), anchor="w")
    _central_url_lbl.pack(anchor="w", padx=10, pady=(4, 2))
    _lan_url_lbl = tk.Label(card_mode, bg=_INNER, fg=_GREEN,
                            font=ctk.CTkFont(size=11, weight="bold"), anchor="w")
    _lan_url_lbl.pack(anchor="w", padx=10, pady=(0, 2))
    _remote_inet_lbl = tk.Label(card_mode, bg=_INNER, fg="#38bdf8",
                                font=ctk.CTkFont(size=11, weight="bold"), anchor="w")
    _public_url_lbl = tk.Label(card_mode, bg=_INNER, fg="#a78bfa",
                               font=ctk.CTkFont(size=11, weight="bold"), anchor="w")
    _public_url_lbl.pack(anchor="w", padx=10, pady=(0, 4))
    tk.Label(
        card_mode,
        text="DNS do domínio → túnel/proxy (ex.: Cloudflare) ou IP público. "
             "A loja local roda em http://IP-LAN:porta; o HTTPS público é externo.",
        bg=_INNER, fg="gray45", font=ctk.CTkFont(size=9), wraplength=720, justify="left",
    ).pack(anchor="w", padx=10, pady=(0, 8))
    _central_url_lbl.config(text=f"🔌  API plugins → {resolve_plugin_api_url(shop)}")
    _refresh_access_labels()

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

    port_row = tk.Frame(card_status, bg=_INNER)
    port_row.pack(fill="x", padx=10, pady=2)
    tk.Label(port_row, text="Porta:", bg=_INNER, fg="gray50",
             font=ctk.CTkFont(size=10)).pack(side="left", padx=(0, 8))
    ctk.CTkEntry(port_row, textvariable=_port_var, width=90, height=26).pack(side="left")
    port_var_trace = _port_var.trace_add("write", lambda *_: _refresh_access_labels())

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

    _diag_busy = {"on": False}

    def _refresh_status() -> None:
        is_host = _mode_var.get() == "host"
        port = max(1, int(_port_var.get().strip() or DEFAULT_SHOP_PORT))
        _save_shop_from_ui()
        url = resolve_website_url(shop)
        if is_host:
            proc_up = _is_web_running(port)
            btn_start.configure(state="disabled" if proc_up else "normal")
            btn_stop.configure(state="normal" if proc_up else "disabled")
        else:
            status_dot.config(fg="#3b82f6")
            status_lbl.config(text="Modo cliente", fg="#3b82f6")
            btn_start.configure(state="disabled")
            btn_stop.configure(state="disabled")

        if _diag_busy["on"]:
            return
        _diag_busy["on"] = True
        conn_lbl.config(text="Testando local, LAN e domínio…", fg="gray50")

        def _worker() -> None:
            report = diagnose_shop_connectivity(shop)
            tail = ""
            if is_host and not report.local_ok and _web_process and _web_process.poll() is not None:
                tail = read_webstore_log_tail(4)

            def _done() -> None:
                _diag_busy["on"] = False
                if is_host:
                    status_dot.config(fg=report.status_color())
                    status_lbl.config(text=report.status_label(), fg=report.status_color())
                detail = " · ".join(report.lines)
                if tail:
                    detail = f"{detail} | log: {tail[:160]}"
                conn_lbl.config(
                    text=f"Diagnóstico: {detail} — {url}",
                    fg="#22c55e" if report.players_ok else ("#f59e0b" if report.process_up else "#ef4444"),
                )

            parent.after(0, _done)

        threading.Thread(target=_worker, daemon=True, name="ShopDiag").start()

    def _start_web() -> None:
        if _mode_var.get() != "host" or _is_web_running(max(1, int(_port_var.get().strip() or DEFAULT_SHOP_PORT))):
            return
        _save_shop_from_ui()
        collect_catalog()

        def _worker() -> None:
            ok, msg = _launch_webstore_process(shop)
            def _done() -> None:
                if not ok:
                    conn_lbl.config(
                        text=f"Falha ao iniciar Web Store: {msg[:240]}",
                        fg="#ef4444",
                    )
                _refresh_status()
            parent.after(0, _done)

        threading.Thread(target=_worker, daemon=True).start()

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
                  command=_refresh_status).pack(side="left", padx=(0, 8))

    def _fix_webstore_firewall() -> None:
        _save_shop_from_ui()
        port = max(1, int(_port_var.get().strip() or DEFAULT_SHOP_PORT))
        if not messagebox.askyesno(
            "Firewall — Web Store",
            f"Liberar TCP porta {port} no Windows Defender Firewall?\n\n"
            "Necessário para outras máquinas na rede acessarem a loja.\n"
            "Uma janela UAC pode aparecer.",
            parent=parent.winfo_toplevel(),
        ):
            return

        def _worker() -> None:
            ok, msg = create_webstore_firewall_rule(port)

            def _done() -> None:
                if ok:
                    messagebox.showinfo("Firewall", msg, parent=parent.winfo_toplevel())
                else:
                    messagebox.showerror("Firewall", msg, parent=parent.winfo_toplevel())
                _refresh_status()

            parent.after(0, _done)

        threading.Thread(target=_worker, daemon=True).start()

    ctk.CTkButton(btn_row, text="🔒  Firewall", height=34,
                  fg_color="#3a2a10", hover_color="#5a3a18",
                  command=_fix_webstore_firewall).pack(side="left")

    tk.Label(
        card_status,
        text="Outras máquinas na LAN: use http://IP-LAN:porta — exige regra no firewall do Windows (não só do modem).",
        bg=_INNER, fg="gray45", font=ctk.CTkFont(size=9), wraplength=720, justify="left",
    ).pack(anchor="w", padx=10, pady=(0, 8))

    _host_only_widgets.append(card_status)

    # ── Banco de pedidos ──────────────────────────────────────────────────
    card_db = tk.Frame(scr, bg=_INNER, highlightthickness=1, highlightbackground=_BDR)
    card_db.pack(fill="x", padx=12, pady=6)
    _head(card_db, "🗄️  Banco de Pedidos (arkshop_web)")

    _field_row(card_db, "URL completa (opcional)", _orders_url_var, bg=_INNER,
               hint="sqlite:///... ou mysql+pymysql://user:pass@host/db", width=360)
    _field_row(card_db, "MySQL Host (servidor remoto)", _odb_host, bg=_INNER,
               hint="IP LAN do servidor onde o MySQL roda (192.168.15.51)", width=200)
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
        text="Home = card na página inicial da loja. Loja = cadastro em servers.json (desmarque para remover do cross).",
        bg=_INNER, fg="gray50", font=ctk.CTkFont(size=9),
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
            home_var = tk.BooleanVar(value=getattr(srv, "shop_show_on_home", True))
            shop_var = tk.BooleanVar(value=not getattr(srv, "shop_exclude", False))
            prefix = "TEK" if kind == "tek" else "PRIM"
            installed = is_customshop_installed(srv.install_dir)
            status = "✓" if installed else "○"
            tk.Label(
                row, text=f"{status} [{prefix}] {srv.name[:18]}", bg="#1a1a30", fg="gray70",
                font=ctk.CTkFont(size=10, weight="bold"), width=140, anchor="w",
            ).pack(side="left", padx=(4, 4))
            ctk.CTkEntry(row, textvariable=sid_var, width=100, height=24,
                         placeholder_text="shop id").pack(side="left", padx=2)
            ctk.CTkCheckBox(
                row, text="Home", variable=home_var, width=58, height=24,
                checkbox_width=16, checkbox_height=16,
                font=ctk.CTkFont(size=9),
            ).pack(side="left", padx=2)
            ctk.CTkCheckBox(
                row, text="Loja", variable=shop_var, width=58, height=24,
                checkbox_width=16, checkbox_height=16,
                font=ctk.CTkFont(size=9),
            ).pack(side="left", padx=2)
            ctk.CTkEntry(row, textvariable=path_var, width=300, height=24).pack(
                side="left", padx=2)
            _server_rows.append((kind, srv, sid_var, path_var, home_var, shop_var))

    _rebuild_server_rows()

    def _apply_plugins() -> None:
        if not _validate_shared_shop_requirements():
            return
        _save_shop_from_ui()
        collect_catalog()
        for _kind, srv, sid_var, path_var, home_var, shop_var in _server_rows:
            srv.shop_server_id = sid_var.get().strip() or slugify_server_id(srv.name, srv.id)
            srv.customshop_config_path = path_var.get().strip()
            srv.shop_show_on_home = bool(home_var.get())
            srv.shop_exclude = not bool(shop_var.get())
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
        if not _validate_shared_shop_requirements():
            return
        asm_cm = getattr(app, "asm_config_manager", None)
        targets = iter_shop_servers(app.config_manager, asm_cm)
        if not targets:
            messagebox.showwarning("Instalar", "Nenhum servidor cadastrado no app.")
            return
        if not messagebox.askyesno(
            "Instalar CustomShop",
            f"Copiar CustomShop.dll, libmariadb.dll e z.dll para {len(targets)} servidor(es)?\n\n"
            "As DLLs de dependência vão para Plugins/CustomShop/ e Win64/\n"
            "(necessário para evitar Error 126 ao carregar o plugin).\n\n"
            "Também será criado/sincronizado Permissions/config.json (banco ark_permission).\n"
            "config.json existente do CustomShop não será sobrescrito.",
        ):
            return
        ok, errs = install_customshop_all(
            app.config_manager, asm_cm, overwrite_dlls=True,
        )
        _save_shop_from_ui()
        collect_catalog()
        shop_cfg = app.config_manager.config.shop
        catalog = get_catalog()
        sync_ok, sync_errs = sync_all_plugins(
            app.config_manager, shop_cfg, catalog, get_catalog_path(),
            asm_cm=asm_cm,
        )
        _rebuild_server_rows()
        msg = f"{len(ok)} servidor(es) com plugin instalado."
        if sync_ok:
            msg += f" Config sincronizado em {len(sync_ok)}."
        all_errs = list(errs) + list(sync_errs)
        if all_errs:
            msg += "\n" + "\n".join(all_errs[:5])
        try:
            app._show_toast(msg[:120], "success" if ok else "warning")  # type: ignore[attr-defined]
        except AttributeError:
            messagebox.showinfo("Instalar CustomShop", msg)

    def _reload_customshop_all_servers() -> None:
        if not _validate_shared_shop_requirements():
            return
        _save_shop_from_ui()
        collect_catalog()
        for _kind, srv, sid_var, path_var, home_var, shop_var in _server_rows:
            srv.shop_server_id = sid_var.get().strip() or slugify_server_id(srv.name, srv.id)
            srv.customshop_config_path = path_var.get().strip()
            srv.shop_show_on_home = bool(home_var.get())
            srv.shop_exclude = not bool(shop_var.get())
        app.config_manager.save_servers()
        asm_cm = getattr(app, "asm_config_manager", None)
        if asm_cm:
            asm_cm.save()
        catalog = get_catalog()
        sync_ok, sync_errs = sync_all_plugins(
            app.config_manager, shop, catalog, get_catalog_path(),
            asm_cm=asm_cm,
        )
        rcon_ok, rcon_errs, rcon_skips = _reload_customshop_rcon_all(app)

        lines = [
            f"Sincronizados: {len(sync_ok)} plugin(s)",
            f"Reload RCON OK: {len(rcon_ok)} servidor(es)",
        ]
        if rcon_skips:
            lines.append(f"Ignorados: {len(rcon_skips)}")
        if sync_errs or rcon_errs:
            lines.append("Erros:")
            for err in list(sync_errs)[:3]:
                lines.append(f"- {err}")
            for err in rcon_errs[:3]:
                lines.append(f"- {err}")
        if rcon_skips:
            lines.append("Ignorados:")
            for skip in rcon_skips[:3]:
                lines.append(f"- {skip}")

        msg = "\n".join(lines)
        level = "success" if rcon_ok else "warning"
        try:
            app._show_toast(
                f"Loja recarregada em {len(rcon_ok)} servidor(es)",
                level,
            )  # type: ignore[attr-defined]
        except AttributeError:
            pass
        messagebox.showinfo("Recarregar plugin CustomShop", msg, parent=parent.winfo_toplevel())

    def _provision_groups() -> None:
        if not _validate_shared_shop_requirements():
            return
        catalog = get_catalog()
        groups = collect_groups_from_catalog(catalog)
        if not groups:
            messagebox.showinfo(
                "Grupos Permissions",
                "Nenhum grupo definido no catálogo (Kits.Permissions ou TimedPointsReward.Groups).",
                parent=parent.winfo_toplevel(),
            )
            return
        asm_cm = getattr(app, "asm_config_manager", None)
        servers = iter_shop_servers(app.config_manager, asm_cm)
        preview = ", ".join(groups[:12])
        if len(groups) > 12:
            preview += f" (+{len(groups) - 12})"
        if not messagebox.askyesno(
            "Provisionar grupos via RCON",
            f"Criar {len(groups)} grupo(s) via Permissions.AddGroup?\n\n{preview}\n\n"
            "Requer servidor online com RCON ativo e Permissions.dll carregado.",
            parent=parent.winfo_toplevel(),
        ):
            return

        ok, failed, skipped = provision_permission_groups_for_servers(
            servers, catalog, server_manager=app.server_manager,
        )
        lines = [f"Grupos provisionados: {len(ok)} comando(s) OK"]
        if failed:
            lines.append(f"Falhas: {len(failed)}")
            lines.extend(f"- {e}" for e in failed[:5])
        if skipped:
            lines.append(f"Ignorados: {len(skipped)}")
            lines.extend(f"- {s}" for s in skipped[:5])
        messagebox.showinfo(
            "Grupos Permissions",
            "\n".join(lines),
            parent=parent.winfo_toplevel(),
        )

    act_row = tk.Frame(card_srv, bg=_INNER)
    act_row.pack(fill="x", padx=10, pady=(6, 10))
    ctk.CTkButton(act_row, text="📦  Instalar CustomShop",
                  height=34, fg_color="#1a4a6a", hover_color="#1a5a8a",
                  command=_install_customshop).pack(side="left", padx=(0, 10))
    ctk.CTkButton(act_row, text="🔄  Aplicar em todos os plugins",
                  height=34, fg_color=_GREEN_DARK, hover_color=_GREEN_HOVER,
                  command=_apply_plugins).pack(side="left", padx=(0, 10))
    ctk.CTkButton(act_row, text="♻  Sync + Reload RCON (todos)",
                  height=34, fg_color="#0e7490", hover_color="#155e75",
                  command=_reload_customshop_all_servers).pack(side="left", padx=(0, 10))
    ctk.CTkButton(act_row, text="👥  Provisionar grupos (RCON)",
                  height=34, fg_color="#4a3728", hover_color="#5c4632",
                  command=_provision_groups).pack(side="left", padx=(0, 10))
    ctk.CTkCheckBox(act_row, text="Auto-sync ao salvar catálogo",
                    variable=_auto_sync_var).pack(side="left")
    ctk.CTkCheckBox(act_row, text="Chat cluster entre mapas (/c)",
                    variable=_cross_chat_var).pack(side="left", padx=(12, 0))
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
