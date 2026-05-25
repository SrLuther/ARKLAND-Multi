from __future__ import annotations

import shutil
import threading
import webbrowser
import zipfile
from pathlib import Path
from tkinter import filedialog, messagebox
from typing import TYPE_CHECKING

import customtkinter as ctk  # type: ignore[reportMissingImports]

from ..ui_constants import (
    _CARD_BG,
    _GREEN_DARK, _GREEN_HOVER,
    _BLUE, _BLUE_HOVER,
)

if TYPE_CHECKING:
    from ..app import ARKServerManagerApp
    from ..server_config import ServerConfig

# ── Caminhos relativos à raiz de instalação do servidor ──────────────────────
_WIN64   = Path("ShooterGame") / "Binaries" / "Win64"
_ARKAPI  = _WIN64 / "ArkApi"
_PLUGINS = _ARKAPI / "Plugins"

# ── Definição dos plugins oficiais ───────────────────────────────────────────
_OFFICIAL_PLUGINS = [
    {
        "name":       "ASE: Server API",
        "version":    "3.56",
        "author":     "Pelayori",
        "tag":        "Base — obrigatório",
        "tag_color":  "#7a5c10",
        "desc":       "API Framework para ARK: Survival Evolved.\n"
                      "Obrigatório para carregar qualquer plugin ArkApi.",
        "url":        "https://ark-server-api.com/resources/ase-server-api.32/",
        "detect":     lambda d: (d / _ARKAPI).is_dir(),
        "install_to": lambda d: d / _WIN64,
    },
    {
        "name":       "ASE Permissions",
        "version":    "2.1",
        "author":     "Pelayori",
        "tag":        "Dependência do ArkShop",
        "tag_color":  "#1a3a6a",
        "desc":       "Adiciona sistema de grupos e permissões ao ArkApi.\n"
                      "Necessário para controle de grupos no ArkShop.",
        "url":        "https://ark-server-api.com/resources/ase-permissions.35/",
        "detect":     lambda d: (d / _PLUGINS / "Permissions" / "Permissions.dll").is_file(),
        "install_to": lambda d: d / _PLUGINS,
    },
    {
        "name":       "ASE ArkShop",
        "version":    "3.04",
        "author":     "Pelayori",
        "tag":        "Plugin",
        "tag_color":  "#2d5a2d",
        "desc":       "Loja de itens, sistema de moeda e kits para servidores ARK.\n"
                      "Requer MySQL ≤ 8.0.27 ou MariaDB (MySQL 8.0.28+ não é suportado).",
        "url":        "https://ark-server-api.com/resources/ase-arkshop.36/",
        "detect":     lambda d: (d / _PLUGINS / "ArkShop" / "ArkShop.dll").is_file(),
        "install_to": lambda d: d / _PLUGINS,
    },
    {
        "name":       "ArkShopUI",
        "version":    "1.12",
        "author":     "Lethal",
        "tag":        "Plugin",
        "tag_color":  "#2d5a2d",
        "desc":       "Integra o ArkShop com o mod FC_ArkShopUI\n"
                      "(Steam Workshop ID 2693727499).",
        "url":        "https://ark-server-api.com/resources/arkshopui.28/",
        "detect":     lambda d: (d / _PLUGINS / "ArkShopUI" / "ArkShopUI.dll").is_file(),
        "install_to": lambda d: d / _PLUGINS,
    },
    {
        "name":       "Plugin Limit Fix",
        "version":    "latest",
        "author":     "WETBATMAN",
        "tag":        "Fix",
        "tag_color":  "#7a2d2d",
        "desc":       "Corrige crash ao iniciar o servidor quando\n"
                      "muitos plugins estão instalados ao mesmo tempo.",
        "url":        "https://ark-server-api.com/resources/plugin-limit-fix.293/",
        "detect":     None,
        "install_to": lambda d: d / _PLUGINS,
    },
]


def _is_installed(plugin: dict, install_dir: str) -> bool | None:
    """Retorna True/False/None (None = não detectável ou diretório inválido)."""
    if not install_dir or plugin["detect"] is None:
        return None
    try:
        return plugin["detect"](Path(install_dir))
    except Exception:
        return None


def _extract_zip(zip_path: str, target: Path) -> None:
    target.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(target)


