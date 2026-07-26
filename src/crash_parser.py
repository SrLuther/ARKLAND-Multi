"""
Utilitários de análise de crash do ARK: Survival Evolved.

Extrai e interpreta arquivos .crashstack, CrashContext.runtime-xml e
blocos 'Fatal error!' do ShooterGame.log.
"""
from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import List, Optional


# DLLs/módulos do engine que NÃO são candidatos a "culpado" em crash
_ENGINE_DLL_PREFIXES = (
    "shootergameserver",
    "kernel32",
    "ntdll",
    "msvcrt",
    "vcruntime",
    "d3d",
    "opengl32",
    "dxgi",
    "ue4",
    "steamapi",
    "steamclient",
    "tier0",
    "vstdlib",
    "version",      # ArkApi principal (version.dll)
)


def _identify_crash_culprit(crash_text: str) -> str:
    """Retorna o primeiro DLL não-engine encontrado no call stack do crash."""
    for line in crash_text.splitlines():
        m = re.search(r'([\w\-]+\.dll)', line, re.IGNORECASE)
        if m:
            dll = m.group(1).lower()
            if not any(dll.startswith(p) for p in _ENGINE_DLL_PREFIXES):
                return m.group(1)
    return ""


# ── Tabela de diagnósticos conhecidos ─────────────────────────────────────────
# (padrão_no_erro, dll_culpada, diagnóstico_legível)
_CRASH_INTERPRETATIONS: List[tuple] = [
    ("access violation",  "",               "Acesso ilegal à memória (ponteiro nulo ou corrompido). "
                                             "Causa mais comum: plugin incompatível com a versão atual do ArkApi."),
    ("out of memory",     "",               "Servidor ficou sem memória RAM. "
                                             "Reduza o número de mods, players ou objetos no mundo."),
    ("stack overflow",    "",               "Estouro de pilha (recursão infinita). "
                                             "Algum plugin está em loop de chamada."),
    ("assertion failed",  "",               "Falha de asserção interna do engine. "
                                             "Pode indicar dados de jogo corrompidos ou versão incompatível."),
    ("divide by zero",    "",               "Divisão por zero. Bug em plugin ou lógica interna do servidor."),
    ("",  "libmariadb.dll",                 "Falha na biblioteca MariaDB. "
                                             "Verifique conectividade com o banco de dados e compatibilidade da DLL."),
    ("",  "libmysql.dll",                   "Falha na biblioteca MySQL. "
                                             "Verifique conectividade com o banco de dados."),
    ("",  "customshop.dll",                 "O plugin CustomShop causou o crash. "
                                             "Verifique o config.json e se a versão é compatível com o ArkApi."),
    ("",  "permissions.dll",                "O plugin ASE Permissions causou o crash. "
                                             "Atualize para a versão mais recente."),
    ("",  "arkshop.dll",                    "O plugin ArkShop causou o crash."),
    ("",  "steam_api.dll",                  "Falha no módulo Steam. "
                                             "Verifique a conexão com os servidores Steam."),
]


def _interpret_crash(error_msg: str, culprit: str) -> str:
    """Retorna um diagnóstico legível baseado na mensagem de erro e DLL culpada."""
    em = error_msg.lower()
    cp = culprit.lower()
    for err_pat, dll_pat, diagnosis in _CRASH_INTERPRETATIONS:
        err_match = (not err_pat) or (err_pat in em)
        dll_match = (not dll_pat) or (dll_pat == cp) or (dll_pat in cp)
        if err_match and dll_match:
            return diagnosis
    if culprit and not any(culprit.lower().startswith(p) for p in _ENGINE_DLL_PREFIXES):
        return (f"Plugin externo suspeito: {culprit}. "
                "Tente desativar temporariamente para confirmar.")
    # Fatal error! sozinho — provisório; crash_ai enriquece em seguida.
    if "fatal error" in em and len(em.strip()) < 40:
        return (
            "Crash fatal sem detalhe no extracto inicial. "
            "A IA integrada vai analisar o ShooterGame.log automaticamente; "
            "se não houver API key, será usada análise local do log."
        )
    return "Causa não identificada. Consulte o call stack e o ShooterGame.log para mais detalhes."


