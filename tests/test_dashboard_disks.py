"""Testes — métricas de disco no dashboard."""
from __future__ import annotations

from src.asm_ui.asm_dashboard import _format_disk_gb, _get_disk_usage


def test_format_disk_gb():
    assert _format_disk_gb(50.5) == "50.5 GB"
    assert _format_disk_gb(512) == "512 GB"
    assert _format_disk_gb(2048) == "2.0 TB"


def test_get_disk_usage_returns_list():
    disks = _get_disk_usage()
    assert isinstance(disks, list)
    for d in disks:
        assert "mount" in d
        assert d["free_gb"] <= d["total_gb"]
        assert 0 <= d["used_pct"] <= 100
