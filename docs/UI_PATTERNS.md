# Padrões de UI — ARKLAND Server Manager

Guia rápido para novos painéis e seções. Seguir estes padrões evita freeze da interface.

## 1. Lazy loading (frames)

- **Páginas top-level:** cache em `show_frame_tek.py` — revisitar = instantâneo.
- **Seções do servidor:** um `CTkScrollableFrame` por seção, criado só na 1ª visita (`asm_server_panel.py`).
- **Abas internas (Loja, DB):** placeholder + `after(0)` ou visita à aba (`customshop_panel.py`, `db_manager_panel.py`).

## 2. Chunked build

Use quando uma seção cria **>15 widgets** ou listas dinâmicas.

```python
from ..ui.server_field_widgets import run_ui_tasks_chunked, build_cards_layout_chunked

def _build_secao(sf, srv, vars_ref, bg, accent, *, on_done=None, is_cancelled=None, on_progress=None):
    def _cards():
        ...
    def _help():
        add_collapsible_help(...)
        if on_done:
            on_done()
    build_cards_layout_chunked(sf, ctx, cards, on_complete=lambda r: _help(), ...)
```

Registrar a seção em `_CHUNKED_SECTIONS` no painel servidor.

**Helpers:** `src/ui/chunked_builder.py`, `run_ui_tasks_chunked`, `run_chunked_list`.

## 3. Listas longas

- **Mods, agregados, INI:** lotes de 5–12 itens com `after(0)` entre lotes.
- **Status de arquivo (mods):** adiar 120 ms ou manual; não bloquear o build inicial.

## 4. Loading overlay

Seções chunked mostram overlay com nome + progresso `X/Y` via `on_progress`.

## 5. Banco de dados

- **Assistente:** `🧙 Assistente` → wizard 3 passos (`db_setup_wizard.py`).
- **SQL:** `setup_db.sql` no bundle PyInstaller + cópia em `%APPDATA%\ARKLAND-ServerManager\`.
- **Conexão root:** senha vazia em instalação nova; usuário `arkland` após setup.

## 6. Instrumentação

`src/ui/perf_monitor.py` — `timed_build()` grava tempos em `docs/perf_baseline.json`.

## 7. Anti-padrões

- Não criar 31 scroll frames upfront.
- Não popular listas de 50+ itens em um único `for` síncrono.
- Não auto-conectar com banco que ainda não existe (usar retry sem `database`).
