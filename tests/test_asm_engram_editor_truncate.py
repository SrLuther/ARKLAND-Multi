"""Corte do sufixo _C e exclusão/edição no editor de engramas."""
from __future__ import annotations

from pathlib import Path

from src.asm_engine.asm_engram_entries import (
    ENGRAM_CLASS_MAX_LEN,
    EngramOverride,
    clamp_engram_class,
    class_column_text,
    delete_engram_row,
    edit_engram_class,
    load_engram_rows,
    name_column_text,
    parse_engram_overrides,
    persist_engram_rows,
)
from src.asm_engine.asm_ini_manager import write_ini
from src.asm_engine.asm_server_config import AsmServerConfig

_METAL_C = "EngramEntry_BlueprintStation_Metal_C"
_METAL_CUT = "EngramEntry_BlueprintStation_Metal"
_STATION_C = "EngramEntry_BlueprintStation_C"


def _line(entry_class: str, level: int) -> str:
    return (
        "OverrideNamedEngramEntries="
        f'(EngramClassName="{entry_class}",EngramHidden=True,'
        f"EngramPointsCost=0,EngramLevelRequirement={level},RemoveEngramPreReq=False)"
    )


def _saved_blob() -> str:
    return "\n".join(
        [
            _line(_STATION_C, 1003),
            _line(_METAL_C, 1003),
            _line(_METAL_CUT, 1004),
            "",
        ]
    )


def test_metal_class_is_not_truncated_to_34_chars():
    assert ENGRAM_CLASS_MAX_LEN == 50
    assert len(_METAL_C) == 36
    assert _METAL_C[:34] == _METAL_CUT
    assert clamp_engram_class(_METAL_C) == _METAL_C
    assert len(clamp_engram_class("E" * 60)) == 50

    assert class_column_text(_METAL_C) == _METAL_C
    assert name_column_text(_METAL_C) == _METAL_C
    assert len(class_column_text(_METAL_C)) == 36

    parsed = parse_engram_overrides(_line(_METAL_C, 1003))
    assert len(parsed) == 1
    assert parsed[0].entry_class == _METAL_C
    assert f'EngramClassName="{_METAL_C}"' in parsed[0].to_ini_line()
    assert f'EngramClassName="{_METAL_CUT}"' not in parsed[0].to_ini_line()

    src = Path("src/asm_ui/asm_engram_editor.py").read_text(encoding="utf-8")
    assert "[:32]" not in src
    assert "[:34]" not in src
    assert 'text="Editar"' in src
    assert 'text="Excluir"' in src
    assert '"<Double-Button-1>"' in src


def test_same_class_two_levels_stay_editable_and_deletable():
    """1003 e 1004 da mesma classe não podem colidir numa chave só."""
    raw = "\n".join([_line(_METAL_C, 1003), _line(_METAL_C, 1004), ""])
    rows = load_engram_rows([raw], known=[])
    assert [row.level for row in rows] == [1003, 1004]
    assert all(row.entry_class == _METAL_C for row in rows)

    kept = delete_engram_row(rows, rows[1])
    assert [row.level for row in kept] == [1003]
    assert rows[0] in kept
    assert kept[0].entry_class == _METAL_C

    edit_engram_class(kept[0], _METAL_C)
    assert kept[0].entry_class == _METAL_C
    assert kept[0].to_ini_line().count(_METAL_C) == 1


def test_already_cut_metal_row_can_be_fixed_or_deleted():
    rows = load_engram_rows([_saved_blob()], known=[])
    assert [(row.entry_class, row.level) for row in rows] == [
        (_STATION_C, 1003),
        (_METAL_C, 1003),
        (_METAL_CUT, 1004),
    ]
    full = rows[1]
    cut = rows[2]
    assert class_column_text(full.entry_class) == _METAL_C
    assert class_column_text(cut.entry_class) == _METAL_CUT

    edit_engram_class(cut, _METAL_C)
    assert cut.entry_class == _METAL_C
    assert f'EngramClassName="{_METAL_C}"' in cut.to_ini_line()

    rows = delete_engram_row(rows, full)
    rows = delete_engram_row(rows, cut)
    assert [row.entry_class for row in rows] == [_STATION_C]

    srv = AsmServerConfig()
    srv.custom_game_ini = _saved_blob()
    body = persist_engram_rows(srv, rows, known=[])
    assert _STATION_C in body
    assert _METAL_C not in srv.engram_entries_raw
    assert _METAL_CUT not in srv.engram_entries_raw
    assert not hasattr(srv, "custom_game_ini")


def test_legacy_field_reloads_both_metal_rows_for_delete(tmp_path):
    srv = AsmServerConfig()
    srv.install_dir = str(tmp_path)
    srv.custom_game_ini = _saved_blob()

    rows = load_engram_rows(
        [getattr(srv, "custom_game_ini", "")],
        known=[],
    )
    metal = [row for row in rows if "BlueprintStation_Metal" in row.entry_class]
    assert [(row.entry_class, row.level) for row in metal] == [
        (_METAL_C, 1003),
        (_METAL_CUT, 1004),
    ]

    for row in list(metal):
        rows = delete_engram_row(rows, row)
    persist_engram_rows(srv, rows, known=[])

    assert _METAL_C not in srv.engram_entries_raw
    assert '"EngramEntry_BlueprintStation_Metal"' not in srv.engram_entries_raw
    assert _STATION_C in srv.engram_entries_raw

    write_ini(srv)
    game = (
        tmp_path
        / "ShooterGame"
        / "Saved"
        / "Config"
        / "WindowsServer"
        / "Game.ini"
    )
    text = game.read_text(encoding="utf-16")
    assert text.count(f'"{_STATION_C}"') == 1
    assert f'"{_METAL_C}"' not in text
    assert f'"{_METAL_CUT}"' not in text


