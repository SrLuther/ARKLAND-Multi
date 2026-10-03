"""Doctor — «Verificar saúde» do ARKLAND Server Manager.

Cada checagem é uma função independente ``(DoctorContext) -> CheckResult | list[CheckResult]``
registrada com :func:`register_check`. O runner executa cada uma em sua própria thread,
com timeout; exceção ou estouro de tempo viram um resultado **ERRO** daquela checagem
(as demais continuam). Nada aqui bloqueia a UI: use :func:`run_doctor_async`.

Para criar uma nova checagem::

    @register_check("minha_checagem", "Título legível")
    def _check_minha(ctx: DoctorContext):
        if tudo_certo:
            return ok("minha_checagem", "Título", "Detalhe")
        return warn("minha_checagem", "Título", "O que houve", hint="Como corrigir")
"""
from __future__ import annotations

import importlib
import logging
import os
import re
import shutil
import tempfile
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple, Union

from . import arkapi, paths
from .events import CAT_DIAG, diag_event
from .servers import ServerView, load_server_views, read_json_file, read_text_any

_LOG = logging.getLogger("arkland")

SEV_OK = "OK"
SEV_WARN = "AVISO"
SEV_ERR = "ERRO"
_SEV_ORDER = {SEV_OK: 0, SEV_WARN: 1, SEV_ERR: 2}

DEFAULT_CHECK_TIMEOUT_S = 15.0

# Limiares de disco (bytes livres)
DISK_ERR_BYTES = 2 * 1024 ** 3
DISK_WARN_BYTES = 10 * 1024 ** 3


@dataclass
class CheckResult:
    id: str
    title: str
    severity: str
    detail: str = ""
    hint: str = ""

    def to_dict(self) -> Dict[str, str]:
        return {"id": self.id, "title": self.title, "severity": self.severity,
                "detail": self.detail, "hint": self.hint}


def ok(id_: str, title: str, detail: str = "", hint: str = "") -> CheckResult:
    return CheckResult(id_, title, SEV_OK, detail, hint)


def warn(id_: str, title: str, detail: str = "", hint: str = "") -> CheckResult:
    return CheckResult(id_, title, SEV_WARN, detail, hint)


def err(id_: str, title: str, detail: str = "", hint: str = "") -> CheckResult:
    return CheckResult(id_, title, SEV_ERR, detail, hint)


@dataclass
class DoctorContext:
    config_dir: Path
    app_config: Dict[str, Any] = field(default_factory=dict)
    servers: List[ServerView] = field(default_factory=list)
    app: Any = None
    http_timeout: float = 5.0

    @classmethod
    def from_config_dir(cls, config_dir: Optional[Path] = None, app: Any = None,
                        http_timeout: float = 5.0) -> "DoctorContext":
        cdir = Path(config_dir) if config_dir else paths.app_data_dir()
        cfg = read_json_file(cdir / "config.json")
        return cls(
            config_dir=cdir,
            app_config=cfg if isinstance(cfg, dict) else {},
            servers=load_server_views(cdir, app),
            app=app,
            http_timeout=http_timeout,
        )

    def cfg_get(self, *keys: str, default: Any = None) -> Any:
        cur: Any = self.app_config
        for k in keys:
            if not isinstance(cur, dict) or k not in cur:
                return default
            cur = cur[k]
        return cur


CheckFn = Callable[[DoctorContext], Union[CheckResult, List[CheckResult]]]
CHECKS: List[Tuple[str, str, CheckFn]] = []


def register_check(check_id: str, title: str) -> Callable[[CheckFn], CheckFn]:
    def decorator(fn: CheckFn) -> CheckFn:
        CHECKS.append((check_id, title, fn))
        return fn
    return decorator


# ─────────────────────────────────────────────────────────────────────────────
# Runner
# ─────────────────────────────────────────────────────────────────────────────

