"""Índice operacional de blueprints e classes já citados no projeto.

Lê fontes locais (catálogo, JSON do plugin, ferramentas, lista estática de
engramas e, se existirem, caches locais). Grava só a tabela ``blueprint_index``.
Não escreve catalog.json, não chama a API Beacon e não abre ini de mapa.
"""
from __future__ import annotations

import csv
import io
import json
import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import inspect, text

log = logging.getLogger("arkshop.blueprint_index")

TABLE = "blueprint_index"
# Tipos do cadastro nesta página. Os demais continuam na classificação automática.
FORM_KINDS = ("dino", "sela", "recurso", "estrutura", "outro")
KINDS = ("item", "dino", "engrama", "estrutura", "comando", "outro", "sela", "recurso")
_KIND_RANK = {kind: index for index, kind in enumerate(KINDS)}
_CLASS_ONLY_RE = re.compile(r"^(?:EngramEntry_|PrimalItem_)[A-Za-z0-9_]+_C$")
SOURCE_LABELS = {
    "catalog_items": "Catálogo — itens",
    "catalog_kits": "Catálogo — kits",
    "catalog_comandos": "Catálogo — comandos",
    "catalog_vitrine": "Catálogo — vitrine",
    "catalog": "Catálogo",
    "market_species_defaults": "Padrões de espécies",
    "ark_species_registry": "Registro de espécies",
    "mod_catalog_verified": "Mods verificados",
    "official_vanilla": "Vanilla oficial",
    "market_species": "Banco — espécies",
    "market_aliases": "Banco — aliases",
    "itensalfa_blueprints": "ItensAlfa — blueprints",
    "itensalfa_creatures": "ItensAlfa — criaturas",
    "blueprint_matrix": "Matriz de blueprints",
    "asm_known_engrams": "ASM — engramas conhecidos",
    "asm_engram_entries": "ASM — código de engramas",
    "beacon_cache": "Cache Beacon local",
    "spawnexact_cache": "Cache SpawnExact",
    "servers_json": "servers.json",
    "asm_servers": "asm_servers.json",
    "manual": "Cadastro manual",
}

_GAME_RE = re.compile(r"/Game/[A-Za-z0-9_+\-./]*\.[A-Za-z0-9_+\-]+")
_ENGRAM_RE = re.compile(r"\bEngramEntry_[A-Za-z0-9_]+_C\b")
_ENGRAM_TUPLE_RE = re.compile(
    r'\(\s*"(EngramEntry_[A-Za-z0-9_]+_C)"\s*,\s*"([^"]*)"'
)
_SOURCE_RE = re.compile(r"^[a-z0-9_]{1,64}$")
_ID_KEY_RE = re.compile(r"[A-Za-z0-9_]{2,64}")

_NAME_KEYS = (
    "Name",
    "display_name",
    "display_name_pt",
    "label",
    "alternateLabel",
    "species_name",
    "variant_label",
    "family",
)
_TOKEN_KEYS = ("species_key", "item_id", "catalog_item_id")
_SKIP_KEYS = {
    "password",
    "user",
    "host",
    "port",
    "database",
    "rcon_password",
    "steam_key",
    "secret",
    "token",
    "api_key",
}
_STRUCT_KEYS = {
    "items",
    "kits",
    "dinos",
    "commands",
    "command",
    "resources",
    "resourcevitrine",
    "vitrineresources",
    "blueprint_aliases",
    "blueprint_paths",
    "species",
    "entries",
    "families",
    "creatures",
    "blueprints",
    "economy_stats",
    "debug",
    "database",
    "permissions",
    "global_stat_labels",
}

_DATA_FILES = (
    ("market_species_defaults.json", "market_species_defaults"),
    ("ark_species_registry.json", "ark_species_registry"),
    ("mod_catalog_verified.json", "mod_catalog_verified"),
    ("official_vanilla_species.json", "official_vanilla"),
)
_TOOL_FILES = (
    ("itensalfa_blueprints.json", "itensalfa_blueprints"),
    ("itensalfa_creatures.json", "itensalfa_creatures"),
    ("blueprint_catalog_matrix.csv", "blueprint_matrix"),
)
_MAX_FILE_BYTES = 32 * 1024 * 1024

_DDL_SQLITE = """
CREATE TABLE IF NOT EXISTS blueprint_index (
  ident_norm VARCHAR(512) PRIMARY KEY NOT NULL,
  identifier VARCHAR(512) NOT NULL,
  kind VARCHAR(16) NOT NULL,
  display_name VARCHAR(200) NOT NULL DEFAULT '',
  token VARCHAR(128) NOT NULL DEFAULT '',
  sources_json TEXT NOT NULL,
  note TEXT NOT NULL DEFAULT '',
  manual INTEGER NOT NULL DEFAULT 0,
  mod_name VARCHAR(200) NOT NULL DEFAULT '',
  class_name VARCHAR(200) NOT NULL DEFAULT '',
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
)
"""
_DDL_MYSQL = """
CREATE TABLE IF NOT EXISTS blueprint_index (
  ident_norm VARCHAR(512) NOT NULL,
  identifier VARCHAR(512) NOT NULL,
  kind VARCHAR(16) NOT NULL,
  display_name VARCHAR(200) NOT NULL DEFAULT '',
  token VARCHAR(128) NOT NULL DEFAULT '',
  sources_json TEXT NOT NULL,
  note TEXT NOT NULL,
  manual INTEGER NOT NULL DEFAULT 0,
  mod_name VARCHAR(200) NOT NULL DEFAULT '',
  class_name VARCHAR(200) NOT NULL DEFAULT '',
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (ident_norm),
  KEY idx_bidx_kind (kind)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
"""


