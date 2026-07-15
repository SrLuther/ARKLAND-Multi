"""Testes de reconnect TEK — baseline v1.10.36 + aditivos seguros."""
from __future__ import annotations

from src.asm_engine.asm_server_config import AsmServerConfig, ASM_STATUS_STOPPED, ASM_STATUS_RUNNING
from src.asm_engine.asm_server_manager import (
    AsmServerManager,
    _PsutilProcessWrapper,
    _bound_ports_match_cfg,
    _build_listening_port_index,
    _cmdline_matches_server,
    _normalize_install_dir,
    _parse_netstat_line,
    _process_matches_cfg,
)


def _cfg(**kwargs) -> AsmServerConfig:
    base = {
        "id": "srv-1",
        "name": "The Island",
        "install_dir": "D:/ARK/TheIsland",
        "server_map": "TheIsland",
        "server_port": 7777,
        "query_port": 27015,
        "rcon_enabled": True,
        "rcon_port": 27020,
    }
    base.update(kwargs)
    return AsmServerConfig.from_dict(base)


def test_normalize_collapses_double_backslashes():
    assert _normalize_install_dir(r"D:\\ARK\\TheIsland") == "d:/ark/theisland"
    assert _normalize_install_dir(r"D:\ARK\TheIsland") == "d:/ark/theisland"
    assert _normalize_install_dir("D:/ARK/TheIsland/") == "d:/ark/theisland"


def test_v11036_install_dir_in_exe_single_map():
    """Caso canónico que funcionava em 1.10.36: um mapa, install_dir no exe."""
    cfg = _cfg()
    exe = "d:/ark/theisland/shootergame/binaries/win64/shootergameserver.exe"
    install = _normalize_install_dir(cfg.install_dir)
    assert install in exe
    assert _process_matches_cfg(cfg, exe, "", {install: 1})


def test_v11036_shared_install_requires_port():
    install = "d:/ark/cluster"
    counts = {install: 2}
    island = _cfg(id="a", install_dir="D:/ARK/cluster", server_port=7777, query_port=27015)
    rag = _cfg(
        id="b",
        install_dir="D:/ARK/cluster",
        server_map="Ragnarok",
        server_port=7778,
        query_port=27016,
    )
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


def test_install_dir_match_via_cmdline_when_exe_empty():
    """Aditivo pós-36: install_dir na cmdline quando exe vem vazio."""
    cfg = _cfg()
    install = _normalize_install_dir(cfg.install_dir)
    cmdline = (
        '"d:/ark/theisland/shootergame/binaries/win64/shootergameserver.exe" '
        "theisland?listen?port=7777?queryport=27015 -nosteamclient -game -server -log"
    )
    assert _process_matches_cfg(cfg, "", cmdline, {install: 1})


def test_query_port_in_cmdline_matches():
    cfg = _cfg(server_port=7777, query_port=27015)
    cmdline = "shootergameserver.exe theisland?listen?queryport=27015"
    assert _cmdline_matches_server(cmdline, cfg)
    assert _process_matches_cfg(cfg, "", cmdline, {})


def test_port_only_match_when_install_unknown():
    cfg = _cfg(install_dir="")
    cmdline = "shootergameserver.exe theisland?listen?port=7777?queryport=27015"
    assert _cmdline_matches_server(cmdline, cfg)
    assert _process_matches_cfg(cfg, "", cmdline, {})


def test_port_prefix_does_not_false_positive():
    cfg = _cfg(server_port=7777, query_port=27015)
    cmdline = "shootergameserver.exe map?listen?port=77770?queryport=270150"
    assert not _cmdline_matches_server(cmdline, cfg)


def test_bound_ports_adjunct_when_exe_cmdline_empty():
    cfg = _cfg()
    bound = {7777, 27015, 27020}
    assert _bound_ports_match_cfg(cfg, bound)
    assert _process_matches_cfg(cfg, "", "", {}, bound_ports=bound)
    assert not _process_matches_cfg(cfg, "", "", {}, bound_ports={9999})


def test_window_title_adjunct():
    cfg = _cfg(name="Island PvE", session_name="My Session")
    assert _process_matches_cfg(
        cfg, "", "", {}, bound_ports=set(), window_title="Island PvE"
    )
    assert not _process_matches_cfg(
        cfg, "", "", {}, bound_ports=set(), window_title="Other Map"
    )


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


