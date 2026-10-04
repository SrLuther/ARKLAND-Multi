"""Comparação de blueprint da Vitrine de Recursos.

Mesma regra no C++ (`plugin/CustomShop/src/VitrineMatch.h`): casa se o path
canônico for igual OU se o nome curto da classe (sem ``_C``) for igual.
Stack, quantidade, peso e preço não entram nesta comparação.
"""
from __future__ import annotations

import re
from typing import Any

_BP_RE = re.compile(r"(/(?:Game|Script|Engine)/[A-Za-z0-9_./\-]+)")

HIDE_BLUEPRINT = (
    "/Game/PrimalEarth/CoreBlueprints/Resources/"
    "PrimalItemResource_Hide.PrimalItemResource_Hide"
)

# Formas que o ARK (ou o admin) pode entregar para o mesmo Couro.
HIDE_ARK_FORMS = (
    HIDE_BLUEPRINT,
    f"Blueprint'{HIDE_BLUEPRINT}'",
    (
        "BlueprintGeneratedClass /Game/PrimalEarth/CoreBlueprints/Resources/"
        "PrimalItemResource_Hide.PrimalItemResource_Hide_C"
    ),
    (
        "PrimalItemResource_Hide_C /Game/PrimalEarth/CoreBlueprints/Resources/"
        "PrimalItemResource_Hide.Default__PrimalItemResource_Hide_C"
    ),
    "PrimalItemResource_Hide",
    "PrimalItemResource_Hide_C",
)


def _strip_class_suffix(name: str) -> str:
    if len(name) > 2 and name[-2] == "_" and name[-1] in "Cc":
        return name[:-2]
    return name


def canonical_blueprint(raw: Any) -> tuple[str, str] | None:
    """``(path /Game/.../X.X, chave minúscula)`` ou None se não houver path."""
    text_in = str(raw or "").strip()
    if not text_in or len(text_in) > 400:
        return None
    match = _BP_RE.search(text_in)
    if not match:
        return None
    path = match.group(1).rstrip("/.")
    slash = path.rfind("/")
    dot = path.rfind(".")
    if dot != -1 and dot > slash:
        obj = path[dot + 1 :]
        if obj.startswith("Default__") and len(obj) > 9:
            obj = obj[9:]
        obj = _strip_class_suffix(obj)
        if not obj:
            return None
        path = path[: dot + 1] + obj
    else:
        path = _strip_class_suffix(path)
        last = path.rsplit("/", 1)[-1]
        if not last:
            return None
        if "." not in last:
            path = f"{path}.{last}"
    if len(path) > 255 or ".." in path:
        return None
    return path, path.lower()


def short_token(raw: Any) -> str:
    """Nome curto da classe, minúsculo, sem ``_C`` e sem prefixo de tipo."""
    text = str(raw or "").strip()
    if not text or len(text) > 400:
        return ""
    if " " in text or "\t" in text:
        text = text.split()[-1]
    text = text.strip("'\"")
    if "/" in text:
        text = text.rsplit("/", 1)[-1]
    if "." in text:
        text = text.rsplit(".", 1)[-1]
    if text.startswith("Default__") and len(text) > 9:
        text = text[9:]
    text = _strip_class_suffix(text).lower()
    if len(text) < 8 or len(text) > 80 or "_" not in text:
        return ""
    if any(not (ch.isalnum() or ch == "_") for ch in text):
        return ""
    return text


def identify(raw: Any) -> dict[str, str]:
    canon = canonical_blueprint(raw)
    path, key = canon if canon else ("", "")
    short = short_token(raw)
    if not short and path:
        short = short_token(path)
    return {"path": path, "key": key, "short": short}


def resources_match(left: Any, right: Any) -> bool:
    """True se o path canônico coincidir ou se o nome curto coincidir."""
    a = identify(left)
    b = identify(right)
    if a["key"] and b["key"] and a["key"] == b["key"]:
        return True
    if a["short"] and b["short"] and a["short"] == b["short"]:
        return True
    return False


def choose_vitrine_source(
    http_ok: bool,
    http_resources: list[Any] | None,
    file_resources: list[Any] | None,
) -> tuple[str, list[Any]]:
    """MySQL (HTTP) primeiro; catalog local se a lista vier vazia ou a chamada falhar.

    Espelha o `/vitrine` do plugin. ``file_resources`` é o bloco do catalog.json.
    """
    rows = list(http_resources or [])
    if http_ok and rows:
        return "mysql", rows
    return "arquivo", list(file_resources or [])