def _is_sqlite(engine: Any) -> bool:
    return "sqlite" in str(getattr(engine, "url", "")).lower()


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _module_dir() -> Path:
    return Path(__file__).resolve().parent


class BlueprintIndexError(Exception):
    """Cadastro recusado. ``code`` é empty, invalid, kind ou duplicate."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def ensure_blueprint_index_schema(engine: Any) -> None:
    """Cria ``blueprint_index`` se ainda não existir. Não altera outras tabelas."""
    if engine is None:
        return
    ddl = _DDL_SQLITE if _is_sqlite(engine) else _DDL_MYSQL
    index = "CREATE INDEX IF NOT EXISTS idx_bidx_kind ON blueprint_index (kind)"
    with engine.begin() as conn:
        conn.execute(text(ddl))
        if _is_sqlite(engine):
            conn.execute(text(index))
    cols = {str(col["name"]).lower() for col in inspect(engine).get_columns(TABLE)}
    alters: list[str] = []
    if "note" not in cols:
        alters.append("ALTER TABLE blueprint_index ADD COLUMN note TEXT NOT NULL DEFAULT ''")
    if "manual" not in cols:
        alters.append(
            "ALTER TABLE blueprint_index ADD COLUMN manual INTEGER NOT NULL DEFAULT 0"
        )
    if "mod_name" not in cols:
        alters.append(
            "ALTER TABLE blueprint_index ADD COLUMN mod_name VARCHAR(200) NOT NULL DEFAULT ''"
        )
    if "class_name" not in cols:
        alters.append(
            "ALTER TABLE blueprint_index ADD COLUMN class_name VARCHAR(200) NOT NULL DEFAULT ''"
        )
    if not alters:
        return
    with engine.begin() as conn:
        for statement in alters:
            conn.execute(text(statement))


def _pick_str(node: dict[str, Any], keys: tuple[str, ...]) -> str:
    for key in keys:
        value = node.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()[:200]
    return ""


def _clean_game(path: str) -> str:
    path = path.strip()
    if "." not in path:
        return ""
    package, cls = path.rsplit(".", 1)
    if cls.lower().endswith("_c") and len(cls) > 2:
        cls = cls[:-2]
    if not package.startswith("/Game/") or not cls:
        return ""
    return f"{package}.{cls}"


def class_from_blueprint(raw: str) -> str:
    """Último segmento do caminho, sem aspas. EngramEntry_*_C e PrimalItem_*_C ficam inteiros."""
    text_value = (raw or "").strip()
    if (
        len(text_value) >= 2
        and text_value[0] == text_value[-1]
        and text_value[0] in "\"'"
    ):
        text_value = text_value[1:-1].strip()
    wrapped = re.search(r"Blueprint'([^']+)'", text_value, flags=re.IGNORECASE)
    if wrapped:
        text_value = wrapped.group(1).strip()
    text_value = text_value.strip().strip('"').strip("'")
    if _CLASS_ONLY_RE.fullmatch(text_value):
        return text_value[:200]
    segment = text_value.rsplit("/", 1)[-1].strip().strip('"').strip("'")
    if _CLASS_ONLY_RE.fullmatch(segment):
        return segment[:200]
    if "." in segment:
        segment = segment.rsplit(".", 1)[-1].strip()
    return segment[:200]


def _short_token(display: str) -> str:
    if display.lower().startswith("engramentry_") and display.endswith("_C"):
        return display[len("EngramEntry_") : -2][:128]
    if "." in display:
        return display.rsplit(".", 1)[-1][:128]
    return ""


def _hint_kind(hint: str) -> str | None:
    key = (hint or "").strip().lower()
    if key in ("dino", "dinos", "creature", "criatura"):
        return "dino"
    if key in ("item", "items", "resource", "arma", "armadura"):
        return "item"
    if key in ("structure", "estrutura", "structures"):
        return "estrutura"
    if key in ("command", "commands", "comando", "comandos"):
        return "comando"
    if key in ("engram", "engrama", "engrams"):
        return "engrama"
    return None


def classify_identifier(display: str, hint: str = "") -> str:
    low = (display or "").lower()
    if low.startswith("engramentry_") and low.endswith("_c"):
        return "engrama"
    if "/dinos/" in low or "character_bp" in low:
        return "dino"
    if "/structures/" in low or "primalitemstructure" in low:
        return "estrutura"
    if (
        "primalitem" in low
        or "/items/" in low
        or "/weapons/" in low
        or "/armor/" in low
        or "/resources/" in low
    ):
        return "item"
    hinted = _hint_kind(hint)
    if hinted:
        return hinted
    return "outro"


def extract_identifiers(raw: str) -> list[tuple[str, str]]:
    """Devolve ``(texto para copiar, chave normalizada)`` ou lista vazia."""
    if not isinstance(raw, str):
        return []
    text_value = raw.strip()
    if not text_value or len(text_value) > 8000:
        return []
    found: list[tuple[str, str]] = []
    seen: set[str] = set()
    for match in _ENGRAM_RE.finditer(text_value):
        display = match.group(0)
        norm = display.lower()
        if norm in seen or len(norm) > 512:
            continue
        seen.add(norm)
        found.append((display, norm))
    for match in _GAME_RE.finditer(text_value):
        display = _clean_game(match.group(0))
        if not display:
            continue
        norm = display.lower()
        if norm in seen or len(display) > 512 or len(norm) > 512:
            continue
        seen.add(norm)
        found.append((display, norm))
    return found


def _child_source(source: str, key: Any) -> str:
    lowered = str(key).lower()
    if lowered in ("command", "commands") and source.startswith("catalog"):
        return "catalog_comandos"
    if source == "catalog" and lowered == "kits":
        return "catalog_kits"
    if source == "catalog" and lowered == "items":
        return "catalog_items"
    if lowered in ("resourcevitrine", "vitrineresources"):
        return "catalog_vitrine"
    return source


def _add(
    bucket: dict[str, dict[str, Any]],
    raw: str,
    *,
    source: str,
    name: str = "",
    hint: str = "",
    token: str = "",
) -> None:
    label = (name or "").strip()[:200]
    explicit = (token or "").strip()[:128]
    for display, norm in extract_identifiers(raw):
        kind = classify_identifier(display, hint)
        row = bucket.get(norm)
        if row is None:
            bucket[norm] = {
                "ident_norm": norm,
                "identifier": display,
                "kind": kind,
                "display_name": label,
                "token": explicit or _short_token(display),
                "sources": {source},
            }
            continue
        row["sources"].add(source)
        if _KIND_RANK.get(kind, 0) > _KIND_RANK.get(row["kind"], 0):
            row["kind"] = kind
        if label and not row["display_name"]:
            row["display_name"] = label
        if explicit and not row["token"]:
            row["token"] = explicit


def _walk(
    node: Any,
    source: str,
    name: str,
    hint: str,
    token: str,
    bucket: dict[str, dict[str, Any]],
) -> None:
    if isinstance(node, dict):
        local_name = _pick_str(node, _NAME_KEYS) or name
        local_token = _pick_str(node, _TOKEN_KEYS) or token
        local_hint = hint
        for key in ("Type", "type"):
            value = node.get(key)
            if isinstance(value, str) and value.strip():
                local_hint = value.strip()
                break
        for key, value in node.items():
            if str(key).lower() in _SKIP_KEYS:
                continue
            child_source = _child_source(source, key)
            child_token = local_token
            if (
                not child_token
                and isinstance(value, dict)
                and child_source.startswith("catalog")
                and _ID_KEY_RE.fullmatch(str(key))
                and str(key).lower() not in _STRUCT_KEYS
            ):
                child_token = str(key)[:128]
            _walk(value, child_source, local_name, local_hint, child_token, bucket)
        return
    if isinstance(node, list):
        for item in node:
            _walk(item, source, name, hint, token, bucket)
        return
    if isinstance(node, str):
        _add(bucket, node, source=source, name=name, hint=hint, token=token)


def rows_from_trees(parts: list[tuple[Any, str]]) -> list[dict[str, Any]]:
    """Junta árvores JSON já em memória. Usado pelos testes e pelo coletor."""
    bucket: dict[str, dict[str, Any]] = {}
    for node, source in parts:
        _walk(node, source, "", "", "", bucket)
    return _finalize(bucket)


def _finalize(bucket: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in bucket.values():
        sources = sorted(item for item in row["sources"] if item)[:32]
        rows.append(
            {
                "ident_norm": row["ident_norm"],
                "identifier": row["identifier"],
                "kind": row["kind"] if row["kind"] in KINDS else "outro",
                "display_name": row["display_name"] or "",
                "token": (row["token"] or "")[:128],
                "sources": sources,
            }
        )
    rows.sort(key=lambda item: item["identifier"].lower())
    return rows


def _ingest_loose_text(raw: str, source: str, bucket: dict[str, dict[str, Any]]) -> None:
    """Acha caminhos no texto inteiro. Cada match é curto; o arquivo pode ser grande."""
    for match in _ENGRAM_RE.finditer(raw or ""):
        _add(bucket, match.group(0), source=source, hint="engrama")
    for match in _GAME_RE.finditer(raw or ""):
        _add(bucket, match.group(0), source=source)


def _ingest_engram_text(raw: str, source: str, bucket: dict[str, dict[str, Any]]) -> None:
    _ingest_loose_text(raw, source, bucket)
    for match in _ENGRAM_TUPLE_RE.finditer(raw or ""):
        _add(
            bucket,
            match.group(1),
            source=source,
            name=match.group(2),
            hint="engrama",
        )


def _read_text(path: Path) -> str | None:
    try:
        if not path.is_file():
            return None
        if path.stat().st_size > _MAX_FILE_BYTES:
            log.warning("blueprint_index: arquivo grande demais, ignorado: %s", path.name)
            return None
        return path.read_text(encoding="utf-8-sig")
    except OSError as exc:
        log.warning("blueprint_index: falha ao ler %s: %s", path.name, exc)
        raise


def _load_json_file(path: Path) -> Any:
    raw = _read_text(path)
    if raw is None:
        return None
    return json.loads(raw)


def _load_csv_rows(path: Path) -> list[dict[str, str]] | None:
    raw = _read_text(path)
    if raw is None:
        return None
    return list(csv.DictReader(io.StringIO(raw)))


def _remember_file(
    path: Path,
    source: str,
    bucket: dict[str, dict[str, Any]],
    errors: list[str],
    *,
    csv_file: bool = False,
    engram_text: bool = False,
) -> None:
    if not path.is_file():
        return
    try:
        if engram_text:
            raw = _read_text(path)
            if raw:
                _ingest_engram_text(raw, source, bucket)
            return
        if csv_file:
            rows = _load_csv_rows(path)
            if rows is not None:
                _walk(rows, source, "", "", "", bucket)
            return
        loaded = _load_json_file(path)
        if loaded is None:
            return
        if source == "beacon_cache" and isinstance(loaded, dict):
            loaded = loaded.get("blueprints") or []
        _walk(loaded, source, "", "", "", bucket)
    except Exception as exc:
        log.warning("blueprint_index: falha em %s: %s", path.name, exc)
        errors.append(path.name)


def _existing_tables(engine: Any) -> set[str]:
    try:
        return set(inspect(engine).get_table_names())
    except Exception as exc:
        log.warning("blueprint_index: tabelas indisponíveis: %s", exc)
        return set()


def _collect_database(engine: Any, bucket: dict[str, dict[str, Any]], errors: list[str]) -> None:
    if engine is None:
        return
    tables = _existing_tables(engine)
    try:
        with engine.connect() as conn:
            if "market_species" in tables:
                result = conn.execute(
                    text(
                        "SELECT blueprint_path, display_name, species_key "
                        "FROM market_species"
                    )
                )
                for path, name, key in result:
                    _add(
                        bucket,
                        str(path or ""),
                        source="market_species",
                        name=str(name or ""),
                        token=str(key or ""),
                    )
            if "market_species_aliases" in tables:
                result = conn.execute(
                    text(
                        "SELECT blueprint_path, variant_label "
                        "FROM market_species_aliases"
                    )
                )
                for path, label in result:
                    _add(
                        bucket,
                        str(path or ""),
                        source="market_aliases",
                        name=str(label or ""),
                    )
    except Exception as exc:
        log.warning("blueprint_index: leitura de espécies: %s", exc)
        errors.append("market_species")


def _catalog_files(repo: Path, include_live: bool) -> list[Path]:
    found: list[Path] = []
    seen: set[Path] = set()
    bundled = repo / "plugin" / "CustomShop" / "catalog.json"
    if bundled.is_file():
        found.append(bundled)
        try:
            seen.add(bundled.resolve())
        except OSError:
            seen.add(bundled)
    if not include_live:
        return found
    override = os.environ.get("ARKSHOP_CONFIG_PATH", "").strip()
    if override:
        live = Path(override)
    else:
        try:
            from src.shop_integration import canonical_master_catalog_path

            live = Path(canonical_master_catalog_path())
        except Exception as exc:
            log.warning("blueprint_index: catálogo configurado indisponível: %s", exc)
            return found
    if not live.is_file():
        return found
    try:
        key = live.resolve()
    except OSError:
        key = live
    if key not in seen:
        found.append(live)
    return found


def _server_files() -> list[tuple[Path, str]]:
    found: list[tuple[Path, str]] = []
    seen: set[Path] = set()

    def _push(path: Path, source: str) -> None:
        if not path.is_file():
            return
        try:
            key = path.resolve()
        except OSError:
            key = path
        if key in seen:
            return
        seen.add(key)
        found.append((path, source))

    env_dir = os.environ.get("ARKSHOP_DATA_DIR", "").strip()
    if env_dir:
        _push(Path(env_dir) / "servers.json", "servers_json")
    appdata = os.environ.get("APPDATA", "").strip()
    if appdata:
        base = Path(appdata) / "ARKLAND-ServerManager"
        _push(base / "asm_servers.json", "asm_servers")
        _push(base / "servers.json", "asm_servers")
    if not env_dir:
        try:
            from src.shop_integration import webstore_data_dir

            _push(Path(webstore_data_dir()) / "servers.json", "servers_json")
        except Exception as exc:
            log.warning("blueprint_index: servers.json da loja: %s", exc)
    return found


def collect_blueprint_index(
    *,
    repo_root: Path | None = None,
    include_live: bool = True,
    include_bundled: bool = True,
    engine: Any = None,
) -> dict[str, Any]:
    """Varre as fontes conhecidas uma vez. Não grava catálogo nem outras tabelas."""
    repo = Path(repo_root) if repo_root is not None else _repo_root()
    bucket: dict[str, dict[str, Any]] = {}
    errors: list[str] = []
    if include_bundled:
        data_dir = _module_dir() / "data"
        for filename, source in _DATA_FILES:
            _remember_file(data_dir / filename, source, bucket, errors)
        tools = repo / "tools"
        for filename, source in _TOOL_FILES:
            _remember_file(
                tools / filename,
                source,
                bucket,
                errors,
                csv_file=filename.endswith(".csv"),
            )
        for path, source in (
            (repo / "src" / "asm_ui" / "asm_engram_editor.py", "asm_known_engrams"),
            (repo / "src" / "asm_engine" / "asm_engram_entries.py", "asm_engram_entries"),
        ):
            _remember_file(path, source, bucket, errors, engram_text=True)
        _remember_file(
            repo / ".cache" / "spawnexact_blueprints.json",
            "spawnexact_cache",
            bucket,
            errors,
        )
        for path in _catalog_files(repo, include_live=False):
            _remember_file(path, "catalog", bucket, errors)
    if include_live:
        already: set[Path] = set()
        if include_bundled:
            for path in _catalog_files(repo, include_live=False):
                try:
                    already.add(path.resolve())
                except OSError:
                    already.add(path)
        for path in _catalog_files(repo, include_live=True):
            try:
                key = path.resolve()
            except OSError:
                key = path
            if key in already:
                continue
            _remember_file(path, "catalog", bucket, errors)
        beacon = (
            Path(os.environ.get("APPDATA", str(Path.home())))
            / "ARKLAND-ServerManager"
            / "beacon_blueprints_cache.json"
        )
        _remember_file(beacon, "beacon_cache", bucket, errors)
        for path, source in _server_files():
            try:
                raw = _read_text(path)
            except OSError:
                errors.append(path.name)
                continue
            if raw:
                _ingest_loose_text(raw, source, bucket)
        _collect_database(engine, bucket, errors)
    elif engine is not None:
        _collect_database(engine, bucket, errors)
    return {"rows": _finalize(bucket), "errors": errors}


def _db_params(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    payload: list[dict[str, Any]] = []
    for row in rows:
        sources = row.get("sources") or []
        if isinstance(sources, str):
            sources_json = sources
        else:
            sources_json = json.dumps(list(sources), ensure_ascii=False)
        payload.append(
            {
                "ident_norm": row["ident_norm"],
                "identifier": row["identifier"],
                "kind": row["kind"],
                "display_name": row.get("display_name") or "",
                "token": row.get("token") or "",
                "sources_json": sources_json,
                "note": row.get("note") or "",
                "manual": 1 if row.get("manual") else 0,
                "mod_name": (row.get("mod_name") or "")[:200],
                "class_name": (
                    row.get("class_name") or class_from_blueprint(str(row.get("identifier") or ""))
                )[:200],
                "updated_at": now,
            }
        )
    return payload


def _apply_rows(engine: Any, rows: list[dict[str, Any]]) -> None:
    """Grava a varredura automática. Cadastro manual (manual=1) permanece."""
    statement = text(
        """
        INSERT INTO blueprint_index (
          ident_norm, identifier, kind, display_name, token, sources_json, note, manual,
          mod_name, class_name, updated_at
        ) VALUES (
          :ident_norm, :identifier, :kind, :display_name, :token, :sources_json, :note, :manual,
          :mod_name, :class_name, :updated_at
        )
        """
    )
    payload = _db_params(rows)
    with engine.begin() as conn:
        manual_norms = {
            str(row[0])
            for row in conn.execute(
                text("SELECT ident_norm FROM blueprint_index WHERE manual = 1")
            )
        }
        conn.execute(text("DELETE FROM blueprint_index WHERE manual = 0"))
        fresh: list[dict[str, Any]] = []
        incoming_norms = {row["ident_norm"] for row in payload}
        for row in payload:
            if row["ident_norm"] not in manual_norms:
                fresh.append(row)
                continue
            current = conn.execute(
                text(
                    "SELECT sources_json, display_name FROM blueprint_index "
                    "WHERE ident_norm = :ident_norm"
                ),
                {"ident_norm": row["ident_norm"]},
            ).fetchone()
            sources: set[str] = set()
            if current and current[0]:
                try:
                    loaded = json.loads(current[0])
                    if isinstance(loaded, list):
                        sources.update(str(item) for item in loaded)
                except (TypeError, ValueError):
                    sources = set()
            try:
                incoming = json.loads(row["sources_json"] or "[]")
                if isinstance(incoming, list):
                    sources.update(str(item) for item in incoming)
            except (TypeError, ValueError):
                pass
            sources.add("manual")
            conn.execute(
                text(
                    """
                    UPDATE blueprint_index
                    SET sources_json = :sources_json,
                        class_name = :class_name,
                        display_name = CASE
                          WHEN display_name IS NULL OR display_name = '' THEN :display_name
                          ELSE display_name
                        END,
                        updated_at = :updated_at
                    WHERE ident_norm = :ident_norm AND manual = 1
                    """
                ),
                {
                    "sources_json": json.dumps(sorted(sources), ensure_ascii=False),
                    "class_name": row["class_name"],
                    "display_name": row["display_name"],
                    "updated_at": row["updated_at"],
                    "ident_norm": row["ident_norm"],
                },
            )
        for norm in manual_norms - incoming_norms:
            conn.execute(
                text(
                    """
                    UPDATE blueprint_index
                    SET sources_json = :sources_json
                    WHERE ident_norm = :ident_norm AND manual = 1
                    """
                ),
                {
                    "sources_json": json.dumps(["manual"], ensure_ascii=False),
                    "ident_norm": norm,
                },
            )
        for offset in range(0, len(fresh), 400):
            conn.execute(statement, fresh[offset : offset + 400])


def _count(engine: Any) -> int:
    with engine.connect() as conn:
        value = conn.execute(text(f"SELECT COUNT(*) FROM {TABLE}")).scalar()
    return int(value or 0)


def sync_blueprint_index(
    engine: Any,
    *,
    force: bool = False,
    rows: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Recria o índice. Em pytest, sem ``force`` nem ``rows``, não varre o disco."""
    ensure_blueprint_index_schema(engine)
    if rows is None and not force and os.environ.get("PYTEST_CURRENT_TEST"):
        return {"ok": True, "skipped": True, "count": _count(engine)}
    if rows is None:
        packed = collect_blueprint_index(include_live=True, engine=engine)
        if not packed["rows"] and packed["errors"]:
            return {
                "ok": True,
                "kept": True,
                "count": _count(engine),
                "warning": "Falha ao ler fontes; índice anterior mantido.",
            }
        rows = packed["rows"]
    _apply_rows(engine, rows)
    log.info("blueprint_index: %s caminhos automáticos", len(rows))
    return {"ok": True, "skipped": False, "count": _count(engine)}


