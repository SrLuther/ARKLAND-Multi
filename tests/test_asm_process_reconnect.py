"""Testes de correspondência processo ↔ servidor TEK (scan/reconnect após restart)."""
from __future__ import annotations

from src.asm_engine.asm_server_config import AsmServerConfig
from src.asm_engine.asm_server_manager import (
    _cmdline_disambiguate,
    _cmdline_matches_server,
    _install_dir_in_process,
    _process_matches_cfg,
    _read_shooter_process_fields,
)


def _cfg(**kwargs) -> AsmServerConfig:
    base = {
        "id": "srv-1",
        "name": "The Island",
        "install_dir": r"D:\ARK\TheIsland",
        "server_map": "TheIsland",
        "server_port": 7777,
        "query_port": 27015,
    }
    base.update(kwargs)
    return AsmServerConfig.from_dict(base)


def test_install_dir_match_via_cmdline_when_exe_empty():
    cfg = _cfg()
    install = "d:/ark/theisland"
    cmdline = (
        r'"d:\ark\theisland\shootergame\binaries\win64\shootergameserver.exe" '
        "theisland?listen?port=7777?queryport=27015 -nosteamclient -game -server -log"
    )
    assert _install_dir_in_process("", cmdline, install)
    assert _process_matches_cfg(cfg, "", cmdline, {install: 1})


def test_shared_install_dir_requires_port():
    install = "d:/ark/cluster"
    counts = {install: 2}
    island = _cfg(id="a", server_port=7777, query_port=27015)
    rag = _cfg(id="b", server_map="Ragnarok", server_port=7778, query_port=27016)

    island_cmd = (
        "d:/ark/cluster/shootergame/binaries/win64/shootergameserver.exe "
        "theisland?listen?port=7777?queryport=27015"
    )
    rag_cmd = (
        "d:/ark/cluster/shootergame/binaries/win64/shootergameserver.exe "
        "ragnarok?listen?port=7778?queryport=27016"
    )

    assert _process_matches_cfg(island, island_cmd, island_cmd, counts)
    assert _process_matches_cfg(rag, rag_cmd, rag_cmd, counts)
    assert not _process_matches_cfg(island, rag_cmd, rag_cmd, counts)


def test_port_only_match_when_install_unknown():
    cfg = _cfg(install_dir="")
    cmdline = "shootergameserver.exe theisland?listen?port=7777?queryport=27015"
    assert _cmdline_matches_server(cmdline, cfg)
    assert _process_matches_cfg(cfg, "", cmdline, {})


def test_query_port_disambiguates_shared_install():
    install = "d:/ark/cluster"
    cfg = _cfg(server_port=7777, query_port=27015)
    cmdline = (
        "d:/ark/cluster/shootergame/binaries/win64/shootergameserver.exe "
        "theisland?listen?queryport=27015"
    )
    assert _cmdline_disambiguate(cmdline, cfg)
    assert _process_matches_cfg(cfg, cmdline, cmdline, {install: 2})


def test_read_shooter_process_fields_refetches_cmdline(monkeypatch):
    class _FakePsutil:
        class Process:
            def __init__(self, pid: int) -> None:
                self._pid = pid

            def exe(self) -> str:
                return r"D:\ARK\TheIsland\ShooterGame\Binaries\Win64\ShooterGameServer.exe"

            def cmdline(self) -> list[str]:
                return [
                    r"D:\ARK\TheIsland\ShooterGame\Binaries\Win64\ShooterGameServer.exe",
                    "TheIsland?listen?Port=7777",
                ]

    import src.asm_engine.asm_server_manager as mgr

    monkeypatch.setattr(mgr, "_PSUTIL_OK", True)
    monkeypatch.setattr(mgr, "_psutil", _FakePsutil)

    class _Proc:
        info = {"pid": 4242, "exe": "", "cmdline": []}

    exe, cmdline = _read_shooter_process_fields(_Proc())
    assert "theisland" in exe
    assert "?port=7777" in cmdline
