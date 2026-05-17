import sys
import os

# Garante que o diretório raiz esteja no path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ── Guard de instância única (Windows) ───────────────────────────────────────
if sys.platform == "win32":
    import ctypes

    _MUTEX_NAME = "ARKLAND_ServerManager_SingleInstance"
    _mutex = ctypes.windll.kernel32.CreateMutexW(None, True, _MUTEX_NAME)

    if ctypes.windll.kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
        # Procura a janela existente (mesmo que esteja recolhida na bandeja)
        _found: list = []

        _EnumProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_size_t, ctypes.c_size_t)

        def _enum_cb(hwnd: int, _: int) -> bool:
            buf = ctypes.create_unicode_buffer(256)
            ctypes.windll.user32.GetWindowTextW(hwnd, buf, 256)
            if "ARKLAND" in buf.value:
                _found.append(hwnd)
                return False  # para a enumeração ao achar
            return True

        ctypes.windll.user32.EnumWindows(_EnumProc(_enum_cb), 0)

        if _found:
            # Restaura e traz para frente (funciona mesmo com app na bandeja)
            ctypes.windll.user32.ShowWindow(_found[0], 9)   # SW_RESTORE
            ctypes.windll.user32.SetForegroundWindow(_found[0])
        else:
            # Fallback: janela não localizada — só avisa
            ctypes.windll.user32.MessageBoxW(
                0,
                "O ARKLAND - Server Manager já está em execução.\n"
                "Verifique a bandeja do sistema (systray).",
                "Já em execução",
                0x40,   # MB_ICONINFORMATION
            )

        sys.exit(0)
# ─────────────────────────────────────────────────────────────────────────────

from src.app import ARKServerManagerApp

if __name__ == "__main__":
    app = ARKServerManagerApp()
    app.mainloop()