def _parse_sources(raw: Any) -> list[str]:
    try:
        loaded = json.loads(raw or "[]")
    except (TypeError, ValueError):
        return []
    if not isinstance(loaded, list):
        return []
    return [str(item) for item in loaded]


def _project_sources(sources: list[str]) -> list[str]:
    return [item for item in sources if item != "manual"]


def _origin_message(sources: list[str]) -> str:
    labels = [SOURCE_LABELS.get(item, item) for item in _project_sources(sources)]
    shown = ", ".join(labels) if labels else "o projeto"
    return f"Essa blueprint já existe no projeto ({shown}). Atualize na origem."


def _page_only(manual: Any, sources: list[str]) -> bool:
    return bool(manual) and not _project_sources(sources)


def _row_from_db(row: Any) -> dict[str, Any]:
    sources = _parse_sources(row[7])
    manual = bool(row[9])
    return {
        "ident_norm": row[0],
        "identifier": row[1],
        "kind": row[2],
        "display_name": row[3] or "",
        "mod_name": row[4] or "",
        "class_name": row[5] or "",
        "token": row[6] or "",
        "sources": sources,
        "note": row[8] or "",
        "manual": manual,
        "editable": _page_only(manual, sources),
    }


_ROW_SQL = (
    "SELECT ident_norm, identifier, kind, display_name, mod_name, class_name, "
    "token, sources_json, note, manual FROM blueprint_index "
)


