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