def test_scan_reconnects_like_v11036_via_exe(monkeypatch):
    """Passo 1 = process_iter + install_dir no exe (path 1.10.36)."""
    import src.asm_engine.asm_server_manager as mgr

    cfg = _cfg(id="map-a")
    events: list[tuple[str, str]] = []

    class _IterProc:
        info = {
            "pid": 4242,
            "name": "ShooterGameServer.exe",
            "exe": r"D:\ARK\TheIsland\ShooterGame\Binaries\Win64\ShooterGameServer.exe",
            "cmdline": [
                r"D:\ARK\TheIsland\ShooterGame\Binaries\Win64\ShooterGameServer.exe",
                "TheIsland?listen?Port=7777?QueryPort=27015",
            ],
            "create_time": 100.0,
        }

    class _Raw:
        pid = 4242

        def is_running(self) -> bool:
            return True

        def status(self) -> str:
            return "running"

    class _FakePsutil:
        NoSuchProcess = type("NoSuchProcess", (Exception,), {})

        class Process:
            def __init__(self, pid: int) -> None:
                assert pid == 4242
                self.pid = pid

            def is_running(self) -> bool:
                return True

            def status(self) -> str:
                return "running"

        @staticmethod
        def process_iter(attrs):  # noqa: ARG001
            return [_IterProc()]

        @staticmethod
        def net_connections(kind="inet"):  # noqa: ARG001
            return []

    monkeypatch.setattr(mgr, "_PSUTIL_OK", True)
    monkeypatch.setattr(mgr, "_psutil", _FakePsutil)
    # Passo 2 não deve ser necessário — força índice vazio
    monkeypatch.setattr(mgr, "_build_listening_port_index", lambda _ports=None: {})
    monkeypatch.setattr(mgr, "_windows_titles_by_pid", lambda: {})

    mgr_obj = AsmServerManager(on_status_change=lambda sid, st: events.append((sid, st)))
    n = mgr_obj.scan_running_servers([cfg])
    assert n == 1
    inst = mgr_obj.get_instance(cfg.id)
    assert inst is not None
    assert inst.status == ASM_STATUS_RUNNING
    assert inst.pid == 4242
    assert events and events[0] == (cfg.id, "running")


def test_scan_port_fallback_when_process_iter_empty(monkeypatch):
    """Passo 2 adjunct: sem process_iter, casa por porta."""
    import src.asm_engine.asm_server_manager as mgr

    cfg = _cfg(id="map-a")
    events: list[tuple[str, str]] = []

    class _FakePsutil:
        NoSuchProcess = type("NoSuchProcess", (Exception,), {})
        AccessDenied = PermissionError

        class Process:
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

    mgr_obj = AsmServerManager(on_status_change=lambda sid, st: events.append((sid, st)))
    n = mgr_obj.scan_running_servers([cfg])
    assert n == 1
    assert mgr_obj.get_instance(cfg.id).pid == 5555


def test_scan_two_maps_shared_install_via_ports(monkeypatch):
    import src.asm_engine.asm_server_manager as mgr

    island = _cfg(
        id="a",
        name="Island",
        install_dir="D:/ARK/cluster",
        server_port=7777,
        query_port=27015,
        rcon_port=27020,
    )
    rag = _cfg(
        id="b",
        name="Rag",
        server_map="Ragnarok",
        install_dir="D:/ARK/cluster",
        server_port=7778,
        query_port=27016,
        rcon_port=27021,
    )

    class _FakePsutil:
        NoSuchProcess = type("NoSuchProcess", (Exception,), {})

        class Process:
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

    mgr_obj = AsmServerManager()
    n = mgr_obj.scan_running_servers([island, rag])
    assert n == 2
    assert mgr_obj.get_instance("a").pid == 1001
    assert mgr_obj.get_instance("b").pid == 1002


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


def test_empty_exe_cmdline_without_ports_fails():
    cfg = _cfg()
    assert not _process_matches_cfg(cfg, "", "", {_normalize_install_dir(cfg.install_dir): 1})


def test_path_boundary_gate_from_v11040_removed():
    """Regressão 1.10.40: boundary rejeitava paths válidos? Garantimos substring 36."""
    cfg = _cfg(install_dir="D:/ARK/Server")
    # Prefixo estrito de outro dir — 36 também casava (substring). Aceitável no baseline.
    exe_other = "d:/ark/server2/shootergame/binaries/win64/shootergameserver.exe"
    install = _normalize_install_dir(cfg.install_dir)
    # Com boundary antiga, server2 NÃO casava; com 36, CASAVA.
    assert install in exe_other
    assert _process_matches_cfg(cfg, exe_other, "", {install: 1})
