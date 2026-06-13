"""Constrói widgets em lotes via after(0) para não congelar o event loop do Tkinter."""
from __future__ import annotations

from typing import Callable, Optional

import customtkinter as ctk  # type: ignore[reportMissingImports]


class ChunkedSectionBuilder:
    """Executa tarefas de construção de UI em chunks, cedendo o controle entre lotes."""

    def __init__(
        self,
        parent: ctk.CTkBaseClass,
        *,
        chunk_size: int = 8,
        on_progress: Optional[Callable[[int, int], None]] = None,
        on_done: Optional[Callable[[], None]] = None,
        on_cancelled: Optional[Callable[[], None]] = None,
    ) -> None:
        self._parent = parent
        self._chunk_size = max(1, chunk_size)
        self._on_progress = on_progress
        self._on_done = on_done
        self._on_cancelled = on_cancelled
        self._tasks: list[Callable[[], None]] = []
        self._cancelled = False
        self._running = False

    def add(self, fn: Callable[[], None]) -> "ChunkedSectionBuilder":
        self._tasks.append(fn)
        return self

    def cancel(self) -> None:
        self._cancelled = True

    @property
    def running(self) -> bool:
        return self._running

    def run(self) -> None:
        if self._running or not self._tasks:
            if self._on_done and not self._running:
                self._on_done()
            return
        self._running = True
        self._cancelled = False
        self._run_chunk(0)

    def _run_chunk(self, start: int) -> None:
        if self._cancelled:
            self._running = False
            if self._on_cancelled:
                self._on_cancelled()
            return

        total = len(self._tasks)
        end = min(start + self._chunk_size, total)
        for i in range(start, end):
            if self._cancelled:
                self._running = False
                if self._on_cancelled:
                    self._on_cancelled()
                return
            self._tasks[i]()

        if self._on_progress:
            self._on_progress(end, total)

        if end < total:
            self._parent.after(0, lambda: self._run_chunk(end))
            return

        self._running = False
        if self._on_done:
            self._on_done()


def run_chunked_list(
    parent: ctk.CTkBaseClass,
    items: list,
    render_one: Callable[[object], None],
    *,
    chunk_size: int = 5,
    on_done: Optional[Callable[[], None]] = None,
) -> ChunkedSectionBuilder:
    """Helper: renderiza uma lista de itens em lotes."""
    builder = ChunkedSectionBuilder(parent, chunk_size=chunk_size, on_done=on_done)

    def _make_task(item: object) -> Callable[[], None]:
        return lambda i=item: render_one(i)

    for item in items:
        builder.add(_make_task(item))
    return builder
