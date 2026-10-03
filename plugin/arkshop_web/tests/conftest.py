"""Fixtures compartilhadas dos testes arkshop_web."""
from __future__ import annotations

import atexit
import os
import shutil
import sys
import tempfile
from pathlib import Path

# Migração síncrona em testes — evita race com threads de boot do app.
os.environ.setdefault("ARKSHOP_SYNC_DB_MIGRATE", "1")
os.environ.setdefault("ARKSHOP_SKIP_DB_BOOT", "1")
os.environ.setdefault("ARKSHOP_WEB_SECRET", "test-secret")

# Raiz do repo no sys.path: ``market_economy._writable_data_dir`` faz ``from src.shop_integration
# import webstore_data_dir``; sem isto (ex.: ``pytest`` sem ``python -m``) cai no fallback que
# aponta para ``plugin/arkshop_web/data`` — o próprio arquivo versionado — e os testes de PATCH
# gravariam nele.
_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

# Isolamento do diretório de dados da Web Store. Sem ``ARKSHOP_DATA_DIR``, ``webstore_data_dir()``
# resolve para o ambiente REAL do usuário (ex.: ``...\ARKLAND SERVER\WEBSTORE``) e os testes de
# economia liam/gravavam uma cópia antiga de ``market_species_defaults.json`` (30 espécies, sem
# carcha/premium_budget) em vez do arquivo do repo. Aponta para um diretório temporário.
_SESSION_DATA_DIR = Path(tempfile.mkdtemp(prefix="arkshop_tests_data_"))
os.environ["ARKSHOP_DATA_DIR"] = str(_SESSION_DATA_DIR)
atexit.register(shutil.rmtree, _SESSION_DATA_DIR, ignore_errors=True)

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from db_diagnostics import record_circuit_success


@pytest.fixture(autouse=True)
def _isolate_webstore_data_dir(tmp_path_factory, monkeypatch):
    """Diretório de dados novo por teste + reset do estado global de ``market_economy``.

    ``market_economy`` guarda o caminho em ``_DEFAULTS_FILE`` (singleton de módulo) e o conteúdo
    em cache por (path, mtime). Sem reset, um teste que grava defaults (PATCH admin, sync do
    catálogo) vazava o arquivo para os seguintes (falhas só na rodada completa).
    """
    data_dir = tmp_path_factory.mktemp("webstore_data")
    monkeypatch.setenv("ARKSHOP_DATA_DIR", str(data_dir))
    def _reset() -> None:
        me = sys.modules.get("market_economy")
        if me is not None:
            # Atribuição direta (não monkeypatch): o undo do monkeypatch restauraria
            # justamente o valor vazado de um teste anterior.
            me._DEFAULTS_FILE = None
            me.invalidate_defaults_cache()

    _reset()
    yield
    _reset()


@pytest.fixture(autouse=True)
def _isolate_steam_api_from_env(monkeypatch):
    """Evita chamadas reais à Steam Web API quando STEAM_API_KEY vem do .env local."""
    monkeypatch.delenv("STEAM_API_KEY", raising=False)
    record_circuit_success()


@pytest.fixture()
def db_session(tmp_path):
    path = tmp_path / "chat.db"
    engine = create_engine(f"sqlite:///{path}", future=True)
    with engine.connect() as conn:
        conn.execute(text(
            "CREATE TABLE cross_server_chat ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT,"
            "channel TEXT, source_server TEXT, steam_id TEXT,"
            "player_name TEXT, tribe_name TEXT DEFAULT '', message TEXT, "
            "created_at TEXT DEFAULT CURRENT_TIMESTAMP)"
        ))
        conn.execute(text(
            "CREATE TABLE cross_server_chat_mutes ("
            "steam_id TEXT PRIMARY KEY, muted_until TEXT, reason TEXT)"
        ))
        conn.commit()
    Session = sessionmaker(bind=engine)
    db = Session()
    try:
        yield db
    finally:
        db.close()