def _extract_error_message(lines: list) -> str:
    """Escolhe a melhor linha de erro (evita ficar só em 'Fatal error!')."""
    if not lines:
        return "Fatal error! (ver call stack)"
    preferred = []
    for ln in lines:
        low = ln.lower()
        if low in ("fatal error!", "fatal error"):
            continue
        if any(
            k in low
            for k in (
                "assertion",
                "exception",
                "access violation",
                "ensure ",
                "error:",
                "fatal error:",
                "out of memory",
                "stack overflow",
            )
        ):
            preferred.append(ln.strip()[:300])
    if preferred:
        return preferred[-1]
    for ln in lines:
        if ln.strip().lower() not in ("fatal error!", "fatal error"):
            return ln.strip()[:300]
    return lines[0].strip()[:300]


def _build_crashstack_record(cs_file: "Path", dump_files: list) -> dict:
    """Constrói um dict de registro de crash a partir de um arquivo .crashstack."""
    import os as _os
    cs_mtime = cs_file.stat().st_mtime
    ts = datetime.fromtimestamp(cs_mtime)
    nearest_dump_path = ""
    nearest_dump_kb   = 0
    if dump_files:
        best = min(dump_files, key=lambda x: abs(x[1] - cs_mtime))
        if abs(best[1] - cs_mtime) < 900:
            nearest_dump_path = str(best[0])
            try:
                nearest_dump_kb = best[0].stat().st_size // 1024
            except Exception:
                pass
    try:
        content = cs_file.read_text(encoding="utf-8", errors="replace")
    except Exception:
        content = ""
    lines = [ln.strip() for ln in content.splitlines() if ln.strip()]
    error_msg = _extract_error_message(lines)
    culprit   = _identify_crash_culprit(content)
    return {
        "folder":        cs_file.stem,
        "path":          str(cs_file),
        "timestamp":     ts,
        "error_message": error_msg,
        "call_stack":    lines[:25],
        "culprit":       culprit,
        "has_dump":      bool(nearest_dump_path),
        "dump_size_kb":  nearest_dump_kb,
        "dump_path":     nearest_dump_path,
        "diagnosis":     _interpret_crash(error_msg, culprit),
        "log_lines":     lines[:25],
        "source":        "crashstack",
    }


def _parse_crash_from_logs_dir(install_dir: str, saved_root: "Path | None" = None) -> List[dict]:
    """Detecta crashes pelos arquivos .crashstack e Dump*.dmp em Saved/Logs/.

    O ARK ASE padrão salva os crash reports diretamente na pasta de logs,
    não em Saved/Crashes/ como o UE4 puro faria.
    """
    if saved_root is None:
        saved_root = Path(install_dir) / "ShooterGame" / "Saved"
    logs_dir = saved_root / "Logs"
    if not logs_dir.exists():
        return []

    records: list[dict] = []
    try:
        crashstack_files = sorted(
            logs_dir.glob("*.crashstack"),
            key=lambda f: f.stat().st_mtime,
            reverse=True,
        )
        if not crashstack_files:
            return []

        # Pré-carrega Dump*.dmp para associação por proximidade de tempo
        dump_files = [(f, f.stat().st_mtime) for f in logs_dir.glob("Dump*.dmp")]

        for cs_file in crashstack_files:
            records.append(_build_crashstack_record(cs_file, dump_files))
    except Exception:
        pass

    return records


