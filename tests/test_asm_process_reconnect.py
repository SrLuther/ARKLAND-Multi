"""Reconnect TEK — baseline v1.10.36 + adjunct; fixture grounded em `.bug` real."""
from __future__ import annotations

from pathlib import Path

from src.asm_engine.asm_server_config import (
    AsmServerConfig,
    ASM_STATUS_CRASHED,
    ASM_STATUS_RUNNING,
    ASM_STATUS_STOPPED,
)
from src.asm_engine.asm_server_manager import (
    AsmServerManager,
    _PsutilProcessWrapper,
    _bound_ports_match_cfg,
    _build_listening_port_index,
    _cmdline_matches_server,
    _normalize_install_dir,
    _parse_netstat_line,
    _path_belongs_to_install,
    _pid_safe_to_kill,
    _process_matches_cfg,
    _window_title_matches,
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


# ── shapes reais de `.bug/asm_servers.json` (sem passwords/rcon secrets) ──────
# PIDs de `.bug/shooter_procs.txt` (ExecutablePath e CommandLine vazios nos 6).
_BUG_MAPS = [
    # name, install_dir, server_port, query_port, rcon_port, pid
    ("Brighamia", r"C:\ARKLAND SERVER\MAPAS\BR", 7790, 27100, 32400, 988),
    ("Crystal", r"C:\ARKLAND SERVER\MAPAS\CI", 7796, 27103, 32403, 8888),
    ("Alps", r"C:\ARKLAND SERVER\MAPAS\AL", 7792, 27101, 32401, 12140),
    ("Gen2", r"C:\ARKLAND SERVER\MAPAS\G2", 7794, 27102, 32402, 9088),
    ("Volcano", r"C:\ARKLAND SERVER\MAPAS\VL", 7798, 27104, 32404, 5920),
    ("Amissa", r"C:\ARKLAND SERVER\MAPAS\AM", 7800, 27105, 32405, 7180),
]


def _bug_servers() -> list[AsmServerConfig]:
    out: list[AsmServerConfig] = []
    for i, (name, install, sport, qport, rport, _pid) in enumerate(_BUG_MAPS):
        out.append(
            _cfg(
                id=f"bug-{i}",
                name=name,
                install_dir=install,
                server_port=sport,
                query_port=qport,
                rcon_port=rport,
                rcon_enabled=True,
            )
        )
    return out


def test_normalize_collapses_double_backslashes():
    assert _normalize_install_dir(r"D:\\ARK\\TheIsland") == "d:/ark/theisland"
    assert _normalize_install_dir(r"D:\ARK\TheIsland") == "d:/ark/theisland"
    assert _normalize_install_dir("D:/ARK/TheIsland/") == "d:/ark/theisland"


def test_v11020_rules_fail_on_bug_empty_exe_cmdline():
    """Sob regras estritas v1.10.20 (só exe + ?port=): 0/6 no shape `.bug`."""
    servers = _bug_servers()
    counts: dict[str, int] = {}
    for s in servers:
        key = _normalize_install_dir(s.install_dir)
        counts[key] = counts.get(key, 0) + 1
    for s in servers:
        # Exactamente o dump CIM: ExecutablePath/CommandLine vazios
        assert not _process_matches_cfg(s, "", "", counts)


def test_bug_fixture_unique_install_dirs():
    dirs = {_normalize_install_dir(s.install_dir) for s in _bug_servers()}
    assert len(dirs) == 6


def test_bound_ports_adjunct_matches_bug_ports():
    for s, row in zip(_bug_servers(), _BUG_MAPS):
        sport, qport, rport = row[2], row[3], row[4]
        assert _bound_ports_match_cfg(s, {sport, qport, rport})
        assert _process_matches_cfg(
            s, "", "", {}, bound_ports={sport, qport, rport}
        )


def test_scan_bug_six_empty_exe_cmdline_via_ports(monkeypatch):
    """exe vazio no process_iter → QueryFullProcessImageName devolve path por mapa."""
    import src.asm_engine.asm_server_manager as mgr

    servers = _bug_servers()
    path_by_pid = {
        row[5]: str(Path(row[1]) / "ShooterGame" / "Binaries" / "Win64" / "ShooterGameServer.exe")
        for row in _BUG_MAPS
    }

    class _P:
        def __init__(self, pid: int) -> None:
            self.info = {
                "pid": pid,
                "name": "ShooterGameServer.exe",
                "exe": "",
                "cmdline": [],
                "create_time": 1.0,
            }

    procs = [_P(row[5]) for row in _BUG_MAPS]
    port_index: dict[int, set[int]] = {}
    for row in _BUG_MAPS:
        _name, _inst, sport, qport, rport, pid = row
        for p in (sport, qport, rport):
            port_index.setdefault(p, set()).add(pid)

    class _Fake:
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
                return path_by_pid.get(self.pid, "")

            def cmdline(self) -> list:
                return []

        @staticmethod
        def process_iter(attrs):  # noqa: ARG001
            return procs

        @staticmethod
        def net_connections(kind="inet"):  # noqa: ARG001
            return []

    monkeypatch.setattr(mgr, "_PSUTIL_OK", True)
    monkeypatch.setattr(mgr, "_psutil", _Fake)
    monkeypatch.setattr(mgr, "_build_listening_port_index", lambda _ports=None: port_index)
    monkeypatch.setattr(mgr, "_windows_titles_by_pid", lambda: {})
    monkeypatch.setattr(
        mgr,
        "_query_full_process_image_name",
        lambda pid: path_by_pid.get(int(pid), "").replace("\\", "/").lower(),
    )
    monkeypatch.setattr(mgr, "_load_last_pids", lambda: {})
    monkeypatch.setattr(mgr, "_save_last_pids", lambda _d: None)

    m = AsmServerManager()
    n = m.scan_running_servers(servers)
    assert n == 6
    assert m.count_running(servers) == 6
    for s, row in zip(servers, _BUG_MAPS):
        assert m.get_instance(s.id).pid == row[5]
        assert m.get_instance(s.id).status == ASM_STATUS_RUNNING


def test_v11036_install_dir_in_exe_single_map():
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
    import src.asm_engine.asm_server_manager as mgr

    cfg = _cfg(id="map-a")
    events: list[tuple[str, str]] = []
    exe_path = r"D:\ARK\TheIsland\ShooterGame\Binaries\Win64\ShooterGameServer.exe"

    class _IterProc:
        info = {
            "pid": 4242,
            "name": "ShooterGameServer.exe",
            "exe": exe_path,
            "cmdline": [
                exe_path,
                "TheIsland?listen?Port=7777?QueryPort=27015",
            ],
            "create_time": 100.0,
        }

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

            def name(self) -> str:
                return "ShooterGameServer.exe"

            def exe(self) -> str:
                return exe_path

            def cmdline(self) -> list:
                return [exe_path, "TheIsland?listen?Port=7777?QueryPort=27015"]

            def create_time(self) -> float:
                return 100.0

        @staticmethod
        def process_iter(attrs):  # noqa: ARG001
            return [_IterProc()]

        @staticmethod
        def net_connections(kind="inet"):  # noqa: ARG001
            return []

    monkeypatch.setattr(mgr, "_PSUTIL_OK", True)
    monkeypatch.setattr(mgr, "_psutil", _FakePsutil)
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
    import src.asm_engine.asm_server_manager as mgr

    cfg = _cfg(id="map-a")
    exe_path = r"D:\ARK\TheIsland\ShooterGame\Binaries\Win64\ShooterGameServer.exe"

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
    monkeypatch.setattr(
        mgr, "_query_full_process_image_name",
        lambda pid: exe_path.replace("\\", "/").lower() if int(pid) == 5555 else "",
    )
    monkeypatch.setattr(mgr, "_load_last_pids", lambda: {})
    monkeypatch.setattr(mgr, "_save_last_pids", lambda _d: None)

    mgr_obj = AsmServerManager()
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
    exe = r"D:\ARK\cluster\ShooterGame\Binaries\Win64\ShooterGameServer.exe"

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
                return exe

            def cmdline(self) -> list:
                if self.pid == 1001:
                    return [exe, "TheIsland?listen?Port=7777?QueryPort=27015"]
                return [exe, "Ragnarok?listen?Port=7778?QueryPort=27016"]

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
    monkeypatch.setattr(mgr, "_load_last_pids", lambda: {})
    monkeypatch.setattr(mgr, "_save_last_pids", lambda _d: None)

    mgr_obj = AsmServerManager()
    n = mgr_obj.scan_running_servers([island, rag])
    assert n == 2
    assert mgr_obj.get_instance("a").pid == 1001
    assert mgr_obj.get_instance("b").pid == 1002


def test_ci_process_does_not_attach_amissa(monkeypatch):
    """Um Shooter sob MAPAS\\CI — Amissa fica offline; Crystal online."""
    import src.asm_engine.asm_server_manager as mgr

    ci = _cfg(
        id="crystal",
        name="Crystal",
        install_dir=r"C:\ARKLANDSERVER\MAPAS\CI",
        server_port=7796,
        query_port=27103,
        rcon_port=32403,
    )
    am = _cfg(
        id="amissa",
        name="Amissa",
        install_dir=r"C:\ARKLANDSERVER\MAPAS\AM",
        server_port=7800,
        query_port=27105,
        rcon_port=32405,
    )
    ci_exe = r"C:\ARKLANDSERVER\MAPAS\CI\ShooterGame\Binaries\Win64\ShooterGameServer.exe"

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
                return ci_exe

            def cmdline(self) -> list:
                return [ci_exe, "CrystalIsles?Port=7796"]

        @staticmethod
        def process_iter(attrs):  # noqa: ARG001
            class _Info:
                info = {
                    "pid": 8888,
                    "name": "ShooterGameServer.exe",
                    "exe": ci_exe,
                    "cmdline": [ci_exe, "CrystalIsles?Port=7796"],
                    "create_time": 1.0,
                }

            return [_Info()]

        @staticmethod
        def net_connections(kind="inet"):  # noqa: ARG001
            return []

    monkeypatch.setattr(mgr, "_PSUTIL_OK", True)
    monkeypatch.setattr(mgr, "_psutil", _FakePsutil)
    monkeypatch.setattr(mgr, "_build_listening_port_index", lambda _ports=None: {})
    monkeypatch.setattr(mgr, "_windows_titles_by_pid", lambda: {})
    monkeypatch.setattr(mgr, "_load_last_pids", lambda: {"amissa": 8888, "crystal": 8888})
    monkeypatch.setattr(mgr, "_save_last_pids", lambda _d: None)
    monkeypatch.setattr(mgr, "_query_full_process_image_name", lambda _pid: "")

    m = AsmServerManager()
    n = m.scan_running_servers([ci, am])
    assert n == 1
    assert m.get_instance("crystal").pid == 8888
    assert m.get_instance("crystal").status == ASM_STATUS_RUNNING
    assert m.count_running([am]) == 0
    assert m.get_instance("amissa").status == ASM_STATUS_STOPPED


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
    assert not _process_matches_cfg(
        cfg, "", "", {_normalize_install_dir(cfg.install_dir): 1}
    )


def test_count_running_is_dashboard_truth():
    m = AsmServerManager()
    cfg = _cfg(id="br")
    m.register_servers([cfg])
    inst = m.get_instance("br")
    assert inst is not None
    inst.status = ASM_STATUS_RUNNING
    assert m.count_running([cfg]) == 1
    inst.status = ASM_STATUS_CRASHED
    assert m.count_running([cfg]) == 0


def test_ghost_running_poll_dead_cleared(monkeypatch):
    """RUNNING sem processo vivo não infla ONLINE (ghost count)."""
    import src.asm_engine.asm_server_manager as mgr

    class _Dead:
        pid = 1

        def poll(self):
            return -1

    class _Fake:
        NoSuchProcess = type("NoSuchProcess", (Exception,), {})

        @staticmethod
        def process_iter(attrs):  # noqa: ARG001
            return []

        @staticmethod
        def net_connections(kind="inet"):  # noqa: ARG001
            return []

    monkeypatch.setattr(mgr, "_PSUTIL_OK", True)
    monkeypatch.setattr(mgr, "_psutil", _Fake)
    monkeypatch.setattr(mgr, "_build_listening_port_index", lambda _ports=None: {})
    monkeypatch.setattr(mgr, "_windows_titles_by_pid", lambda: {})
    monkeypatch.setattr(mgr, "_load_last_pids", lambda: {})
    monkeypatch.setattr(mgr, "_save_last_pids", lambda _d: None)
    monkeypatch.setattr(mgr, "_query_full_process_image_name", lambda _pid: "")

    m = AsmServerManager()
    cfg = _cfg(id="ghost")
    m.register_servers([cfg])
    inst = m.get_instance("ghost")
    assert inst is not None
    inst.status = ASM_STATUS_RUNNING
    inst._proc = _Dead()
    assert m.count_running([cfg]) == 1
    n = m.scan_running_servers([cfg])
    assert n == 0
    assert m.count_running([cfg]) == 0
    assert m.get_instance("ghost").status != ASM_STATUS_RUNNING


def test_status_callback_under_scan_does_not_deadlock(monkeypatch):
    """Regressão v1.10.44: attach/reconcile com lock + clear_force_day no callback = freeze UI.

    Simula o caminho real de app_tek._on_server_status_change (clear_force_day_pending
    reentra em self._lock). Sem o defer de notify, scan trava e Iniciar/Parar travam.
    """
    import threading

    import src.asm_engine.asm_server_manager as mgr

    exe_path = r"D:\ARK\TheIsland\ShooterGame\Binaries\Win64\ShooterGameServer.exe"

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
                return exe_path

            def cmdline(self) -> list:
                return ["ShooterGameServer.exe", "TheIsland?Port=7777?QueryPort=27015"]

        @staticmethod
        def process_iter(attrs):  # noqa: ARG001
            class _Info:
                info = {
                    "pid": 4242,
                    "name": "ShooterGameServer.exe",
                    "exe": exe_path,
                    "cmdline": ["ShooterGameServer.exe", "TheIsland?Port=7777?QueryPort=27015"],
                    "create_time": 1.0,
                }

            return [_Info()]

        @staticmethod
        def net_connections(kind="inet"):  # noqa: ARG001
            return []

    monkeypatch.setattr(mgr, "_PSUTIL_OK", True)
    monkeypatch.setattr(mgr, "_psutil", _FakePsutil)
    monkeypatch.setattr(mgr, "_build_listening_port_index", lambda _ports=None: {})
    monkeypatch.setattr(mgr, "_windows_titles_by_pid", lambda: {})
    monkeypatch.setattr(mgr, "_load_last_pids", lambda: {})
    monkeypatch.setattr(mgr, "_save_last_pids", lambda _d: None)
    monkeypatch.setattr(mgr, "_query_full_process_image_name", lambda _pid: "")

    holder: dict = {}

    def _on_status(server_id: str, status: str) -> None:
        # Mesmo padrão do app TEK: callback sincronamente toca o lock do manager.
        m = holder["m"]
        if status == ASM_STATUS_RUNNING:
            m.clear_force_day_pending(server_id)
        elif status in (ASM_STATUS_STOPPED, ASM_STATUS_CRASHED):
            m.clear_force_day_pending(server_id)

    m = AsmServerManager(on_status_change=_on_status)
    holder["m"] = m
    cfg = _cfg(id="lock-test")
    m.register_servers([cfg])

    done = threading.Event()
    result: dict = {"n": -1, "err": None}

    def _run() -> None:
        try:
            result["n"] = m.scan_running_servers([cfg])
        except Exception as exc:  # pragma: no cover
            result["err"] = exc
        finally:
            done.set()

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    assert done.wait(timeout=5.0), "scan_running_servers deadlocked (status callback + lock)"
    assert result["err"] is None
    assert result["n"] == 1
    assert m.count_running([cfg]) == 1

    # Ghost reconcile com o mesmo callback também não pode travar.
    class _Dead:
        pid = 4242

        def poll(self):
            return -1

    monkeypatch.setattr(
        _FakePsutil,
        "process_iter",
        staticmethod(lambda attrs: []),  # noqa: ARG005
    )
    inst = m.get_instance("lock-test")
    assert inst is not None
    inst.status = ASM_STATUS_RUNNING
    inst._proc = _Dead()
    done2 = threading.Event()
    result2: dict = {"n": -1}

    def _run_ghost() -> None:
        result2["n"] = m.scan_running_servers([cfg])
        done2.set()

    threading.Thread(target=_run_ghost, daemon=True).start()
    assert done2.wait(timeout=5.0), "ghost reconcile deadlocked"
    assert m.count_running([cfg]) == 0
    assert m.get_instance("lock-test").status == ASM_STATUS_STOPPED


def test_path_belongs_rejects_other_map():
    am = _cfg(
        id="am",
        name="Amissa",
        install_dir=r"C:\ARKLAND SERVER\MAPAS\AM",
        server_port=7800,
        query_port=27105,
        rcon_port=32405,
    )
    other = r"c:/arkland server/mapas/br/shootergame/binaries/win64/shootergameserver.exe"
    own = r"c:/arkland server/mapas/am/shootergame/binaries/win64/shootergameserver.exe"
    assert _path_belongs_to_install(am, other, "") is False
    assert _path_belongs_to_install(am, own, "") is True
    assert _path_belongs_to_install(am, "", "") is None


def test_window_title_short_folder_am_not_steam():
    am = _cfg(name="Amissa", install_dir=r"C:\ARKLAND SERVER\MAPAS\AM")
    assert not _window_title_matches("Steam", am)
    assert not _window_title_matches("TeamViewer", am)
    assert _window_title_matches("Amissa", am)


def test_wrong_map_exe_not_matched_by_ports_alone():
    am = _cfg(
        id="am",
        install_dir=r"C:\ARKLAND SERVER\MAPAS\AM",
        server_port=7800,
        query_port=27105,
        rcon_port=32405,
    )
    br_exe = r"c:/arkland server/mapas/br/shootergame/binaries/win64/shootergameserver.exe"
    # Mesmo com portas de Amissa no bound set, path de BR rejeita
    assert not _process_matches_cfg(
        am, br_exe, "", {}, bound_ports={7800, 27105, 32405}
    )


def test_last_pid_recycle_wrong_map_not_reattached(monkeypatch):
    """Pós-reboot: last_pid aponta para Shooter de OUTRO mapa → não anexa Amissa."""
    import src.asm_engine.asm_server_manager as mgr

    am = _cfg(
        id="amissa",
        name="Amissa",
        install_dir=r"C:\ARKLAND SERVER\MAPAS\AM",
        server_port=7800,
        query_port=27105,
        rcon_port=32405,
    )
    br_exe = r"C:\ARKLAND SERVER\MAPAS\BR\ShooterGame\Binaries\Win64\ShooterGameServer.exe"

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
                return br_exe

            def cmdline(self) -> list:
                return [br_exe, "Brighamia?Port=7790"]

        @staticmethod
        def process_iter(attrs):  # noqa: ARG001
            class _Info:
                info = {
                    "pid": 7180,
                    "name": "ShooterGameServer.exe",
                    "exe": br_exe,
                    "cmdline": [br_exe, "Brighamia?Port=7790"],
                    "create_time": 1.0,
                }

            return [_Info()]

        @staticmethod
        def net_connections(kind="inet"):  # noqa: ARG001
            return []

    monkeypatch.setattr(mgr, "_PSUTIL_OK", True)
    monkeypatch.setattr(mgr, "_psutil", _FakePsutil)
    monkeypatch.setattr(mgr, "_build_listening_port_index", lambda _ports=None: {})
    monkeypatch.setattr(mgr, "_windows_titles_by_pid", lambda: {})
    monkeypatch.setattr(mgr, "_load_last_pids", lambda: {"amissa": 7180})
    monkeypatch.setattr(mgr, "_save_last_pids", lambda _d: None)
    monkeypatch.setattr(mgr, "_query_full_process_image_name", lambda _pid: "")

    m = AsmServerManager()
    n = m.scan_running_servers([am])
    assert n == 0
    assert m.count_running([am]) == 0


def test_pid_safe_to_kill_requires_install_dir(monkeypatch):
    import src.asm_engine.asm_server_manager as mgr

    am = _cfg(install_dir=r"C:\ARKLAND SERVER\MAPAS\AM", server_port=7800, query_port=27105)
    br_exe = r"C:\ARKLAND SERVER\MAPAS\BR\ShooterGame\Binaries\Win64\ShooterGameServer.exe"
    am_exe = r"C:\ARKLAND SERVER\MAPAS\AM\ShooterGame\Binaries\Win64\ShooterGameServer.exe"

    class _FakePsutil:
        class Process:
            def __init__(self, pid: int) -> None:
                self.pid = pid
                self._exe = br_exe if pid == 100 else am_exe

            def name(self) -> str:
                return "ShooterGameServer.exe"

            def exe(self) -> str:
                return self._exe

            def cmdline(self) -> list:
                return [self._exe]

        @staticmethod
        def net_connections(kind="inet"):  # noqa: ARG001
            return []

    monkeypatch.setattr(mgr, "_PSUTIL_OK", True)
    monkeypatch.setattr(mgr, "_psutil", _FakePsutil)
    monkeypatch.setattr(mgr, "_query_full_process_image_name", lambda _pid: "")
    monkeypatch.setattr(mgr, "_build_listening_port_index", lambda _ports=None: {})

    assert not _pid_safe_to_kill(am, 100)  # BR path
    assert _pid_safe_to_kill(am, 200)  # AM path
    assert not _pid_safe_to_kill(am, 4)  # System


def test_stop_ghost_wrong_pid_clears_without_taskkill(monkeypatch):
    """Parar com PID errado (ex. DWM/outro mapa): limpa estado, zero taskkill."""
    import src.asm_engine.asm_server_manager as mgr

    am = _cfg(
        id="amissa",
        name="Amissa",
        install_dir=r"C:\ARKLAND SERVER\MAPAS\AM",
        server_port=7800,
        query_port=27105,
    )
    calls: list[list] = []

    class _FakeProc:
        pid = 999

        def poll(self):
            return None

        def terminate(self):
            raise AssertionError("terminate não deve ser chamado")

        def kill(self):
            raise AssertionError("kill não deve ser chamado")

        def wait(self, timeout=None):  # noqa: ARG002
            raise AssertionError("wait não deve ser chamado")

    class _FakePsutil:
        class Process:
            def __init__(self, pid: int) -> None:
                self.pid = pid

            def name(self) -> str:
                return "dwm.exe"

            def exe(self) -> str:
                return r"C:\Windows\System32\dwm.exe"

            def cmdline(self) -> list:
                return []

        @staticmethod
        def net_connections(kind="inet"):  # noqa: ARG001
            return []

    def _fake_run(cmd, **kwargs):  # noqa: ARG001
        calls.append(list(cmd))
        raise AssertionError(f"taskkill não deve rodar: {cmd}")

    monkeypatch.setattr(mgr, "_PSUTIL_OK", True)
    monkeypatch.setattr(mgr, "_psutil", _FakePsutil)
    monkeypatch.setattr(mgr, "_query_full_process_image_name", lambda _pid: "")
    monkeypatch.setattr(mgr, "_load_last_pids", lambda: {"amissa": 999})
    monkeypatch.setattr(mgr, "_save_last_pids", lambda _d: None)
    monkeypatch.setattr(mgr.subprocess, "run", _fake_run)

    m = AsmServerManager()
    m.register_servers([am])
    inst = m.get_instance("amissa")
    assert inst is not None
    inst.status = ASM_STATUS_RUNNING
    inst._proc = _FakeProc()

    done = {"ok": None, "msg": ""}

    def _on_done(ok, msg):
        done["ok"] = ok
        done["msg"] = msg

    m._stop_worker(inst, _on_done)
    assert done["ok"] is True
    assert "não verificado" in done["msg"].lower() or "limpeza" in done["msg"].lower()
    assert inst.status == ASM_STATUS_STOPPED
    assert inst._proc is None
    assert calls == []


def test_stop_verified_am_path_does_taskkill(monkeypatch):
    import src.asm_engine.asm_server_manager as mgr

    am = _cfg(
        id="amissa",
        install_dir=r"C:\ARKLAND SERVER\MAPAS\AM",
        server_port=7800,
        query_port=27105,
        rcon_enabled=False,
    )
    am_exe = r"C:\ARKLAND SERVER\MAPAS\AM\ShooterGame\Binaries\Win64\ShooterGameServer.exe"
    calls: list[list] = []

    class _FakeProc:
        pid = 7180
        _alive = True

        def poll(self):
            return None if self._alive else 0

        def terminate(self):
            self._alive = False

        def kill(self):
            self._alive = False

        def wait(self, timeout=None):  # noqa: ARG002
            self._alive = False
            return 0

    class _FakePsutil:
        class Process:
            def __init__(self, pid: int) -> None:
                self.pid = pid

            def name(self) -> str:
                return "ShooterGameServer.exe"

            def exe(self) -> str:
                return am_exe

            def cmdline(self) -> list:
                return [am_exe]

        @staticmethod
        def net_connections(kind="inet"):  # noqa: ARG001
            return []

    def _fake_run(cmd, **kwargs):  # noqa: ARG001
        calls.append(list(cmd))

        class _R:
            returncode = 0

        return _R()

    monkeypatch.setattr(mgr, "_PSUTIL_OK", True)
    monkeypatch.setattr(mgr, "_psutil", _FakePsutil)
    monkeypatch.setattr(mgr, "_query_full_process_image_name", lambda _pid: "")
    monkeypatch.setattr(mgr, "_load_last_pids", lambda: {})
    monkeypatch.setattr(mgr, "_save_last_pids", lambda _d: None)
    monkeypatch.setattr(mgr.subprocess, "run", _fake_run)
    monkeypatch.setattr(mgr.time, "sleep", lambda _s: None)

    m = AsmServerManager()
    m.register_servers([am])
    inst = m.get_instance("amissa")
    assert inst is not None
    inst.status = ASM_STATUS_RUNNING
    inst._proc = _FakeProc()

    done = {"ok": None}

    m._stop_worker(inst, lambda ok, msg: done.update(ok=ok))
    assert done["ok"] is True
    assert any(c[:3] == ["taskkill", "/F", "/T"] and "7180" in c for c in calls)
    assert inst.status == ASM_STATUS_STOPPED


def test_reconcile_clears_alive_wrong_pid_ghost(monkeypatch):
    """ONLINE com PID vivo que NÃO é Shooter do install_dir → STOPPED sem kill."""
    import src.asm_engine.asm_server_manager as mgr

    am = _cfg(
        id="amissa",
        install_dir=r"C:\ARKLAND SERVER\MAPAS\AM",
        server_port=7800,
        query_port=27105,
    )

    class _Alien:
        pid = 4242

        def poll(self):
            return None  # ainda "vivo"

    class _FakePsutil:
        NoSuchProcess = type("NoSuchProcess", (Exception,), {})

        class Process:
            def __init__(self, pid: int) -> None:
                self.pid = pid

            def name(self) -> str:
                return "notepad.exe"

            def exe(self) -> str:
                return r"C:\Windows\System32\notepad.exe"

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
    monkeypatch.setattr(mgr, "_build_listening_port_index", lambda _ports=None: {})
    monkeypatch.setattr(mgr, "_windows_titles_by_pid", lambda: {})
    monkeypatch.setattr(mgr, "_load_last_pids", lambda: {"amissa": 4242})
    monkeypatch.setattr(mgr, "_save_last_pids", lambda _d: None)
    monkeypatch.setattr(mgr, "_query_full_process_image_name", lambda _pid: "")

    m = AsmServerManager()
    m.register_servers([am])
    inst = m.get_instance("amissa")
    assert inst is not None
    inst.status = ASM_STATUS_RUNNING
    inst._proc = _Alien()

    n = m.scan_running_servers([am])
    assert n == 0
    assert m.count_running([am]) == 0
    assert m.get_instance("amissa").status == ASM_STATUS_STOPPED
    assert m.get_instance("amissa")._proc is None


def test_launch_url_expands_bare_amissa_with_active_mod(tmp_path):
    from src.asm_engine.asm_ini_manager import _launch_url_params

    mods = tmp_path / "ShooterGame" / "Content" / "Mods" / "1383342563"
    mods.mkdir(parents=True)
    cfg = _cfg(
        server_map="Amissa",
        install_dir=str(tmp_path),
        active_mods=["1383342563", "999"],
        server_port=7800,
        query_port=27105,
    )
    url = "".join(_launch_url_params(cfg))
    assert url.startswith("/Game/Mods/1383342563/Amissa?listen")
    assert "?Port=7800" in url


def test_launch_url_keeps_canonical_mod_path():
    from src.asm_engine.asm_ini_manager import _launch_url_params

    cfg = _cfg(
        server_map="/Game/Mods/1383342563/Amissa",
        install_dir=r"C:\ARKLAND SERVER\MAPAS\AM",
        active_mods=["1383342563"],
    )
    url = "".join(_launch_url_params(cfg))
    # map_cli_name extrai o segmento final; bare+ActiveMods só expande ServerMap curto
    assert "Amissa?listen" in url or url.startswith("/Game/Mods/1383342563/Amissa")
