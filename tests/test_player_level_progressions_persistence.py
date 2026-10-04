"""Regressão: «Progressões customizadas» desmarcada não pode voltar marcada ao reiniciar o app.

Reproduz de ponta a ponta (painel TEK headless): construir a seção do painel,
clicar no checkbox, salvar (``_save``), "reiniciar" (novo ``AsmConfigManager`` com
APPDATA em tmp) e rodar o que o boot executa (snapshot / ``read_ini``).
"""
from __future__ import annotations

import json
import types
from pathlib import Path

import pytest

tk = pytest.importorskip("tkinter")
ctk = pytest.importorskip("customtkinter")

from src.asm_engine.asm_config_manager import AsmConfigManager
from src.asm_engine.asm_game_list_ini import (
    _GAME_MODE_SECTION,
    count_ramp_lines_in_section,
)
from src.asm_engine.asm_ini_manager import read_ini, write_ini
from src.asm_engine.asm_server_config import AsmServerConfig
from src.player_level_200 import level_200_ramp_values

_KEY = "player_level_progressions_enabled"


@pytest.fixture(scope="module")
def tk_root():
    try:
        root = ctk.CTk()
    except tk.TclError as exc:  # pragma: no cover - ambiente sem display
        pytest.skip(f"Tk indisponível: {exc}")
    root.withdraw()
    yield root
    try:
        root.destroy()
    except Exception:
        pass


@pytest.fixture
def env(tmp_path, monkeypatch, tk_root):
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    install = tmp_path / "srv"
    install.mkdir()

    mgr = AsmConfigManager()
    cfg = AsmServerConfig()
    cfg.name = "Teste"
    cfg.install_dir = str(install)
    cfg.player_base_level = 199
    setattr(cfg, _KEY, True)
    mgr.add_server(cfg)
    write_ini(cfg)  # estado inicial: ON (rampa + OverrideMaxXP + engrams no Game.ini)
    mgr.update_server(cfg)
    return types.SimpleNamespace(tmp=tmp_path, install=install, mgr=mgr, cfg=cfg, root=tk_root)


def _game_ini(install: Path) -> Path:
    return install / "ShooterGame/Saved/Config/WindowsServer/Game.ini"


def _json_value(mgr: AsmConfigManager):
    data = json.loads(mgr._servers_file.read_text(encoding="utf-8"))
    return data[0][_KEY]


def _fake_app(env, status: str):
    app = types.SimpleNamespace()
    app.asm_config_manager = env.mgr
    app.asm_server_manager = types.SimpleNamespace(
        get_instance=lambda _id: types.SimpleNamespace(status=status)
    )
    app._asm_panel_vars = {}
    app._frame_cache = {}
    app._asm_panel_active_server_id = env.cfg.id
    app._asm_refresh_dashboard = lambda: None
    app._rebuild_server_sidebar = lambda: None
    return app


def _open_panel(env, app, srv):
    """Constrói a seção do painel TEK como ``build_asm_server_panel`` faz."""
    from src.ui.player_level_panel import build_tek_player_level_section

    vars_ref: dict = {"_app": app}
    app._asm_panel_vars[srv.id] = vars_ref
    card = ctk.CTkFrame(env.root)
    ctx = types.SimpleNamespace(srv=srv, vars_ref=vars_ref, theme={}, accent="#22c55e")
    build_tek_player_level_section(ctx, card, start_row=1)
    return vars_ref, card


def _find_progressions_checkbox(widget):
    for child in widget.winfo_children():
        if isinstance(child, ctk.CTkCheckBox) and "Progressões customizadas" in str(
            child.cget("text")
        ):
            return child
        found = _find_progressions_checkbox(child)
        if found is not None:
            return found
    return None


def _quiet_messageboxes(monkeypatch):
    import tkinter.messagebox as mb

    shown: list[str] = []
    monkeypatch.setattr(mb, "showinfo", lambda *a, **k: shown.append("info"))
    monkeypatch.setattr(mb, "showwarning", lambda *a, **k: shown.append("warning"))
    monkeypatch.setattr(mb, "showerror", lambda *a, **k: shown.append("error"))
    return shown


