"""Editable player and tame level tables for ARK ASE server profiles."""
from __future__ import annotations

import json
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk
from typing import Any

from ..player_engram_points import build_engram_points_ini_lines
from ..player_level_ramp import export_ramp_raw, parse_ramp_from_text, ramp_slots_to_values


def _raw_values(raw: str) -> list[int]:
    parsed = parse_ramp_from_text(raw)
    count = int(parsed.get("entry_count", 0) or 0)
    slots = parsed.get("slots", {})
    return ramp_slots_to_values(slots, count)


def _rows_from_tree(tree: ttk.Treeview, *, player: bool) -> list[tuple[int, int | None, int]]:
    rows: list[tuple[int, int | None, int]] = []
    for index, iid in enumerate(tree.get_children(), start=1):
        values = tree.item(iid, "values")
        raw_xp = str(values[1]).replace(",", "").strip()
        xp = int(raw_xp) if raw_xp else None
        if player:
            points = int(str(values[2]).replace(",", "").strip())
            rows.append((index, xp, points))
        else:
            if xp is None:
                raise ValueError("XP do Dino vazio")
            rows.append((index, xp))
    return rows


def _validate(rows: list[tuple[int, int | None, int]], max_xp: int, *, player: bool) -> str | None:
    xp_rows = [row for row in rows if row[1] is not None]
    if not xp_rows:
        return "Adicione pelo menos um nível à tabela habilitada."
    if player and any(row[2] < 0 for row in rows):
        return "Os pontos de engrama não podem ser negativos."
    last_xp = -1
    for expected, row in enumerate(xp_rows, start=1):
        if row[0] != expected:
            return "Os níveis precisam ser sequenciais, começando em 1."
        assert row[1] is not None
        if row[1] < 0 or row[1] < last_xp:
            return "Os limiares de XP precisam ser não negativos e crescentes."
        last_xp = row[1]
    if max_xp < xp_rows[-1][1]:
        return "O XP máximo precisa ser igual ou maior que o limiar do último nível."
    return None


def _replace_raw_widget(widget: Any, text: str) -> None:
    if widget is None:
        return
    try:
        original_state = widget.cget("state")
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", text)
        widget.configure(state=original_state)
    except Exception:
        pass