def _load_row(conn: Any, ident_norm: str) -> dict[str, Any] | None:
    found = conn.execute(
        text(_ROW_SQL + "WHERE ident_norm = :ident_norm"),
        {"ident_norm": ident_norm},
    ).fetchone()
    if found is None:
        return None
    return _row_from_db(found)


def _class_lookup_keys(class_name: str) -> list[str]:
    value = (class_name or "").strip()
    if len(value) < 3:
        return []
    keys = [value]
    if not _CLASS_ONLY_RE.fullmatch(value):
        if value.lower().endswith("_c") and len(value) > 2:
            keys.append(value[:-2])
        else:
            keys.append(value + "_C")
    unique: list[str] = []
    seen: set[str] = set()
    for key in keys:
        marker = key.lower()
        if marker in seen:
            continue
        seen.add(marker)
        unique.append(key)
    return unique


def _load_by_class(conn: Any, class_name: str, *, exclude_norm: str = "") -> dict[str, Any] | None:
    keys = _class_lookup_keys(class_name)
    if not keys:
        return None
    clauses = " OR ".join(f"class_name = :class_{index}" for index in range(len(keys)))
    params: dict[str, Any] = {f"class_{index}": key for index, key in enumerate(keys)}
    params["exclude_norm"] = exclude_norm
    found = conn.execute(
        text(
            _ROW_SQL
            + f"WHERE ({clauses}) AND ident_norm != :exclude_norm LIMIT 1"
        ),
        params,
    ).fetchone()
    if found is None:
        return None
    return _row_from_db(found)


