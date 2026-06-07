"""
Helpers de parse/serialização de spawn de NPCs e caixas de suprimento do ARK.
Extraído de ark_ini.py para manter o módulo principal abaixo de 1000 linhas.
"""
from __future__ import annotations

import re


def _parse_npc_spawn_container(value: str, is_override: bool = False):
    """Parseia o valor de uma linha ConfigAdd/OverrideNPCSpawnEntriesContainer.

    Retorna um dict com chaves: container, max_enemies_multiplier, entries.
    Retorna None em caso de falha.

    Formato esperado:
        (NPCSpawnEntriesContainerClassString="DinoSpawnEntriesBeach_C",
         NPCSpawnEntries=((AnEntryName="X",EntryWeight=1.0,
           NPCsToSpawnStrings=("BP'...'"[,...]))[,...]),
         MaxDesiredNumEnemiesMultiplier=1.0)
    """
    value = value.strip()
    if value.startswith("(") and value.endswith(")"):
        value = value[1:-1]

    # Extrai NPCSpawnEntriesContainerClassString
    m = re.search(r'NPCSpawnEntriesContainerClassString\s*=\s*"([^"]*)"', value)
    container_class = m.group(1) if m else ""

    # Extrai MaxDesiredNumEnemiesMultiplier (override only)
    max_mult = 1.0
    m2 = re.search(r'MaxDesiredNumEnemiesMultiplier\s*=\s*([\d.]+)', value)
    if m2:
        try:
            max_mult = float(m2.group(1))
        except ValueError:
            pass

    # Extrai o bloco NPCSpawnEntries=((…))
    entries = []
    m3 = re.search(r'NPCSpawnEntries\s*=\s*\(', value)
    if m3:
        start = m3.end() - 1  # aponta para o '(' externo
        # Avança até o parêntese externo de fechamento
        block = _extract_balanced(value, start)
        if block:
            inner = block[1:-1]  # remove parênteses externos
            # Cada entry começa com '('
            entry_strings = _split_top_level_parens(inner)
            for es in entry_strings:
                entry = _parse_npc_spawn_entry(es)
                if entry is not None:
                    entries.append(entry)

    return {
        "container": container_class,
        "max_enemies_multiplier": max_mult,
        "entries": entries,
    }


def _extract_balanced(text: str, start: int) -> str:
    """Extrai a substring que começa em text[start]='(' e termina no ')' balanceado."""
    if start >= len(text) or text[start] != "(":
        return ""
    depth = 0
    for i in range(start, len(text)):
        if text[i] == "(":
            depth += 1
        elif text[i] == ")":
            depth -= 1
            if depth == 0:
                return text[start: i + 1]
    return ""


def _split_top_level_parens(text: str):
    """Divide a string em itens separados por vírgula no nível mais externo,
    onde cada item pode ser um grupo entre parênteses ou um valor simples."""
    items = []
    depth = 0
    current: list[str] = []
    for ch in text:
        if ch == "(":
            depth += 1
            current.append(ch)
        elif ch == ")":
            depth -= 1
            current.append(ch)
        elif ch == "," and depth == 0:
            item = "".join(current).strip()
            if item:
                items.append(item)
            current = []
        else:
            current.append(ch)
    item = "".join(current).strip()
    if item:
        items.append(item)
    return items


def _parse_npc_spawn_entry(text: str):
    """Parseia um único entry de NPCSpawnEntries como (AnEntryName=…,EntryWeight=…,NPCsToSpawnStrings=(…))."""
    text = text.strip()
    if text.startswith("(") and text.endswith(")"):
        text = text[1:-1]

    m_name   = re.search(r'AnEntryName\s*=\s*"([^"]*)"', text)
    m_weight = re.search(r'EntryWeight\s*=\s*([\d.]+)', text)
    name   = m_name.group(1)   if m_name   else ""
    try:
        weight = float(m_weight.group(1)) if m_weight else 1.0
    except ValueError:
        weight = 1.0

    # Extrai NPCsToSpawnStrings=(…)
    blueprints: list[str] = []
    m_bp = re.search(r'NPCsToSpawnStrings\s*=\s*\(', text)
    if m_bp:
        start = m_bp.end() - 1
        block = _extract_balanced(text, start)
        if block:
            inner = block[1:-1]
            # cada blueprint é "Blueprint'...'"
            blueprints = [bp.strip().strip('"') for bp in inner.split(",") if bp.strip()]

    return {"name": name, "weight": weight, "blueprints": blueprints}