def _run_one(check_id: str, title: str, fn: CheckFn, ctx: DoctorContext,
             timeout: float) -> List[CheckResult]:
    holder: Dict[str, Any] = {}

    def _target() -> None:
        try:
            holder["value"] = fn(ctx)
        except BaseException as exc:  # noqa: BLE001 — qualquer falha vira resultado ERRO
            holder["error"] = exc

    t = threading.Thread(target=_target, name=f"doctor-{check_id}", daemon=True)
    t.start()
    t.join(timeout)
    if t.is_alive():
        return [err(check_id, title, f"Tempo esgotado ({timeout:.0f}s) — a checagem não respondeu.",
                    "Verifique unidades de rede/discos lentos e tente novamente.")]
    if "error" in holder:
        exc = holder["error"]
        _LOG.warning("Doctor: checagem %s falhou: %r", check_id, exc, exc_info=exc)
        return [err(check_id, title, f"A checagem falhou: {type(exc).__name__}: {exc}",
                    "Gere o diagnóstico (.zip) e envie ao suporte.")]
    value = holder.get("value")
    if isinstance(value, CheckResult):
        return [value]
    if isinstance(value, (list, tuple)):
        return [r for r in value if isinstance(r, CheckResult)] or [
            ok(check_id, title, "Nada a verificar.")]
    return [ok(check_id, title, "Nada a verificar.")]


def run_doctor(ctx: DoctorContext, checks: Optional[Sequence[Tuple[str, str, CheckFn]]] = None,
               timeout: float = DEFAULT_CHECK_TIMEOUT_S,
               on_result: Optional[Callable[[CheckResult], None]] = None) -> List[CheckResult]:
    """Executa as checagens (em paralelo, cada uma com timeout). Ordem = ordem de registro."""
    selected = list(checks if checks is not None else CHECKS)
    outputs: List[Optional[List[CheckResult]]] = [None] * len(selected)

    def _worker(i: int, item: Tuple[str, str, CheckFn]) -> None:
        results = _run_one(item[0], item[1], item[2], ctx, timeout)
        outputs[i] = results
        if on_result is not None:
            for r in results:
                try:
                    on_result(r)
                except Exception:  # noqa: BLE001
                    _LOG.debug("on_result falhou", exc_info=True)

    runners = [threading.Thread(target=_worker, args=(i, item), daemon=True,
                                name=f"doctor-run-{item[0]}") for i, item in enumerate(selected)]
    for r in runners:
        r.start()
    for r in runners:
        r.join(timeout + 5.0)
    flat: List[CheckResult] = []
    for i, item in enumerate(selected):
        res = outputs[i]
        if res is None:
            res = [err(item[0], item[1], "A checagem não terminou.")]
        flat.extend(res)
    summ = summarize(flat)
    diag_event(CAT_DIAG, "Doctor executado", ok=summ["OK"], avisos=summ[SEV_WARN], erros=summ[SEV_ERR])
    return flat


def run_doctor_async(ctx: DoctorContext, on_done: Callable[[List[CheckResult]], None],
                     on_result: Optional[Callable[[CheckResult], None]] = None,
                     timeout: float = DEFAULT_CHECK_TIMEOUT_S) -> threading.Thread:
    """Roda o doctor numa thread de fundo; ``on_done`` vem dessa thread (use ``after`` na UI)."""

    def _go() -> None:
        try:
            results = run_doctor(ctx, timeout=timeout, on_result=on_result)
        except Exception as exc:  # noqa: BLE001
            _LOG.exception("Doctor falhou")
            results = [err("doctor", "Verificar saúde", f"{type(exc).__name__}: {exc}")]
        on_done(results)

    t = threading.Thread(target=_go, name="doctor-main", daemon=True)
    t.start()
    return t


def summarize(results: Sequence[CheckResult]) -> Dict[str, int]:
    out = {SEV_OK: 0, SEV_WARN: 0, SEV_ERR: 0}
    for r in results:
        out[r.severity] = out.get(r.severity, 0) + 1
    return out


def worst_severity(results: Sequence[CheckResult]) -> str:
    worst = SEV_OK
    for r in results:
        if _SEV_ORDER.get(r.severity, 0) > _SEV_ORDER[worst]:
            worst = r.severity
    return worst


def format_report(results: Sequence[CheckResult]) -> str:
    """Relatório em texto (vai para ``doctor.txt`` no pacote)."""
    lines = []
    summ = summarize(results)
    lines.append(f"Resumo: {summ[SEV_OK]} OK, {summ[SEV_WARN]} aviso(s), {summ[SEV_ERR]} erro(s)")
    lines.append("")
    for r in sorted(results, key=lambda x: -_SEV_ORDER.get(x.severity, 0)):
        lines.append(f"[{r.severity:<5}] {r.title}  ({r.id})")
        if r.detail:
            lines.append(f"         {r.detail}")
        if r.hint:
            lines.append(f"         Dica: {r.hint}")
    return "\n".join(lines) + "\n"


