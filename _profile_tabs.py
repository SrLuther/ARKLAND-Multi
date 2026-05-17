"""Mede o tempo de build de cada aba."""
import time, sys

import tkinter as tk
_real_after = tk.Misc.after
def _fake_after(self, ms, func=None, *args):
    return "noop"
tk.Misc.after = _fake_after

import customtkinter as ctk
ctk.set_appearance_mode("dark")

root = ctk.CTk()
root.withdraw()

from src.config_manager import ConfigManager
from src.server_manager import ServerManager
import src.app as app_mod

App = app_mod.ARKServerManagerApp

cm = ConfigManager()
sm = ServerManager()
servers = cm.servers
if not servers:
    print("Nenhum servidor. Adicione um servidor antes de rodar este script.")
    root.destroy()
    sys.exit(0)

srv = servers[0]
print(f"Servidor: {srv.name}\n")

# Instancia mínima do App sem __init__
app = App.__new__(App)
app._server_widgets = {srv.id: {}}
app._server_frames = {}
app._frames = {}
app._nav_buttons = {}
app._current_frame = ""
app._sidebar_server_btns = {}
app._rcon_clients = {}
app._chat_poll_jobs = {}
app._config_search_index = {}
app.config_manager = cm
app.server_manager = sm

frame = ctk.CTkFrame(root, fg_color="#111118", width=1200, height=800)
frame.pack()
tabs = ctk.CTkTabview(frame, width=1180, height=780)
tabs.pack()

BUILDERS = [
    ("Geral",        "_build_tab_general"),
    ("Jogo",         "_build_tab_game"),
    ("Avancado",     "_build_tab_advanced"),
    ("Spawns",       "_build_tab_spawns"),
    ("Loot",         "_build_tab_loot"),
    ("Mods",         "_build_tab_mods"),
    ("Admins",       "_build_tab_admins"),
    ("Jogadores",    "_build_tab_jogadores"),
    ("Plugins",      "_build_tab_plugins"),
    ("Console RCON", "_build_tab_rcon"),
    ("Chat",         "_build_tab_chat"),
    ("Logs",         "_build_tab_logs"),
    ("Historico",    "_build_tab_historico"),
    ("Backup",       "_build_tab_backup"),
]

for name, method in BUILDERS:
    tabs.add(name)

results = []
for name, method in BUILDERS:
    t = tabs.tab(name)
    app._server_widgets[srv.id] = {}  # reset widgets dict
    start = time.perf_counter()
    try:
        getattr(App, method)(app, t, srv)
    except Exception as e:
        pass
    elapsed = (time.perf_counter() - start) * 1000

    def count_widgets(w):
        return 1 + sum(count_widgets(c) for c in w.winfo_children())
    total = count_widgets(t)
    results.append((name, elapsed, total))

print(f"{'Aba':<22} {'Tempo':>8}   {'Widgets':>8}")
print("-" * 44)
for name, ms, wc in results:
    bar = "█" * int(ms / 30)
    flag = " ← PESADA" if ms > 200 else ""
    print(f"{name:<22} {ms:>7.0f}ms   {wc:>7}   {bar}{flag}")

root.destroy()
