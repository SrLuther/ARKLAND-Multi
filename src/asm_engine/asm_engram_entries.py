"""OverrideNamedEngramEntries — parse, edição e gravação sem cortar a classe.

A coluna do editor antigo fatiava o texto em 34 caracteres. Com isso,
``EngramEntry_BlueprintStation_Metal_C`` (36) aparecia como
``EngramEntry_BlueprintStation_Metal``. A carga usava a classe como chave de
dicionário, então duas linhas da mesma classe (níveis diferentes) viravam uma
e a outra não dava para excluir.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

# A coluna antiga cortava em 34 e engolia o ``_C`` de classes com 36 caracteres.
# 50 cabe ``EngramEntry_BlueprintStation_Metal_C`` (36) inteira.
ENGRAM_CLASS_MAX_LEN = 50

_OVERRIDE_LINE_RE = re.compile(
    r"OverrideNamedEngramEntries\s*=\s*\((.*)\)\s*$",
    re.IGNORECASE,
)


@dataclass
class EngramOverride:
    """Uma linha de OverrideNamedEngramEntries."""

    entry_class: str
    display_name: str
    cost: int = 0
    level: int = 1
    hidden: bool = False
    forced: bool = False

    def to_ini_line(self) -> str:
        hidden_str = "True" if self.hidden else "False"
        forced_str = "True" if self.forced else "False"
        return (
            f'OverrideNamedEngramEntries=(EngramClassName="{self.entry_class}",'
            f"EngramHidden={hidden_str},"
            f"EngramPointsCost={self.cost},"
            f"EngramLevelRequirement={self.level},"
            f"RemoveEngramPreReq={forced_str})"
        )


def clamp_engram_class(value: str) -> str:
    """Limite de 50 caracteres. Não parte em ``_`` nem remove o sufixo ``_C``."""
    return (value or "")[:ENGRAM_CLASS_MAX_LEN]


def class_column_text(entry_class: str) -> str:
    """Coluna Classe: até 50 caracteres, com ``_C`` se a classe tiver 36."""
    return clamp_engram_class(entry_class)


def name_column_text(display_name: str) -> str:
    """Coluna Engrama: o mesmo limite de 50, sem o corte antigo de 32."""
    return clamp_engram_class(display_name)


def edit_engram_class(row: EngramOverride, new_class: str) -> None:
    """Grava a classe com até 50 caracteres. Não tira ``_C``."""
    clamped = clamp_engram_class(new_class)
    if row.display_name == row.entry_class:
        row.display_name = clamped
    row.entry_class = clamped


def delete_engram_row(rows: list[EngramOverride], row: EngramOverride) -> list[EngramOverride]:
    """Remove só essa linha. Outra linha com a mesma classe permanece."""
    return [item for item in rows if item is not row]


def _field(body: str, name: str, default: str = "") -> str:
    quoted = re.search(rf'{name}\s*=\s*"([^"]*)"', body, re.IGNORECASE)
    if quoted:
        return quoted.group(1)
    bare = re.search(rf"{name}\s*=\s*([^,\)]+)", body, re.IGNORECASE)
    if bare:
        return bare.group(1).strip()
    return default


def _as_bool(value: str) -> bool:
    return value.strip().lower() == "true"


def _as_int(value: str, default: int = 0) -> int:
    try:
        return int(value.strip())
    except (TypeError, ValueError):
        return default


def parse_engram_overrides(raw: str) -> list[EngramOverride]:
    """Lê cada linha OverrideNamedEngramEntries. Não junta pela classe."""
    found: list[EngramOverride] = []
    for line in (raw or "").splitlines():
        match = _OVERRIDE_LINE_RE.search(line.strip())
        if not match:
            continue
        body = match.group(1)
        entry_class = _field(body, "EngramClassName")
        if not entry_class:
            continue
        found.append(
            EngramOverride(
                entry_class=entry_class,
                display_name=entry_class,
                cost=_as_int(_field(body, "EngramPointsCost", "0")),
                level=_as_int(_field(body, "EngramLevelRequirement", "1"), 1),
                hidden=_as_bool(_field(body, "EngramHidden", "False")),
                forced=_as_bool(_field(body, "RemoveEngramPreReq", "False")),
            )
        )
    return found


def engram_override_lines_for_ini(raw: str) -> list[str]:
    """Linhas brutas de override, na ordem, sem deduplicar por classe."""
    lines: list[str] = []
    for line in (raw or "").splitlines():
        stripped = line.strip()
        if stripped.lower().startswith("overridenamedengramentries="):
            lines.append(stripped)
    return lines


def strip_engram_override_lines(raw: str) -> str:
    kept = [
        line
        for line in (raw or "").splitlines()
        if not line.strip().lower().startswith("overridenamedengramentries=")
    ]
    text = "\n".join(kept).strip()
    return f"{text}\n" if text else ""


def collect_engram_sources(srv: object) -> list[str]:
    """Textos onde o editor já gravou (campo certo e o campo legado)."""
    texts: list[str] = []
    for attr in ("engram_entries_raw", "custom_game_ini_raw", "custom_game_ini"):
        value = getattr(srv, attr, "") or ""
        if isinstance(value, str) and value.strip():
            texts.append(value)
    return texts


def load_engram_rows(
    texts: list[str],
    known: list[tuple] | None = None,
) -> list[EngramOverride]:
    """Monta a tabela.

    Linhas iguais (mesmo texto INI) vindas de dois campos contam uma vez.
    Duas linhas da mesma classe com nível diferente continuam as duas —
    a classe não é chave única.
    """
    parsed: list[EngramOverride] = []
    seen_exact: set[str] = set()
    for text in texts:
        for row in parse_engram_overrides(text):
            key = row.to_ini_line()
            if key in seen_exact:
                continue
            seen_exact.add(key)
            parsed.append(row)

    used = [False] * len(parsed)
    rows: list[EngramOverride] = []
    for item in known or []:
        entry_class, display_name, cost, level = item[0], item[1], item[2], item[3]
        match = next(
            (
                index
                for index, row in enumerate(parsed)
                if not used[index] and row.entry_class == entry_class
            ),
            None,
        )
        if match is None:
            rows.append(EngramOverride(entry_class, display_name, cost, level))
            continue
        parsed[match].display_name = display_name
        rows.append(parsed[match])
        used[match] = True

    for index, row in enumerate(parsed):
        if used[index]:
            continue
        if not row.display_name:
            row.display_name = row.entry_class
        rows.append(row)
    return rows


def row_should_persist(row: EngramOverride, known: list[tuple] | None = None) -> bool:
    entry_class = (row.entry_class or "").strip()
    if not entry_class:
        return False
    for item in known or []:
        if item[0] != entry_class:
            continue
        _name, cost, level = item[1], item[2], item[3]
        return bool(row.hidden or row.forced or row.cost != cost or row.level != level)
    return True


def iter_persisted_rows(
    rows: list[EngramOverride],
    known: list[tuple] | None = None,
) -> list[EngramOverride]:
    kept: list[EngramOverride] = []
    for row in rows:
        entry_class = clamp_engram_class((row.entry_class or "").strip())
        if not entry_class:
            continue
        if row.display_name == row.entry_class or not (row.display_name or "").strip():
            row.display_name = entry_class
        row.entry_class = entry_class
        if row_should_persist(row, known):
            kept.append(row)
    return kept


def persist_engram_rows(
    srv: object,
    rows: list[EngramOverride],
    known: list[tuple] | None = None,
) -> str:
    """Grava no campo que o Game.ini realmente lê (``engram_entries_raw``)."""
    lines = [row.to_ini_line() for row in iter_persisted_rows(rows, known)]
    body = ("\n".join(lines) + "\n") if lines else ""
    srv.engram_entries_raw = body  # type: ignore[attr-defined]

    if hasattr(srv, "custom_game_ini_raw"):
        srv.custom_game_ini_raw = strip_engram_override_lines(
            getattr(srv, "custom_game_ini_raw", "") or ""
        )
    if "custom_game_ini" in getattr(srv, "__dict__", {}):
        cleaned = strip_engram_override_lines(getattr(srv, "custom_game_ini", "") or "")
        if cleaned.strip():
            srv.custom_game_ini = cleaned  # type: ignore[attr-defined]
        else:
            del srv.custom_game_ini  # type: ignore[attr-defined]
    return body


def merged_engram_ini_lines(engram_entries_raw: str, custom_game_ini_raw: str = "") -> list[str]:
    """Linhas para o Game.ini. A mesma linha em dois campos entra uma vez.

    Níveis diferentes da mesma classe continuam em linhas separadas: o
    configparser do INI não pode ficar com uma única chave.
    """
    seen: set[str] = set()
    lines: list[str] = []
    for raw in (engram_entries_raw, custom_game_ini_raw):
        for line in engram_override_lines_for_ini(raw):
            if line in seen:
                continue
            seen.add(line)
            lines.append(line)
    return lines
