"""Testes da biblioteca global de broadcasts TEK."""
import json
import uuid

from src.pages.broadcast_profile_io import (
    FORMAT_ID,
    build_export_document,
    get_library,
    merge_library,
    normalize_entry,
    parse_import_document,
    set_library,
)


def _sample_entries():
    return [
        {
            "id": "aaa-111",
            "label": "Reinício",
            "message": "Servidor reinicia em 5 minutos",
            "created_at": "2026-01-01T12:00:00+00:00",
            "updated_at": "2026-01-01T12:00:00+00:00",
        },
        {
            "id": "bbb-222",
            "label": "Evento",
            "message": "2x XP ativo!",
            "created_at": "2026-01-02T12:00:00+00:00",
            "updated_at": "2026-01-02T12:00:00+00:00",
        },
    ]


class _FakeConfig:
    def __init__(self, lib=None):
        from src.config_manager import BroadcastTekConfig
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


def test_normalize_entry_requires_fields():
    try:
        normalize_entry({"label": "", "message": "x"})
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_normalize_entry_assigns_id():
    e = normalize_entry({"label": "A", "message": "B"})
    assert e["label"] == "A"
    assert uuid.UUID(e["id"])


def test_build_export_document():
    app = _FakeApp(_sample_entries())
    doc = build_export_document(app)
    assert doc["format"] == FORMAT_ID
    assert doc["version"] == 1
    assert len(doc["messages"]) == 2
    assert doc["messages"][0]["label"] == "Reinício"


def test_parse_import_document():
    doc = build_export_document(_FakeApp(_sample_entries()))
    messages, meta = parse_import_document(json.dumps(doc))
    assert len(messages) == 2
    assert meta["format"] == FORMAT_ID


def test_parse_invalid_raises():
    try:
        parse_import_document('{"foo": 1}')
        assert False
    except ValueError:
        pass


def test_merge_library_updates_and_adds():
    current = _sample_entries()
    imported = [
        {**current[0], "message": "Texto atualizado"},
        {"id": "ccc-333", "label": "Novo", "message": "Olá"},
    ]
    merged = merge_library(current, imported)
    assert len(merged) == 3
    by_id = {e["id"]: e for e in merged}
    assert by_id["aaa-111"]["message"] == "Texto atualizado"
    assert by_id["ccc-333"]["label"] == "Novo"


def test_set_and_get_library():
    app = _FakeApp()
    set_library(app, _sample_entries())
    assert len(get_library(app)) == 2
    assert app.config_manager.saved


def test_round_trip_file(tmp_path):
    from src.pages.broadcast_profile_io import export_broadcast_library, import_broadcast_library_from_file

    app = _FakeApp(_sample_entries())
    out = tmp_path / "test.arkbroadcast"
    export_broadcast_library(app, str(out))
    assert out.exists()

    app2 = _FakeApp()
    added, updated, meta = import_broadcast_library_from_file(app2, str(out), replace=False)
    assert added == 2
    assert updated == 0
    assert len(get_library(app2)) == 2
    assert meta["format"] == FORMAT_ID

    added2, updated2, _ = import_broadcast_library_from_file(
        app2, str(out), replace=False,
    )
    assert added2 == 0
    assert updated2 == 2

    app3 = _FakeApp([{"id": "x", "label": "Old", "message": "old"}])
    added3, _, _ = import_broadcast_library_from_file(app3, str(out), replace=True)
    assert added3 == 2
    assert len(get_library(app3)) == 2
