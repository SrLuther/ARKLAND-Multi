"""Catalog.json é a fonte da Vitrine; MySQL é a cópia.

O bloco ``ResourceVitrine`` vive no mesmo catalog.json que a Web Store e o
CustomShop já abrem (catálogo partilhado, não o config.json de cada mapa).
Na leitura e na subida, o arquivo atualiza o banco. Gravação atômica só do
JSON inteiro com esse bloco trocado — não mexe em outro caminho.
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

import resource_vitrine_service as svc
from vitrine_match import identify, resources_match

log = logging.getLogger("arkshop.resource_vitrine.catalog")

_ENV_PATH = "ARKLAND_VITRINE_CATALOG"


def resolve_vitrine_catalog_path() -> Path | None:
    """Caminho do catalog.json.

    Durante pytest o arquivo real não é lido nem gravado, a menos que o teste
    ligue ``ARKLAND_VITRINE_CATALOG_ALLOW=1`` e aponte ``ARKLAND_VITRINE_CATALOG``.
    """
    in_pytest = bool(os.environ.get("PYTEST_CURRENT_TEST"))
    if in_pytest and os.environ.get("ARKLAND_VITRINE_CATALOG_ALLOW") != "1":
        return None
    override = (os.environ.get(_ENV_PATH) or "").strip()
    if override:
        return Path(override)
    if in_pytest:
        return None
    try:
        from src.shop_integration import canonical_master_catalog_path

        path = canonical_master_catalog_path()
    except Exception as exc:
        log.warning("Vitrine: catalog.json indisponivel: %s", exc)
        return None
    if path is None:
        return None
    return Path(path)


def _load(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(data, dict):
        raise svc.RVError("catalog.json inválido", "invalid_input")
    return data


def atomic_write_catalog(path: Path, catalog: dict[str, Any]) -> None:
    """Substitui o arquivo inteiro via tmp + replace. Preserva as outras chaves."""
    if not isinstance(catalog, dict):
        raise svc.RVError("catalog.json inválido", "invalid_input")
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(catalog, indent=2, ensure_ascii=False) + "\n"
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(payload, encoding="utf-8")
    os.replace(tmp, path)


def refresh_db_from_catalog_path(db: Any, path: Path | None = None) -> dict[str, Any]:
    target = path or resolve_vitrine_catalog_path()
    if target is None or not target.is_file():
        return {"applied": False, "reason": "no-file"}
    try:
        catalog = _load(target)
    except Exception as exc:
        log.warning("Vitrine: falha ao ler %s: %s", target, exc)
        return {"applied": False, "reason": "read-error"}
    result = svc.sync_vitrine_from_catalog(db, catalog)
    result["path"] = str(target)
    return result


def sync_catalog_file_on_boot(engine: Any) -> dict[str, Any]:
    path = resolve_vitrine_catalog_path()
    if path is None or not path.is_file():
        return {"applied": False, "reason": "no-file"}
    from sqlalchemy.orm import Session

    db = Session(engine)
    try:
        return refresh_db_from_catalog_path(db, path)
    except Exception as exc:
        log.warning("Vitrine: sync na subida falhou: %s", exc)
        return {"applied": False, "reason": "error", "error": str(exc)}
    finally:
        db.close()


def _seed_block_from_db(db: Any, catalog: dict[str, Any]) -> dict[str, Any]:
    block = svc.extract_vitrine_block(catalog)
    if isinstance(block, dict) and isinstance(block.get("resources"), list):
        return block
    resources = []
    for row in svc.list_catalog(db, include_disabled=True):
        resources.append(
            {
                "blueprint": row["blueprint"],
                "name": row["name"],
                "stack_size": row["stack_size"],
                "min_lot_price": row["min_lot_price"],
                "max_lot_price": row["max_lot_price"],
                "enabled": bool(row["enabled"]),
            }
        )
    return {"max_types_per_player": svc.get_max_types(db), "resources": resources}


def _item_from_body(body: dict[str, Any]) -> dict[str, Any]:
    ident = identify(body.get("blueprint"))
    if not ident["path"]:
        raise svc.RVError("Blueprint inválido (use o caminho /Game/.../Nome.Nome)", "invalid_input")
    name = str(body.get("name") or "").strip()
    if not name:
        raise svc.RVError("Nome inválido (1–80 caracteres, sem símbolos de controle)", "invalid_input")
    item: dict[str, Any] = {
        "blueprint": ident["path"],
        "name": name,
        "stack_size": body.get("stack_size", 100),
        "enabled": body.get("enabled", True) is not False,
    }
    if body.get("min_lot_price") not in (None, ""):
        item["min_lot_price"] = body.get("min_lot_price")
    if body.get("max_lot_price") not in (None, ""):
        item["max_lot_price"] = body.get("max_lot_price")
    return item


def _write_block(path: Path, catalog: dict[str, Any], block: dict[str, Any]) -> None:
    catalog = dict(catalog)
    catalog["ResourceVitrine"] = block
    atomic_write_catalog(path, catalog)


def _row_for_blueprint(db: Any, blueprint: str) -> dict[str, Any]:
    ident = identify(blueprint)
    for row in svc.list_catalog(db, include_disabled=True):
        if resources_match(row.get("blueprint"), ident["path"] or blueprint):
            return row
    raise svc.RVError("Recurso não encontrado", "not_found", 404)


def publish_admin_upsert(db: Any, body: dict[str, Any], *, admin_steam_id: str | None = None) -> dict[str, Any]:
    """Grava o bloco no catalog.json e só então atualiza o MySQL. Sem arquivo, só o banco."""
    path = resolve_vitrine_catalog_path()
    if path is None or not path.is_file():
        return svc.upsert_catalog_resource(db, body, admin_steam_id=admin_steam_id)
    catalog = _load(path)
    block = _seed_block_from_db(db, catalog)
    item = _item_from_body(body)
    old_bp = None
    if body.get("id") not in (None, ""):
        for row in svc.list_catalog(db, include_disabled=True):
            if int(row["id"]) == int(body["id"]):
                old_bp = row["blueprint"]
                break
    resources = [r for r in (block.get("resources") or []) if isinstance(r, dict)]
    replaced = False
    kept: list[dict[str, Any]] = []
    for current in resources:
        same_old = old_bp and resources_match(current.get("blueprint"), old_bp)
        same_new = resources_match(current.get("blueprint"), item["blueprint"])
        if same_old or same_new:
            if not replaced:
                merged = dict(current)
                merged.update(item)
                kept.append(merged)
                replaced = True
            continue
        kept.append(current)
    if not replaced:
        kept.append(item)
    block["resources"] = kept
    if "max_types_per_player" not in block:
        block["max_types_per_player"] = svc.get_max_types(db)
    _write_block(path, catalog, block)
    catalog["ResourceVitrine"] = block
    svc.sync_vitrine_from_catalog(db, catalog)
    return _row_for_blueprint(db, item["blueprint"])


def publish_admin_disable(db: Any, resource_id: int, *, admin_steam_id: str | None = None) -> dict[str, Any]:
    path = resolve_vitrine_catalog_path()
    if path is None or not path.is_file():
        return svc.disable_catalog_resource(db, resource_id, admin_steam_id=admin_steam_id)
    current = None
    for row in svc.list_catalog(db, include_disabled=True):
        if int(row["id"]) == int(resource_id):
            current = row
            break
    if current is None:
        raise svc.RVError("Recurso não encontrado", "not_found", 404)
    catalog = _load(path)
    block = _seed_block_from_db(db, catalog)
    kept = []
    for item in block.get("resources") or []:
        if isinstance(item, dict) and resources_match(item.get("blueprint"), current["blueprint"]):
            continue
        kept.append(item)
    block["resources"] = kept
    _write_block(path, catalog, block)
    catalog["ResourceVitrine"] = block
    svc.sync_vitrine_from_catalog(db, catalog)
    return {"id": resource_id, "enabled": False, "has_dependents": svc._resource_has_dependents(db, resource_id)}


def publish_max_types(db: Any, value: Any) -> int:
    number = svc.set_max_types(db, value)
    path = resolve_vitrine_catalog_path()
    if path is None or not path.is_file():
        return number
    catalog = _load(path)
    block = svc.extract_vitrine_block(catalog)
    if not isinstance(block, dict) or not isinstance(block.get("resources"), list):
        return number
    block = dict(block)
    block["max_types_per_player"] = number
    _write_block(path, catalog, block)
    return number
