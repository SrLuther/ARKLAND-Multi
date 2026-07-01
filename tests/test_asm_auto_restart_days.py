"""Testes de reinício automático por dia da semana (TEK)."""
from __future__ import annotations

from src.asm_engine.asm_server_config import AsmServerConfig
from src.pages.asm_scheduler_tick import _auto_restart_days_list


def test_auto_restart_days_default_all_week():
    srv = AsmServerConfig()
    assert _auto_restart_days_list(srv) == list(range(7))


def test_auto_restart_days_respects_custom_list():
    srv = AsmServerConfig(auto_restart_days=[0, 2, 4])
    assert _auto_restart_days_list(srv) == [0, 2, 4]


def test_auto_restart_days_empty_means_disabled():
    srv = AsmServerConfig(auto_restart_days=[])
    assert _auto_restart_days_list(srv) == []


def test_config_roundtrip_days():
    srv = AsmServerConfig(auto_restart_days=[1, 3, 5])
    data = srv.to_dict()
    restored = AsmServerConfig.from_dict(data)
    assert restored.auto_restart_days == [1, 3, 5]
