"""
src/breeding_calculator.py
Calculadora de Breeding para ARK: Survival Evolved.

Design unificado:
  • Painel superior — seleciona criatura de referência + define metas de tempo
    → calcula os multiplicadores necessários em tempo real
  • Tabela ao vivo — exibe TODAS as criaturas com os tempos resultantes
    dos multiplicadores calculados (atualiza automaticamente)
  • Botão "Aplicar ao Servidor" — grava os multiplicadores no servidor
"""
from __future__ import annotations

import re
import tkinter as tk
import webbrowser
from typing import Callable, Optional

import customtkinter as ctk

# ── Paleta ────────────────────────────────────────────────────────────────────
_FG_TOP   = "#0e1018"
_FG_CARD  = "#13151f"
_FG_EVEN  = "#16192a"
_FG_ODD   = "#1a1d2e"
_FG_REF   = "#152515"   # linha da criatura de referência (verde escuro)
_TEXT_DIM = "#5a7090"
_COL_EGG  = "#7ec8e3"
_COL_MAM  = "#f0a070"
_COL_GRN  = "#4caf78"
_COL_YEL  = "#d4a030"
_COL_RED  = "#c05050"
_BTN_GRN  = "#2d6a4f"
_BTN_HOV  = "#1b4332"

# ── Larguras das colunas da tabela ────────────────────────────────────────────
_CW = (204, 74, 144, 144, 140)   # Criatura | Tipo | Incub./Gest. | Maturação | Acasalamento
_CUDDLE_BASE_S = 3600.0           # intervalo base de cuddle em 1× (1 hora)

