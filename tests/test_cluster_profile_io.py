"""Testes de exportação/importação de perfis Cross-ARK entre máquinas."""
import json
import uuid

from src.pages.cluster_profile_io import (
    FORMAT_ID,
    build_export_document,
    merge_imported_profile,
    parse_import_document,
)
from src.server_config import ClusterProfile


def _sample_profile() -> ClusterProfile:
    return ClusterProfile(
        id="orig-id",
        name="Meu Cluster",
        mode="network",
        cluster_id="abc123clusterid00001",
        cluster_dir=r"\\NAS\ARKCluster",
        prevent_download_dinos=True,
        sync_enabled=True,
        local_cluster_dir=r"C:\ARK\clusters",
        sync_interval=45,
    )


def test_build_export_document_structure():
    class FakeApp:
        pass

    app = FakeApp()
    prof = _sample_profile()

    class FakeCM:
        servers = []
        clusters = []

        def get_cluster(self, cid):
            return prof if cid == prof.id else None

    app.config_manager = FakeCM()
    app._cluster_selected_id = ""

    doc = build_export_document(app, prof.id)
    assert doc["format"] == FORMAT_ID
    assert doc["version"] == 1
    assert doc["profile"]["cluster_id"] == "abc123clusterid00001"
    assert doc["profile"]["cluster_dir"] == r"\\NAS\ARKCluster"
    assert "id" not in doc["profile"]
    assert "exported_at" in doc
    assert "source_host" in doc


def test_parse_import_document_assigns_new_id():
    prof = _sample_profile()
    doc = {
        "format": FORMAT_ID,
        "version": 1,
        "profile": prof.to_dict(),
        "linked_servers": [{"name": "Island", "map": "TheIsland", "port": 7777}],
    }
    raw = json.dumps(doc)
    imported, hints, meta = parse_import_document(raw)
    assert imported.cluster_id == prof.cluster_id
    assert imported.name == prof.name
    assert imported.id != prof.id
    assert uuid.UUID(imported.id)
    assert len(hints) == 1
    assert meta["format"] == FORMAT_ID


def test_parse_legacy_flat_json():
    prof = _sample_profile()
    raw = json.dumps(prof.to_dict())
    imported, hints, meta = parse_import_document(raw)
    assert imported.cluster_id == prof.cluster_id
    assert hints == []
    assert meta == {}


def test_merge_imported_profile_avoids_duplicate_names():
    class FakeCM:
        clusters = [ClusterProfile(name="Meu Cluster")]

        def add_cluster(self, p):
            self.clusters.append(p)

    app = type("App", (), {"config_manager": FakeCM()})()
    prof = _sample_profile()
    merged = merge_imported_profile(app, prof)
    assert merged.name == "Meu Cluster (importado)"


def test_round_trip_file(tmp_path):
    from src.pages.cluster_profile_io import export_cluster_profile, import_cluster_profile_from_file

    class FakeApp:
        pass

    app = FakeApp()
    prof = _sample_profile()

    class FakeCM:
        clusters = []
        servers = []

        def get_cluster(self, cid):
            return prof if cid == prof.id else None

        def add_cluster(self, p):
            self.clusters.append(p)

    app.config_manager = FakeCM()
    app._cluster_selected_id = ""

    out = tmp_path / "test.arkcluster"
    export_cluster_profile(app, prof.id, str(out))
    assert out.exists()

    imported, hints, _ = import_cluster_profile_from_file(app, str(out))
    assert imported.cluster_id == prof.cluster_id
    assert imported.cluster_dir == prof.cluster_dir
    assert imported.sync_enabled is True
    assert len(app.config_manager.clusters) == 1
