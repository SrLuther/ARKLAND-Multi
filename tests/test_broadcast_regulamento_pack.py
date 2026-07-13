"""Testes do pacote Regulamento para broadcasts TEK."""
from src.pages.broadcast_profile_io import get_library, normalize_entry
from src.pages.broadcast_regulamento_pack import (
    PACK_VERSION,
    REGULAMENTO_SOURCE,
    build_regulamento_pack_entries,
    regulamento_pack_catalog,
    seed_regulamento_pack,
)
from src.config_manager import BroadcastTekConfig


class _FakeConfig:
    def __init__(self, lib=None):
        self.broadcast_library = list(lib or [])
        self.broadcast_tek = BroadcastTekConfig()


class _FakeCM:
    def __init__(self, lib=None):
        self.config = _FakeConfig(lib)
        self.saved = False

    def save(self):
        self.saved = True


class _FakeApp:
    def __init__(self, lib=None):
        self.config_manager = _FakeCM(lib)


def test_catalog_has_stable_ids_and_punitive_sections():
    catalog = regulamento_pack_catalog()
    assert len(catalog) >= 8
    ids = [e["id"] for e in catalog]
    assert len(ids) == len(set(ids))
    assert "arkland-reg-3.5-doacao-licenca" in ids
    assert "arkland-reg-5.4-rmt" in ids
    assert "arkland-reg-6.1-cheats" in ids
    sections = {e["section"] for e in catalog}
    assert "3.5" in sections
    assert PACK_VERSION


def test_build_entries_normalize_source_metadata():
    entries = build_regulamento_pack_entries()
    assert entries
    for e in entries:
        assert e["source"] == REGULAMENTO_SOURCE
        assert e["category"] == "Regulamento"
        assert e["section"]
        assert e["label"]
        assert e["message"].startswith("[ARKLAND]")
        assert len(e["message"]) <= 900


def test_normalize_entry_preserves_metadata():
    e = normalize_entry({
        "id": "arkland-reg-x",
        "label": "Teste",
        "message": "Mensagem curta",
        "source": "regulamento",
        "category": "Regulamento",
        "section": "3.5",
    })
    assert e["source"] == "regulamento"
    assert e["category"] == "Regulamento"
    assert e["section"] == "3.5"


def test_seed_adds_then_updates():
    app = _FakeApp([])
    added, updated = seed_regulamento_pack(app)
    assert added == len(regulamento_pack_catalog())
    assert updated == 0
    assert app.config_manager.saved
    lib = get_library(app)
    assert all(e.get("source") == REGULAMENTO_SOURCE for e in lib)

    # altera texto e re-seed com update
    lib[0]["message"] = "texto customizado antigo"
    app.config_manager.config.broadcast_library = lib
    added2, updated2 = seed_regulamento_pack(app, update_existing=True)
    assert added2 == 0
    assert updated2 == len(regulamento_pack_catalog())
    restored = get_library(app)
    assert restored[0]["message"].startswith("[ARKLAND]")


def test_seed_without_update_keeps_custom_text():
    app = _FakeApp([])
    seed_regulamento_pack(app)
    lib = get_library(app)
    target_id = lib[0]["id"]
    lib[0]["message"] = "texto editado pelo admin"
    app.config_manager.config.broadcast_library = lib

    added, updated = seed_regulamento_pack(app, update_existing=False)
    assert added == 0
    assert updated == 0
    kept = next(e for e in get_library(app) if e["id"] == target_id)
    assert kept["message"] == "texto editado pelo admin"
