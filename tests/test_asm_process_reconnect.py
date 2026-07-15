"""Testes de correspondência processo ↔ servidor TEK (scan/reconnect após restart)."""
from __future__ import annotations

from src.asm_engine.asm_server_config import AsmServerConfig, ASM_STATUS_STOPPED
from src.asm_engine.asm_server_manager import (
    AsmServerManager,
    _PsutilProcessWrapper,
    _bound_ports_match_cfg,
    _build_listening_port_index,
    _cmdline_disambiguate,
    _cmdline_matches_server,
    _install_dir_in_process,
    _is_shooter_candidate,
    _match_diagnostic,
    _parse_netstat_line,
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
        "rcon_enabled": True,
        "rcon_port": 27020,
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


def test_access_denied_exe_and_empty_cmdline_still_match_via_bound_ports():
    """Modo real no Windows: exe/cmdline AccessDenied → só portas binding."""
    cfg = _cfg()
    bound = {7777, 27015, 27020}
    assert _bound_ports_match_cfg(cfg, bound)
    assert _process_matches_cfg(cfg, "", "", {}, bound_ports=bound)
    assert not _process_matches_cfg(cfg, "", "", {}, bound_ports={9999})


def test_rcon_port_alone_matches_when_game_udp_hidden():
    cfg = _cfg()
    assert _process_matches_cfg(cfg, "", "", {}, bound_ports={27020})


def test_window_title_match_from_runserver_start():
    cfg = _cfg(name="Island PvE", session_name="My Session")
    assert _process_matches_cfg(
        cfg, "", "", {}, bound_ports=set(), window_title="Island PvE"
    )
    assert not _process_matches_cfg(
        cfg, "", "", {}, bound_ports=set(), window_title="Other Map"
    )


def test_match_diagnostic_reports_empty_fields():
    cfg = _cfg()
    bits = _match_diagnostic(cfg, "", "", {}, bound_ports={7777}, window_title="")
    assert "exe_cmdline_empty" in bits
    assert "bound=[7777]" in bits


def test_is_shooter_candidate_allows_blank_for_port_fallback():
    assert _is_shooter_candidate("", "", "")
    assert _is_shooter_candidate("ShooterGameServer.exe", "", "")
    assert not _is_shooter_candidate("chrome.exe", "c:/chrome.exe", "")


def test_psutil_wrapper_poll_access_denied_keeps_alive():
    class _Proc:
        pid = 99

        def is_running(self) -> bool:
            raise PermissionError("AccessDenied")

        def status(self) -> str:
            raise PermissionError("AccessDenied")

    wrap = _PsutilProcessWrapper(_Proc())
    assert wrap.poll() is None
    assert wrap.returncode is None


def test_psutil_wrapper_poll_no_such_process_marks_dead():
    NoSuchProcess = type("NoSuchProcess", (Exception,), {})

    class _Proc:
        pid = 98

        def is_running(self) -> bool:
            raise NoSuchProcess("gone")

    wrap = _PsutilProcessWrapper(_Proc())
    assert wrap.poll() == -1


def test_scan_reconnects_via_port_index_without_cmdline(monkeypatch):
    """scan_running_servers deve anexar instância só com PID↔porta (sem cmdline)."""
    import src.asm_engine.asm_server_manager as mgr

    cfg = _cfg(id="map-a")
    events: list[tuple[str, str]] = []

    class _RawProc:
        pid = 5555

        def is_running(self) -> bool:
            return True

        def status(self) -> str:
            return "running"

        def name(self) -> str:
            return "ShooterGameServer.exe"

        def create_time(self) -> float:
            return 1.0

        def exe(self) -> str:
            raise PermissionError("AccessDenied")

        def cmdline(self) -> list:
            raise PermissionError("AccessDenied")

    class _FakePsutil:
        NoSuchProcess = type("NoSuchProcess", (Exception,), {})
        AccessDenied = PermissionError

        class Process:
            def __init__(self, pid: int) -> None:
                assert pid == 5555
                self.pid = pid
                self._raw = _RawProc()

            def is_running(self) -> bool:
                return True

            def status(self) -> str:
                return "running"

            def name(self) -> str:
                return "ShooterGameServer.exe"

            def create_time(self) -> float:
                return 1.0

            def exe(self) -> str:
                raise PermissionError("AccessDenied")

            def cmdline(self) -> list:
                raise PermissionError("AccessDenied")

        @staticmethod
        def process_iter(attrs):  # noqa: ARG001
            return []

        @staticmethod
        def net_connections(kind="inet"):  # noqa: ARG001
            return []

    monkeypatch.setattr(mgr, "_PSUTIL_OK", True)
    monkeypatch.setattr(mgr, "_psutil", _FakePsutil)
    monkeypatch.setattr(
        mgr,
        "_build_listening_port_index",
        lambda _ports=None: {7777: {5555}, 27015: {5555}, 27020: {5555}},
    )
    monkeypatch.setattr(mgr, "_windows_titles_by_pid", lambda: {})
    monkeypatch.setattr(mgr, "_query_full_process_image_name", lambda _pid: "")

    mgr_obj = AsmServerManager(on_status_change=lambda sid, st: events.append((sid, st)))
    n = mgr_obj.scan_running_servers([cfg])
    assert n == 1
    inst = mgr_obj.get_instance(cfg.id)
    assert inst is not None
    assert inst.status != ASM_STATUS_STOPPED
    assert inst.pid == 5555
    assert events and events[0] == (cfg.id, "running")


def test_port_prefix_does_not_false_positive():
    cfg = _cfg(server_port=7777, query_port=27015)
    cmdline = "shootergameserver.exe map?listen?port=77770?queryport=270150"
    assert not _cmdline_matches_server(cmdline, cfg)


def test_build_listening_port_index_uses_psutil(monkeypatch):
    import src.asm_engine.asm_server_manager as mgr

    class _Addr:
        port = 27020

    class _Conn:
        pid = 42
        laddr = _Addr()
        status = "LISTEN"
        type = type("T", (), {"name": "SOCK_STREAM"})()

    class _FakePsutil:
        @staticmethod
        def net_connections(kind="inet"):  # noqa: ARG001
            return [_Conn()]

    monkeypatch.setattr(mgr, "_PSUTIL_OK", True)
    monkeypatch.setattr(mgr, "_psutil", _FakePsutil)
    monkeypatch.setattr(mgr, "_enrich_port_index_netstat", lambda _idx: None)

    idx = _build_listening_port_index({27020})
    assert idx[27020] == {42}


def test_parse_netstat_udp_tcp_and_ipv6():
    assert _parse_netstat_line(
        "  UDP    0.0.0.0:7777           *:*                                    5555"
    ) == (7777, 5555)
    assert _parse_netstat_line(
        "  TCP    0.0.0.0:27020          0.0.0.0:0              LISTENING       5555"
    ) == (27020, 5555)
    assert _parse_netstat_line(
        "  TCP    [::]:27020             [::]:0                 LISTENING       5555"
    ) == (27020, 5555)
    assert _parse_netstat_line(
        "  TCP    127.0.0.1:27020        127.0.0.1:1            ESTABLISHED     5555"
    ) is None


def test_v11040_failure_empty_exe_cmdline_no_ports():
    """Modo de falha da v1.10.40: exe+cmdline vazios sem match por porta → False."""
    cfg = _cfg()
    assert not _process_matches_cfg(cfg, "", "", { "d:/ark/theisland": 1 })


def test_shared_install_empty_cmdline_disambiguates_by_bound_ports():
    """Vários mapas no mesmo install_dir; só portas binding identificam o PID."""
    install = "d:/ark/cluster"
    counts = {install: 2}
    island = _cfg(id="a", name="Island", server_port=7777, query_port=27015, rcon_port=27020)
    rag = _cfg(
        id="b",
        name="Rag",
        server_map="Ragnarok",
        install_dir=r"D:\ARK\cluster",
        server_port=7778,
        query_port=27016,
        rcon_port=27021,
    )
    assert _process_matches_cfg(island, "", "", counts, bound_ports={7777, 27015})
    assert not _process_matches_cfg(island, "", "", counts, bound_ports={7778, 27016})
    assert _process_matches_cfg(rag, "", "", counts, bound_ports={7778, 27016, 27021})


def test_scan_reconnects_two_maps_same_install_via_ports_only(monkeypatch):
    """Scan com process_iter vazio + índice de portas: multi-mapa no mesmo install_dir."""
    import src.asm_engine.asm_server_manager as mgr

    island = _cfg(
        id="a",
        name="Island",
        install_dir=r"D:\ARK\cluster",
        server_port=7777,
        query_port=27015,
        rcon_port=27020,
    )
    rag = _cfg(
        id="b",
        name="Rag",
        server_map="Ragnarok",
        install_dir=r"D:\ARK\cluster",
        server_port=7778,
        query_port=27016,
        rcon_port=27021,
    )
    events: list[tuple[str, str]] = []

    class _Raw:
        def __init__(self, pid: int) -> None:
            self.pid = pid

        def is_running(self) -> bool:
            return True

        def status(self) -> str:
            return "running"

        def name(self) -> str:
            return "ShooterGameServer.exe"

        def create_time(self) -> float:
            return 1.0

        def exe(self) -> str:
            return ""

        def cmdline(self) -> list:
            return []

    class _FakePsutil:
        NoSuchProcess = type("NoSuchProcess", (Exception,), {})
        AccessDenied = PermissionError

        class Process:
            def __init__(self, pid: int) -> None:
                self.pid = pid
                self._raw = _Raw(pid)

            def is_running(self) -> bool:
                return True

            def status(self) -> str:
                return "running"

            def name(self) -> str:
                return "ShooterGameServer.exe"

            def create_time(self) -> float:
                return 1.0

            def exe(self) -> str:
                return ""

            def cmdline(self) -> list:
                return []

        @staticmethod
        def process_iter(attrs):  # noqa: ARG001
            return []

        @staticmethod
        def net_connections(kind="inet"):  # noqa: ARG001
            return []

    monkeypatch.setattr(mgr, "_PSUTIL_OK", True)
    monkeypatch.setattr(mgr, "_psutil", _FakePsutil)
    monkeypatch.setattr(
        mgr,
        "_build_listening_port_index",
        lambda _ports=None: {
            7777: {1001},
            27015: {1001},
            27020: {1001},
            7778: {1002},
            27016: {1002},
            27021: {1002},
        },
    )
    monkeypatch.setattr(mgr, "_windows_titles_by_pid", lambda: {})
    monkeypatch.setattr(mgr, "_query_full_process_image_name", lambda _pid: "")

    logs: list[str] = []
    mgr_obj = AsmServerManager(
        on_status_change=lambda sid, st: events.append((sid, st)),
        on_log=lambda msg, _lvl: logs.append(msg),
    )
    n = mgr_obj.scan_running_servers([island, rag])
    assert n == 2
    assert mgr_obj.get_instance("a").pid == 1001
    assert mgr_obj.get_instance("b").pid == 1002
    assert {e[0] for e in events} == {"a", "b"}


def test_scan_logs_summary_when_nothing_matches(monkeypatch):
    import src.asm_engine.asm_server_manager as mgr

    cfg = _cfg()
    logs: list[tuple[str, str]] = []

    class _FakePsutil:
        @staticmethod
        def process_iter(attrs):  # noqa: ARG001
            return []

        @staticmethod
        def net_connections(kind="inet"):  # noqa: ARG001
            return []

    monkeypatch.setattr(mgr, "_PSUTIL_OK", True)
    monkeypatch.setattr(mgr, "_psutil", _FakePsutil)
    monkeypatch.setattr(mgr, "_build_listening_port_index", lambda _ports=None: {})
    monkeypatch.setattr(mgr, "_windows_titles_by_pid", lambda: {})

    mgr_obj = AsmServerManager(on_log=lambda msg, lvl: logs.append((msg, lvl)))
    assert mgr_obj.scan_running_servers([cfg]) == 0
    assert any("0 reconectados" in m for m, _ in logs)