# ─────────────────────────────────────────────────────────────────────────────
# Checagens globais
# ─────────────────────────────────────────────────────────────────────────────

_REQUIRED_MODULES = (("customtkinter", "customtkinter"), ("requests", "requests"),
                     ("PIL", "Pillow"), ("psutil", "psutil"))
_OPTIONAL_MODULES = (("discord", "discord.py (bot oBobonic embutido)"),
                     ("pystray", "pystray (bandeja do sistema)"),
                     ("pymysql", "pymysql (banco da Web Store)"))


@register_check("python_deps", "Dependências Python")
def check_python_deps(ctx: DoctorContext) -> List[CheckResult]:
    results: List[CheckResult] = []
    missing = []
    for mod, label in _REQUIRED_MODULES:
        try:
            importlib.import_module(mod)
        except Exception as exc:  # noqa: BLE001
            missing.append(f"{label} ({type(exc).__name__})")
    if missing:
        results.append(err("python_deps", "Dependências Python obrigatórias",
                           "Falha ao importar: " + ", ".join(missing),
                           "Reinstale o app ou execute: pip install -r requirements.txt"))
    else:
        results.append(ok("python_deps", "Dependências Python obrigatórias",
                          ", ".join(lbl for _m, lbl in _REQUIRED_MODULES)))
    opt_missing = []
    for mod, label in _OPTIONAL_MODULES:
        try:
            importlib.import_module(mod)
        except Exception:  # noqa: BLE001 — opcionais: só avisa
            opt_missing.append(label)
    if opt_missing:
        results.append(warn("python_deps_optional", "Dependências Python opcionais",
                            "Não importadas: " + ", ".join(opt_missing),
                            "Só é um problema se você usa esse recurso."))
    else:
        results.append(ok("python_deps_optional", "Dependências Python opcionais", "Todas disponíveis."))
    return results


@register_check("app_data", "Pasta de dados e logs")
def check_app_data(ctx: DoctorContext) -> List[CheckResult]:
    results: List[CheckResult] = []
    cdir = ctx.config_dir
    try:
        cdir.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(prefix=".doctor-", dir=str(cdir))
        os.close(fd)
        os.unlink(tmp)
        results.append(ok("app_data", "Pasta de dados gravável", str(cdir)))
    except OSError as exc:
        results.append(err("app_data", "Pasta de dados gravável", f"{cdir}: {exc}",
                           "Verifique permissões da pasta %APPDATA%\\ARKLAND-ServerManager."))
    log_path = cdir / "logs" / paths.LOG_FILE_NAME
    if log_path.is_file():
        results.append(ok("app_log", "Arquivo de log ativo",
                          f"{log_path} ({log_path.stat().st_size // 1024} KB)"))
    else:
        results.append(warn("app_log", "Arquivo de log ativo", f"{log_path} não existe.",
                            "Reinicie o app; o logging é iniciado no boot."))
    return results


@register_check("config_files", "Arquivos de configuração do app")
def check_config_files(ctx: DoctorContext) -> List[CheckResult]:
    results: List[CheckResult] = []
    for name in ("config.json", "servers.json", "asm_servers.json"):
        p = ctx.config_dir / name
        if not p.is_file():
            if name == "config.json":
                results.append(warn(f"config_files.{name}", name, "Arquivo ainda não existe.",
                                    "Será criado quando você salvar as configurações."))
            continue
        try:
            import json
            json.loads(p.read_text(encoding="utf-8-sig"))
            results.append(ok(f"config_files.{name}", name, f"JSON válido ({p.stat().st_size} bytes)"))
        except Exception as exc:  # noqa: BLE001
            results.append(err(f"config_files.{name}", name, f"JSON inválido: {exc}",
                               "Restaure um backup (*.corrupt-*, *.bak) desta pasta."))
    try:
        corrupt = sorted(p.name for p in ctx.config_dir.glob("*.corrupt-*"))
    except OSError:
        corrupt = []
    if corrupt:
        results.append(warn("config_files.corrupt", "Cópias de config corrompida",
                            f"{len(corrupt)} arquivo(s): " + ", ".join(corrupt[:5]),
                            "O app já se recuperou; confira se alguma opção foi perdida."))
    return results


