from __future__ import annotations

import tkinter as tk
import tkinter.font as tkfont
from typing import Callable

import customtkinter as ctk
import pyte

from .service import SSHConnection


_COLORS = {
    "black": "#111827", "red": "#f7768e", "green": "#9ece6a", "brown": "#e0af68",
    "blue": "#7aa2f7", "magenta": "#bb9af7", "cyan": "#7dcfff", "white": "#c0caf5",
    "brightblack": "#565f89", "brightred": "#ff9eaa", "brightgreen": "#b9f27c",
    "brightbrown": "#ffca8a", "brightblue": "#8db0ff", "brightmagenta": "#c7a0ff",
    "brightcyan": "#89ddff", "brightwhite": "#ffffff",
}


class TerminalView(ctk.CTkFrame):
    """Small xterm-compatible terminal surface backed by pyte and a Paramiko channel."""

    def __init__(self, master, *, on_resize: Callable[[int, int], None] | None = None, **kwargs):
        super().__init__(master, **kwargs)
        self.columns = 100
        self.lines = 28
        self.screen = pyte.Screen(self.columns, self.lines)
        self.stream = pyte.Stream(self.screen)
        self._connection: SSHConnection | None = None
        self._after_id: str | None = None
        self._on_resize = on_resize
        self._render_scheduled = False
        # CTkTextbox valida il tipo da font e rejeita tkinter.font.Font. Usar
        # CTkFont evita que a construção do painel SSH pare antes de os
        # callbacks dos botões serem ligados.
        self._font = ctk.CTkFont(family="Consolas", size=10)
        self.textbox = ctk.CTkTextbox(
            self, wrap="none", font=self._font,
            fg_color="#11151b", text_color="#d8dee9",
            activate_scrollbars=True,
        )
        self.textbox.pack(fill="both", expand=True)
        self._text = self.textbox._textbox
        self._text.configure(state="normal", insertbackground="#ffffff", takefocus=True)
        self._text.bind("<KeyPress>", self._on_key)
        self._text.bind("<<Paste>>", self._on_paste)
        self._text.bind("<Configure>", self._on_configure)
        self._configure_tags()
        self.append_local("SSH aguardando conexão. A identidade do host deve ser confiada antes de conectar.\n")

    def _configure_tags(self) -> None:
        for color, hex_color in _COLORS.items():
            self._text.tag_configure(f"fg_{color}", foreground=hex_color)
            self._text.tag_configure(f"bg_{color}", background=hex_color)
        self._text.tag_configure("terminal_bold", font=tkfont.Font(family="Consolas", size=10, weight="bold"))
        self._text.tag_configure("terminal_default", foreground="#d8dee9", background="#11151b")

    def _on_key(self, event) -> str:
        if self._connection is None:
            if event.keysym in ("Prior", "Next"):
                self._text.yview_scroll(-1 if event.keysym == "Prior" else 1, "pages")
            return "break"
        sequences = {
            "Return": "\r", "KP_Enter": "\r", "BackSpace": "\x7f", "Tab": "\t",
            "Up": "\x1b[A", "Down": "\x1b[B", "Right": "\x1b[C", "Left": "\x1b[D",
            "Home": "\x1b[H", "End": "\x1b[F", "Delete": "\x1b[3~",
            "Insert": "\x1b[2~", "Prior": "\x1b[5~", "Next": "\x1b[6~",
            "Escape": "\x1b",
        }
        value = sequences.get(event.keysym)
        if value is None and event.state & 0x4 and event.keysym.lower() in "abcdefghijklmnopqrstuvwxyz":
            value = chr(ord(event.keysym.upper()) - 64)
        elif value is None and event.char and event.char.isprintable():
            value = event.char
        if value:
            try:
                self._connection.send(value)
            except Exception as exc:  # noqa: BLE001
                self.append_local(f"\n[SSH] Falha ao enviar entrada: {exc}\n")
                self.disconnect()
        return "break"

    def _on_paste(self, _event) -> str:
        if self._connection is not None:
            try:
                self._connection.send(self.clipboard_get())
            except Exception:
                pass
        return "break"

    def _on_configure(self, event) -> None:
        if event.width < 50 or event.height < 50:
            return
        char_width = max(1, self._font.measure("M"))
        line_height = max(1, self._font.metrics("linespace"))
        columns = max(20, (event.width - 24) // char_width)
        lines = max(5, (event.height - 12) // line_height)
        if (columns, lines) == (self.columns, self.lines):
            return
        self.columns, self.lines = columns, lines
        self.screen.resize(lines=lines, columns=columns)
        if self._connection is not None and self._on_resize:
            self._on_resize(columns, lines)
        self._schedule_render()

    def attach(self, connection: SSHConnection) -> None:
        self.disconnect()
        self._connection = connection
        connection.resize(self.columns, self.lines)
        self._poll_output()
        self._text.focus_set()

    def _poll_output(self) -> None:
        connection = self._connection
        if connection is None:
            return
        try:
            while connection.channel.recv_ready():
                chunk = connection.recv()
                if not chunk:
                    break
                self.stream.feed(chunk.decode("utf-8", errors="replace"))
                self._schedule_render()
            if connection.channel.exit_status_ready() or connection.channel.closed:
                self.append_local("\n[SSH] Sessão encerrada pelo host remoto.\n")
                self.disconnect()
                return
        except Exception as exc:  # noqa: BLE001
            self.append_local(f"\n[SSH] Conexão encerrada: {exc}\n")
            self.disconnect()
            return
        self._after_id = self.after(40, self._poll_output)

    def _schedule_render(self) -> None:
        if self._render_scheduled:
            return
        self._render_scheduled = True
        self.after_idle(self._render_screen)

    def _cell_tags(self, cell) -> tuple[str, ...]:
        tags = []
        fg = str(cell.fg).casefold()
        bg = str(cell.bg).casefold()
        if fg in _COLORS:
            tags.append(f"fg_{fg}")
        elif fg.startswith("#") and len(fg) == 7:
            tag = f"fg_{fg[1:]}"
            self._text.tag_configure(tag, foreground=fg)
            tags.append(tag)
        if bg in _COLORS:
            tags.append(f"bg_{bg}")
        elif bg.startswith("#") and len(bg) == 7:
            tag = f"bg_{bg[1:]}"
            self._text.tag_configure(tag, background=bg)
            tags.append(tag)
        if cell.bold:
            tags.append("terminal_bold")
        if cell.underscore:
            tags.append("underline")
        return tuple(tags) or ("terminal_default",)

    def _render_screen(self) -> None:
        self._render_scheduled = False
        self._text.configure(state="normal")
        self._text.delete("1.0", "end")
        for row in range(self.screen.lines):
            cells = self.screen.buffer[row]
            start = 0
            while start < self.screen.columns:
                tags = self._cell_tags(cells[start])
                end = start + 1
                while end < self.screen.columns and self._cell_tags(cells[end]) == tags:
                    end += 1
                text = "".join(cells[col].data for col in range(start, end))
                self._text.insert("end", text, tags)
                start = end
            if row < self.screen.lines - 1:
                self._text.insert("end", "\n")
        self._text.see("end")
        self._text.configure(state="normal")

    def append_local(self, text: str) -> None:
        self._text.configure(state="normal")
        self._text.insert("end", text, ("terminal_default",))
        self._text.see("end")

    def disconnect(self) -> None:
        if self._after_id is not None:
            try:
                self.after_cancel(self._after_id)
            except tk.TclError:
                pass
            self._after_id = None
        connection, self._connection = self._connection, None
        if connection is not None:
            try:
                connection.close()
            except Exception:
                pass