def open_level_progression_editor(parent: tk.Misc, config: Any, vars_ref: dict | None = None) -> None:
    """Open a side-by-side, scrollable table editor and apply to the profile."""
    window = tk.Toplevel(parent)
    window.title("Progressões de nível — ARK: Survival Evolved")
    window.geometry("1220x760")
    window.minsize(900, 560)
    window.transient(parent.winfo_toplevel())

    player_values = list(getattr(config, "player_level_xp_thresholds", []) or [])
    if not player_values:
        player_values = _raw_values(str(getattr(config, "player_level_stats_raw", "") or ""))
    if not player_values:
        player_values = [0]
    player_points = list(getattr(config, "player_engram_points", []) or [])
    if not player_points:
        for line in build_engram_points_ini_lines(config):
            try:
                player_points.append(int(line.split("=", 1)[1]))
            except (IndexError, ValueError):
                break
    player_row_count = max(len(player_values), len(player_points))
    player_values.extend([None] * (player_row_count - len(player_values)))
    player_points.extend([0] * (player_row_count - len(player_points)))
    dino_values = _raw_values(str(getattr(config, "dino_level_stats_raw", "") or ""))

    body = ttk.Frame(window, padding=12)
    body.pack(fill="both", expand=True)
    body.columnconfigure((0, 1), weight=1, uniform="progression")
    body.rowconfigure(1, weight=1)

    tables: dict[str, ttk.Treeview] = {}
    enabled_vars: dict[str, tk.BooleanVar] = {}
    max_vars: dict[str, tk.StringVar] = {}

    def create_table(parent_frame: ttk.Frame, key: str, title: str, rows: list[int | None], player: bool) -> None:
        parent_frame.columnconfigure(0, weight=1)
        parent_frame.rowconfigure(2, weight=1)
        ttk.Label(parent_frame, text=title, font=("Segoe UI", 12, "bold")).grid(row=0, column=0, sticky="w", pady=(0, 8))
        controls = ttk.Frame(parent_frame)
        controls.grid(row=1, column=0, sticky="ew", pady=(0, 8))
        enabled_vars[key] = tk.BooleanVar(value=bool(
            getattr(config, "player_level_progressions_enabled" if player else "dino_level_progressions_enabled", False)
        ))
        ttk.Checkbutton(controls, text="Habilitar", variable=enabled_vars[key]).pack(side="left")
        ttk.Label(controls, text="XP máximo:").pack(side="left", padx=(16, 4))
        cap = int(getattr(config, "override_max_xp_player" if player else "override_max_xp_dino", 0) or 0)
        last_xp = next((value for value in reversed(rows) if value is not None), 0)
        if cap <= 0 and rows:
            cap = int(last_xp) + 1
        max_vars[key] = tk.StringVar(value=str(cap))
        ttk.Entry(controls, textvariable=max_vars[key], width=16).pack(side="left")
        columns = ("level", "xp", "engram", "total") if player else ("level", "xp")
        tree = ttk.Treeview(parent_frame, columns=columns, show="headings", selectmode="extended")
        labels = {"level": "Nível", "xp": "XP necessário", "engram": "Pontos de engrama", "total": "Total acumulado"}
        widths = {"level": 72, "xp": 150, "engram": 150, "total": 150}
        for column in columns:
            tree.heading(column, text=labels[column])
            tree.column(column, width=widths[column], anchor="center", stretch=column != "level")
        scrollbar = ttk.Scrollbar(parent_frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        tree.grid(row=2, column=0, sticky="nsew")
        scrollbar.grid(row=2, column=1, sticky="ns")
        total = 0
        for index, xp in enumerate(rows, start=1):
            if player:
                points = int(player_points[index - 1]) if index - 1 < len(player_points) else 0
                tree.insert("", "end", iid=str(index), values=(index, "" if xp is None else xp, points, f"{total:,}"))
                total += points
            else:
                tree.insert("", "end", iid=str(index), values=(index, xp))
        tables[key] = tree

        buttons = ttk.Frame(parent_frame)
        buttons.grid(row=3, column=0, sticky="ew", pady=(8, 0))

        def add_row() -> None:
            count = len(tree.get_children())
            last_xp = next((int(tree.item(iid, "values")[1]) for iid in reversed(tree.get_children()) if str(tree.item(iid, "values")[1]).strip()), 0)
            values = (count + 1, last_xp + 1, 0, "") if player else (count + 1, last_xp + 1)
            existing_ids = [int(value) for value in tree.get_children() if str(value).isdigit()]
            iid = str(max(existing_ids, default=0) + 1)
            tree.insert("", "end", iid=iid, values=values)
            tree.see(iid)

        def remove_rows() -> None:
            for iid in tree.selection():
                tree.delete(iid)
            renumber_rows(tree, player)

        def edit_cell(event: tk.Event) -> None:
            row_id = tree.identify_row(event.y)
            column_id = tree.identify_column(event.x)
            column_index = int(column_id[1:]) - 1 if column_id.startswith("#") else -1
            if not row_id or column_index <= 0:
                return
            box = tree.bbox(row_id, column_id)
            if not box:
                return
            x, y, width, height = box
            current = tree.item(row_id, "values")[column_index]
            editor = ttk.Entry(tree)
            editor.place(x=x, y=y, width=width, height=height)
            editor.insert(0, str(current).replace(",", ""))
            editor.focus_set()

            def commit(_event: tk.Event | None = None) -> None:
                try:
                    value = max(0, int(editor.get().replace(",", "").strip()))
                except ValueError:
                    editor.destroy()
                    return
                values = list(tree.item(row_id, "values"))
                values[column_index] = value
                tree.item(row_id, values=values)
                renumber_rows(tree, player)
                editor.destroy()

            editor.bind("<Return>", commit)
            editor.bind("<FocusOut>", commit)

        def import_table() -> None:
            path = filedialog.askopenfilename(parent=window, filetypes=[("JSON", "*.json"), ("Texto", "*.txt *.csv"), ("Todos", "*.*")])
            if not path:
                return
            try:
                content = open(path, "r", encoding="utf-8-sig").read()
                try:
                    payload = json.loads(content)
                except json.JSONDecodeError:
                    payload = [part.strip() for part in content.replace("\n", ",").split(",") if part.strip()]
                imported = payload.get("levels", []) if isinstance(payload, dict) else payload
                tree.delete(*tree.get_children())
                for i, item in enumerate(imported, start=1):
                    if isinstance(item, dict):
                        xp = int(item.get("xp_required", item.get("xp", 0)))
                        points = int(item.get("engram_points", 0))
                    else:
                        xp, points = int(item), 0
                    values = (i, xp, points, "") if player else (i, xp)
                    tree.insert("", "end", iid=str(i), values=values)
                renumber_rows(tree, player)
            except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
                messagebox.showerror("Importação", f"Não foi possível importar a tabela: {exc}", parent=window)

        def export_table() -> None:
            path = filedialog.asksaveasfilename(parent=window, defaultextension=".json", filetypes=[("JSON", "*.json")])
            if not path:
                return
            rows_out = []
            for row in _rows_from_tree(tree, player=player):
                if row[1] is None:
                    continue
                item = {"level": row[0], "xp_required": row[1]}
                if player:
                    item["engram_points"] = row[2]
                rows_out.append(item)
            with open(path, "w", encoding="utf-8") as stream:
                json.dump({"levels": rows_out}, stream, ensure_ascii=False, indent=2)

        tree.bind("<Double-1>", edit_cell)
        ttk.Button(buttons, text="Adicionar nível", command=add_row).pack(side="left", padx=(0, 6))
        ttk.Button(buttons, text="Remover selecionado", command=remove_rows).pack(side="left", padx=(0, 6))
        ttk.Button(buttons, text="Importar", command=import_table).pack(side="left", padx=(0, 6))
        ttk.Button(buttons, text="Exportar", command=export_table).pack(side="left")

    left = ttk.LabelFrame(body, text="Jogador", padding=10)
    right = ttk.LabelFrame(body, text="Dino domesticado", padding=10)
    left.grid(row=0, column=0, rowspan=2, sticky="nsew", padx=(0, 8))
    right.grid(row=0, column=1, rowspan=2, sticky="nsew", padx=(8, 0))
    create_table(left, "player", "Progressão do jogador", player_values, True)
    create_table(right, "dino", "Progressão do Dino", dino_values, False)

    status = ttk.Label(body, text="Edite uma célula com duplo clique. A gravação no INI será feita pelo ARKLAND Multi.")
    status.grid(row=2, column=0, columnspan=2, sticky="w", pady=(12, 0))

    def apply() -> None:
        try:
            player_rows = _rows_from_tree(tables["player"], player=True)
            dino_rows = _rows_from_tree(tables["dino"], player=False)
            player_cap = int(max_vars["player"].get().replace(",", "").strip() or "0")
            dino_cap = int(max_vars["dino"].get().replace(",", "").strip() or "0")
        except ValueError:
            messagebox.showerror("Progressões", "XP máximo e valores das tabelas devem ser números inteiros.", parent=window)
            return
        if enabled_vars["player"].get():
            error = _validate(player_rows, player_cap, player=True)
            if error:
                messagebox.showerror("Progressão do jogador", error, parent=window)
                return
        if enabled_vars["dino"].get():
            error = _validate(dino_rows, dino_cap, player=False)
            if error:
                messagebox.showerror("Progressão do Dino", error, parent=window)
                return

        config.player_level_progressions_enabled = enabled_vars["player"].get()
        config.dino_level_progressions_enabled = enabled_vars["dino"].get()
        for name, value in (
            ("player_level_progressions_enabled", config.player_level_progressions_enabled),
            ("dino_level_progressions_enabled", config.dino_level_progressions_enabled),
            ("override_max_xp_player", player_cap if config.player_level_progressions_enabled else 0),
            ("override_max_xp_dino", dino_cap if config.dino_level_progressions_enabled else 0),
        ):
            variable = (vars_ref or {}).get(name)
            if variable is not None and hasattr(variable, "set"):
                try:
                    variable.set(value)
                except Exception:
                    pass
        if config.player_level_progressions_enabled:
            config.player_level_xp_thresholds = [row[1] for row in player_rows if row[1] is not None]
            config.player_engram_points = [row[2] for row in player_rows]
            config.player_level_stats_raw = export_ramp_raw(config.player_level_xp_thresholds)
            config.override_max_xp_player = player_cap
            _replace_raw_widget((vars_ref or {}).get("_raw_player_level_stats_raw"), config.player_level_stats_raw)
        else:
            config.player_level_xp_thresholds = []
            config.player_engram_points = []
            config.player_level_stats_raw = ""
        if config.dino_level_progressions_enabled:
            config.dino_level_stats_raw = export_ramp_raw([row[1] for row in dino_rows])
            config.override_max_xp_dino = dino_cap
        else:
            config.dino_level_stats_raw = ""
            config.override_max_xp_dino = 0
        _replace_raw_widget((vars_ref or {}).get("_raw_dino_level_stats_raw"), config.dino_level_stats_raw)
        status.configure(text="Tabela aplicada ao perfil. Salve o perfil para gravar os arquivos Game.ini e GameUserSettings.ini.")
        messagebox.showinfo("Progressões", "As tabelas foram aplicadas ao perfil. Salve o servidor para gravar as configurações.", parent=window)

    actions = ttk.Frame(body)
    actions.grid(row=3, column=0, columnspan=2, sticky="e", pady=(10, 0))
    ttk.Button(actions, text="Aplicar ao perfil", command=apply).pack(side="right", padx=(8, 0))
    ttk.Button(actions, text="Fechar", command=window.destroy).pack(side="right")


def renumber_rows(tree: ttk.Treeview, player: bool) -> None:
    accumulated = 0
    for index, iid in enumerate(tree.get_children(), start=1):
        values = list(tree.item(iid, "values"))
        values[0] = index
        if player:
            values[3] = f"{accumulated:,}"
            accumulated += int(values[2])
        tree.item(iid, values=values)