def _reject_if_taken(existing: dict[str, Any] | None) -> None:
    if existing is None:
        return
    if _project_sources(existing["sources"]):
        raise BlueprintIndexError("duplicate", _origin_message(existing["sources"]))
    raise BlueprintIndexError("duplicate", "Esse cadastro já existe nesta página.")


def _manual_payload(
    *,
    identifier: str,
    kind: str,
    display_name: str,
    mod_name: str,
    note: str,
) -> dict[str, Any]:
    raw = (identifier or "").strip()
    if not raw:
        raise BlueprintIndexError("empty", "Informe a blueprint.")
    name = (display_name or "").strip()[:200]
    if not name:
        raise BlueprintIndexError("empty", "Informe o nome.")
    mod = (mod_name or "").strip()[:200]
    if not mod:
        raise BlueprintIndexError("empty", "Informe o mod.")
    kind_key = (kind or "").strip().lower()
    if kind_key not in FORM_KINDS:
        raise BlueprintIndexError(
            "kind",
            "Escolha o tipo: dino, sela, recurso, estrutura ou outro.",
        )
    found = extract_identifiers(raw)
    display = ""
    norm = ""
    if len(found) == 1:
        display, norm = found[0]
    elif len(found) > 1:
        raise BlueprintIndexError(
            "invalid",
            "Informe uma blueprint por vez.",
        )
    else:
        bare = raw.strip().strip('"').strip("'")
        if _CLASS_ONLY_RE.fullmatch(bare) and bare.startswith("PrimalItem_"):
            display, norm = bare, bare.lower()
        else:
            raise BlueprintIndexError(
                "invalid",
                "Use um caminho /Game/... ou uma classe EngramEntry_..._C ou PrimalItem_..._C.",
            )
    class_name = class_from_blueprint(raw)
    if not class_name:
        raise BlueprintIndexError(
            "invalid",
            "Não foi possível extrair a classe dessa blueprint.",
        )
    return {
        "ident_norm": norm,
        "identifier": display,
        "kind": kind_key,
        "display_name": name,
        "mod_name": mod,
        "class_name": class_name,
        "token": _short_token(display),
        "note": (note or "").strip()[:500],
        "sources": ["manual"],
        "manual": 1,
    }


