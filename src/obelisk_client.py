"""
Fase 6.2 — Cliente de manifesto de espécies (ArkUtils Obelisk).

Fonte: arkutils/Obelisk — data/asb/values.json (atualizado diariamente).
Formato: ASB 1.x — campo "species" com blueprintPath + variants[].
"""
from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from typing import Callable, List, Optional

_OBELISK_BASE = "https://raw.githubusercontent.com/arkutils/Obelisk/master/data/asb/"
_VALUES_URL   = _OBELISK_BASE + "values.json"
_CACHE_FILE   = Path(__file__).parent.parent / ".cache" / "obelisk_values.json"
_CACHE_TTL    = 86400  # 1 dia em segundos

# Variantes consideradas "ruído" para exibição (já estão implícitas no contexto)
_SKIP_VARIANTS = {"TheIsland", "Scorched", "Aberration", "Extinction",
                  "Genesis", "Genesis2", "LostIsland", "Fjordur",
                  "CrystalIsles", "Valguero"}


class Species:
    __slots__ = ("name", "blueprint", "mod_id", "dino_name_tag", "no_spawner", "variants")

    def __init__(self, name: str, blueprint: str, mod_id: Optional[str],
                 dino_name_tag: str, no_spawner: bool,
                 variants: Optional[List[str]] = None) -> None:
        self.name          = name
        self.blueprint     = blueprint
        self.mod_id        = mod_id
        self.dino_name_tag = dino_name_tag
        self.no_spawner    = no_spawner
        self.variants: List[str] = variants or []

    def __repr__(self) -> str:
        return f"Species({self.name!r})"

    def display_name(self) -> str:
        """Nome exibido na lista: nome + variantes relevantes + mod se houver."""
        tags: list[str] = [v for v in self.variants if v not in _SKIP_VARIANTS]
        suffix = ""
        if tags:
            suffix = f"  ({', '.join(tags)})"
        if self.mod_id:
            suffix += f"  [mod {self.mod_id}]"
        return f"{self.name}{suffix}"


class ObeliskClient:
    """Gerencia o manifesto de espécies do ArkUtils."""

    def __init__(self) -> None:
        self._species: list[Species] = []
        self._loaded = False
        self._lock   = threading.Lock()

    # ── Carregamento ─────────────────────────────────────────────────────────

    def load(self, on_done: Optional[Callable[[bool, str], None]] = None) -> None:
        """Carrega o manifesto em background. Usa cache se fresco."""
        threading.Thread(target=self._load_worker, args=(on_done,), daemon=True).start()

    def _load_worker(self, on_done: Optional[Callable[[bool, str], None]]) -> None:
        try:
            data = self._fetch_or_cache()
            species = _parse_species(data)
            with self._lock:
                self._species = species
                self._loaded  = True
            if on_done:
                on_done(True, f"{len(species)} espécies carregadas.")
        except Exception as exc:
            if on_done:
                on_done(False, str(exc))

    def _fetch_or_cache(self) -> dict:
        _CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        if _CACHE_FILE.exists():
            age = time.time() - _CACHE_FILE.stat().st_mtime
            if age < _CACHE_TTL:
                return json.loads(_CACHE_FILE.read_text(encoding="utf-8"))
        import urllib.request
        with urllib.request.urlopen(_VALUES_URL, timeout=20) as resp:
            raw = resp.read()
        _CACHE_FILE.write_bytes(raw)
        return json.loads(raw)

    # ── Consulta ─────────────────────────────────────────────────────────────

    @property
    def loaded(self) -> bool:
        with self._lock:
            return self._loaded

    def all_species(self, mod_ids: Optional[list[str]] = None) -> list[Species]:
        """Retorna lista filtrada. None = somente oficiais + mod_ids."""
        with self._lock:
            s = self._species
        if mod_ids is None:
            return [x for x in s if x.mod_id is None]
        allowed = set(mod_ids)
        return [x for x in s if x.mod_id is None or x.mod_id in allowed]

    def search(self, query: str, mod_ids: Optional[list[str]] = None) -> list[Species]:
        q = query.lower().strip()
        if not q:
            return self.all_species(mod_ids)
        return [
            sp for sp in self.all_species(mod_ids)
            if q in sp.name.lower()
            or q in sp.blueprint.lower()
            or any(q in v.lower() for v in sp.variants)
        ]

    def by_blueprint(self, bp: str) -> Optional[Species]:
        with self._lock:
            s = self._species
        for sp in s:
            if sp.blueprint == bp:
                return sp
        return None

    def invalidate_cache(self) -> None:
        try:
            _CACHE_FILE.unlink(missing_ok=True)
        except OSError:
            pass


def _parse_species(data: dict) -> list[Species]:
    """Parseia o values.json do Obelisk (formato 1.x ASB).

    Deduplicação: blueprints idênticos são descartados (só mantém o primeiro).
    Variantes: exibidas entre parênteses, exceto nomes de mapa (ruído).
    """
    raw = data.get("species") or []
    result: list[Species] = []
    seen_blueprints: set[str] = set()

    for item in raw:
        name    = item.get("name") or ""
        bp_path = item.get("blueprintPath") or ""
        if not name or not bp_path:
            continue

        # Reconstrói o blueprint no formato exigido pelo jogo
        if not bp_path.startswith("Blueprint'"):
            cls_name = bp_path.rsplit("/", 1)[-1]
            bp = f"Blueprint'{bp_path}.{cls_name}'"
        else:
            bp = bp_path

        # Descarta blueprint duplicado
        if bp in seen_blueprints:
            continue
        seen_blueprints.add(bp)

        variants: list[str] = item.get("variants") or []
        mod_obj  = item.get("mod") or {}
        mod_id   = mod_obj.get("id") if isinstance(mod_obj, dict) else None
        tag      = item.get("dinoNameTag") or item.get("nameTag") or ""
        no_sp    = bool(item.get("noSpawner") or False)

        result.append(Species(name, bp, mod_id, tag, no_sp, variants))

    return sorted(result, key=lambda s: s.display_name().lower())


# Instância singleton
_default_client = ObeliskClient()


def get_client() -> ObeliskClient:
    return _default_client
