"""Coletor do pacote de diagnóstico (.zip).

Conteúdo (tudo com segredos mascarados ANTES de entrar no zip)::

    app_info.json            versão do app, Python, SO, exe, modo (clássico/TEK), hora
    README.txt               o que é o pacote e o que foi mascarado
    doctor.json / doctor.txt resultado de «Verificar saúde»
    events.json              últimos eventos de domínio (diag_event)
    logs/arkland.log*        logs recentes (últimos N MB)
    config/*.json            config.json, servers.json, asm_servers.json, ui_prefs.json…
    servers/<nome-id>/state.json
    servers/<nome-id>/ini/GameUserSettings.ini, Game.ini
    servers/<nome-id>/arkapi/plugins.json, plugins/<Plugin>/config.json, logs/*

Como camada extra, todos os valores de chaves sensíveis lidos das configs do app são
varridos (``scrub``) em TODO o texto do pacote — um segredo que escapasse às regras
por formato diferente ainda seria removido.
"""
from __future__ import annotations

import json
import logging
import os
import re
import zipfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from . import arkapi, paths
from .boot import collect_app_info
from .doctor import CheckResult, DoctorContext, format_report, run_doctor, summarize
from .events import CAT_DIAG, diag_event, recent_events
from .redact import (OPTIONAL_RULES, REDACTED, REDACTION_RULES, SENSITIVE_KEYWORDS, is_sensitive_key,
                     redact_obj, redact_text)
from .servers import ServerView, load_server_views, read_json_file, read_text_any

_LOG = logging.getLogger("arkland")

MB = 1024 * 1024
DEFAULT_LOG_BUDGET_BYTES = 4 * MB          # «últimos N MB» de log
DEFAULT_MAX_ZIP_BYTES = 25 * MB            # teto do .zip final
DISCORD_MAX_ZIP_BYTES = int(7.5 * MB)      # webhook aceita ~8 MB
MAX_CONFIG_JSON_BYTES = 3 * MB
MAX_INI_BYTES = 2 * MB
MAX_PLUGIN_CONFIG_BYTES = 512 * 1024
MAX_ARKAPI_LOG_BYTES = 200 * 1024
ARKAPI_LOG_FILES = 3
MIN_SECRET_LEN = 6                          # varredura por valor só p/ segredos ≥ 6 chars

# Arquivos .json do app que nunca entram (credenciais puras).
_SKIP_CONFIG_NAME = re.compile(r"(token|secret|credential|cookie|keystore)", re.IGNORECASE)

# Tentativas de reduzir o pacote se passar do teto (fator aplicado a logs/INIs).
_SCALES = (1.0, 0.5, 0.25, 0.1)


@dataclass
class CollectResult:
    path: Path
    size: int
    files: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    over_limit: bool = False
    doctor_summary: Dict[str, int] = field(default_factory=dict)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _tail_bytes(path: Path, limit: int) -> Tuple[bytes, bool]:
    """Últimos ``limit`` bytes do arquivo (alinhado ao início de linha) e flag de truncado."""
    size = path.stat().st_size
    with open(path, "rb") as fh:
        if size > limit:
            fh.seek(size - limit)
            data = fh.read()
            nl = data.find(b"\n")
            if 0 <= nl < len(data) - 1:
                data = data[nl + 1:]
            return data, True
        return fh.read(), False


def _gather_secret_values(config_dir: Path) -> List[str]:
    """Valores de chaves sensíveis nas configs do app (para a varredura por valor)."""
    found: set[str] = set()

    def walk(node: Any, force: bool = False) -> None:
        if isinstance(node, dict):
            for k, v in node.items():
                walk(v, force or is_sensitive_key(k))
        elif isinstance(node, (list, tuple)):
            for v in node:
                walk(v, force)
        elif force and isinstance(node, str):
            val = node.strip()
            if len(val) >= MIN_SECRET_LEN:
                found.add(val)

    try:
        for p in Path(config_dir).glob("*.json"):
            if p.stat().st_size <= MAX_CONFIG_JSON_BYTES:
                data = read_json_file(p)
                if data is not None:
                    walk(data)
    except OSError:
        pass
    # mais longos primeiro (evita substituição parcial)
    return sorted(found, key=len, reverse=True)


