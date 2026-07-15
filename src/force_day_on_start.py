"""Força DayNumber via RCON (SetDay) após start/restart do servidor TEK."""
from __future__ import annotations

import logging
import threading
import time
from typing import Callable, Optional

_log = logging.getLogger("arkland")

# Poll RCON até sucesso — RUNNING do TEK chega cedo (~15s); o mundo pode demorar bem mais.
_INITIAL_DELAY_S = 10.0
_MAX_WAIT_S = 900.0  # 15 min
_BACKOFF_START_S = 5.0
_BACKOFF_MAX_S = 45.0


def schedule_force_day(
    *,
    server_id: str,
    server_name: str,
    rcon_host: str,
    rcon_port: int,
    rcon_password: str,
    day: int,
    on_log: Optional[Callable[[str, str], None]] = None,
    save_world: bool = True,
) -> None:
    """Lança thread daemon que espera RCON e aplica SetDay <day>."""
    t = threading.Thread(
        target=_apply_force_day_worker,
        kwargs={
            "server_id": server_id,
            "server_name": server_name,
            "rcon_host": rcon_host or "127.0.0.1",
            "rcon_port": int(rcon_port),
            "rcon_password": rcon_password or "",
            "day": int(day),
            "on_log": on_log,
            "save_world": save_world,
        },
        daemon=True,
        name=f"ForceDay-{server_id[:8]}",
    )
    t.start()


def _emit(on_log: Optional[Callable[[str, str], None]], msg: str, level: str) -> None:
    _log.log(
        logging.WARNING if level == "warning" else logging.INFO
        if level == "info"
        else logging.ERROR,
        msg,
    )
    if on_log:
        try:
            on_log(msg, level)
        except Exception:
            pass


def _apply_force_day_worker(
    *,
    server_id: str,
    server_name: str,
    rcon_host: str,
    rcon_port: int,
    rcon_password: str,
    day: int,
    on_log: Optional[Callable[[str, str], None]],
    save_world: bool,
) -> None:
    from .rcon_client import RconClient
    from .rcon_util import sanitize_rcon_password

    label = server_name or server_id
    day = max(0, min(int(day), 2_147_483_647))
    pwd = sanitize_rcon_password(rcon_password)
    if not pwd:
        _emit(
            on_log,
            f"[ForceDay] {label}: senha RCON/admin vazia — SetDay {day} não enviado.",
            "warning",
        )
        return

    _emit(
        on_log,
        f"[ForceDay] {label}: agendado SetDay {day} (aguarda RCON, até {_MAX_WAIT_S:.0f}s).",
        "info",
    )
    time.sleep(_INITIAL_DELAY_S)

    deadline = time.monotonic() + _MAX_WAIT_S
    delay = _BACKOFF_START_S
    last_err = "timeout"
    attempt = 0

    while time.monotonic() < deadline:
        attempt += 1
        client: RconClient | None = None
        try:
            client = RconClient(rcon_host, rcon_port, pwd)
            client.connect()
            ok, resp = client.send_command_with_retry(f"SetDay {day}", retries=3)
            if not ok:
                last_err = resp or "SetDay falhou"
                raise RuntimeError(last_err)

            save_note = ""
            if save_world:
                sok, sresp = client.send_command_with_retry("SaveWorld", retries=2)
                if sok:
                    save_note = " + SaveWorld"
                else:
                    save_note = f" (SaveWorld falhou: {sresp})"

            _emit(
                on_log,
                f"[ForceDay] {label}: SetDay {day} aplicado"
                f" (tentativa {attempt}){save_note}.",
                "info",
            )
            return
        except Exception as exc:
            last_err = str(exc)
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            sleep_for = min(delay, remaining, _BACKOFF_MAX_S)
            _emit(
                on_log,
                f"[ForceDay] {label}: RCON ainda indisponível "
                f"(tentativa {attempt}): {last_err} — retry em {sleep_for:.0f}s.",
                "warning",
            )
            time.sleep(sleep_for)
            delay = min(delay * 1.5, _BACKOFF_MAX_S)
        finally:
            if client is not None:
                try:
                    client.disconnect()
                except Exception:
                    pass

    _emit(
        on_log,
        f"[ForceDay] {label}: falha ao aplicar SetDay {day} após {_MAX_WAIT_S:.0f}s "
        f"({attempt} tentativa(s)). Último erro: {last_err}",
        "error",
    )