@register_check("steamcmd", "SteamCMD")
def check_steamcmd(ctx: DoctorContext) -> CheckResult:
    raw = str(ctx.cfg_get("steamcmd_path", default="") or "").strip()
    if not raw:
        return warn("steamcmd", "SteamCMD", "Caminho do SteamCMD não configurado.",
                    "Configurações › Geral › SteamCMD (necessário para instalar/atualizar servidor e mods).")
    p = Path(raw)
    exe = p if p.is_file() else p / "steamcmd.exe"
    if exe.is_file():
        return ok("steamcmd", "SteamCMD", str(exe))
    return err("steamcmd", "SteamCMD", f"steamcmd.exe não encontrado em: {raw}",
               "Corrija o caminho em Configurações ou use «Baixar SteamCMD».")


def _drive_anchor(path: Path) -> str:
    return path.anchor or str(path)


@register_check("disk_space", "Espaço em disco")
def check_disk_space(ctx: DoctorContext) -> List[CheckResult]:
    targets: Dict[str, Path] = {_drive_anchor(ctx.config_dir): ctx.config_dir}
    for s in ctx.servers:
        if s.install_dir:
            targets.setdefault(_drive_anchor(Path(s.install_dir)), Path(s.install_dir))
    results: List[CheckResult] = []
    for anchor, path in targets.items():
        probe = path
        while not probe.exists() and probe != probe.parent:
            probe = probe.parent
        rid = f"disk_space.{re.sub(r'[^A-Za-z0-9]', '', anchor) or 'root'}"
        try:
            free = shutil.disk_usage(str(probe)).free
        except OSError as exc:
            results.append(err(rid, f"Espaço em disco ({anchor})", str(exc)))
            continue
        gb = free / 1024 ** 3
        detail = f"{gb:.1f} GB livres em {anchor}"
        if free < DISK_ERR_BYTES:
            results.append(err(rid, f"Espaço em disco ({anchor})", detail,
                               "Libere espaço: saves, backups e logs crescem rápido."))
        elif free < DISK_WARN_BYTES:
            results.append(warn(rid, f"Espaço em disco ({anchor})", detail,
                                "Menos de 10 GB livres — planeje limpeza de backups."))
        else:
            results.append(ok(rid, f"Espaço em disco ({anchor})", detail))
    return results


def _default_backup_root(kind: str) -> str:
    root = os.environ.get("ARKLAND_BACKUP_ROOT", "").strip()
    if root:
        return str(Path(root) / kind)
    return r"D:\Backups\servers" if kind == "servers" else r"D:\Backups\database"


@register_check("backup_paths", "Pastas de backup")
def check_backup_paths(ctx: DoctorContext) -> List[CheckResult]:
    results: List[CheckResult] = []
    specs = [("backup", "servers", "Backup de servidores", bool(ctx.cfg_get("backup", "auto_backup", default=False))),
             ("db_backup", "database", "Backup do banco", bool(ctx.cfg_get("db_backup", "enabled", default=False)))]
    for key, kind, title, enabled in specs:
        configured = str(ctx.cfg_get(key, "backup_dir", default="") or "").strip()
        target = Path(configured or _default_backup_root(kind))
        rid = f"backup_paths.{key}"
        if not configured and not enabled:
            results.append(ok(rid, title, f"Desativado (padrão: {target})."))
            continue
        if target.is_dir():
            try:
                fd, tmp = tempfile.mkstemp(prefix=".doctor-", dir=str(target))
                os.close(fd)
                os.unlink(tmp)
                results.append(ok(rid, title, f"{target} (gravável)"))
            except OSError as exc:
                results.append(err(rid, title, f"{target} sem permissão de escrita: {exc}",
                                   "Escolha outra pasta ou ajuste permissões."))
            continue
        parent = target
        while not parent.exists() and parent != parent.parent:
            parent = parent.parent
        if parent.exists():
            results.append(warn(rid, title, f"{target} ainda não existe (será criada no 1º backup).",
                                "Nenhuma ação necessária se o caminho estiver correto."))
        else:
            results.append(err(rid, title, f"Unidade/pasta inexistente: {target}",
                               "Configure um caminho de backup em unidade disponível."))
    return results


@register_check("servers_present", "Servidores cadastrados")
def check_servers_present(ctx: DoctorContext) -> CheckResult:
    if not ctx.servers:
        return warn("servers_present", "Servidores cadastrados", "Nenhum servidor cadastrado.",
                    "Use o botão ＋ na barra lateral para adicionar um servidor.")
    tek = sum(1 for s in ctx.servers if s.mode == "tek")
    return ok("servers_present", "Servidores cadastrados",
              f"{len(ctx.servers)} servidor(es) ({tek} TEK, {len(ctx.servers) - tek} clássico).")