class _Bundle:
    """Acumula entradas do zip, aplicando mascaramento + varredura por valor."""

    def __init__(self, secrets: Iterable[str]) -> None:
        self.entries: Dict[str, bytes] = {}
        self._secrets = list(secrets)

    def scrub(self, text: str) -> str:
        text = redact_text(text)
        for secret in self._secrets:
            if secret in text:
                text = text.replace(secret, REDACTED)
        return text

    def add_text(self, name: str, text: str) -> None:
        self.entries[name] = self.scrub(text).encode("utf-8")

    def add_json(self, name: str, obj: Any) -> None:
        safe = redact_obj(obj)
        self.entries[name] = self.scrub(json.dumps(safe, indent=2, ensure_ascii=False, default=str)).encode("utf-8")


# ─────────────────────────────────────────────────────────────────────────────
# Seções do pacote
# ─────────────────────────────────────────────────────────────────────────────

def _add_logs(b: _Bundle, budget: int, warnings: List[str]) -> None:
    logs = paths.logs_dir()
    names = [paths.LOG_FILE_NAME] + [f"{paths.LOG_FILE_NAME}.{i}" for i in range(1, 8)]
    remaining = budget
    for name in names:
        p = logs / name
        if remaining <= 0:
            break
        try:
            if not p.is_file():
                continue
            data, truncated = _tail_bytes(p, remaining)
        except OSError as exc:
            warnings.append(f"Log {name} ilegível: {exc}")
            continue
        remaining -= len(data)
        text = data.decode("utf-8", errors="replace")
        if truncated:
            text = f"[... início truncado pelo limite de tamanho ...]\n{text}"
        b.add_text(f"logs/{name}", text)


def _add_app_configs(b: _Bundle, config_dir: Path, scale: float, warnings: List[str]) -> None:
    try:
        candidates = sorted(Path(config_dir).glob("*.json"))
    except OSError as exc:
        warnings.append(f"Pasta de configs ilegível: {exc}")
        return
    for p in candidates:
        if _SKIP_CONFIG_NAME.search(p.name):
            continue
        try:
            if p.stat().st_size > MAX_CONFIG_JSON_BYTES * scale:
                warnings.append(f"{p.name} ignorado (muito grande: {p.stat().st_size // 1024} KB)")
                continue
            raw = p.read_text(encoding="utf-8-sig", errors="replace")
        except OSError as exc:
            warnings.append(f"{p.name} ilegível: {exc}")
            continue
        try:
            b.add_json(f"config/{p.name}", json.loads(raw))
        except ValueError:
            b.add_text(f"config/{p.name}", raw)


