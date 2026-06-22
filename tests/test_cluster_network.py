"""Testes de caminhos de cluster Cross-ARK em rede."""
from src.cluster_paths import (
    default_local_cluster_dir,
    ensure_cluster_directories,
    format_cluster_dir_launch_flag,
    normalize_cluster_path,
    resolve_cluster_dir_override,
    validate_network_cluster_dir,
)
from src.server_config import ClusterProfile


def test_normalize_unc_forward_slashes():
    assert normalize_cluster_path("//192.168.1.10/ARKCluster") == r"\\192.168.1.10\ARKCluster"


def test_normalize_unc_single_leading_backslash():
    assert normalize_cluster_path(r"\NAS\ARKCluster").startswith("\\\\")


def test_launch_flag_quotes_unc():
    flag = format_cluster_dir_launch_flag(r"\\192.168.1.10\ARKCluster")
    assert flag.startswith('"')
    assert flag.endswith('"')
    assert r"\\192.168.1.10\ARKCluster" in flag


def test_launch_flag_no_quotes_simple_local():
    flag = format_cluster_dir_launch_flag(r"C:\ARKCluster")
    assert flag == r"-ClusterDirOverride=C:\ARKCluster"


def test_network_direct_unc_uses_shared_path():
    prof = ClusterProfile(mode="network", cluster_dir=r"\\NAS\ARK", sync_enabled=False)
    assert resolve_cluster_dir_override(prof, install_dir=r"D:\ARK") == r"\\NAS\ARK"


def test_network_sync_uses_per_server_local():
    prof = ClusterProfile(
        mode="network",
        cluster_dir=r"\\NAS\ARK",
        sync_enabled=True,
    )
    local = resolve_cluster_dir_override(prof, install_dir=r"D:\Servers\Island")
    assert local.endswith("clusters")
    assert "Island" in local


def test_default_local_cluster_dir():
    p = default_local_cluster_dir(r"C:\ARK")
    assert p.endswith(r"ShooterGame\Saved\clusters")


def test_ensure_creates_local_cluster_dir(tmp_path):
    from src.server_config import ClusterProfile

    install = tmp_path / "ARK"
    install.mkdir()
    prof = ClusterProfile(
        mode="network",
        cluster_dir=r"\\NAS\ARK",
        sync_enabled=True,
    )
    created, failed = ensure_cluster_directories(prof, [str(install)])
    expected = default_local_cluster_dir(str(install))
    assert expected in created or __import__("os").path.isdir(expected)
    assert not failed


def test_validate_warns_local_c_on_network_without_sync():
    prof = ClusterProfile(mode="network", cluster_dir=r"C:\ARKCluster", sync_enabled=False)
    msg = validate_network_cluster_dir(prof)
    assert msg is not None
    assert "UNC" in msg


def test_validate_warns_local_c_on_network_with_sync():
    prof = ClusterProfile(
        mode="network",
        cluster_dir=r"C:\ARKLAND SERVER\cluster\crossark",
        sync_enabled=True,
    )
    msg = validate_network_cluster_dir(prof)
    assert msg is not None
    assert "UNC" in msg
    assert "TODAS" in msg or "todas" in msg.lower()


def test_validate_ok_unc_with_sync():
    prof = ClusterProfile(
        mode="network",
        cluster_dir=r"\\192.168.1.10\ARKCluster\crossark",
        sync_enabled=True,
    )
    assert validate_network_cluster_dir(prof) is None