def _parse_crash_folder(crash_dir: Path) -> dict:
    """Extrai informações estruturadas de uma pasta de crash do ARK."""
    result: dict = {
        "folder":       crash_dir.name,
        "path":         str(crash_dir),
        "timestamp":    datetime.fromtimestamp(crash_dir.stat().st_mtime),
        "error_message": "",
        "call_stack":   [],
        "culprit":      "",
        "has_dump":     False,
        "dump_size_kb": 0,
        "dump_path":    "",
        "diagnosis":    "",
        "log_lines":    [],
    }

    # CrashContext.runtime-xml
    ctx_file = crash_dir / "CrashContext.runtime-xml"
    if ctx_file.exists():
        try:
            ctx = ctx_file.read_text(encoding="utf-8", errors="replace")
            m_err = re.search(r'<ErrorMessage>(.*?)</ErrorMessage>', ctx,
                              re.DOTALL | re.IGNORECASE)
            if m_err:
                result["error_message"] = m_err.group(1).strip()[:500]
            m_stack = re.search(r'<CallStack>(.*?)</CallStack>', ctx,
                                re.DOTALL | re.IGNORECASE)
            if m_stack:
                lines = [ln.strip() for ln in m_stack.group(1).splitlines() if ln.strip()]
                result["call_stack"] = lines[:20]
                result["culprit"] = _identify_crash_culprit("\n".join(lines))
        except Exception:
            pass

    # .dmp files
    try:
        dmp_files = sorted(crash_dir.glob("*.dmp"),
                           key=lambda f: f.stat().st_size, reverse=True)
        if dmp_files:
            result["has_dump"]     = True
            result["dump_size_kb"] = dmp_files[0].stat().st_size // 1024
            result["dump_path"]    = str(dmp_files[0])
    except Exception:
        pass

    _enrich_from_log_tail(crash_dir, result)
    result["diagnosis"] = _interpret_crash(result["error_message"], result["culprit"])
    return result


def _enrich_from_log_tail(crash_dir: "Path", result: dict) -> None:
    """Preenche log_lines, culprit e error_message a partir da cauda do ShooterGame.log."""
    log_file = crash_dir / "ShooterGame.log"
    if not log_file.exists():
        log_file = crash_dir.parent.parent / "Logs" / "ShooterGame.log"
    if not log_file.exists():
        return
    try:
        file_size = log_file.stat().st_size
        with open(log_file, "rb") as fh:
            fh.seek(max(0, file_size - 262_144))
            tail = fh.read().decode("utf-8", errors="replace")
        fatal_idx = tail.rfind("Fatal error!")
        if fatal_idx == -1:
            return
        start = max(0, fatal_idx - 2500)
        crash_section = tail[start:]
        lines = [ln.strip() for ln in crash_section.splitlines() if ln.strip()]
        result["log_lines"] = lines[:40]
        if not result["call_stack"]:
            result["call_stack"] = lines[:40]
        if not result["culprit"]:
            result["culprit"] = _identify_crash_culprit(crash_section)
        better = _extract_error_message(lines)
        if better and (
            not result.get("error_message")
            or result["error_message"].lower().strip() in ("fatal error!", "fatal error")
            or "ver call stack" in result["error_message"].lower()
        ):
            result["error_message"] = better
    except Exception:
        pass


def _extract_block_ts(content: str, pos: int, log_file: "Path") -> "datetime":
    """Extrai o timestamp da linha anterior a um bloco Fatal error!."""
    pre = content[max(0, pos - 120):pos]
    ts_match = re.search(r'\[(\d{4}\.\d{2}\.\d{2}-\d{2}\.\d{2}\.\d{2})', pre)
    if ts_match:
        try:
            return datetime.strptime(ts_match.group(1), "%Y.%m.%d-%H.%M.%S")
        except ValueError:
            pass
    return datetime.fromtimestamp(log_file.stat().st_mtime)