def _add_server(b: _Bundle, s: ServerView, scale: float, warnings: List[str]) -> None:
    base = f"servers/{s.safe_label}"
    install = Path(s.install_dir) if s.install_dir else None
    install_ok = bool(install and install.is_dir())
    state: Dict[str, Any] = {
        "mode": s.mode, "id": s.id, "name": s.name, "map": s.map,
        "status": s.status, "install_dir": s.install_dir, "install_dir_exists": install_ok,
        "ports": s.all_ports(), "admin_password_set": s.admin_password_set,
        "player_level_progressions_enabled": s.progressions_enabled,
        "player_ramp_entry_count": s.ramp_entry_count,
        "server_exe_present": bool(install_ok and arkapi.server_exe_path(s.install_dir).is_file()),
    }
    ini_info: Dict[str, Any] = {}
    if install_ok:
        for fname in ("GameUserSettings.ini", "Game.ini"):
            p = s.ini_dir / fname
            if not p.is_file():
                ini_info[fname] = {"exists": False}
                continue
            try:
                st = p.stat()
                text = read_text_any(p, max_bytes=int(MAX_INI_BYTES * scale))
                truncated = st.st_size > int(MAX_INI_BYTES * scale)
                if truncated:
                    text += "\n; [... arquivo truncado pelo limite de tamanho ...]\n"
                ini_info[fname] = {"exists": True, "size": st.st_size, "truncated": truncated,
                                   "modified": datetime.fromtimestamp(st.st_mtime).isoformat(timespec="seconds")}
                b.add_text(f"{base}/ini/{fname}", text)
            except OSError as exc:
                ini_info[fname] = {"exists": True, "error": str(exc)}
                warnings.append(f"{s.name}: {fname} ilegível ({exc})")
    state["ini_files"] = ini_info
    b.add_json(f"{base}/state.json", state)

    if not install_ok:
        return
    plugins = arkapi.list_plugins(s.install_dir)
    b.add_json(f"{base}/arkapi/plugins.json", {
        "arkapi_dir_exists": arkapi.arkapi_dir(s.install_dir).is_dir(),
        "version_dll_present": (arkapi.win64_dir(s.install_dir) / "version.dll").is_file(),
        "permissions_dll_present": arkapi.permissions_dll_path(s.install_dir).is_file(),
        "permissions_dll_expected_at": str(arkapi.permissions_dll_path(s.install_dir)),
        "plugins": [pl.to_dict() for pl in plugins],
    })
    for pl in plugins:
        cfg = pl.path / "config.json"
        try:
            if cfg.is_file() and cfg.stat().st_size <= MAX_PLUGIN_CONFIG_BYTES:
                raw = cfg.read_text(encoding="utf-8-sig", errors="replace")
                try:
                    b.add_json(f"{base}/arkapi/plugins/{pl.name}/config.json", json.loads(raw))
                except ValueError:
                    b.add_text(f"{base}/arkapi/plugins/{pl.name}/config.json", raw)
        except OSError as exc:
            warnings.append(f"{s.name}: config do plugin {pl.name} ilegível ({exc})")
    for ldir in arkapi.arkapi_log_dirs(s.install_dir):
        try:
            files = sorted((f for f in ldir.iterdir() if f.is_file()),
                           key=lambda f: f.stat().st_mtime, reverse=True)[:ARKAPI_LOG_FILES]
        except OSError:
            continue
        for f in files:
            try:
                data, truncated = _tail_bytes(f, int(MAX_ARKAPI_LOG_BYTES * scale))
            except OSError:
                continue
            text = data.decode("utf-8", errors="replace")
            if truncated:
                text = f"[... início truncado ...]\n{text}"
            b.add_text(f"{base}/arkapi/logs/{ldir.name}__{f.name}", text)


_README = """ARKLAND Server Manager — pacote de diagnóstico
================================================

Gerado em {when} (app v{version}, modo {mode}).

Segredos mascarados automaticamente antes de entrar neste pacote: tokens, senhas
(ServerPassword, ServerAdminPassword, RCON, SMTP, banco…), API keys, webhooks, cookies,
cabeçalhos Authorization/Bearer, hashes/segredos de configuração e credenciais em URLs.
O texto «{redacted}» marca o que foi removido.

NÃO são anonimizados nesta versão: IPs, nomes de servidor e SteamIDs.

Conteúdo: app_info.json, doctor.json/.txt (verificação de saúde), events.json, logs/,
config/ (configs do app), servers/<nome>/ (estado, INIs, plugins ArkApi e logs).
"""