def _udp_tcp_ports(s: ServerView) -> List[Tuple[str, int, str]]:
    ports = [("udp", s.server_port, "porta do jogo"), ("udp", s.query_port, "porta de consulta")]
    if s.use_raw_sockets and s.server_port:
        ports.append(("udp", s.server_port + 1, "porta raw (jogo+1)"))
    ports.append(("tcp", s.rcon_port, "RCON"))
    return [(proto, port, role) for proto, port, role in ports if port]


@register_check("ports_duplicated", "Portas duplicadas")
def check_ports_duplicated(ctx: DoctorContext) -> CheckResult:
    usage: Dict[Tuple[str, int], List[str]] = {}
    for s in ctx.servers:
        for proto, port, role in _udp_tcp_ports(s):
            usage.setdefault((proto, port), []).append(f"{s.name or s.id} ({role})")
    clashes = {k: v for k, v in usage.items() if len(v) > 1}
    if not clashes:
        return ok("ports_duplicated", "Portas duplicadas", "Nenhum conflito de portas entre os servidores.")
    parts = [f"{proto.upper()} {port}: " + " × ".join(v) for (proto, port), v in sorted(clashes.items())]
    return err("ports_duplicated", "Portas duplicadas", "; ".join(parts[:6]),
               "Cada servidor precisa de portas de jogo/consulta/RCON únicas (veja a aba Geral do servidor).")


@register_check("webstore", "Web Store")
def check_webstore(ctx: DoctorContext) -> CheckResult:
    shop = ctx.cfg_get("shop", default={}) or {}
    api_key = str(shop.get("api_key") or "").strip() if isinstance(shop, dict) else ""
    if not api_key:
        return ok("webstore", "Web Store", "Não configurada (api_key vazia) — verificação ignorada.")
    base = ""
    try:
        from ..config_manager import ShopGlobalConfig
        from ..shop_integration import resolve_plugin_api_url
        from dataclasses import fields as _fields
        names = {f.name for f in _fields(ShopGlobalConfig)}
        base = resolve_plugin_api_url(ShopGlobalConfig(**{k: v for k, v in shop.items() if k in names}))
    except Exception:  # noqa: BLE001
        base = str(shop.get("central_url") or shop.get("public_url") or "")
    base = (base or "").rstrip("/")
    if not base:
        return warn("webstore", "Web Store", "api_key configurada, mas sem URL da loja.",
                    "Defina a URL em Configurações › Loja.")
    try:
        req = urllib.request.Request(f"{base}/api/health", headers={"User-Agent": "ARKLAND-Doctor/1.0"})
        with urllib.request.urlopen(req, timeout=ctx.http_timeout) as resp:
            code = int(resp.status)
        if 200 <= code < 300:
            return ok("webstore", "Web Store", f"{base} respondeu HTTP {code}.")
        return warn("webstore", "Web Store", f"{base} respondeu HTTP {code}.",
                    "Verifique se a loja está no ar e se a URL está correta.")
    except urllib.error.HTTPError as exc:
        return warn("webstore", "Web Store", f"{base} respondeu HTTP {exc.code}.",
                    "Verifique se a loja está no ar e se a URL está correta.")
    except Exception as exc:  # noqa: BLE001
        return warn("webstore", "Web Store", f"Não foi possível alcançar {base}: {type(exc).__name__}",
                    "Verifique internet/firewall e a URL da loja em Configurações.")


# ─────────────────────────────────────────────────────────────────────────────
# Checagens por servidor
# ─────────────────────────────────────────────────────────────────────────────

def _sid(s: ServerView, what: str) -> str:
    return f"server.{s.safe_label}.{what}"


def _stitle(s: ServerView, what: str) -> str:
    return f"{s.name or s.id}: {what}"


@register_check("server_install", "Instalação do servidor")
def check_server_install(ctx: DoctorContext) -> List[CheckResult]:
    results: List[CheckResult] = []
    for s in ctx.servers:
        rid, title = _sid(s, "install"), _stitle(s, "instalação")
        if not s.install_dir.strip():
            results.append(err(rid, title, "install_dir não configurado.",
                               "Defina a pasta de instalação na aba Geral do servidor."))
        elif not Path(s.install_dir).is_dir():
            results.append(err(rid, title, f"Pasta inexistente: {s.install_dir}",
                               "Corrija o caminho ou reinstale o servidor via SteamCMD."))
        elif not arkapi.server_exe_path(s.install_dir).is_file():
            results.append(err(rid, title, "ShooterGameServer.exe não encontrado em "
                               f"{arkapi.win64_dir(s.install_dir)}",
                               "Instale/valide o servidor com o SteamCMD (app 376030)."))
        else:
            results.append(ok(rid, title, f"{s.install_dir} (ShooterGameServer.exe presente)"))
    return results


