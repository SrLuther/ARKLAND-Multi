"""Abre um arquivo JSON com o melhor editor disponível no sistema."""
from __future__ import annotations
import os
import subprocess


def open_json_editor(path: str) -> None:
    """
    Abre um arquivo JSON com o melhor editor disponível no sistema.
    Prioridade: Notepad++ → VS Code → Sublime Text → Notepad → os.startfile (padrão).
    """

    candidates = [
        r"C:\Program Files\Notepad++\notepad++.exe",
        r"C:\Program Files (x86)\Notepad++\notepad++.exe",
        os.path.join(os.environ.get("LOCALAPPDATA", ""),
                     "Programs", "Microsoft VS Code", "Code.exe"),
        r"C:\Program Files\Microsoft VS Code\Code.exe",
        r"C:\Program Files\Sublime Text\sublime_text.exe",
        r"C:\Program Files\Sublime Text 3\sublime_text.exe",
        r"C:\Program Files\Sublime Text 4\sublime_text.exe",
        r"C:\Windows\System32\notepad.exe",
    ]

    for editor in candidates:
        if os.path.isfile(editor):
            try:
                subprocess.Popen([editor, path])
                return
            except OSError:
                continue

    os.startfile(path)