def _build_log_crash_record(block: str, idx: int, log_file: "Path", ts: "datetime") -> dict:
    """Constrói um dict de crash a partir de um bloco Fatal error! do log."""
    lines   = [ln.strip() for ln in block.splitlines() if ln.strip()]
    culprit = _identify_crash_culprit(block)
    error_msg = _extract_error_message(lines)
    return {
        "folder":        f"ShooterGame.log #{idx + 1}",
        "path":          str(log_file),
        "timestamp":     ts,
        "error_message": error_msg,
        "call_stack":    lines[:40],
        "culprit":       culprit,
        "has_dump":      False,
        "dump_size_kb":  0,
        "dump_path":     "",
        "diagnosis":     _interpret_crash(error_msg, culprit),
        "log_lines":     lines[:40],
        "source":        "log",
    }


def _parse_crash_from_log(install_dir: str, saved_root: "Path | None" = None) -> List[dict]:
    """Extrai blocos 'Fatal error!' do ShooterGame.log como registros sintéticos.

    Fallback para quando não há pastas de crash com .dmp — o crash fatal do ARK
    deixa rastro no log mesmo quando o UE4 crash reporter não gera dump.
    Inclui preamble (~2.5 KB antes do Fatal) — Error/Warning costumam estar ali.
    """
    if saved_root is None:
        saved_root = Path(install_dir) / "ShooterGame" / "Saved"
    log_file = saved_root / "Logs" / "ShooterGame.log"
    if not log_file.exists():
        return []

    records: list[dict] = []
    try:
        file_size = log_file.stat().st_size
        offset = max(0, file_size - 1024 * 1024)
        with open(log_file, "rb") as fh:
            fh.seek(offset)
            content = fh.read().decode("utf-8", errors="replace")

        fatal_positions = [m.start() for m in re.finditer(r'Fatal error!', content)]
        for idx, pos in enumerate(fatal_positions):
            next_pos = fatal_positions[idx + 1] if idx + 1 < len(fatal_positions) else min(len(content), pos + 4500)
            preamble_start = max(0, pos - 2500)
            block = content[preamble_start:next_pos]
            ts    = _extract_block_ts(content, pos, log_file)
            records.append(_build_log_crash_record(block, idx, log_file, ts))
    except Exception:
        pass

    records.sort(key=lambda r: r["timestamp"], reverse=True)
    return records


def _collect_crash_folders(saved_roots: list, records: list) -> None:
    """Escaneia pastas CrashReport-* e adiciona os registros encontrados."""
    for sr in saved_roots:
        crash_base = sr / "Crashes"
        if crash_base.exists():
            try:
                subdirs = [d for d in crash_base.iterdir() if d.is_dir()]
                subdirs.sort(key=lambda d: d.stat().st_mtime, reverse=True)
                records.extend(_parse_crash_folder(d) for d in subdirs)
            except Exception:
                pass


def _list_crash_records(install_dir: str, alt_save_dir: str = "") -> List[dict]:
    """Lista todos os registros de crash da instalação (mais recente primeiro).

    Combina pastas de dump em ShooterGame/Saved/Crashes/ com blocos
    'Fatal error!' do ShooterGame.log (crashs sem dump gerado).
    Também busca em AltSaveDirectoryName se fornecido.
    """
    records: list[dict] = []
    saved_root = Path(install_dir) / "ShooterGame" / "Saved"
    saved_roots: list[Path] = [saved_root]
    if alt_save_dir:
        alt_root = saved_root / alt_save_dir.strip()
        if alt_root != saved_root:
            saved_roots.append(alt_root)

    _collect_crash_folders(saved_roots, records)

    # ── 2. Arquivos .crashstack em Saved/Logs/ — ARK ASE padrão ──────────
    for sr in saved_roots:
        for cs in _parse_crash_from_logs_dir(install_dir, saved_root=sr):
            duplicate = any(
                abs((cs["timestamp"] - r["timestamp"]).total_seconds()) < 60
                for r in records
                if not r.get("source")
            )
            if not duplicate:
                records.append(cs)

    # ── 3. Fallback: blocos Fatal error! no ShooterGame.log ──────────────
    for sr in saved_roots:
        for lr in _parse_crash_from_log(install_dir, saved_root=sr):
            duplicate = any(
                abs((lr["timestamp"] - r["timestamp"]).total_seconds()) < 120
                for r in records
                if r.get("source") != "log"
            )
            if not duplicate:
                records.append(lr)

    records.sort(key=lambda r: r["timestamp"], reverse=True)
    return records