def _serialize_npc_spawn_container(container: dict, is_override: bool = False) -> str:
    """Serializa um container de spawn de dinos para o formato INI do ARK.

    Retorna a linha completa SEM a chave prefix (ex: só o valor entre parênteses).
    """
    parts = [f'NPCSpawnEntriesContainerClassString="{container.get("container", "")}"']

    # Entries
    entry_strs = []
    for entry in container.get("entries", []):
        name     = entry.get("name", "")
        weight   = entry.get("weight", 1.0)
        bps      = entry.get("blueprints", [])
        bp_str   = ",".join(f'"{bp}"' for bp in bps)
        entry_strs.append(
            f'(AnEntryName="{name}",EntryWeight={weight},NPCsToSpawnStrings=({bp_str}))'
        )
    entries_inner = ",".join(entry_strs)
    parts.append(f"NPCSpawnEntries=({entries_inner})")

    if is_override:
        mult = container.get("max_enemies_multiplier", 1.0)
        parts.append(f"MaxDesiredNumEnemiesMultiplier={mult}")

    return "(" + ",".join(parts) + ")"


# ── Multiplicadores por Classe de Dino ─────────────────────────────────────

def _parse_dino_class_multiplier(value: str):
    """Parseia (ClassName="<name>",Multiplier=<float>)."""
    value = value.strip()
    if value.startswith("(") and value.endswith(")"):
        value = value[1:-1]
    m = re.search(r'ClassName\s*=\s*"([^"]*)"', value)
    if not m:
        return None
    m2 = re.search(r'Multiplier\s*=\s*([\d.]+)', value)
    try:
        mult = float(m2.group(1)) if m2 else 1.0
    except ValueError:
        mult = 1.0
    return {"class_name": m.group(1), "multiplier": mult}


def _serialize_dino_class_multiplier(entry: dict) -> str:
    return f'(ClassName="{entry.get("class_name", "")}",Multiplier={entry.get("multiplier", 1.0)})'


# ── Supply Crate Item Overrides ─────────────────────────────────────────────

def _parse_supply_item_entry(text: str):
    """Parseia um ItemEntry de supply crate."""
    text = text.strip()
    if text.startswith("(") and text.endswith(")"):
        text = text[1:-1]

    def _flt(pat, default=1.0):
        m = re.search(pat, text)
        try:
            return float(m.group(1)) if m else default
        except (ValueError, AttributeError):
            return default

    def _bl(pat, default=False):
        m = re.search(pat, text)
        return m.group(1).strip().lower() in ("true", "1") if m else default

    weight    = _flt(r'EntryWeight\s*=\s*([\d.]+)', 1.0)
    min_qty   = _flt(r'MinQuantity\s*=\s*([\d.]+)', 1.0)
    max_qty   = _flt(r'MaxQuantity\s*=\s*([\d.]+)', 1.0)
    min_ql    = _flt(r'MinQuality\s*=\s*([\d.]+)', 1.0)
    max_ql    = _flt(r'MaxQuality\s*=\s*([\d.]+)', 1.0)
    force_bp  = _bl(r'bForceBlueprint\s*=\s*(\w+)', False)
    bp_chance = _flt(r'ChanceToBeBlueprintOverride\s*=\s*([\d.]+)', 0.0)

    items: list[str] = []
    m_items = re.search(r'ItemClassStrings\s*=\s*\(', text)
    if m_items:
        block = _extract_balanced(text, m_items.end() - 1)
        if block:
            items = [s.strip().strip('"') for s in block[1:-1].split(",") if s.strip()]

    return {
        "weight": weight,
        "items": items,
        "min_qty": min_qty,
        "max_qty": max_qty,
        "min_quality": min_ql,
        "max_quality": max_ql,
        "force_blueprint": force_bp,
        "blueprint_chance": bp_chance,
    }


def _parse_supply_item_set(text: str):
    """Parseia um ItemSet de supply crate."""
    text = text.strip()
    if text.startswith("(") and text.endswith(")"):
        text = text[1:-1]

    def _flt(pat, default=1.0):
        m = re.search(pat, text)
        try:
            return float(m.group(1)) if m else default
        except (ValueError, AttributeError):
            return default

    def _int(pat, default=1):
        m = re.search(pat, text)
        try:
            return int(float(m.group(1))) if m else default
        except (ValueError, AttributeError):
            return default

    def _bl(pat, default=True):
        m = re.search(pat, text)
        return m.group(1).strip().lower() in ("true", "1") if m else default

    entries: list[dict] = []
    m_e = re.search(r'ItemEntries\s*=\s*\(', text)
    if m_e:
        block = _extract_balanced(text, m_e.end() - 1)
        if block:
            for es in _split_top_level_parens(block[1:-1]):
                e = _parse_supply_item_entry(es)
                if e is not None:
                    entries.append(e)

    return {
        "min_items":          _int(r'MinNumItems\s*=\s*([\d.]+)', 1),
        "max_items":          _int(r'MaxNumItems\s*=\s*([\d.]+)', 2),
        "num_items_power":    _flt(r'NumItemsPower\s*=\s*([\d.]+)', 1.0),
        "set_weight":         _flt(r'SetWeight\s*=\s*([\d.]+)', 1.0),
        "items_no_replacement": _bl(r'bItemsRandomWithoutReplacement\s*=\s*(\w+)', True),
        "entries":            entries,
    }