def build_tab_plugins(app: "ARKServerManagerApp", parent, srv: "ServerConfig") -> None:
    parent.grid_columnconfigure(0, weight=1)
    parent.grid_rowconfigure(1, weight=1)

    # ── Cabeçalho ─────────────────────────────────────────────────────────────
    hdr = ctk.CTkFrame(parent, fg_color="transparent")
    hdr.grid(row=0, column=0, padx=14, pady=(14, 6), sticky="ew")
    hdr.grid_columnconfigure(0, weight=1)

    ctk.CTkLabel(
        hdr,
        text="🔌  Plugins Oficiais — ASE (ArkApi)",
        font=ctk.CTkFont(size=14, weight="bold"),
        anchor="w",
    ).grid(row=0, column=0, sticky="w")

    ctk.CTkLabel(
        hdr,
        text="Baixe no site oficial e instale via ZIP ou DLL.",
        font=ctk.CTkFont(size=11),
        text_color="gray50",
        anchor="w",
    ).grid(row=1, column=0, sticky="w", pady=(2, 0))

    # ── Banner de compatibilidade (branch / mapa) ─────────────────────────────
    _map    = getattr(srv, "map",         None) or ""
    _branch = getattr(srv, "branch_name", None) or ""

    if _map == "Aquatica":
        _banner_bg   = "#5a2a00"
        _banner_fg   = "#ffbb66"
        _banner_text = (
            "⚠️  Os plugins ArkApi não são compilados para o mapa Aquatic (Aquatica).\n"
            "    Plugins instalados neste servidor não terão efeito."
        )
    elif _branch == "preaquatica":
        _banner_bg   = "#1a3d1a"
        _banner_fg   = "#66cc77"
        _banner_text = (
            "✅  Branch preaquatica detectado — versão 358, última com suporte a ArkApi.\n"
            "    Plugins devem funcionar normalmente neste servidor."
        )
    else:
        _banner_bg   = "#5a3300"
        _banner_fg   = "#ffcc55"
        _banner_text = (
            "⚠️  A atualização recente da Snail (v359+) quebrou os plugins ArkApi.\n"
            "    Para usar plugins, vá em  Geral  e configure o Branch como  preaquatica .\n"
            "    Última versão com suporte: 358."
        )

    _banner_frame = ctk.CTkFrame(hdr, fg_color=_banner_bg, corner_radius=8)
    _banner_frame.grid(row=2, column=0, columnspan=2, pady=(10, 0), sticky="ew")
    ctk.CTkLabel(
        _banner_frame,
        text=_banner_text,
        font=ctk.CTkFont(size=11),
        text_color=_banner_fg,
        anchor="w",
        justify="left",
    ).grid(row=0, column=0, padx=14, pady=8, sticky="w")

    refresh_btn = ctk.CTkButton(
        hdr, text="🔄", width=36, height=32,
        fg_color=_CARD_BG, hover_color="#2a2a42",
        command=lambda: _refresh_all(),
    )
    refresh_btn.grid(row=0, column=1, rowspan=2, padx=(8, 0))

    # ── Área de scroll com os cards ───────────────────────────────────────────
    scroll = ctk.CTkScrollableFrame(parent, fg_color="transparent")
    scroll.grid(row=1, column=0, padx=10, pady=(0, 10), sticky="nsew")
    scroll.grid_columnconfigure(0, weight=1)

    # Mapeia nome do plugin → CTkLabel de status
    _status_labels: dict[str, ctk.CTkLabel] = {}

    def _refresh_all() -> None:
        for plug in _OFFICIAL_PLUGINS:
            lbl = _status_labels.get(plug["name"])
            if lbl is None:
                continue
            status = _is_installed(plug, srv.install_dir)
            if status is True:
                lbl.configure(text="✅  Instalado", text_color="#55cc77")
            elif status is False:
                lbl.configure(text="❌  Não instalado", text_color="#cc5555")
            else:
                lbl.configure(text="⚪  Desconhecido", text_color="gray50")

    def _do_install(plug: dict) -> None:
        if not srv.install_dir:
            messagebox.showerror(
                "Sem diretório",
                "Configure o diretório de instalação do servidor antes de instalar plugins.",
                parent=app,
            )
            return

        path = filedialog.askopenfilename(
            title=f"Selecionar arquivo — {plug['name']}",
            filetypes=[
                ("ZIP / DLL", "*.zip *.dll"),
                ("Todos os arquivos", "*.*"),
            ],
            parent=app,
        )
        if not path:
            return

        target: Path = plug["install_to"](Path(srv.install_dir))

        def _run() -> None:
            try:
                if path.lower().endswith(".zip"):
                    _extract_zip(path, target)
                else:
                    # DLL avulsa → subdiretório com o nome-base do arquivo
                    subdir = target / Path(path).stem
                    subdir.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(path, subdir / Path(path).name)

                app.after(0, lambda: (
                    messagebox.showinfo(
                        "Instalação concluída",
                        f"{plug['name']} instalado em:\n{target}",
                        parent=app,
                    ),
                    _refresh_all(),
                ))
            except Exception as exc:
                app.after(0, lambda e=exc: messagebox.showerror(
                    "Erro na instalação",
                    f"Não foi possível instalar {plug['name']}:\n{e}",
                    parent=app,
                ))

        threading.Thread(target=_run, daemon=True).start()

    # ── Cards ─────────────────────────────────────────────────────────────────
    for i, plug in enumerate(_OFFICIAL_PLUGINS):
        card = ctk.CTkFrame(scroll, corner_radius=10, fg_color=_CARD_BG)
        card.grid(row=i, column=0, padx=4, pady=(0, 8), sticky="ew")
        card.grid_columnconfigure(0, weight=1)

        # Linha 0: nome + versão + tag + autor
        top = ctk.CTkFrame(card, fg_color="transparent")
        top.grid(row=0, column=0, padx=16, pady=(12, 4), sticky="ew")
        top.grid_columnconfigure(3, weight=1)

        ctk.CTkLabel(
            top,
            text=plug["name"],
            font=ctk.CTkFont(size=13, weight="bold"),
            anchor="w",
        ).grid(row=0, column=0, sticky="w")

        ctk.CTkLabel(
            top,
            text=f"v{plug['version']}",
            font=ctk.CTkFont(size=11),
            text_color="gray55",
        ).grid(row=0, column=1, padx=(8, 0), sticky="w")

        ctk.CTkLabel(
            top,
            text=f"  {plug['tag']}  ",
            font=ctk.CTkFont(size=10),
            fg_color=plug["tag_color"],
            corner_radius=4,
            text_color="#dddddd",
        ).grid(row=0, column=2, padx=(10, 0), sticky="w")

        ctk.CTkLabel(
            top,
            text=f"por {plug['author']}",
            font=ctk.CTkFont(size=10),
            text_color="gray45",
            anchor="e",
        ).grid(row=0, column=3, sticky="e")

        # Linha 1: descrição
        ctk.CTkLabel(
            card,
            text=plug["desc"],
            font=ctk.CTkFont(size=11),
            text_color="gray60",
            anchor="w",
            justify="left",
        ).grid(row=1, column=0, padx=16, pady=(0, 8), sticky="w")

        # Linha 2: status + botões
        bot = ctk.CTkFrame(card, fg_color="transparent")
        bot.grid(row=2, column=0, padx=12, pady=(0, 12), sticky="ew")

        status_lbl = ctk.CTkLabel(
            bot,
            text="⚪  Verificando...",
            font=ctk.CTkFont(size=11),
            text_color="gray50",
            anchor="w",
        )
        status_lbl.pack(side="left", padx=(4, 0))
        _status_labels[plug["name"]] = status_lbl

        ctk.CTkButton(
            bot,
            text="📥 Instalar",
            width=100, height=28,
            fg_color=_GREEN_DARK, hover_color=_GREEN_HOVER,
            command=lambda p=plug: _do_install(p),
        ).pack(side="right", padx=(4, 4))

        ctk.CTkButton(
            bot,
            text="🌐 Download",
            width=100, height=28,
            fg_color=_BLUE, hover_color=_BLUE_HOVER,
            command=lambda url=plug["url"]: webbrowser.open(url),
        ).pack(side="right", padx=(0, 0))

    # Atualiza status logo após construção
    app.after(150, _refresh_all)