def test_write_ini_keeps_both_levels_with_full_class(tmp_path):
    srv = AsmServerConfig()
    srv.install_dir = str(tmp_path)
    rows = [
        EngramOverride(_METAL_C, _METAL_C, cost=0, level=1003, hidden=True),
        EngramOverride(_METAL_C, _METAL_C, cost=0, level=1004, hidden=True),
    ]
    persist_engram_rows(srv, rows, known=[])
    assert srv.engram_entries_raw.count(f'"{_METAL_C}"') == 2

    write_ini(srv)
    game = (
        tmp_path
        / "ShooterGame"
        / "Saved"
        / "Config"
        / "WindowsServer"
        / "Game.ini"
    )
    text = game.read_text(encoding="utf-16")
    assert text.count(f'"{_METAL_C}"') == 2
    assert "EngramLevelRequirement=1003" in text
    assert "EngramLevelRequirement=1004" in text
    assert f'"{_METAL_CUT}"' not in text


def _row_parts(frame):
    entries: list[str] = []
    edit = delete = None
    for child in frame.winfo_children():
        kind = type(child).__name__
        if kind == "CTkEntry":
            entries.append(child.get())
        elif kind == "CTkButton":
            label = child.cget("text")
            if label == "Editar":
                edit = child
            elif label == "Excluir":
                delete = child
    return entries, edit, delete


def test_table_edit_and_delete_buttons_work_on_cut_and_full_rows():
    """Editar e Excluir ficam na linha, dentro da janela, e agem naquela linha."""
    import tkinter.font as tkfont

    import customtkinter as ctk

    from src.asm_ui.asm_engram_editor import _EngramEditorWindow

    blob = "\n".join(
        [
            _line(_STATION_C, 1003),
            _line(_METAL_CUT, 1003),
            _line(_METAL_CUT, 1004),
            _line(_METAL_C, 1005),
            "",
        ]
    )
    root = ctk.CTk()
    root.geometry("1460x680")
    srv = AsmServerConfig()
    srv.id = "valhalla-test"
    srv.name = "04 Valhalla"
    srv.engram_entries_raw = blob
    win = _EngramEditorWindow(root, srv, object())
    try:
        win._filter_text.set("blu")
        root.update_idletasks()
        root.update()

        font = tkfont.Font(family="Consolas", size=11)
        assert font.measure(_METAL_C) <= 430
        assert font.measure("M" * ENGRAM_CLASS_MAX_LEN) <= 430

        frames = list(win._scroll.winfo_children())
        assert frames, "a busca blu não mostrou linhas"
        seen_levels: dict[str, str] = {}
        for frame in frames:
            frame.update_idletasks()
            entries, edit, delete = _row_parts(frame)
            assert edit is not None and delete is not None
            assert edit.winfo_ismapped() and delete.winfo_ismapped()
            for button in (edit, delete):
                right = button.winfo_x() + button.winfo_width()
                assert right <= frame.winfo_width() + 2
            classes = [value for value in entries if value.startswith("EngramEntry_")]
            assert classes
            assert len(classes[0]) <= ENGRAM_CLASS_MAX_LEN
            if "BlueprintStation_Metal" not in classes[0]:
                continue
            level = next(value for value in entries if value in {"1003", "1004", "1005"})
            seen_levels[level] = classes[0]

        assert seen_levels["1003"] == _METAL_CUT
        assert seen_levels["1004"] == _METAL_CUT
        assert seen_levels["1005"] == _METAL_C
        assert len(seen_levels["1005"]) == 36

        def _button_for(level: str, label: str):
            for frame in win._scroll.winfo_children():
                entries, edit, delete = _row_parts(frame)
                if level not in entries:
                    continue
                if not any(value.startswith("EngramEntry_BlueprintStation_Metal") for value in entries):
                    continue
                return edit if label == "Editar" else delete
            raise AssertionError(f"botão {label} da linha {level} não está na tabela")

        win._prompt_engram_class = lambda title, initial="": _METAL_C
        _button_for("1003", "Editar").invoke()
        root.update_idletasks()

        metal_1003 = next(
            row for row in win._rows
            if row.entry_class == _METAL_C and row.level == 1003
        )
        assert metal_1003.entry_class == _METAL_C
        assert len(metal_1003.entry_class) == 36

        still_cut = [
            row for row in win._rows
            if row.entry_class == _METAL_CUT and row.level == 1004
        ]
        assert len(still_cut) == 1

        _button_for("1004", "Excluir").invoke()
        root.update_idletasks()
        assert not any(row.level == 1004 and "Metal" in row.entry_class for row in win._rows)
        assert any(row.level == 1003 and row.entry_class == _METAL_C for row in win._rows)
        assert any(row.level == 1005 and row.entry_class == _METAL_C for row in win._rows)
    finally:
        win.destroy()
        root.destroy()
