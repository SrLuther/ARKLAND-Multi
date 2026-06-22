"""Testes do simulador de viagem Cross-ARK."""
import time
from pathlib import Path

from src.cluster_probe import (
    probe_path_read_write,
    run_cluster_travel_test,
    scan_transfer_files,
)
from src.server_config import ClusterProfile


def test_probe_read_write(tmp_path):
    ok, note = probe_path_read_write(str(tmp_path / "cluster"))
    assert ok is True
    assert "OK" in note


def test_scan_transfer_files_finds_arkprofile(tmp_path):
    cid = "MyCluster2024"
    base = tmp_path / "shared" / cid
    base.mkdir(parents=True)
    profile = base / "76561198000000001.arkprofile"
    profile.write_bytes(b"x" * 120)
    found = scan_transfer_files(str(tmp_path / "shared"), cid)
    assert len(found) == 1
    assert found[0].kind == "Sobrevivente"


def test_travel_test_two_members(tmp_path):
    prof = ClusterProfile(
        name="Test",
        mode="local",
        cluster_id="clusterA",
        cluster_dir=str(tmp_path / "cluster"),
    )
    shared = Path(prof.cluster_dir)
    shared.mkdir(parents=True)
    (shared / prof.cluster_id).mkdir()

    class _Srv:
        id = "1"
        name = "Island"
        map = "TheIsland"
        server_port = 7777
        install_dir = str(tmp_path / "ark1")
        cluster_profile_id = ""
        cluster = type("C", (), {
            "enabled": True,
            "cluster_id": prof.cluster_id,
            "cluster_dir_override": prof.cluster_dir,
            "no_transfer_from_filtering": False,
            "prevent_download_survivors": False,
            "prevent_download_items": False,
            "prevent_download_dinos": False,
        })()
        advanced_settings = type("A", (), {
            "prevent_download_survivors": False,
            "prevent_download_items": False,
            "prevent_download_dinos": False,
        })()

    class _Srv2(_Srv):
        id = "2"
        name = "Ragnarok"
        map = "Ragnarok"
        server_port = 7779
        install_dir = str(tmp_path / "ark2")

    result = run_cluster_travel_test(prof, [], [_Srv(), _Srv2()])
    assert len(result.members) == 2
    assert result.shared_dir
    assert len(result.simulated_listings) == 2
