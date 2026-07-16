"""Reconnect TEK — baseline v1.10.36 + adjunct; fixture grounded em `.bug` real."""
from __future__ import annotations

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
    """Modo de falha real `.bug`: 6 Shooter com exe+cmdline vazios → adjunct portas = 6/6."""
    import src.asm_engine.asm_server_manager as mgr

    servers = _bug_servers()

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
                return ""

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
                return r"D:\ARK\TheIsland\ShooterGame\Binaries\Win64\ShooterGameServer.exe"

            def cmdline(self) -> list:
                return ["ShooterGameServer.exe", "TheIsland?Port=7777?QueryPort=27015"]

        @staticmethod
        def process_iter(attrs):  # noqa: ARG001
            class _Info:
                info = {
                    "pid": 4242,
                    "name": "ShooterGameServer.exe",
                    "exe": r"D:\ARK\TheIsland\ShooterGame\Binaries\Win64\ShooterGameServer.exe",
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