def _parse_supply_crate_override(value: str):
    """Parseia o valor de uma linha ConfigOverrideSupplyCrateItems."""
    value = value.strip()
    if value.startswith("(") and value.endswith(")"):
        value = value[1:-1]

    m = re.search(r'SupplyCrateClassString\s*=\s*"([^"]*)"', value)
    crate_class = m.group(1) if m else ""

    def _flt(pat, default=1.0):
        m2 = re.search(pat, value)
        try:
            return float(m2.group(1)) if m2 else default
        except (ValueError, AttributeError):
            return default

    def _int(pat, default=1):
        m2 = re.search(pat, value)
        try:
            return int(float(m2.group(1))) if m2 else default
        except (ValueError, AttributeError):
            return default

    def _bl(pat, default=True):
        m2 = re.search(pat, value)
        return m2.group(1).strip().lower() in ("true", "1") if m2 else default

    item_sets: list[dict] = []
    m_s = re.search(r'ItemSets\s*=\s*\(', value)
    if m_s:
        block = _extract_balanced(value, m_s.end() - 1)
        if block:
            for ss in _split_top_level_parens(block[1:-1]):
                s = _parse_supply_item_set(ss)
                if s is not None:
                    item_sets.append(s)

    return {
        "crate_class":       crate_class,
        "min_sets":          _int(r'MinItemSets\s*=\s*([\d.]+)', 1),
        "max_sets":          _int(r'MaxItemSets\s*=\s*([\d.]+)', 1),
        "num_sets_power":    _flt(r'NumItemSetsPower\s*=\s*([\d.]+)', 1.0),
        "sets_no_replacement": _bl(r'bSetsRandomWithoutReplacement\s*=\s*(\w+)', True),
        "item_sets":         item_sets,
    }


def _serialize_supply_crate_override(crate: dict) -> str:
    """Serializa um supply crate override para o formato INI do ARK."""
    set_strs: list[str] = []
    for item_set in crate.get("item_sets", []):
        entry_strs: list[str] = []
        for entry in item_set.get("entries", []):
            items = entry.get("items", [])
            items_str = ",".join('"' + i + '"' for i in items)
            weights_str = ",".join("1.0" for _ in items)
            ep = (
                f'EntryWeight={entry.get("weight", 1.0)},'
                f'ItemClassStrings=({items_str}),'
                f'ItemsWeights=({weights_str}),'
                f'MinQuantity={entry.get("min_qty", 1.0)},'
                f'MaxQuantity={entry.get("max_qty", 1.0)},'
                f'MinQuality={entry.get("min_quality", 1.0)},'
                f'MaxQuality={entry.get("max_quality", 1.0)},'
                f'bForceBlueprint={"True" if entry.get("force_blueprint", False) else "False"},'
                f'ChanceToBeBlueprintOverride={entry.get("blueprint_chance", 0.0)}'
            )
            entry_strs.append(f'({ep})')
        sp = (
            f'MinNumItems={item_set.get("min_items", 1)},'
            f'MaxNumItems={item_set.get("max_items", 2)},'
            f'NumItemsPower={item_set.get("num_items_power", 1.0)},'
            f'SetWeight={item_set.get("set_weight", 1.0)},'
            f'bItemsRandomWithoutReplacement={"True" if item_set.get("items_no_replacement", True) else "False"},'
            f'ItemEntries=({",".join(entry_strs)})'
        )
        set_strs.append(f'({sp})')

    parts = (
        f'SupplyCrateClassString="{crate.get("crate_class", "")}",'
        f'MinItemSets={crate.get("min_sets", 1)},'
        f'MaxItemSets={crate.get("max_sets", 1)},'
        f'NumItemSetsPower={crate.get("num_sets_power", 1.0)},'
        f'bSetsRandomWithoutReplacement={"True" if crate.get("sets_no_replacement", True) else "False"},'
        f'ItemSets=({",".join(set_strs)})'
    )
    return f'({parts})'


# ══════════════════════════════════════════════════════════════════════════════

def _level_to_xp(level: int) -> int:
    """Converte nível-teto em XP total cumulativo usando a curva padrão do ARK SE.

    Fórmula: soma de round(0.667 * i^2.04) para i de 1 a level-1.
    Dá ~226 000 XP para atingir o nível 100 (curva default).
    """
    if level <= 1:
        return 0
    return sum(max(1, round(0.667 * i ** 2.04)) for i in range(1, level))
