"""Regressão de UI: as caixas do painel oBobonic persistem marcado E desmarcado."""
from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

ctk = pytest.importorskip("customtkinter")

from src.config_manager import ConfigManager  # noqa: E402


@pytest.fixture()
def fake_app(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    try:
        app = ctk.CTk()
    except Exception as exc:  # sem display (CI headless)
        pytest.skip(f"Tk indisponível: {exc}")
    app.withdraw()
    app.config_manager = ConfigManager()
    app.toasts = []
    app._toast = lambda msg, kind="info": app.toasts.append((kind, msg))
    app._global_log = lambda *a, **k: None
    yield app
    try:
        from src.obobonic_bot import shutdown_obobonic_for_app

        shutdown_obobonic_for_app(app)
        app.destroy()
    except Exception:
        pass


def _widgets(root, cls, out=None):
    out = [] if out is None else out
    for child in root.winfo_children():
        if isinstance(child, cls):
            out.append(child)
        _widgets(child, cls, out)
    return out


def _build(app):
    from src.pages.obobonic_panel import build_obobonic_panel

    frame = ctk.CTkFrame(app)
    frame.pack()
    build_obobonic_panel(app, frame)
    app.update()
    return frame


def _checks(frame):
    return {c.cget("text"): c for c in _widgets(frame, ctk.CTkCheckBox)}


def test_unchecked_boxes_stay_unchecked_after_app_restart(fake_app, tmp_path, monkeypatch):
    frame = _build(fake_app)
    boxes = _checks(frame)
    assert boxes["Iniciar com o app"].get() == 1       # default
    assert boxes["Reiniciar ao crash"].get() == 0

    boxes["Iniciar com o app"].toggle()                # desmarca
    boxes["Reiniciar ao crash"].toggle()               # marca
    fake_app.update()

    frame.destroy()
    # «reinicia o app»: config relida do disco + painel reconstruído
    monkeypatch.setenv("APPDATA", str(tmp_path))
    fake_app.config_manager = ConfigManager()
    frame2 = _build(fake_app)
    boxes2 = _checks(frame2)
    assert boxes2["Iniciar com o app"].get() == 0
    assert boxes2["Reiniciar ao crash"].get() == 1


def test_toggle_after_config_reload_still_persists(fake_app, tmp_path, monkeypatch):
    frame = _build(fake_app)
    fake_app.config_manager.load()                     # objeto de config trocado por baixo do painel
    _checks(frame)["Iniciar com o app"].toggle()
    fake_app.update()
    monkeypatch.setenv("APPDATA", str(tmp_path))
    assert ConfigManager().config.obobonic.auto_start is False


def test_save_failure_reverts_checkbox_and_warns(fake_app, monkeypatch):
    frame = _build(fake_app)
    box = _checks(frame)["Iniciar com o app"]

    def boom():
        raise PermissionError("bloqueado")

    monkeypatch.setattr(fake_app.config_manager, "save", boom)
    box.toggle()
    fake_app.update()
    assert box.get() == 1                              # UI volta ao valor realmente gravado
    assert any(kind == "error" for kind, _ in fake_app.toasts)


def test_panel_has_no_external_folder_controls(fake_app):
    frame = _build(fake_app)
    texts = " | ".join(
        str(w.cget("text"))
        for cls in (ctk.CTkLabel, ctk.CTkButton, ctk.CTkCheckBox)
        for w in _widgets(frame, cls)
    )
    for removed in ("Pasta do bot", "Instalar deps", "Sync TEK", "Abrir pasta", "Backup .env",
                    "Restaurar", "Modo oculto", "Verificar RCON", "bot.py"):
        assert removed not in texts, removed
    for kept in ("Iniciar", "Parar", "Reiniciar", "Iniciar com o app", "Reiniciar ao crash",
                 "Dev Portal", "Convidar bot", "Salvar configuração", "Importar dados do bot antigo"):
        assert kept in texts, kept


def test_save_fields_from_panel_persists_token_and_ids(fake_app, tmp_path, monkeypatch):
    frame = _build(fake_app)
    entries = _widgets(frame, ctk.CTkEntry)
    assert len(entries) == 7
    token = "fake.discord.token-for-tests"
    entries[0].delete(0, "end")
    entries[0].insert(0, token)
    entries[2].delete(0, "end")
    entries[2].insert(0, "123456789")
    save_btn = next(b for b in _widgets(frame, ctk.CTkButton) if "Salvar configuração" in b.cget("text"))
    save_btn.invoke()
    fake_app.update()
    monkeypatch.setenv("APPDATA", str(tmp_path))
    o = ConfigManager().config.obobonic
    assert o.token == token and o.guild_id == "123456789"
