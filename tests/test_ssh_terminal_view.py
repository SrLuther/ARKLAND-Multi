from __future__ import annotations

import customtkinter as ctk
import pytest
from types import SimpleNamespace

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


def test_terminal_disconnect_notifies_panel_and_releases_connection():
    try:
        root = ctk.CTk()
    except Exception as exc:  # ambiente sem display disponível
        pytest.skip(f"Tk indisponível neste ambiente: {exc}")

    root.withdraw()
    messages: list[str | None] = []
    terminal = None
    try:
        terminal = TerminalView(root, on_disconnect=messages.append)
        connection = SimpleNamespace(close=lambda: None)
        terminal._connection = connection
        terminal.disconnect("Sessão encerrada pelo host remoto.")
        assert terminal._connection is None
        assert messages == ["Sessão encerrada pelo host remoto."]
    finally:
        if terminal is not None:
            terminal.destroy()
        root.destroy()
