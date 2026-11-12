"""Testes do scheduler de broadcasts TEK."""
from src.config_manager import BroadcastTekConfig
from src.pages.broadcast_tek_scheduler import (
    broadcast_tek_scheduler_start,
    broadcast_tek_scheduler_stop,
)


class _FakeApp:
    def __init__(self, settings: BroadcastTekConfig | None = None):
        class C:
            broadcast_tek = settings or BroadcastTekConfig()
        class CM:
            config = C()
            def save(self):
                pass
        self.config_manager = CM()
        self._broadcast_tek_scheduler_running = False
        self._broadcast_tek_scheduler_job = None
        self._jobs: list[tuple[int, object]] = []
        self._next_job = 1

    def after(self, ms, fn):
        jid = self._next_job
        self._next_job += 1
        self._jobs.append((ms, fn))
        return jid

    def after_cancel(self, job):
        self._jobs = [(ms, fn) for ms, fn in self._jobs if fn is not None]

    def _global_log(self, *_args, **_kwargs):
        pass


def test_start_keeps_scheduler_enabled():
    app = _FakeApp(BroadcastTekConfig(scheduler_enabled=False))
    broadcast_tek_scheduler_start(app)
    assert app.config_manager.config.broadcast_tek.scheduler_enabled is True
    assert app._broadcast_tek_scheduler_running is True


def test_stop_keeps_scheduler_enabled():
    app = _FakeApp(BroadcastTekConfig(scheduler_enabled=True))
    broadcast_tek_scheduler_start(app)
    broadcast_tek_scheduler_stop(app)
    assert app.config_manager.config.broadcast_tek.scheduler_enabled is True
    assert app._broadcast_tek_scheduler_running is False


def test_broadcast_tek_config_defaults_enabled():
    cfg = BroadcastTekConfig()
    assert cfg.scheduler_enabled is True


def test_obobonic_config_auto_start_default():
    from src.config_manager import ObobonicBotConfig

    cfg = ObobonicBotConfig()
    assert cfg.auto_start is True


def test_individual_backup_scheduler_calls_one_server_action_not_global(monkeypatch):
    from datetime import datetime, timedelta
    from types import SimpleNamespace
    import src.pages.asm_scheduler_tick as scheduler

    calls = []

    class ImmediateThread:
        def __init__(self, target, args=(), daemon=None):
            self.target, self.args = target, args
        def start(self):
            self.target(*self.args)

    monkeypatch.setattr(scheduler.threading, "Thread", ImmediateThread)
    now = datetime(2026, 11, 10, 12, 0)
    srv = SimpleNamespace(
        id="srv-one", enable_auto_restart=False, enable_auto_update_check=False,
        backup_enabled=True, backup_interval_hours=1,
        enable_scheduled_broadcast=False,
    )
    app = SimpleNamespace(
        _asm_server_backup_last_run={"srv-one": now - timedelta(hours=1)},
        _asm_do_scheduled_backup=lambda target: calls.append(target),
        _run_global_backup=lambda: (_ for _ in ()).throw(AssertionError("global backup called")),
    )

    scheduler._process_server_scheduled_tasks(app, srv, now, "12:00")

    assert calls == [srv]


def test_scheduled_broadcast_passes_only_selected_server(monkeypatch):
    from datetime import datetime
    from types import SimpleNamespace
    import src.pages.asm_scheduler_tick as scheduler

    calls = []

    class ImmediateThread:
        def __init__(self, target, args=(), daemon=None):
            self.target, self.args = target, args
        def start(self):
            self.target(*self.args)

    monkeypatch.setattr(scheduler.threading, "Thread", ImmediateThread)
    srv = SimpleNamespace(
        id="srv-two", enable_auto_restart=False, enable_auto_update_check=False,
        backup_enabled=False, enable_scheduled_broadcast=True,
        scheduled_broadcast_time="12:30", scheduled_broadcast_message="hello",
    )
    app = SimpleNamespace(
        _asm_do_scheduled_broadcast=lambda target, message: calls.append((target, message)),
    )

    scheduler._process_server_scheduled_tasks(
        app, srv, datetime(2026, 11, 10, 12, 30), "12:30"
    )

    assert calls == [(srv, "hello")]
