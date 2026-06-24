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
        on_error: Optional[Callable[[BaseException], None]] = None,
        is_cancelled: Optional[Callable[[], bool]] = None,
    ) -> None:
        self._parent = parent
        self._chunk_size = max(1, chunk_size)
        self._on_progress = on_progress
        self._on_done = on_done
        self._on_cancelled = on_cancelled
        self._on_error = on_error
        self._is_cancelled = is_cancelled
        self._tasks: list[Callable[[], None]] = []
        self._cancelled = False
        self._running = False
        self._aborted = False

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
        self._aborted = False
        self._run_chunk(0)

    def _should_stop(self) -> bool:
        return self._cancelled or self._aborted or (
            self._is_cancelled is not None and self._is_cancelled()
        )

    def _abort_cancelled(self) -> None:
        self._running = False
        if self._on_cancelled:
            self._on_cancelled()

    def _abort_error(self, exc: BaseException) -> None:
        self._aborted = True
        self._running = False
        if self._on_error:
            self._on_error(exc)

    def _run_chunk(self, start: int) -> None:
        if self._should_stop():
            self._abort_cancelled()
            return

        total = len(self._tasks)
        end = min(start + self._chunk_size, total)
        for i in range(start, end):
            if self._should_stop():
                self._abort_cancelled()
                return
            try:
                self._tasks[i]()
            except Exception as exc:
                self._abort_error(exc)
                return

        if self._on_progress:
            self._on_progress(end, total)

        if end < total:
            self._parent.after(0, lambda s=end: self._run_chunk(s))
            return

        self._running = False
        if self._should_stop():
            self._abort_cancelled()
            return
        if self._on_done:
            self._on_done()


def run_chunked_list(
    parent: ctk.CTkBaseClass,
    items: list,
    render_one: Callable[[object], None],
    *,
    chunk_size: int = 5,
    on_done: Optional[Callable[[], None]] = None,
    on_error: Optional[Callable[[BaseException], None]] = None,
    on_cancelled: Optional[Callable[[], None]] = None,
    is_cancelled: Optional[Callable[[], bool]] = None,
) -> ChunkedSectionBuilder:
    """Helper: renderiza uma lista de itens em lotes."""
    builder = ChunkedSectionBuilder(
        parent,
        chunk_size=chunk_size,
        on_done=on_done,
        on_error=on_error,
        on_cancelled=on_cancelled,
        is_cancelled=is_cancelled,
    )

    def _make_task(item: object) -> Callable[[], None]:
        return lambda i=item: render_one(i)

    for item in items:
        builder.add(_make_task(item))
    return builder