@register_check("server_inis", "INIs do servidor")
def check_server_inis(ctx: DoctorContext) -> List[CheckResult]:
    results: List[CheckResult] = []
    for s in ctx.servers:
        if not s.install_dir or not Path(s.install_dir).is_dir():
            continue
        for fname in ("GameUserSettings.ini", "Game.ini"):
            p = s.ini_dir / fname
            rid, title = _sid(s, fname), _stitle(s, fname)
            if not p.is_file():
                results.append(warn(rid, title, f"Não existe: {p}",
                                    "Salve as configurações do servidor ou inicie-o uma vez para gerar o arquivo."))
                continue
            try:
                text = read_text_any(p, max_bytes=8 * 1024 * 1024)
                if not text.strip():
                    results.append(warn(rid, title, "Arquivo vazio.", "Salve o servidor para regenerar."))
                else:
                    results.append(ok(rid, title, f"Legível ({p.stat().st_size // 1024} KB)"))
            except OSError as exc:
                results.append(err(rid, title, f"Ilegível: {exc}",
                                   "Feche programas que usam o arquivo e verifique permissões."))
    return results


@register_check("server_admin_password", "Senha de administrador")
def check_admin_password(ctx: DoctorContext) -> List[CheckResult]:
    results: List[CheckResult] = []
    for s in ctx.servers:
        rid, title = _sid(s, "admin_password"), _stitle(s, "senha de administrador")
        if s.admin_password_set:
            results.append(ok(rid, title, "Preenchida."))
        else:
            results.append(err(rid, title, "ServerAdminPassword em branco.",
                               "Sem ela o RCON e os comandos de admin não funcionam; defina na aba Geral."))
    return results


@register_check("server_arkapi", "ArkApi")
def check_arkapi(ctx: DoctorContext) -> List[CheckResult]:
    results: List[CheckResult] = []
    for s in ctx.servers:
        if not s.install_dir or not Path(s.install_dir).is_dir():
            continue
        rid, title = _sid(s, "arkapi"), _stitle(s, "ArkApi")
        adir = arkapi.arkapi_dir(s.install_dir)
        if not adir.is_dir():
            results.append(warn(rid, title, f"Pasta ArkApi não encontrada ({adir}).",
                                "Normal se você não usa plugins; senão instale o ArkApi no servidor."))
            continue
        loader = arkapi.win64_dir(s.install_dir) / "version.dll"
        if not loader.is_file():
            results.append(warn(rid, title, "Pasta ArkApi existe, mas version.dll (loader) não está em Win64.",
                                "Reinstale o ArkApi (o loader carrega os plugins)."))
        elif not arkapi.plugins_dir(s.install_dir).is_dir():
            results.append(warn(rid, title, "ArkApi instalado, sem pasta Plugins.", "Crie/instale os plugins."))
        else:
            results.append(ok(rid, title, f"Instalado em {adir}"))
    return results


@register_check("server_plugins", "Plugins ArkApi")
def check_plugins(ctx: DoctorContext) -> List[CheckResult]:
    results: List[CheckResult] = []
    for s in ctx.servers:
        if not s.install_dir or not arkapi.plugins_dir(s.install_dir).is_dir():
            continue
        plugins = arkapi.list_plugins(s.install_dir)
        for pl in plugins:
            rid, title = _sid(s, f"plugin.{pl.name}"), _stitle(s, f"plugin {pl.name}")
            problems, hints = [], []
            if not pl.main_dll_present:
                problems.append(f"{pl.name}.dll ausente na pasta do plugin")
                hints.append(f"Copie {pl.name}.dll para {pl.path}")
            sev_err = not pl.main_dll_present
            if not pl.config_present:
                problems.append("config.json ausente")
                hints.append("Inicie o servidor uma vez ou copie a configuração padrão do plugin")
            if not problems:
                ver = f" v{pl.version}" if pl.version else ""
                results.append(ok(rid, title, f"DLL + config.json presentes{ver}"))
            elif sev_err:
                results.append(err(rid, title, "; ".join(problems), "; ".join(hints)))
            else:
                results.append(warn(rid, title, "; ".join(problems), "; ".join(hints)))
        # DLLs soltas direto em Plugins\ (não são carregadas como plugin)
        try:
            loose = [p.name for p in arkapi.plugins_dir(s.install_dir).glob("*.dll")]
        except OSError:
            loose = []
        if loose:
            results.append(warn(_sid(s, "plugins_loose"), _stitle(s, "DLLs soltas em Plugins"),
                                ", ".join(loose[:5]),
                                "Cada plugin deve ficar em Plugins\\<Nome>\\<Nome>.dll"))
    return results