def add_manual_blueprint(
    engine: Any,
    *,
    identifier: str,
    kind: str,
    display_name: str = "",
    mod_name: str = "",
    note: str = "",
) -> dict[str, Any]:
    """Cadastra um caminho fora do projeto. Não grava catálogo, JSON nem ini."""
    ensure_blueprint_index_schema(engine)
    payload_row = _manual_payload(
        identifier=identifier,
        kind=kind,
        display_name=display_name,
        mod_name=mod_name,
        note=note,
    )
    with engine.connect() as conn:
        _reject_if_taken(_load_row(conn, payload_row["ident_norm"]))
        _reject_if_taken(
            _load_by_class(conn, payload_row["class_name"], exclude_norm=payload_row["ident_norm"])
        )
    payload = _db_params([payload_row])[0]
    payload["class_name"] = payload_row["class_name"]
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO blueprint_index (
                  ident_norm, identifier, kind, display_name, token, sources_json,
                  note, manual, mod_name, class_name, updated_at
                ) VALUES (
                  :ident_norm, :identifier, :kind, :display_name, :token, :sources_json,
                  :note, :manual, :mod_name, :class_name, :updated_at
                )
                """
            ),
            payload,
        )
    return {
        "ident_norm": payload_row["ident_norm"],
        "identifier": payload_row["identifier"],
        "kind": payload_row["kind"],
        "display_name": payload_row["display_name"],
        "mod_name": payload_row["mod_name"],
        "class_name": payload_row["class_name"],
        "token": payload_row["token"],
        "note": payload_row["note"],
        "manual": True,
        "editable": True,
        "sources": ["manual"],
    }


def update_manual_blueprint(
    engine: Any,
    *,
    ident_norm: str,
    identifier: str,
    kind: str,
    display_name: str = "",
    mod_name: str = "",
    note: str = "",
) -> dict[str, Any]:
    """Altera só um cadastro feito nesta página e que ainda não está no projeto."""
    ensure_blueprint_index_schema(engine)
    current_norm = (ident_norm or "").strip()
    if not current_norm:
        raise BlueprintIndexError("empty", "Cadastro não encontrado.")
    payload_row = _manual_payload(
        identifier=identifier,
        kind=kind,
        display_name=display_name,
        mod_name=mod_name,
        note=note,
    )
    with engine.connect() as conn:
        current = _load_row(conn, current_norm)
        if current is None:
            raise BlueprintIndexError("missing", "Cadastro não encontrado.")
        if not current["editable"]:
            raise BlueprintIndexError("locked", _origin_message(current["sources"]))
        if payload_row["ident_norm"] != current_norm:
            _reject_if_taken(_load_row(conn, payload_row["ident_norm"]))
        _reject_if_taken(
            _load_by_class(
                conn,
                payload_row["class_name"],
                exclude_norm=current_norm,
            )
        )
    payload = _db_params([payload_row])[0]
    payload["class_name"] = payload_row["class_name"]
    payload["old_norm"] = current_norm
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                UPDATE blueprint_index
                SET ident_norm = :ident_norm,
                    identifier = :identifier,
                    kind = :kind,
                    display_name = :display_name,
                    token = :token,
                    note = :note,
                    mod_name = :mod_name,
                    class_name = :class_name,
                    updated_at = :updated_at
                WHERE ident_norm = :old_norm AND manual = 1
                """
            ),
            payload,
        )
    return {
        "ident_norm": payload_row["ident_norm"],
        "identifier": payload_row["identifier"],
        "kind": payload_row["kind"],
        "display_name": payload_row["display_name"],
        "mod_name": payload_row["mod_name"],
        "class_name": payload_row["class_name"],
        "token": payload_row["token"],
        "note": payload_row["note"],
        "manual": True,
        "editable": True,
        "sources": ["manual"],
    }


