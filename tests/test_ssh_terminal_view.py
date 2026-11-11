from __future__ import annotations

import customtkinter as ctk
import pytest

from src.ssh_access.terminal_view import TerminalView


def test_terminal_view_uses_customtkinter_font_and_constructs():
    """A fonte incompatível fazia o painel parar antes de ligar os botões SSH."""
    try:
        root = ctk.CTk()
    except Exception as exc:  # ambiente sem display disponível
        pytest.skip(f"Tk indisponível neste ambiente: {exc}")

    root.withdraw()
    terminal = None
    try:
        terminal = TerminalView(root)
        assert isinstance(terminal._font, ctk.CTkFont)
        assert terminal.textbox is not None
    finally:
        if terminal is not None:
            terminal.destroy()
        root.destroy()
