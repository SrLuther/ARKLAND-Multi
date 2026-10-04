"""O preset nivel200.txt resolve em dev e no bundle, e não derruba a tela se faltar."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

from src.player_level_200 import (
    level_200_preset_error,
    level_200_preset_path,
    load_level_200_preset,
    preset_text,
)

_REPO = Path(__file__).resolve().parents[1]
_SOURCE = _REPO / "src" / "data" / "nivel200.txt"


class _Var:
    def __init__(self, value):
        self.value = value

    def get(self):
        return self.value

    def set(self, value):
        self.value = value


class _Cfg:
    def __init__(self) -> None:
        self.player_base_level = 199
        self.player_level_progressions_enabled = True
        self.player_level_stats_raw = "ExperiencePointsForLevel[0]=5"


def _clear_preset_cache() -> None:
    preset_text.cache_clear()
    load_level_200_preset.cache_clear()


def test_dev_path_finds_nivel200_file():
    path = level_200_preset_path()
    assert path == _SOURCE
    assert path.is_file()
    assert path.read_text(encoding="utf-8").startswith(
        "OverrideMaxExperiencePointsPlayer="
    )
    assert level_200_preset_error() is None
    spec = (_REPO / "ARKLAND-Multi.spec").read_text(encoding="utf-8")
    assert "('src/data/nivel200.txt'" in spec
    assert "'src/data')" in spec


def test_frozen_path_reads_bundled_file(tmp_path, monkeypatch):
    bundled = tmp_path / "src" / "data" / "nivel200.txt"
    bundled.parent.mkdir(parents=True)
    bundled.write_text("; bundled\n" + _SOURCE.read_text(encoding="utf-8"), encoding="utf-8")
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)
    _clear_preset_cache()
    try:
        assert level_200_preset_path() == bundled
        assert preset_text().startswith("; bundled\n")
        assert level_200_preset_error() is None
        assert load_level_200_preset()[0] == 1529554000
    finally:
        _clear_preset_cache()


def test_missing_preset_fallback_keeps_page_data(tmp_path, monkeypatch):
    """Sem o arquivo, o recálculo da tela não levanta e o botão fica com o erro."""
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)
    _clear_preset_cache()
    try:
        missing = level_200_preset_path()
        assert missing == tmp_path / "src" / "data" / "nivel200.txt"
        assert not missing.is_file()
        err = level_200_preset_error()
        assert err
        assert "indisponível" in err.lower()
        assert "nivel200.txt" in err

        from src.ui.player_level_panel import sync_player_level_vars

        raw = _Var("ExperiencePointsForLevel[0]=5")
        status = _Var("")
        engram = _Var("")
        sync_player_level_vars(
            {
                "player_base_level": _Var("199"),
                "player_level_progressions_enabled": _Var(True),
                "_pl_level200_status": status,
                "player_level_stats_raw": raw,
                "_pl_engram_var": engram,
            },
            cfg=_Cfg(),
        )
        assert "indisponível" in status.get().lower()
        assert raw.get() == "ExperiencePointsForLevel[0]=5"
        assert engram.get() == "preset indisponível"
    finally:
        _clear_preset_cache()


def _find_button(widget, text: str):
    import customtkinter as ctk

    for child in widget.winfo_children():
        if isinstance(child, ctk.CTkButton) and text in str(child.cget("text")):
            return child
        found = _find_button(child, text)
        if found is not None:
            return found
    return None


def test_classic_panel_mounts_when_preset_missing(tmp_path, monkeypatch):
    tk = pytest.importorskip("tkinter")
    ctk = pytest.importorskip("customtkinter")
    from src.server_config import ServerGameSettings
    from src.ui.player_level_panel import (
        LEVEL_200_SHORTCUT_BUTTON_TEXT,
        build_classic_player_level_panel,
    )

    try:
        root = ctk.CTk()
    except tk.TclError as exc:
        pytest.skip(f"Tk indisponível: {exc}")
    root.withdraw()
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)
    _clear_preset_cache()
    try:
        gs = ServerGameSettings()
        gs.player_base_level = 80
        gs.player_level_progressions_enabled = False
        parent = tk.Frame(root)
        w: dict = {}
        build_classic_player_level_panel(parent, 0, w, gs)
        assert "indisponível" in w["_pl_level200_status"].get().lower()
        btn = _find_button(parent, LEVEL_200_SHORTCUT_BUTTON_TEXT)
        assert btn is not None
        btn.cget("command")()
        assert gs.player_base_level == 80
        assert gs.player_level_progressions_enabled is False
        assert w["gs_player_base_level"].get() == "80"
        assert "aplicado" not in w["_pl_level200_status"].get().lower()
        assert "indisponível" in w["_pl_level200_status"].get().lower()

        gs199 = ServerGameSettings()
        gs199.player_base_level = 199
        gs199.player_level_progressions_enabled = True
        parent199 = tk.Frame(root)
        w199: dict = {
            "player_level_stats_raw": tk.StringVar(value="ExperiencePointsForLevel[0]=5"),
        }
        build_classic_player_level_panel(parent199, 0, w199, gs199)
        assert "indisponível" in w199["_pl_level200_status"].get().lower()
        assert w199["player_level_stats_raw"].get() == "ExperiencePointsForLevel[0]=5"
    finally:
        _clear_preset_cache()
        try:
            root.destroy()
        except Exception:
            pass