def delete_manual_blueprint(engine: Any, *, ident_norm: str) -> dict[str, Any]:
    """Exclui só um cadastro feito nesta página e que ainda não está no projeto."""
    ensure_blueprint_index_schema(engine)
    current_norm = (ident_norm or "").strip()
    if not current_norm:
        raise BlueprintIndexError("empty", "Cadastro não encontrado.")
    with engine.begin() as conn:
        current = _load_row(conn, current_norm)
        if current is None:
            raise BlueprintIndexError("missing", "Cadastro não encontrado.")
        if not current["editable"]:
            raise BlueprintIndexError("locked", _origin_message(current["sources"]))
        conn.execute(
            text(
                "DELETE FROM blueprint_index WHERE ident_norm = :ident_norm AND manual = 1"
            ),
            {"ident_norm": current_norm},
        )
    return {"deleted": True, "ident_norm": current_norm}


def _like_contains(value: str) -> str:
    """Trecho literal para LIKE. ``!`` é o escape, igual no SQLite e no MySQL."""
    escaped = value.replace("!", "!!").replace("%", "!%").replace("_", "!_")
    return f"%{escaped}%"


def list_blueprint_index(
    engine: Any,
    *,
    q: str = "",
    kind: str = "",
    source: str = "",
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    """Lê o índice já gravado. O filtro não varre o disco."""
    ensure_blueprint_index_schema(engine)
    clauses: list[str] = []
    params: dict[str, Any] = {}
    query = (q or "").strip()[:200]
    if query:
        params["q"] = _like_contains(query)
        clauses.append(
            "(identifier LIKE :q ESCAPE '!' OR display_name LIKE :q ESCAPE '!' "
            "OR token LIKE :q ESCAPE '!' OR ident_norm LIKE :q ESCAPE '!' "
            "OR note LIKE :q ESCAPE '!' OR mod_name LIKE :q ESCAPE '!' "
            "OR class_name LIKE :q ESCAPE '!')"
        )
    kind_key = (kind or "").strip().lower()
    if kind_key in KINDS:
        clauses.append("kind = :kind")
        params["kind"] = kind_key
    source_key = (source or "").strip().lower()
    if _SOURCE_RE.fullmatch(source_key):
        clauses.append("sources_json LIKE :source ESCAPE '!'")
        params["source"] = _like_contains(f'"{source_key}"')
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    safe_limit = max(1, min(int(limit or 50), 200))
    safe_offset = max(0, int(offset or 0))
    with engine.connect() as conn:
        total = conn.execute(
            text(f"SELECT COUNT(*) FROM blueprint_index{where}"),
            params,
        ).scalar()
        params["limit"] = safe_limit
        params["offset"] = safe_offset
        result = conn.execute(
            text(
                "SELECT ident_norm, identifier, kind, display_name, mod_name, class_name, "
                "token, sources_json, note, manual "
                f"FROM blueprint_index{where} "
                "ORDER BY identifier LIMIT :limit OFFSET :offset"
            ),
            params,
        )
        page: list[dict[str, Any]] = []
        for row in result:
            page.append(_row_from_db(row))
    return {
        "rows": page,
        "total": int(total or 0),
        "limit": safe_limit,
        "offset": safe_offset,
    }