def _build_bundle(*, config_dir: Path, servers: List[ServerView], doctor_results: List[CheckResult],
                  mode: str, scale: float, warnings: List[str]) -> Dict[str, bytes]:
    b = _Bundle(_gather_secret_values(config_dir))
    info = collect_app_info(mode)
    info["servers_count"] = len(servers)
    info["doctor_summary"] = summarize(doctor_results)
    try:
        import logging as _lg
        info["log_level"] = _lg.getLevelName(_lg.getLogger().level)
    except Exception:  # noqa: BLE001
        pass
    b.add_json("app_info.json", info)
    b.add_text("README.txt", _README.format(
        when=info["generated_at"], version=info["app_version"], mode=mode, redacted=REDACTED))
    b.add_json("redaction_info.json", {
        "placeholder": REDACTED,
        "static_rules": [r.name for r in REDACTION_RULES],
        "optional_rules_available": list(OPTIONAL_RULES),
        "sensitive_key_keywords": list(SENSITIVE_KEYWORDS),
    })
    b.add_json("doctor.json", {"summary": summarize(doctor_results),
                               "results": [r.to_dict() for r in doctor_results]})
    b.add_text("doctor.txt", format_report(doctor_results))
    b.add_json("events.json", recent_events())
    _add_logs(b, int(DEFAULT_LOG_BUDGET_BYTES * scale), warnings)
    _add_app_configs(b, config_dir, scale, warnings)
    for s in servers:
        try:
            _add_server(b, s, scale, warnings)
        except Exception as exc:  # noqa: BLE001 — um servidor com problema não aborta o pacote
            _LOG.warning("Coleta do servidor %s falhou", s.name, exc_info=True)
            warnings.append(f"{s.name}: coleta falhou ({type(exc).__name__}: {exc})")
    return b.entries


def _write_zip(target: Path, entries: Dict[str, bytes]) -> int:
    tmp = target.with_suffix(".part")
    with zipfile.ZipFile(tmp, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for name in sorted(entries):
            zf.writestr(name, entries[name])
    os.replace(tmp, target)
    return target.stat().st_size


def collect_diagnostics(*, app: Any = None, mode: Optional[str] = None,
                        config_dir: Optional[Path] = None, out_dir: Optional[Path] = None,
                        max_zip_bytes: int = DEFAULT_MAX_ZIP_BYTES,
                        doctor_results: Optional[List[CheckResult]] = None,
                        run_doctor_checks: bool = True, http_timeout: float = 4.0) -> CollectResult:
    """Gera o .zip de diagnóstico e devolve ``CollectResult``.

    Se o pacote passar de ``max_zip_bytes`` o coletor reduz logs/INIs em passos (100 %, 50 %,
    25 %, 10 %); se ainda assim passar, ``over_limit=True`` (o chamador decide o que fazer).
    """
    cdir = Path(config_dir) if config_dir else paths.app_data_dir()
    odir = Path(out_dir) if out_dir else paths.diagnostics_dir()
    odir.mkdir(parents=True, exist_ok=True)
    if mode is None:
        mode = "tek" if getattr(app, "asm_config_manager", None) is not None else "classic" if app is not None else "?"

    ctx = DoctorContext.from_config_dir(cdir, app=app, http_timeout=http_timeout)
    if doctor_results is None:
        doctor_results = run_doctor(ctx, timeout=10.0) if run_doctor_checks else []

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    target = odir / f"arkland-diagnostico-{stamp}.zip"
    n = 1
    while target.exists():
        n += 1
        target = odir / f"arkland-diagnostico-{stamp}-{n}.zip"

    warnings: List[str] = []
    size = 0
    entries: Dict[str, bytes] = {}
    over = True
    for scale in _SCALES:
        warnings = []
        entries = _build_bundle(config_dir=cdir, servers=ctx.servers, doctor_results=doctor_results,
                                mode=mode, scale=scale, warnings=warnings)
        size = _write_zip(target, entries)
        if size <= max_zip_bytes:
            over = False
            break
        if scale != _SCALES[-1]:
            target.unlink(missing_ok=True)
    if over:
        warnings.append(f"Pacote ({size // 1024} KB) acima do limite de {max_zip_bytes // 1024} KB mesmo reduzido.")
    result = CollectResult(path=target, size=size, files=sorted(entries), warnings=warnings,
                           over_limit=over, doctor_summary=summarize(doctor_results))
    diag_event(CAT_DIAG, "Pacote de diagnóstico gerado", file=str(target), size_kb=size // 1024,
               files=len(entries), over_limit=over, warnings=len(warnings))
    return result