def _boot_everything(srv: AsmServerConfig) -> None:
    """O que o app executa no boot e que relê os INIs (snapshot web + buff restore)."""
    from src.buff_manager import BuffManager
    from src.server_config_snapshot import collect_server_snapshot

    collect_server_snapshot(srv)
    read_ini(srv)
    fake_self = types.SimpleNamespace(
        _persist_server_config=lambda sid, c: None,
        _on_log=lambda *a, **k: None,
    )
    BuffManager._sync_profile_from_ini(fake_self, srv.id, srv)


def test_cycle_on_uncheck_save_stopped_restart_stays_off(env, monkeypatch):
    """ON -> desmarcar -> Salvar (servidor parado) -> reiniciar app: permanece OFF."""
    import src.asm_ui.asm_server_panel as panel

    _quiet_messageboxes(monkeypatch)
    app = _fake_app(env, "stopped")
    srv = env.mgr.get_server(env.cfg.id)
    vars_ref, card = _open_panel(env, app, srv)
    assert vars_ref[_KEY].get() is True

    cb = _find_progressions_checkbox(card)
    assert cb is not None
    cb.toggle()  # usuário desmarca (dispara o command do checkbox)
    assert vars_ref[_KEY].get() is False

    panel._save(app, srv)

    assert _json_value(env.mgr) is False
    text = _game_ini(env.install).read_text(encoding="utf-16")
    assert count_ramp_lines_in_section(text, _GAME_MODE_SECTION) == 0

    # --- reinício do app ---
    mgr2 = AsmConfigManager()
    srv2 = mgr2.servers[0]
    assert getattr(srv2, _KEY) is False
    _boot_everything(srv2)
    assert getattr(srv2, _KEY) is False

    vars2, _card2 = _open_panel(env, _fake_app(env, "stopped"), srv2)
    assert vars2[_KEY].get() is False


def test_uncheck_while_server_running_persists_without_save(env, monkeypatch):
    """Com o servidor no ar o Salvar é bloqueado; o clique mesmo assim tem de sobreviver."""
    import src.asm_ui.asm_server_panel as panel

    shown = _quiet_messageboxes(monkeypatch)
    app = _fake_app(env, "running")
    srv = env.mgr.get_server(env.cfg.id)
    vars_ref, card = _open_panel(env, app, srv)

    _find_progressions_checkbox(card).toggle()
    panel._save(app, srv)  # bloqueado: servidor em execução
    assert shown == ["warning"]

    mgr2 = AsmConfigManager()
    srv2 = mgr2.servers[0]
    assert getattr(srv2, _KEY) is False
    _boot_everything(srv2)
    assert getattr(srv2, _KEY) is False


def test_boot_with_stale_ramp_in_game_ini_does_not_reenable(env):
    """Game.ini ainda com rampa (servidor rodando / backup restaurado) + perfil OFF."""
    srv = env.mgr.get_server(env.cfg.id)
    # estado em disco: rampa ON gravada
    text = _game_ini(env.install).read_text(encoding="utf-16")
    assert count_ramp_lines_in_section(text, _GAME_MODE_SECTION) == len(level_200_ramp_values())

    setattr(srv, _KEY, False)
    env.mgr.update_server(srv)  # perfil salvo como OFF, mas o INI não foi regravado

    mgr2 = AsmConfigManager()
    srv2 = mgr2.servers[0]
    _boot_everything(srv2)
    assert getattr(srv2, _KEY) is False
    env.mgr.update_server(srv2)  # qualquer save posterior do perfil
    assert _json_value(env.mgr) is False


def test_on_still_writes_ramp_and_legacy_profiles_infer_on(env):
    """Comportamento desejado preservado: ON grava rampa; perfil antigo sem chave infere ON."""
    text = _game_ini(env.install).read_text(encoding="utf-16")
    assert count_ramp_lines_in_section(text, _GAME_MODE_SECTION) == len(level_200_ramp_values())
    assert "overridemaxexperiencepointsplayer=" in text.lower()

    legacy_with_ramp = AsmServerConfig.from_dict({
        "player_base_level": 160,
        "player_level_stats_raw": (
            "LevelExperienceRampOverrides=(ExperiencePointsForLevel[0]=70)"
        ),
    })
    assert getattr(legacy_with_ramp, _KEY) is True
    legacy_plain = AsmServerConfig.from_dict({"player_base_level": 160})
    assert getattr(legacy_plain, _KEY) is False