@register_check("server_permissions", "Permissions.dll")
def check_permissions_dll(ctx: DoctorContext) -> List[CheckResult]:
    """Só verifica presença em disco do ``Permissions.dll`` no caminho esperado."""
    results: List[CheckResult] = []
    for s in ctx.servers:
        if not s.install_dir or not arkapi.arkapi_dir(s.install_dir).is_dir():
            continue
        rid, title = _sid(s, "permissions_dll"), _stitle(s, "Permissions.dll")
        dll = arkapi.permissions_dll_path(s.install_dir)
        if dll.is_file():
            results.append(ok(rid, title, f"Presente: {dll}"))
            continue
        installed = {p.name for p in arkapi.list_plugins(s.install_dir)}
        dependents = sorted(set(arkapi.PERMISSIONS_DEPENDENT_PLUGINS) & installed)
        hint = f"Instale o plugin Permissions em {dll.parent} (arquivo Permissions.dll)."
        if dependents:
            results.append(err(rid, title, f"Ausente em {dll}, mas há plugins que dependem dele: "
                               + ", ".join(dependents), hint))
        else:
            results.append(warn(rid, title, f"Ausente em {dll}.", hint))
    return results


_RAMP_RE = re.compile(r"^\s*LevelExperienceRampOverrides\s*=", re.IGNORECASE | re.MULTILINE)
_MAXXP_RE = re.compile(r"^\s*OverrideMaxExperiencePointsPlayer\s*=", re.IGNORECASE | re.MULTILINE)
_ENGRAM_RE = re.compile(r"^\s*OverridePlayerLevelEngramPoints\s*=", re.IGNORECASE | re.MULTILINE)


@register_check("server_level_toggle", "Progressões de nível (perfil × Game.ini)")
def check_level_toggle(ctx: DoctorContext) -> List[CheckResult]:
    results: List[CheckResult] = []
    for s in ctx.servers:
        if s.progressions_enabled is None:
            continue
        rid, title = _sid(s, "level_toggle"), _stitle(s, "progressões de nível")
        game_ini = s.ini_dir / "Game.ini"
        if not s.install_dir or not game_ini.is_file():
            results.append(ok(rid, title, "Game.ini ainda não existe — nada a comparar."))
            continue
        text = read_text_any(game_ini, max_bytes=16 * 1024 * 1024)
        ramp_lines = len(_RAMP_RE.findall(text))
        has_ramp, has_max, has_eng = ramp_lines > 0, bool(_MAXXP_RE.search(text)), bool(_ENGRAM_RE.search(text))
        present = [n for n, f in (("LevelExperienceRampOverrides", has_ramp),
                                  ("OverrideMaxExperiencePointsPlayer", has_max),
                                  ("OverridePlayerLevelEngramPoints", has_eng)) if f]
        if s.progressions_enabled is False and present:
            results.append(err(rid, title,
                               "Perfil diz progressões OFF, mas o Game.ini contém: " + ", ".join(present)
                               + f" ({ramp_lines} linha(s) de rampa).",
                               "Abra «Nível máximo do jogador», confira o toggle e salve com o servidor parado "
                               "(o salvar remove as chaves quando OFF)."))
        elif s.progressions_enabled is True and not has_ramp:
            results.append(warn(rid, title,
                                "Perfil diz progressões ON, mas o Game.ini não tem LevelExperienceRampOverrides.",
                                "Salve o servidor (parado) para gravar a rampa, ou desligue o toggle."))
        else:
            state = "ON" if s.progressions_enabled else "OFF"
            results.append(ok(rid, title, f"Consistente (perfil {state}; {ramp_lines} linha(s) de rampa no Game.ini)."))
    return results