def _read_crash_folder_part(crash_dir: Path, parts: list) -> None:
    """Lê CrashContext.runtime-xml e .dmp da pasta de crash mais recente."""
    parts.append(f"Pasta de crash: {crash_dir.name}")
    ctx_file = crash_dir / "CrashContext.runtime-xml"
    if ctx_file.exists():
        try:
            ctx = ctx_file.read_text(encoding="utf-8", errors="replace")
            for tag, label in (("ErrorMessage", "Erro"), ("CallStack", None)):
                m = re.search(rf'<{tag}>(.*?)</{tag}>', ctx, re.DOTALL | re.IGNORECASE)
                if m:
                    content = m.group(1).strip()
                    if tag == "CallStack":
                        stack_lines = [sl.strip() for sl in content.splitlines() if sl.strip()]
                        if stack_lines:
                            culprit = _identify_crash_culprit("\n".join(stack_lines[:15]))
                            if culprit:
                                parts.append(f"** Possível causador: {culprit} **")
                            parts.append("Call Stack (CrashContext):")
                            for sl in stack_lines[:12]:
                                parts.append(f"  {sl}")
                    else:
                        parts.append(f"{label}: {content[:200]}")
        except Exception:
            pass
    try:
        dmp_files = sorted(crash_dir.glob("*.dmp"), key=lambda f: f.stat().st_size, reverse=True)
        if dmp_files:
            kb = dmp_files[0].stat().st_size // 1024
            parts.append(f"Dump gerado: {dmp_files[0].name} ({kb} KB) — em {crash_dir}")
    except Exception:
        pass


def _read_crash_log_part(base: Path, crash_dir: Optional[Path], parts: list) -> None:
    """Lê tail do ShooterGame.log e extrai bloco Fatal error!."""
    log_file = base / "ShooterGame" / "Saved" / "Logs" / "ShooterGame.log"
    if not log_file.exists() and crash_dir:
        alt = crash_dir / "ShooterGame.log"
        if alt.exists():
            log_file = alt
    if not log_file.exists():
        return
    try:
        file_size = log_file.stat().st_size
        offset = max(0, file_size - 20480)
        with open(log_file, "rb") as fh:
            fh.seek(offset)
            tail = fh.read().decode("utf-8", errors="replace")
        fatal_idx = tail.rfind("Fatal error!")
        if fatal_idx != -1:
            crash_section = tail[fatal_idx:]
            crash_lines = [cl for cl in crash_section.splitlines() if cl.strip()]
            culprit = _identify_crash_culprit(crash_section)
            if culprit and not any("Possível causador" in p for p in parts):
                parts.append(f"** Possível causador: {culprit} **")
            parts.append("Log (Fatal error!):")
            for cl in crash_lines[:20]:
                parts.append(f"  {cl.strip()}")
    except Exception:
        pass


def _read_crash_info(install_dir: str) -> str:
    """Lê arquivos de crash do ARK e retorna um resumo diagnóstico."""
    base = Path(install_dir)
    parts: list[str] = []
    crash_base = base / "ShooterGame" / "Saved" / "Crashes"
    crash_dir: Optional[Path] = None
    if crash_base.exists():
        try:
            subdirs = [d for d in crash_base.iterdir() if d.is_dir()]
            if subdirs:
                crash_dir = max(subdirs, key=lambda d: d.stat().st_mtime)
        except Exception:
            pass
    if crash_dir:
        _read_crash_folder_part(crash_dir, parts)
    _read_crash_log_part(base, crash_dir, parts)
    return "\n".join(parts)
