"""Ponte RCON da Web Store → RconClient compartilhado (off-thread, retry ASE)."""
from __future__ import annotations

import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeoutError
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from src.rcon_client import RconClient, RconError  # noqa: E402
from src.rcon_util import sanitize_rcon_password  # noqa: E402

# 12 workers: fan-out paralelo de 6 mapas + folga; 4 saturava quando tasks
# órfãs (future timeout sem cancel real) seguiam em retry no pool.
_RCON_POOL_WORKERS = max(4, int(os.environ.get("ARKSHOP_RCON_POOL_WORKERS", "12") or 12))
_EXECUTOR = ThreadPoolExecutor(max_workers=_RCON_POOL_WORKERS, thread_name_prefix="web-rcon")
_RCON_OP_TIMEOUT = 18.0
_RELOAD_CONNECT_RETRIES = 5
_RELOAD_RETRY_DELAY = 2.0


def _run_rcon_sync(
    host: str,
    port: int,
    password: str,
    command: str,
    *,
    connect_retries: int = 1,
    retry_delay: float = _RELOAD_RETRY_DELAY,
    deadline: float | None = None,
) -> str:
    pwd = sanitize_rcon_password(password)
    if not pwd:
        raise ValueError("Senha RCON não configurada")

    def _expired() -> bool:
        return deadline is not None and time.monotonic() >= deadline

    last_error = ""
    for attempt in range(1, max(1, connect_retries) + 1):
        if attempt > 1 and _expired():
            # Chamador já desistiu (future.result timeout) — não virar zombie
            # segurando um worker do pool com retries inúteis.
            last_error = last_error or "deadline excedido antes do retry"
            break
        client = RconClient(host, port, pwd)
        try:
            client.connect()
            ok, response = client.send_command_safe(command)
            if ok:
                return response
            last_error = response
            if _expired():
                break
            ok2, response2 = client.send_command_with_retry(command, retries=2, retry_delay=1.0)
            if ok2:
                return response2
            last_error = response2
        except RconError as exc:
            last_error = str(exc)
        except Exception as exc:
            last_error = str(exc)
        finally:
            try:
                client.disconnect()
            except Exception:
                pass

        if attempt < connect_retries and retry_delay > 0:
            sleep_for = retry_delay * attempt
            if deadline is not None:
                sleep_for = min(sleep_for, max(0.0, deadline - time.monotonic()))
            if sleep_for > 0:
                time.sleep(sleep_for)

    raise RuntimeError(last_error or "Falha RCON")


def rcon_command(
    host: str,
    port: int,
    password: str,
    command: str,
    timeout: float = _RCON_OP_TIMEOUT,
    connect_retries: int = 1,
) -> str:
    """Executa comando RCON em thread pool (não bloqueia worker Flask)."""
    deadline = time.monotonic() + max(1.0, float(timeout))
    future = _EXECUTOR.submit(
        _run_rcon_sync,
        host,
        port,
        password,
        command,
        connect_retries=connect_retries,
        deadline=deadline,
    )
    try:
        return future.result(timeout=timeout)
    except FuturesTimeoutError as exc:
        future.cancel()
        raise TimeoutError(f"RCON excedeu {timeout:.0f}s em {host}:{port}") from exc


def rcon_test_connection(host: str, port: int, password: str, timeout: float = 12.0) -> tuple[bool, str]:
    """Testa RCON com ListPlayers (leve, somente leitura)."""
    try:
        resp = rcon_command(host, port, password, "ListPlayers", timeout=timeout, connect_retries=2)
        return True, resp or "(conectado — sem jogadores online)"
    except Exception as exc:
        return False, str(exc)