# ── Dados base das criaturas (tempos em segundos a 1×) ──────────────────────
# Formato: (nome, tipo, mating_s, incub_or_gest_s, maturation_s)
#   tipo "egg"    = ovíparo  — incub_or_gest_s = tempo de chocagem do ovo
#   tipo "mammal" = mamífero — incub_or_gest_s = tempo de gestação
BREEDING_DATA: list[tuple] = [
    # (nome, tipo, mating_s, incub_ou_gest_s, maturation_s)  -- valores em 1x da wiki
    # ── Egg layers ─────────────────────────────────────────────────────────
    ("Allosaurus",           "egg",      5940,      16620,   166620),
    ("Ankylosaurus",         "egg",      9420,      17520,   176580),
    ("Araneo",               "egg",      5100,       9000,    90060),
    ("Archaeopteryx",        "egg",      9420,       5520,    55500),
    ("Argentavis",           "egg",     10560,      19560,   202020),
    ("Arthropluera",         "egg",      8940,      18480,   185760),
    ("Baryonyx",             "egg",      7140,      16620,   166620),
    ("Beelzebufo",           "egg",     17940,      13320,   133920),
    ("Bloodstalker",         "egg",     10560,      19560,   202020),
    ("Brontosaurus",         "egg",     17940,      33300,   333300),
    ("Carbonemys",           "egg",      4440,       8280,    83280),
    ("Carcharodontosaurus",  "egg",    180540,      87780,   109200),  # mat. efetiva ~1820min (blueprint 8x interno ASE)
    ("Carnotaurus",          "egg",      5940,      16620,   166620),
    ("Compy",                "egg",      2940,       7560,    75720),
    ("Crystal Wyvern",       "egg",     17940,      33300,   333300),
    ("Deinonychus",          "egg",     17940,      13320,   133920),
    ("Dilophosaur",          "egg",      4080,       7560,    75720),
    ("Dimetrodon",           "egg",      8940,      16620,   166620),
    ("Dimorphodon",          "egg",      4860,       9000,    90060),
    ("Dodo",                 "egg",      2940,       5520,    55500),
    ("Featherlight",         "egg",      5940,      17520,   176580),
    ("Fjordhawk",            "egg",      5940,      16620,   166620),
    ("Gallimimus",           "egg",      5100,       9480,    94020),
    ("Giganotosaurus",       "egg",    180540,      87780,   878340),
    ("Glowtail",             "egg",      8940,      17520,   176580),
    ("Hesperornis",          "egg",      5400,      10080,   100980),
    ("Ichthyornis",          "egg",      5940,      13320,   133920),
    ("Iguanodon",            "egg",      5100,      16620,   166620),
    ("Kairuku",              "egg",      5400,      10080,   100980),
    ("Kaprosuchus",          "egg",      7140,      13320,   133920),
    ("Kentrosaurus",         "egg",      9960,      18480,   185760),
    ("Lymantria",            "egg",      5400,      11100,   111660),
    ("Lystrosaurus",         "egg",      2940,       5520,    55500),
    ("Magmasaur",            "egg",     17940,      66660,   666660),
    ("Mantis",               "egg",      9960,      19560,   202020),
    ("Megalania",            "egg",      7140,      13320,   133920),
    ("Megalosaurus",         "egg",      5940,      33300,   333300),
    ("Microraptor",          "egg",      5100,      19560,   202020),
    ("Morellatops",          "egg",      8940,      11100,   111660),
    ("Moschops",             "egg",      9420,      17520,   176580),
    ("Oviraptor",            "egg",      4080,       7560,    75720),
    ("Pachy",                "egg",      5100,       9480,    94020),
    ("Pachyrhinosaurus",     "egg",      8940,      16620,   166620),
    ("Parasaur",             "egg",      5100,       9480,    94020),
    ("Pegomastax",           "egg",      4080,      11100,   111660),
    ("Pelagornis",           "egg",      5940,      13320,   133920),
    ("Pteranodon",           "egg",      5940,      13320,   133920),
    ("Pulmonoscorpius",      "egg",      7140,      13320,   133920),
    ("Quetzal",              "egg",     59940,      47580,   476160),
    ("Raptor",               "egg",      7140,      13320,   133920),
    ("Rex",                  "egg",     17940,      33300,   333300),
    ("Rock Drake",           "egg",     22440,      33300,   333300),
    ("Sarco",                "egg",      8940,      16620,   166620),
    ("Sinomacrops",          "egg",      9420,      13320,   133920),
    ("Snow Owl",             "egg",     10560,      19560,   202020),
    ("Spino",                "egg",     13800,      25620,   255780),
    ("Stegosaurus",          "egg",      9960,      18480,   185760),
    ("Tapejara",             "egg",      5940,      19560,   202020),
    ("Terror Bird",          "egg",      7140,      16620,   166620),
    ("Therizinosaur",        "egg",      5940,      41640,   415440),
    ("Thorny Dragon",        "egg",      8940,      17520,   176580),
    ("Triceratops",          "egg",      8940,      16620,   166620),
    ("Troodon",              "egg",      4080,       7560,    75720),
    ("Tropeognathus",        "egg",      5940,      19560,   202020),
    ("Velonasaur",           "egg",      4080,      16620,   166620),
    ("Voidwyrm",             "egg",     17940,      33300,   333300),
    ("Vulture",              "egg",      4860,       9000,    90060),
    ("Wyvern",               "egg",     17940,      33300,   333300),
    ("Yutyrannus",           "egg",     17940,      66660,   666660),
    # ── Mammals ────────────────────────────────────────────────────────────
    ("Achatina",             "mammal",  28560,      33300,   333300),
    ("Andrewsarchus",        "mammal",  17820,      20820,   208620),
    ("Astrodelphis",         "mammal",  28560,      19560,   202020),
    ("Basilosaurus",         "mammal",  28560,      41640,   415440),
    ("Bulbdog",              "mammal",  15000,      17520,   176580),
    ("Castoroides",          "mammal",  28560,      22200,   222180),
    ("Chalicotherium",       "mammal",  28560,      29580,   295980),
    ("Daeodon",              "mammal",  28560,      17520,   176580),
    ("Desmodus",             "mammal",  28560,      25620,   255780),
    ("Dinopithecus",         "mammal",  35700,      33300,   333300),
    ("Dire Bear",            "mammal",  14280,      16620,   166620),
    ("Direwolf",             "mammal",  15000,      17520,   176580),
    ("Doedicurus",           "mammal",  17820,      20820,   208620),
    ("Dunkleosteus",         "mammal",  28560,      29580,   295980),
    ("Equus",                "mammal",  28560,      16620,   166620),
    ("Ferox",                "mammal",  35700,      33300,   333300),
    ("Gacha",                "mammal",  28560,      41640,   415440),
    ("Gasbags",              "mammal",  28560,      16620,   166620),
    ("Gigantopithecus",      "mammal",  23760,      27720,   277140),
    ("Hyaenodon",            "mammal",  14280,      16620,   166620),
    ("Ichthyosaurus",        "mammal",  28560,      20820,   208620),
    ("Jerboa",               "mammal",   9480,       7560,    75720),
    ("Maewing",              "mammal",   5100,      16620,   166620),
    ("Mammoth",              "mammal",  28560,      29580,   295980),
    ("Managarmr",            "mammal",  14280,      33300,   333300),
    ("Manta",                "mammal",  28560,      13320,   133920),
    ("Megaloceros",          "mammal",  21960,      25620,   255780),
    ("Megalodon",            "mammal",  21960,      25620,   255780),
    ("Megatherium",          "mammal",  28560,      33300,   333300),
    ("Mesopithecus",         "mammal",   9480,      11100,   111660),
    ("Mosasaurus",           "mammal",  28560,      66660,   666660),
    ("Onyc",                 "mammal",  14280,      10080,   100980),
    ("Otter",                "mammal",  28560,       7560,    75720),
    ("Ovis",                 "mammal",  15000,      17520,   176580),
    ("Paraceratherium",      "mammal",  28560,      33300,   333300),
    ("Phiomia",              "mammal",  35700,      17520,   176580),
    ("Plesiosaur",           "mammal",  28560,      41640,   415440),
    ("Procoptodon",          "mammal",  14280,      16620,   166620),
    ("Purlovia",             "mammal",  15000,      17520,   176580),
    ("Ravager",              "mammal",  15000,      17520,   176580),
    ("Roll Rat",             "mammal",  17820,      20820,   208620),
    ("Sabertooth",           "mammal",  15000,      17520,   176580),
    ("Shadowmane",           "mammal",   8580,      17520,   176580),
    ("Shinehorn",            "mammal",  15000,      17520,   176580),
    ("Thylacoleo",           "mammal",  15000,      17520,   176580),
    ("Unicorn",              "mammal",  28560,      16620,   166620),
    ("Woolly Rhino",         "mammal",  14280,      20820,   208620),
]


