"""
Breakpoint responsivo para painéis TEK.
Slider numérico visível apenas quando largura >= 1200px.
"""
from __future__ import annotations

import tkinter as tk
from typing import Callable, Optional

BREAKPOINT_WIDE = 1200


class ResponsiveWatcher:
    """Observa largura de um widget e notifica callbacks ao cruzar o breakpoint."""

    def __init__(
        self,
        widget: tk.Misc,
        on_wide: Optional[Callable[[], None]] = None,
        on_narrow: Optional[Callable[[], None]] = None,
        breakpoint: int = BREAKPOINT_WIDE,
    ) -> None:
        self._widget = widget
        self._on_wide = on_wide
        self._on_narrow = on_narrow
        self._breakpoint = breakpoint
        self._is_wide: Optional[bool] = None
        self._after_id: Optional[str] = None
        widget.bind("<Configure>", self._on_configure, add="+")

    @property
    def is_wide(self) -> bool:
        if self._is_wide is None:
            try:
                w = self._widget.winfo_width()
                self._is_wide = w >= self._breakpoint if w > 1 else True
            except tk.TclError:
                self._is_wide = True
        return self._is_wide

    def _on_configure(self, _event: tk.Event) -> None:
        if self._after_id:
            try:
                self._widget.after_cancel(self._after_id)
            except tk.TclError:
                pass
        self._after_id = self._widget.after(80, self._apply)

    def _apply(self) -> None:
        self._after_id = None
        try:
            wide = self._widget.winfo_width() >= self._breakpoint
        except tk.TclError:
            return
        if wide == self._is_wide:
            return
        self._is_wide = wide
        if wide and self._on_wide:
            self._on_wide()
        elif not wide and self._on_narrow:
            self._on_narrow()


def attach_slider_visibility(
    watcher: ResponsiveWatcher,
    slider: tk.Misc,
    *,
    wide_width: int = 140,
) -> None:
    """Mostra/oculta slider conforme breakpoint."""

    def _show() -> None:
        try:
            slider.grid()
        except tk.TclError:
            pass

    def _hide() -> None:
        try:
            slider.grid_remove()
        except tk.TclError:
            pass

    watcher._on_wide = _show
    watcher._on_narrow = _hide
    if watcher.is_wide:
        _show()
    else:
        _hide()
