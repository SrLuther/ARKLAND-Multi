from __future__ import annotations
import tkinter as tk
import customtkinter as ctk  # type: ignore[reportMissingImports]


def fast_fill(scroll: "ctk.CTkScrollableFrame", fn) -> None:
    """Executa fn() dentro de um CTkScrollableFrame sem recalcular scrollregion a cada widget.

    O CTkScrollableFrame tem um binding ``<Configure>`` em si mesmo que atualiza a
    scrollregion do canvas interno após cada pack/grid. Com muitos widgets isso vira
    O(n²). Este helper desabilita temporariamente esse binding, executa fn(), e ao
    final faz um único recálculo — tornando o build O(n).
    """
    canvas = scroll._parent_canvas
    scroll.unbind("<Configure>")
    try:
        fn()
    finally:
        scroll.bind(
            "<Configure>",
            lambda _e, c=canvas: c.configure(scrollregion=c.bbox("all")),
        )
        canvas.configure(scrollregion=canvas.bbox("all"))