_DATA_BY_NAME: dict[str, tuple] = {d[0]: d for d in BREEDING_DATA}
CREATURE_NAMES: list[str] = [d[0] for d in BREEDING_DATA]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _fmt_time(seconds: float) -> str:
    """Formata segundos em string legível (ex: '2d 04h 30m')."""
    seconds = max(0, int(seconds))
    if seconds < 60:
        return f"{seconds}s"
    if seconds < 3600:
        m, s = divmod(seconds, 60)
        return f"{m}m {s:02d}s"
    if seconds < 86400:
        h, rem = divmod(seconds, 3600)
        return f"{h}h {rem // 60:02d}m"
    d, rem = divmod(seconds, 86400)
    h = rem // 3600
    m = (rem % 3600) // 60
    return f"{d}d {h:02d}h {m:02d}m"


def _parse_time(s: str) -> Optional[float]:
    """
    Converte entrada do usuário em segundos.
    Formatos aceitos:
      28         → 28 horas
      1.5        → 1h 30m
      1:30       → 1h 30m  (h:mm)
      1:30:00    → 1h 30m  (hh:mm:ss)
      0:45:30    → 45m 30s
      2h 30m     → texto livre com unidades
      45m        → 45 minutos
      90s        → 90 segundos
    Retorna None se inválido ou vazio.
    """
    s = s.strip()
    if not s:
        return None
    try:
        if ":" in s:
            parts = s.split(":")
            if len(parts) == 3:
                return float(parts[0]) * 3600 + float(parts[1]) * 60 + float(parts[2])
            else:
                return float(parts[0]) * 3600 + float(parts[1]) * 60
        if re.search(r"[hHmMsS]", s):
            total = 0.0
            for val, unit in re.findall(r"([\d.]+)\s*([hHmMsS])", s):
                if unit.lower() == "h":
                    total += float(val) * 3600
                elif unit.lower() == "m":
                    total += float(val) * 60
                else:  # s / S
                    total += float(val)
            return total or None
        return float(s.replace(",", ".")) * 3600
    except (ValueError, IndexError):
        return None


# ── Ponto de entrada público ──────────────────────────────────────────────────

def open_breeding_calculator(
    parent: tk.Widget,
    gs,                            # ServerConfig.game_settings
    widgets: dict,                 # _server_widgets[server_id]
    on_apply: Callable[[], None],  # callback após aplicar → dispara save
) -> None:
    """
    Abre a Calculadora de Breeding integrada.

    Layout:
      • Painel superior — criatura de referência + metas de tempo → cálculo ao vivo
      • Cabeçalho fixo da tabela
      • CTkScrollableFrame com todas as criaturas atualizando em tempo real
    """
    dlg = ctk.CTkToplevel(parent)
    dlg.title("🧮  Calculadora de Breeding — ARK")
    dlg.geometry("1020x740")
    dlg.minsize(820, 560)
    dlg.resizable(True, True)
    dlg.grab_set()
    dlg.grid_columnconfigure(0, weight=1)
    dlg.grid_rowconfigure(0, weight=0)   # painel controle
    dlg.grid_rowconfigure(1, weight=0)   # cabeçalho tabela
    dlg.grid_rowconfigure(2, weight=1)   # tabela (expande)

    # ── Estado dos multiplicadores pendentes ──────────────────────────────
    pending = {
        "mature": gs.baby_mature_speed_multiplier,
        "incub":  gs.egg_hatch_speed_multiplier,
        "mating": gs.mating_interval_multiplier,
        "cuddle": gs.baby_cuddle_interval_multiplier,
    }

    # ══════════════════════════════════════════════════════════════════════
    # PAINEL SUPERIOR
    # ══════════════════════════════════════════════════════════════════════
    ctrl = ctk.CTkFrame(dlg, fg_color=_FG_TOP, corner_radius=0)
    ctrl.grid(row=0, column=0, sticky="ew")
    ctrl.grid_columnconfigure(0, weight=1)

    # ── Linha A: título + criatura de referência + filtro ─────────────
    row_a = ctk.CTkFrame(ctrl, fg_color="transparent")
    row_a.grid(row=0, column=0, sticky="ew", padx=14, pady=(12, 4))
    row_a.grid_columnconfigure(4, weight=1)

    ctk.CTkLabel(
        row_a, text="🧮  Calculadora de Breeding",
        font=ctk.CTkFont(size=15, weight="bold"),
    ).grid(row=0, column=0, padx=(0, 24), sticky="w")

    ctk.CTkLabel(
        row_a, text="Criatura de referência:", text_color=_TEXT_DIM,
        font=ctk.CTkFont(size=11),
    ).grid(row=0, column=1, padx=(0, 6))

    creature_var = tk.StringVar(value="Rex")
    combo = ctk.CTkComboBox(
        row_a, variable=creature_var, values=CREATURE_NAMES,
        state="readonly", width=210, font=ctk.CTkFont(size=12),
    )
    combo.grid(row=0, column=2, padx=(0, 28))

    ctk.CTkLabel(row_a, text="🔍", text_color=_TEXT_DIM).grid(
        row=0, column=3, padx=(0, 4))

    search_var = tk.StringVar()
    ctk.CTkEntry(
        row_a, textvariable=search_var,
        placeholder_text="Filtrar tabela…", width=190,
        font=ctk.CTkFont(size=12),
    ).grid(row=0, column=4, sticky="w")

    ctk.CTkButton(
        row_a, text="📋 Tabela base (Wiki)",
        fg_color="#1a2540", hover_color="#243060",
        text_color="#8eb0d0", font=ctk.CTkFont(size=11),
        width=150, height=28, corner_radius=6,
        command=lambda: webbrowser.open(
            "https://ark.wiki.gg/wiki/Breeding#Incubation"
        ),
    ).grid(row=0, column=5, padx=(16, 0), sticky="e")

    # ── Linha B: inputs de meta + multiplicador resultante ────────────
    row_b = ctk.CTkFrame(ctrl, fg_color=_FG_CARD, corner_radius=8)
    row_b.grid(row=1, column=0, sticky="ew", padx=14, pady=(4, 4))

    # (chave_pendente, rótulo, atributo_gs)
    SOLVER_FIELDS = [
        ("mature", "🕐  Maturação",    "baby_mature_speed_multiplier"),
        ("incub",  "🥚  Incubação",     "egg_hatch_speed_multiplier"),
        ("mating", "💞  Cooldown Acas.", "mating_interval_multiplier"),
        ("cuddle", "🤗  Cuddle (Imprint)", "baby_cuddle_interval_multiplier"),
    ]
    # Campos que aceitam tempo (hh:mm:ss) → calcula multiplicador
    _TIME_KEYS = {"mature", "incub", "mating", "cuddle"}

    time_vars: dict[str, tk.StringVar] = {}   # entrada de tempo (hh:mm:ss)
    rate_vars: dict[str, tk.StringVar] = {}   # entrada de multiplicador direto
    result_vars: dict[str, tk.StringVar] = {}

    for ci, (key, label, gs_attr) in enumerate(SOLVER_FIELDS):
        row_b.grid_columnconfigure(ci, weight=1)
        col_f = ctk.CTkFrame(
            row_b, fg_color="#0e1018",
            corner_radius=6, border_width=1, border_color="#1e2840",
        )
        col_f.grid(row=0, column=ci, padx=8, pady=10, sticky="nsew")

        ctk.CTkLabel(
            col_f, text=label,
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color="#8eb0d0",
        ).pack(anchor="w", padx=10, pady=(8, 0))

        if key in _TIME_KEYS:
            time_hint = (
                "Cooldown desejado (hh:mm:ss):" if key == "mating"
                else "Intervalo desejado (hh:mm:ss):" if key == "cuddle"
                else "Tempo desejado (hh:mm:ss):"
            )
            ctk.CTkLabel(
                col_f, text=time_hint,
                font=ctk.CTkFont(size=10), text_color=_TEXT_DIM,
            ).pack(anchor="w", padx=10, pady=(4, 0))
            tv = tk.StringVar()
            time_vars[key] = tv
            ctk.CTkEntry(
                col_f, textvariable=tv,
                placeholder_text="ex: 2:00:00  ou  1h 30m",
                width=168, font=ctk.CTkFont(size=12),
            ).pack(anchor="w", padx=10, pady=(2, 0))

            ctk.CTkLabel(
                col_f, text="Ou multiplicador direto (×):",
                font=ctk.CTkFont(size=10), text_color=_TEXT_DIM,
            ).pack(anchor="w", padx=10, pady=(5, 0))
        else:
            ctk.CTkLabel(
                col_f, text="Multiplicador direto (×):",
                font=ctk.CTkFont(size=10), text_color=_TEXT_DIM,
            ).pack(anchor="w", padx=10, pady=(4, 0))

        rv_in = tk.StringVar()
        rate_vars[key] = rv_in
        ph_rate = "ex: 0.0667" if key == "cuddle" else "ex: 15  (15× mais rápido)"
        ctk.CTkEntry(
            col_f, textvariable=rv_in,
            placeholder_text=ph_rate,
            width=168, font=ctk.CTkFont(size=12),
        ).pack(anchor="w", padx=10, pady=(2, 2))

        rv = tk.StringVar(value="atual: " + _fmt_mult(pending[key]))
        result_vars[key] = rv
        ctk.CTkLabel(
            col_f, textvariable=rv,
            font=ctk.CTkFont(size=10), text_color=_TEXT_DIM,
        ).pack(anchor="w", padx=10, pady=(0, 4))

        if key == "cuddle":
            ctk.CTkLabel(
                col_f,
                text="ℹ Valor global — igual para todos os dinos,\npor isso não aparece na tabela abaixo.",
                font=ctk.CTkFont(size=9),
                text_color="#3a5570",
                justify="left",
            ).pack(anchor="w", padx=10, pady=(0, 8))

    # ── Linha C: painel de resumo + botão aplicar ─────────────────────
    row_c = ctk.CTkFrame(ctrl, fg_color="#0a0c14", corner_radius=6)
    row_c.grid(row=2, column=0, sticky="ew", padx=14, pady=(4, 10))
    row_c.grid_columnconfigure(0, weight=1)

    ctk.CTkLabel(
        row_c,
        text="⚙  Valores que serão gravados em GameUserSettings.ini ao clicar em Aplicar:",
        font=ctk.CTkFont(size=9, weight="bold"),
        text_color="#4a6a8a",
        anchor="w",
    ).grid(row=0, column=0, padx=10, pady=(6, 1), sticky="w")

    mult_summary_var = tk.StringVar()
    ctk.CTkLabel(
        row_c, textvariable=mult_summary_var,
        font=ctk.CTkFont(size=10, weight="bold"),
        text_color="#90b8d8",
        anchor="w",
    ).grid(row=1, column=0, padx=10, pady=(0, 6), sticky="w")

    ctk.CTkButton(
        row_c,
        text="✅  Aplicar ao Servidor",
        fg_color=_BTN_GRN, hover_color=_BTN_HOV,
        width=210, font=ctk.CTkFont(size=12, weight="bold"),
        command=lambda: _apply_to_server(pending, widgets, SOLVER_FIELDS, gs, on_apply),
    ).grid(row=0, column=1, rowspan=2, padx=(0, 10), pady=8, sticky="e")

    # ══════════════════════════════════════════════════════════════════════
    # TABELA — ttk.Treeview (widget nativo; muito mais leve que CTk)
    # ══════════════════════════════════════════════════════════════════════
    import tkinter.ttk as ttk

    _s = ttk.Style()
    try:
        _s.theme_use("default")
    except Exception:
        pass
    _s.configure("Brk.Treeview",
        background="#13151f", foreground="#c8d8e8",
        fieldbackground="#13151f", rowheight=28,
        borderwidth=0, relief="flat",
    )
    _s.configure("Brk.Treeview.Heading",
        background="#090b12", foreground="#7090b0",
        font=("Segoe UI", 11, "bold"), relief="flat",
    )
    _s.map("Brk.Treeview",
        background=[("selected", "#1a2d1a")],
        foreground=[("selected", "#e0f0e0")],
    )

    tbl_wrap = tk.Frame(dlg, bg="#090b12")
    tbl_wrap.grid(row=2, column=0, sticky="nsew")
    tbl_wrap.grid_rowconfigure(0, weight=1)
    tbl_wrap.grid_columnconfigure(0, weight=1)

    vsb = ttk.Scrollbar(tbl_wrap, orient="vertical")
    vsb.grid(row=0, column=1, sticky="ns")

    _COLS = ("name", "tipo", "incub", "mat", "mating")
    tree = ttk.Treeview(
        tbl_wrap, columns=_COLS, show="headings",
        yscrollcommand=vsb.set, style="Brk.Treeview",
    )
    vsb.config(command=tree.yview)
    tree.grid(row=0, column=0, sticky="nsew")

    for col, heading, width in zip(
        _COLS,
        ["Criatura", "Tipo", "Incub. / Gestação", "Maturação", "Cooldown Acas."],
        _CW,
    ):
        tree.heading(col, text=heading, anchor="w")
        tree.column(col, width=width, minwidth=60, anchor="w", stretch=False)

    tree.tag_configure("egg",        foreground=_COL_EGG)
    tree.tag_configure("mammal",     foreground=_COL_MAM)
    tree.tag_configure("egg_ref",    background=_FG_REF, foreground=_COL_EGG)
    tree.tag_configure("mammal_ref", background=_FG_REF, foreground=_COL_MAM)

    _row_data: list[tuple] = []
    _detached: set[str]    = set()

    for name, kind, mating_s, incub_s, mat_s in BREEDING_DATA:
        tipo_txt = "Ovo" if kind == "egg" else "Mamíf."
        tree.insert("", "end", iid=name,
                    values=(name, tipo_txt, "—", "—", "—"),
                    tags=(kind,))
        _row_data.append((name, kind, mating_s, incub_s, mat_s))

    # ══════════════════════════════════════════════════════════════════════
    # LÓGICA REATIVA
    # ══════════════════════════════════════════════════════════════════════

    def _update_table() -> None:
        m_inc = max(pending["incub"],  0.0001)
        m_mat = max(pending["mature"], 0.0001)
        m_mti = pending["mating"]
        ref   = creature_var.get()
        for name, kind, mating_s, incub_s, mat_s in _row_data:
            if name in _detached:
                continue
            tree.set(name, "incub",  _fmt_time(incub_s  / m_inc))
            tree.set(name, "mat",    _fmt_time(mat_s    / m_mat))
            tree.set(name, "mating", _fmt_time(mating_s * m_mti))
            tree.item(name, tags=(kind + "_ref",) if name == ref else (kind,))

    def _update_summary() -> None:
        mult_summary_var.set(
            f"BabyMatureSpeedMultiplier={pending['mature']:.4f}"
            f"   │   EggHatchSpeedMultiplier={pending['incub']:.4f}"
            f"   │   MatingIntervalMultiplier={pending['mating']:.4f}"
            f"   │   BabyCuddleIntervalMultiplier={pending['cuddle']:.4f}"
        )

    _recalc_after_id: list = [None]   # list para mutação em closure

    def _do_recalc() -> None:
        _recalc_after_id[0] = None
        name = creature_var.get()
        data = _DATA_BY_NAME.get(name)
        if not data:
            return
        _, _, mating_s, incub_s, mat_s = data

        def _resolve_time_or_rate(key: str, base_s: float, invert: bool = False) -> None:
            """Resolve valor de multiplicador a partir de tempo ou taxa direta.
            invert=True → multiplicador = t / base_s (acasalamento)
            invert=False → multiplicador = base_s / t (maturação/incubação)
            """
            # Prioridade 1: tempo desejado
            t = _parse_time(time_vars.get(key, tk.StringVar()).get())
            if t and t > 0:
                pending[key] = (t / base_s) if invert else (base_s / t)
                result_vars[key].set(f"→ ×{pending[key]:.4f}")
                return
            # Prioridade 2: multiplicador direto
            raw = rate_vars[key].get().strip().replace(",", ".")
            try:
                v = float(raw)
                if v > 0:
                    pending[key] = v
                    result_vars[key].set(f"→ ×{pending[key]:.4f}")
                    return
            except ValueError:
                pass
            result_vars[key].set(f"atual: {_fmt_mult(pending[key])}")

        _resolve_time_or_rate("mature", mat_s,        invert=False)
        _resolve_time_or_rate("incub",  incub_s,       invert=False)
        _resolve_time_or_rate("mating", mating_s,      invert=True)
        _resolve_time_or_rate("cuddle", _CUDDLE_BASE_S, invert=True)

        _update_summary()
        _update_table()

    def _recalc(*_) -> None:
        # Debounce: espera 200 ms após a última tecla antes de recalcular
        if _recalc_after_id[0] is not None:
            dlg.after_cancel(_recalc_after_id[0])
        _recalc_after_id[0] = dlg.after(200, _do_recalc)

    def _on_search(*_) -> None:
        q = search_var.get().lower().strip()
        for name, *_ in _row_data:
            if q and q not in name.lower():
                if name not in _detached:
                    tree.detach(name)
                    _detached.add(name)
            else:
                if name in _detached:
                    tree.reattach(name, "", "end")
                    _detached.discard(name)

    for tv in time_vars.values():
        tv.trace_add("write", _recalc)
    for rv in rate_vars.values():
        rv.trace_add("write", _recalc)
    search_var.trace_add("write", _on_search)
    combo.configure(command=lambda _v: _recalc())

    # Render inicial
    _update_summary()
    _update_table()


# ── Helpers internos ──────────────────────────────────────────────────────────

def _fmt_mult(v: float) -> str:
    return f"×{v:.4f}"


def _apply_to_server(
    pending: dict,
    widgets: dict,
    solver_fields: list[tuple],
    gs,
    on_apply: Callable[[], None],
) -> None:
    """Aplica os multiplicadores pendentes ao servidor e dispara o save."""
    for key, _label, gs_attr in solver_fields:
        val = pending.get(key)
        if val is None:
            continue
        wk = f"gs_{gs_attr}"
        if wk in widgets:
            widgets[wk].set(val)
        setattr(gs, gs_attr, val)
    on_apply()
