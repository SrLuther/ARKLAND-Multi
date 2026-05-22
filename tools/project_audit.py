#!/usr/bin/env python3
"""
tools/project_audit.py
======================
Scanner arquitetural profissional para o projeto ARKLAND-Multi.

Executa Ruff, Pyright, MyPy (se disponíveis) e análise AST própria,
consolidando tudo num único relatório TXT + JSON + Markdown.

Uso:
    python tools/project_audit.py
    python tools/project_audit.py --verbose
    python tools/project_audit.py --fix
    python tools/project_audit.py --no-mypy --no-pyright
    python tools/project_audit.py --max-func-lines 80 --max-file-lines 300
"""
from __future__ import annotations

import argparse
import ast
import collections
import json
import re
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

# ─────────────────────────────────────────────────────────────────────────────
# CONFIGURAÇÃO
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class AuditConfig:
    root: Path = field(default_factory=lambda: Path("."))
    src_dirs: list[str] = field(default_factory=lambda: ["src", "tools"])
    exclude_dirs: list[str] = field(default_factory=lambda: [
        ".venv", ".git", "__pycache__", "build", "dist",
        ".python", ".python-full", ".python-full", "node_modules",
        "installer", "plugin", "ig",
    ])

    # Thresholds
    max_file_lines: int = 500
    large_file_lines: int = 1000
    huge_file_lines: int = 3000
    max_function_lines: int = 50
    max_function_params: int = 7
    max_class_methods: int = 30
    max_class_lines: int = 500

    # Ferramentas externas
    use_ruff: bool = True
    use_mypy: bool = True
    use_pyright: bool = True

    # Opções de saída
    verbose: bool = False
    fix: bool = False
    output_dir: Path = field(default_factory=lambda: Path("tools/reports"))


# ─────────────────────────────────────────────────────────────────────────────
# CORES ANSI (compatível com Windows via VT mode)
# ─────────────────────────────────────────────────────────────────────────────

def _setup_windows_console() -> None:
    """Força UTF-8 e VT mode no terminal Windows."""
    if sys.platform != "win32":
        return
    # Força UTF-8 no stdout/stderr
    try:
        import io
        if hasattr(sys.stdout, "buffer"):
            sys.stdout = io.TextIOWrapper(
                sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True
            )
        if hasattr(sys.stderr, "buffer"):
            sys.stderr = io.TextIOWrapper(
                sys.stderr.buffer, encoding="utf-8", errors="replace", line_buffering=True
            )
    except Exception:
        pass
    # Tenta habilitar chcp 65001
    try:
        subprocess.run(["chcp", "65001"], capture_output=True, shell=True)
    except Exception:
        pass


def _enable_ansi() -> bool:
    if sys.platform == "win32":
        try:
            import ctypes
            k32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
            mode = ctypes.c_ulong()
            handle = k32.GetStdHandle(-11)
            if k32.GetConsoleMode(handle, ctypes.byref(mode)):
                k32.SetConsoleMode(handle, mode.value | 4)
            return True
        except Exception:
            return False
    return True


_ANSI = _enable_ansi()


def _c(text: str, code: str) -> str:
    return f"\033[{code}m{text}\033[0m" if _ANSI else text


def red(t: str) -> str:    return _c(t, "31")
def yellow(t: str) -> str: return _c(t, "33")
def green(t: str) -> str:  return _c(t, "32")
def cyan(t: str) -> str:   return _c(t, "36")
def bold(t: str) -> str:   return _c(t, "1")
def dim(t: str) -> str:    return _c(t, "2")


# ─────────────────────────────────────────────────────────────────────────────
# BARRA DE PROGRESSO (sem dependências externas)
# ─────────────────────────────────────────────────────────────────────────────

class Progress:
    def __init__(self, total: int, width: int = 38) -> None:
        self.total = max(total, 1)
        self.width = width
        self.current = 0
        self._start = time.time()

    def update(self, label: str = "") -> None:
        self.current += 1
        pct = self.current / self.total
        filled = int(self.width * pct)
        bar = "\u2588" * filled + "\u2591" * (self.width - filled)
        elapsed = time.time() - self._start
        suffix = f" {label[:35]:<35}" if label else ""
        line = f"\r  {cyan(bar)} {pct:>5.1%}{suffix}  {dim(f'{elapsed:.1f}s')}"
        sys.stdout.write(line)
        sys.stdout.flush()
        if self.current >= self.total:
            print()


# ─────────────────────────────────────────────────────────────────────────────
# MODELO DE DADOS
# ─────────────────────────────────────────────────────────────────────────────

CATEGORY_LABELS: dict[str, str] = {
    "import":         "Imports",
    "undefined":      "Undefined Names",
    "typing":         "Tipagem",
    "complexity":     "Complexidade",
    "structure":      "Estrutura",
    "modularization": "Modularização",
    "tkinter":        "Tkinter",
    "other":          "Outros",
}

SEVERITY_ORDER = {"error": 0, "warning": 1, "info": 2}


@dataclass
class Issue:
    file: str
    line: int
    col: int
    code: str
    message: str
    severity: str   # "error" | "warning" | "info"
    category: str   # chave de CATEGORY_LABELS
    source: str     # "ruff" | "mypy" | "pyright" | "ast"

    def as_dict(self) -> dict:
        return {
            "file": self.file,
            "line": self.line,
            "col": self.col,
            "code": self.code,
            "message": self.message,
            "severity": self.severity,
            "category": self.category,
            "source": self.source,
        }

    def __str__(self) -> str:
        sev_char = {
            "error": red("E"), "warning": yellow("W"), "info": cyan("I")
        }.get(self.severity, " ")
        return (
            f"  [{sev_char}] {dim(f'{self.source:>7}')}  "
            f"{self.file}:{self.line}  "
            f"{bold(self.code)}  {self.message}"
        )


# ─────────────────────────────────────────────────────────────────────────────
# UTILITÁRIOS
# ─────────────────────────────────────────────────────────────────────────────

def _run(cmd: list[str], cwd: Path) -> tuple[int, str, str]:
    """Executa um subprocess; nunca levanta exceção."""
    try:
        result = subprocess.run(
            cmd, cwd=str(cwd),
            capture_output=True, text=True,
            encoding="utf-8", errors="replace",
        )
        return result.returncode, result.stdout, result.stderr
    except FileNotFoundError:
        return -1, "", f"not found: {cmd[0]}"
    except Exception as exc:
        return -1, "", str(exc)


def _find_python(root: Path) -> str:
    """Prefere .python-full local; fallback sys.executable."""
    for candidate in [
        root / ".python-full" / "python.exe",
        root / ".python-full" / "python",
        root / ".python" / "python.exe",
        root / ".python" / "python",
    ]:
        if candidate.exists():
            return str(candidate)
    return sys.executable


def _rel(path: str | Path, root: Path) -> str:
    try:
        return str(Path(path).relative_to(root))
    except ValueError:
        return str(path)


# ─────────────────────────────────────────────────────────────────────────────
# RUNNER: RUFF
# ─────────────────────────────────────────────────────────────────────────────

_RUFF_CAT: dict[str, str] = {
    "F": "import", "I": "import", "TCH": "import",
    "E": "structure", "W": "structure", "N": "structure",
    "UP": "structure", "A": "structure", "B": "structure",
    "ANN": "typing",
    "C": "complexity", "PL": "complexity",
    "T": "other", "S": "other",
}


def _ruff_category(code: str) -> str:
    for prefix, cat in _RUFF_CAT.items():
        if code.startswith(prefix):
            return cat
    return "other"


def run_ruff(cfg: AuditConfig) -> list[Issue]:
    python = _find_python(cfg.root)
    ruff_cmd: list[str] | None = None
    for candidate in [["ruff"], [python, "-m", "ruff"]]:
        rc, _, _ = _run(candidate + ["--version"], cfg.root)
        if rc == 0:
            ruff_cmd = candidate
            break
    if ruff_cmd is None:
        print(f"        {yellow('⚠')} Ruff não encontrado, pulando.")
        return []

    cmd = ruff_cmd + ["check", ".", "--output-format", "json"]
    if cfg.fix:
        cmd.append("--fix")
    _, stdout, _ = _run(cmd, cfg.root)

    issues: list[Issue] = []
    try:
        data: list[dict] = json.loads(stdout) if stdout.strip() else []
    except json.JSONDecodeError:
        return []

    for item in data:
        code = item.get("code") or "RUFF"
        loc = item.get("location") or {}
        msg = item.get("message") or ""
        cat = _ruff_category(code)
        # Imports não usados são warnings, não erros
        sev = "warning" if cat in ("import",) else "error"
        if code.startswith(("W", "UP", "N", "I", "ANN")):
            sev = "warning"
        filename = item.get("filename") or ""
        issues.append(Issue(
            file=_rel(filename, cfg.root),
            line=loc.get("row", 0),
            col=loc.get("column", 0),
            code=code,
            message=msg,
            severity=sev,
            category=cat,
            source="ruff",
        ))
    return issues


# ─────────────────────────────────────────────────────────────────────────────
# RUNNER: MYPY
# ─────────────────────────────────────────────────────────────────────────────

_MYPY_RE = re.compile(
    r"^(.+?):(\d+):\s*(error|warning|note):\s*(.+?)(?:\s+\[(.+?)\])?\s*$"
)


def run_mypy(cfg: AuditConfig) -> list[Issue]:
    python = _find_python(cfg.root)
    mypy_cmd: list[str] | None = None
    for candidate in [["mypy"], [python, "-m", "mypy"]]:
        rc, _, _ = _run(candidate + ["--version"], cfg.root)
        if rc == 0:
            mypy_cmd = candidate
            break
    if mypy_cmd is None:
        print(f"        {yellow('⚠')} MyPy não encontrado, pulando.")
        return []

    cmd = mypy_cmd + [
        "src",
        "--ignore-missing-imports",
        "--no-error-summary",
        "--show-column-numbers",
        "--no-strict-optional",
    ]
    _, stdout, _ = _run(cmd, cfg.root)

    issues: list[Issue] = []
    for ln in stdout.splitlines():
        m = _MYPY_RE.match(ln.strip())
        if not m:
            continue
        filepath, lineno, sev, msg, rule = (
            m.group(1), int(m.group(2)),
            m.group(3), m.group(4), m.group(5) or "mypy",
        )
        if sev == "note":
            continue
        cat = "import" if "import" in msg.lower() else "typing"
        issues.append(Issue(
            file=_rel(filepath, cfg.root),
            line=lineno, col=0,
            code=rule, message=msg,
            severity=sev,
            category=cat,
            source="mypy",
        ))
    return issues


# ─────────────────────────────────────────────────────────────────────────────
# RUNNER: PYRIGHT
# ─────────────────────────────────────────────────────────────────────────────

def run_pyright(cfg: AuditConfig) -> list[Issue]:
    rc, _, _ = _run(["pyright", "--version"], cfg.root)
    if rc != 0:
        print(f"        {yellow('⚠')} Pyright não encontrado, pulando.")
        return []

    _, stdout, _ = _run(["pyright", "src", "--outputjson"], cfg.root)
    if not stdout.strip():
        return []

    try:
        data = json.loads(stdout)
    except json.JSONDecodeError:
        return []

    issues: list[Issue] = []
    for diag in data.get("generalDiagnostics", []):
        filepath = diag.get("file") or ""
        rng = diag.get("range") or {}
        start = rng.get("start") or {}
        sev = diag.get("severity") or "warning"
        msg = diag.get("message") or ""
        rule = diag.get("rule") or "pyright"
        cat = "typing"
        if "import" in msg.lower():
            cat = "import"
        elif "undefined" in msg.lower() or "unknown" in msg.lower():
            cat = "undefined"
        issues.append(Issue(
            file=_rel(filepath, cfg.root),
            line=(start.get("line") or 0) + 1,
            col=start.get("character") or 0,
            code=rule, message=msg,
            severity=sev, category=cat,
            source="pyright",
        ))
    return issues


# ─────────────────────────────────────────────────────────────────────────────
# ANÁLISE AST PRÓPRIA
# ─────────────────────────────────────────────────────────────────────────────

class ASTAnalyzer:
    """Verifica um único arquivo Python via ast."""

    def __init__(self, filepath: Path, root: Path, cfg: AuditConfig) -> None:
        self.filepath = filepath
        self.root = root
        self.cfg = cfg
        self.rel = _rel(filepath, root)
        self.issues: list[Issue] = []

    def _add(self, line: int, code: str, msg: str,
             sev: str, cat: str) -> None:
        self.issues.append(Issue(
            file=self.rel, line=line, col=0,
            code=code, message=msg,
            severity=sev, category=cat, source="ast",
        ))

    def analyze(self) -> list[Issue]:
        try:
            source = self.filepath.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return []

        try:
            tree = ast.parse(source, filename=str(self.filepath))
        except SyntaxError as exc:
            self._add(exc.lineno or 0, "AST001",
                      f"SyntaxError: {exc.msg}", "error", "structure")
            return self.issues

        lines = source.splitlines()
        total = len(lines)

        self._check_size(total)
        self._check_functions(tree)
        self._check_classes(tree)
        self._check_imports(tree, source)
        self._check_self_outside_class(tree)
        self._check_tkinter(tree, source)
        self._check_modularization(tree, source, total)
        return self.issues

    # ── Tamanho do arquivo ─────────────────────────────────────────────────

    def _check_size(self, total: int) -> None:
        if total >= self.cfg.huge_file_lines:
            self._add(1, "SIZE003",
                      f"Arquivo enorme: {total} linhas "
                      f"(limite: {self.cfg.huge_file_lines})",
                      "error", "structure")
        elif total >= self.cfg.large_file_lines:
            self._add(1, "SIZE002",
                      f"Arquivo grande: {total} linhas "
                      f"(recomendado: < {self.cfg.large_file_lines})",
                      "warning", "structure")
        elif total >= self.cfg.max_file_lines:
            self._add(1, "SIZE001",
                      f"Arquivo acima do recomendado: {total} linhas "
                      f"(alvo: < {self.cfg.max_file_lines})",
                      "info", "structure")

    # ── Funções ────────────────────────────────────────────────────────────

    def _check_functions(self, tree: ast.AST) -> None:
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            name = node.name
            start = node.lineno
            end = node.end_lineno or start
            func_lines = end - start + 1

            if func_lines > self.cfg.max_function_lines:
                self._add(start, "FUNC001",
                          f"Função '{name}': {func_lines} linhas "
                          f"(máx: {self.cfg.max_function_lines})",
                          "warning", "complexity")

            # Parâmetros (exclui self/cls)
            all_args = node.args.args
            params = [a for a in all_args if a.arg not in ("self", "cls")]
            if len(params) > self.cfg.max_function_params:
                self._add(start, "FUNC002",
                          f"Função '{name}': {len(params)} parâmetros "
                          f"(máx: {self.cfg.max_function_params})",
                          "warning", "complexity")

            # Funções aninhadas (complexidade cognitiva heurística)
            nested = [
                n for n in ast.walk(node)
                if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                and n is not node
            ]
            if len(nested) > 3:
                self._add(start, "FUNC003",
                          f"Função '{name}': {len(nested)} funções aninhadas "
                          "(alta complexidade)",
                          "warning", "complexity")

    # ── Classes ────────────────────────────────────────────────────────────

    def _check_classes(self, tree: ast.AST) -> None:
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            name = node.name
            start = node.lineno
            end = node.end_lineno or start
            class_lines = end - start + 1

            methods = [
                n for n in ast.walk(node)
                if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
            ]
            if len(methods) > self.cfg.max_class_methods:
                self._add(start, "CLS001",
                          f"Classe '{name}': {len(methods)} métodos "
                          f"(máx: {self.cfg.max_class_methods})",
                          "warning", "modularization")

            if class_lines > self.cfg.max_class_lines:
                self._add(start, "CLS002",
                          f"Classe '{name}': {class_lines} linhas "
                          f"(máx: {self.cfg.max_class_lines})",
                          "warning", "modularization")

    # ── Imports ────────────────────────────────────────────────────────────

    def _collect_type_checking_names(self, tree: ast.AST) -> set[str]:
        """Coleta nomes importados dentro de blocos if TYPE_CHECKING:"""
        names: set[str] = set()
        for node in ast.walk(tree):
            if not isinstance(node, ast.If):
                continue
            test = node.test
            is_tc = (
                (isinstance(test, ast.Name) and test.id == "TYPE_CHECKING")
                or (
                    isinstance(test, ast.Attribute)
                    and test.attr == "TYPE_CHECKING"
                )
            )
            if not is_tc:
                continue
            for child in ast.walk(node):
                if isinstance(child, (ast.Import, ast.ImportFrom)):
                    for alias in (child.names if hasattr(child, "names") else []):
                        names.add(alias.asname or alias.name.split(".")[0])
        return names

    def _check_imports(self, tree: ast.AST, source: str) -> None:
        tc_names = self._collect_type_checking_names(tree)
        imported: dict[str, int] = {}   # local_name → line
        seen: list[str] = []            # chave única para duplicatas

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    key = alias.name
                    local = alias.asname or alias.name.split(".")[0]
                    if key in seen:
                        self._add(node.lineno, "IMP002",
                                  f"Import duplicado: '{alias.name}'",
                                  "warning", "import")
                    seen.append(key)
                    imported[local] = node.lineno

            elif isinstance(node, ast.ImportFrom):
                mod = node.module or ""
                for alias in node.names:
                    if alias.name == "*":
                        self._add(node.lineno, "IMP003",
                                  f"Wildcard import de '{mod}' — evitar",
                                  "warning", "import")
                        continue
                    key = f"{mod}.{alias.name}"
                    local = alias.asname or alias.name
                    if key in seen:
                        self._add(node.lineno, "IMP002",
                                  f"Import duplicado: '{alias.name}' de '{mod}'",
                                  "warning", "import")
                    seen.append(key)
                    imported[local] = node.lineno

        # Imports possivelmente não utilizados (heurística simples)
        # Remove linhas de import do source antes de buscar usos
        src_no_imports = re.sub(
            r"^\s*(import|from)\s+.*$", "", source, flags=re.MULTILINE
        )
        for name, lineno in imported.items():
            if name in tc_names:
                continue
            if name.startswith("_"):
                continue
            # Verifica se o nome aparece em algum lugar fora das linhas de import
            if not re.search(r"\b" + re.escape(name) + r"\b", src_no_imports):
                self._add(lineno, "IMP001",
                          f"Import possivelmente não utilizado: '{name}'",
                          "info", "import")

    # ── Self fora de classe ────────────────────────────────────────────────

    def _check_self_outside_class(self, tree: ast.AST) -> None:
        """Detecta funções em nível de módulo com 'self' como 1º parâmetro."""
        for node in tree.body:  # type: ignore[attr-defined]
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            args = node.args.args
            if args and args[0].arg == "self":
                self._add(node.lineno, "SELF001",
                          f"Função '{node.name}' usa 'self' mas não está em uma classe",
                          "warning", "structure")

    # ── Tkinter ────────────────────────────────────────────────────────────

    def _check_tkinter(self, tree: ast.AST, source: str) -> None:
        # Coleta o que está importado de tkinter
        tk_imports: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                mod = node.module or ""
                if "tkinter" in mod or "customtkinter" in mod:
                    for alias in node.names:
                        tk_imports.add(alias.asname or alias.name)
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if "tkinter" in alias.name or "customtkinter" in alias.name:
                        tk_imports.add(alias.asname or alias.name.split(".")[0])

        # messagebox sem import
        if re.search(r"\bmessagebox\s*\.", source) and "messagebox" not in tk_imports:
            for i, ln in enumerate(source.splitlines(), 1):
                if re.search(r"\bmessagebox\s*\.", ln):
                    self._add(i, "TK001",
                              "Uso de 'messagebox' sem import explícito",
                              "warning", "tkinter")
                    break

        # Variáveis Tkinter sem import
        for vartype in ("StringVar", "IntVar", "BooleanVar", "DoubleVar"):
            if not re.search(rf"\b{vartype}\s*\(", source):
                continue
            if (vartype not in tk_imports
                    and "tk" not in tk_imports
                    and "tkinter" not in tk_imports
                    and "ctk" not in tk_imports):
                for i, ln in enumerate(source.splitlines(), 1):
                    if re.search(rf"\b{vartype}\s*\(", ln):
                        self._add(i, "TK002",
                                  f"Uso de '{vartype}' sem import de tkinter",
                                  "warning", "tkinter")
                        break

    # ── Modularização ──────────────────────────────────────────────────────

    def _check_modularization(self, tree: ast.AST, source: str,
                               total: int) -> None:
        # Mistura de UI e lógica de negócio
        ui_kw = ["CTkFrame", "CTkLabel", "CTkButton", "CTkEntry",
                 "CTkTabview", ".pack(", ".grid(", ".place(", ".configure("]
        logic_kw = ["subprocess", "threading", "asyncio", "open(",
                    "requests.", "socket.", "json.load", "os.path"]
        ui_n    = sum(source.count(k) for k in ui_kw)
        logic_n = sum(source.count(k) for k in logic_kw)
        if ui_n > 8 and logic_n > 5 and total > 150:
            self._add(1, "MOD001",
                      f"Mistura UI ({ui_n} refs) + lógica ({logic_n} refs) "
                      "— considere separar em camadas",
                      "info", "modularization")

        # Múltiplas classes em um arquivo (fora de __init__.py)
        if not self.filepath.name.startswith("__"):
            classes = [n for n in tree.body  # type: ignore[attr-defined]
                       if isinstance(n, ast.ClassDef)]
            if len(classes) > 2:
                names = ", ".join(c.name for c in classes[:4])
                self._add(1, "MOD002",
                          f"{len(classes)} classes no mesmo arquivo: {names}… "
                          "— considere dividir",
                          "info", "modularization")

        # Dialog/Panel gigante
        stem = self.filepath.stem.lower()
        if any(kw in stem for kw in ("dialog", "panel", "frame")) and total > 300:
            self._add(1, "MOD003",
                      f"'{self.filepath.name}' tem {total} linhas "
                      "— extrair sub-componentes",
                      "warning", "modularization")


# ─────────────────────────────────────────────────────────────────────────────
# DETECTOR DE IMPORTS CIRCULARES
# ─────────────────────────────────────────────────────────────────────────────

def detect_circular_imports(py_files: list[Path], root: Path) -> list[Issue]:
    """Detecção estática de ciclos via DFS no grafo de imports."""

    def path_to_mod(p: Path) -> str:
        try:
            rel = p.relative_to(root)
        except ValueError:
            rel = p
        return ".".join(rel.with_suffix("").parts)

    mod_map: dict[str, Path] = {path_to_mod(f): f for f in py_files}
    graph: dict[str, set[str]] = {m: set() for m in mod_map}

    for filepath in py_files:
        mod = path_to_mod(filepath)
        try:
            source = filepath.read_text(encoding="utf-8", errors="replace")
            tree = ast.parse(source)
        except Exception:
            continue

        # Coleta imports dentro de blocos TYPE_CHECKING para excluí-los
        tc_nodes: set[int] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.If):
                test = node.test
                is_tc = (
                    (isinstance(test, ast.Name) and test.id == "TYPE_CHECKING")
                    or (isinstance(test, ast.Attribute) and test.attr == "TYPE_CHECKING")
                )
                if is_tc:
                    for child in ast.walk(node):
                        tc_nodes.add(id(child))

        for node in ast.walk(tree):
            if id(node) in tc_nodes:
                continue  # pula imports dentro de TYPE_CHECKING
            if isinstance(node, ast.ImportFrom) and node.module:
                target = node.module
                if node.level > 0:
                    parts = mod.split(".")
                    base = ".".join(parts[:-node.level]) if node.level <= len(parts) else ""
                    target = f"{base}.{target}" if base else target
                if target in mod_map:
                    graph[mod].add(target)
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name in mod_map:
                        graph[mod].add(alias.name)

    # DFS colorido
    WHITE, GRAY, BLACK = 0, 1, 2
    color: dict[str, int] = {m: WHITE for m in graph}
    cycles: list[list[str]] = []

    def dfs(node: str, path: list[str]) -> None:
        color[node] = GRAY
        path = path + [node]
        for nb in graph.get(node, set()):
            if color.get(nb) == GRAY:
                idx = path.index(nb)
                cycles.append(path[idx:] + [nb])
            elif color.get(nb) == WHITE:
                dfs(nb, path)
        color[node] = BLACK

    for mod in list(graph):
        if color[mod] == WHITE:
            dfs(mod, [])

    issues: list[Issue] = []
    seen_keys: set[frozenset] = set()
    for cycle in cycles:
        key: frozenset = frozenset(cycle)
        if key in seen_keys:
            continue
        seen_keys.add(key)
        first = cycle[0]
        fp = mod_map.get(first, Path(first))
        issues.append(Issue(
            file=_rel(fp, root),
            line=1, col=0,
            code="IMP004",
            message="Dependência circular: " + " → ".join(cycle),
            severity="error",
            category="import",
            source="ast",
        ))
    return issues


# ─────────────────────────────────────────────────────────────────────────────
# COLETA DE ARQUIVOS
# ─────────────────────────────────────────────────────────────────────────────

def collect_python_files(cfg: AuditConfig) -> list[Path]:
    files: list[Path] = []
    bases = [cfg.root / d for d in cfg.src_dirs if (cfg.root / d).exists()]
    if not bases:
        bases = [cfg.root]
    excl = set(cfg.exclude_dirs)
    for base in bases:
        for path in base.rglob("*.py"):
            if any(part in excl for part in path.parts):
                continue
            files.append(path)
    return sorted(files)


# ─────────────────────────────────────────────────────────────────────────────
# SCORE E GRAU
# ─────────────────────────────────────────────────────────────────────────────

def calculate_score(issues: list[Issue], total_files: int) -> int:
    if total_files == 0:
        return 100
    errors   = sum(1 for i in issues if i.severity == "error")
    warnings = sum(1 for i in issues if i.severity == "warning")
    infos    = sum(1 for i in issues if i.severity == "info")
    # Penalidade relativa ao número de arquivos
    raw = (errors * 5.0 + warnings * 1.0 + infos * 0.1) / total_files * 10.0
    return max(0, min(100, round(100.0 - raw)))


def score_grade(score: int) -> str:
    if score >= 90:
        return green(f"A  ({score}/100)")
    if score >= 75:
        return cyan(f"B  ({score}/100)")
    if score >= 60:
        return yellow(f"C  ({score}/100)")
    if score >= 40:
        return yellow(f"D  ({score}/100)")
    return red(f"F  ({score}/100)")


# ─────────────────────────────────────────────────────────────────────────────
# GERADOR DE SUGESTÕES
# ─────────────────────────────────────────────────────────────────────────────

def build_suggestions(issues: list[Issue]) -> list[str]:
    sugg: list[str] = []
    by_file: dict[str, list[Issue]] = collections.defaultdict(list)
    for i in issues:
        by_file[i.file].append(i)

    # Arquivos com mais erros
    hot = sorted(by_file.items(), key=lambda x: -sum(1 for i in x[1] if i.severity == "error"))
    for fp, fi in hot[:5]:
        errs = sum(1 for i in fi if i.severity == "error")
        if errs > 0:
            sugg.append(f"Revisar urgente '{fp}' — {errs} erro(s) crítico(s)")

    # Imports circulares
    circ = [i for i in issues if i.code == "IMP004"]
    if circ:
        sugg.append(
            f"Resolver {len(circ)} dependência(s) circular(es) — "
            "pode causar ImportError em runtime"
        )

    # Arquivos enormes
    for i in [x for x in issues if x.code == "SIZE003"][:3]:
        sugg.append(f"Dividir '{i.file}' (arquivo enorme)")

    # Classes com excesso de métodos
    for i in [x for x in issues if x.code == "CLS001"][:3]:
        sugg.append(f"Extrair responsabilidades da classe em '{i.file}'")

    # Muitos imports não usados → ruff fix
    unused = [i for i in issues if i.code in ("F401", "IMP001")]
    if len(unused) > 5:
        sugg.append(
            f"Executar 'ruff check . --fix' para remover ~{len(unused)} "
            "imports não utilizados automaticamente"
        )

    # Mistura UI / negócio
    mixed = [i for i in issues if i.code == "MOD001"]
    if len(mixed) > 3:
        sugg.append(
            f"{len(mixed)} arquivo(s) com UI misturada a lógica — "
            "considere padrão MVP/MVC"
        )

    return sugg


# ─────────────────────────────────────────────────────────────────────────────
# GERADOR DE RELATÓRIOS
# ─────────────────────────────────────────────────────────────────────────────

def write_reports(
    issues: list[Issue],
    py_files: list[Path],
    cfg: AuditConfig,
    elapsed: float,
    suggestions: list[str],
) -> None:
    out = cfg.root / cfg.output_dir
    out.mkdir(parents=True, exist_ok=True)

    errors   = [i for i in issues if i.severity == "error"]
    warnings = [i for i in issues if i.severity == "warning"]
    infos    = [i for i in issues if i.severity == "info"]
    score    = calculate_score(issues, len(py_files))

    by_file: dict[str, list[Issue]] = collections.defaultdict(list)
    for i in issues:
        by_file[i.file].append(i)

    by_cat: dict[str, list[Issue]] = collections.defaultdict(list)
    for i in issues:
        by_cat[i.category].append(i)

    top_files = sorted(by_file.items(), key=lambda x: -len(x[1]))[:20]
    ts = time.strftime("%Y-%m-%dT%H:%M:%S")

    # ── JSON ──────────────────────────────────────────────────────────────
    report = {
        "timestamp": ts,
        "elapsed_seconds": round(elapsed, 2),
        "score": score,
        "summary": {
            "total_files": len(py_files),
            "total_issues": len(issues),
            "errors": len(errors),
            "warnings": len(warnings),
            "infos": len(infos),
        },
        "by_category": {
            cat: [i.as_dict() for i in lst]
            for cat, lst in sorted(by_cat.items())
        },
        "top_files": [
            {
                "file": fp,
                "count": len(fi),
                "errors": sum(1 for i in fi if i.severity == "error"),
            }
            for fp, fi in top_files
        ],
        "suggestions": suggestions,
        "issues": [i.as_dict() for i in issues],
    }
    (out / "latest_report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    # ── TXT ───────────────────────────────────────────────────────────────
    SEP = "=" * 72
    L: list[str] = []
    L += [
        SEP,
        "  ARKLAND-Multi — PROJECT AUDIT REPORT",
        f"  {time.strftime('%d/%m/%Y %H:%M:%S')}  |  Tempo: {elapsed:.1f}s  |  Score: {score}/100",
        SEP, "",
        "## RESUMO",
        f"   Arquivos analisados : {len(py_files)}",
        f"   Total de issues     : {len(issues)}",
        f"   Erros               : {len(errors)}",
        f"   Warnings            : {len(warnings)}",
        f"   Infos               : {len(infos)}",
        f"   Score geral         : {score}/100",
        "",
        "## ERROS POR CATEGORIA",
    ]
    for cat, label in CATEGORY_LABELS.items():
        lst = by_cat.get(cat, [])
        if not lst:
            continue
        e = sum(1 for i in lst if i.severity == "error")
        w = sum(1 for i in lst if i.severity == "warning")
        L.append(f"   {label:<26}  Erros:{e:>5}  Warnings:{w:>5}  Total:{len(lst):>5}")

    L += ["", "## ARQUIVOS MAIS PROBLEMÁTICOS (TOP 20)"]
    for rank, (fp, fi) in enumerate(top_files, 1):
        e = sum(1 for i in fi if i.severity == "error")
        w = sum(1 for i in fi if i.severity == "warning")
        L.append(
            f"   {rank:>2}. {fp:<64}  E:{e:>3}  W:{w:>3}  ({len(fi):>3})"
        )

    L += ["", "## SUGESTÕES AUTOMÁTICAS"]
    for idx, s in enumerate(suggestions, 1):
        L.append(f"   {idx}. {s}")

    for label, lst in [("ERROS", errors), ("WARNINGS", warnings), ("INFOS", infos)]:
        if not lst:
            continue
        L += ["", f"## {label} ({len(lst)})", SEP]
        for i in lst:
            L.append(f"   {i.file}:{i.line}  [{i.code}]  {i.message}")

    (out / "latest_report.txt").write_text("\n".join(L), encoding="utf-8")

    # ── MARKDOWN ──────────────────────────────────────────────────────────
    md: list[str] = [
        "# ARKLAND-Multi — Project Audit Report",
        "",
        f"**Gerado em:** {time.strftime('%d/%m/%Y %H:%M:%S')} &nbsp;|&nbsp; "
        f"**Tempo:** {elapsed:.1f}s &nbsp;|&nbsp; **Score:** {score}/100",
        "",
        "---",
        "",
        "## Resumo",
        "",
        "| Métrica | Valor |",
        "|---------|------:|",
        f"| Arquivos analisados | {len(py_files)} |",
        f"| Total de issues | {len(issues)} |",
        f"| Erros | {len(errors)} |",
        f"| Warnings | {len(warnings)} |",
        f"| Infos | {len(infos)} |",
        f"| Score geral | **{score}/100** |",
        "",
        "---",
        "",
        "## Erros por Categoria",
        "",
        "| Categoria | Erros | Warnings | Infos | Total |",
        "|-----------|------:|---------:|------:|------:|",
    ]
    for cat, label in CATEGORY_LABELS.items():
        lst = by_cat.get(cat, [])
        if not lst:
            continue
        e   = sum(1 for i in lst if i.severity == "error")
        w   = sum(1 for i in lst if i.severity == "warning")
        inf = sum(1 for i in lst if i.severity == "info")
        md.append(f"| {label} | {e} | {w} | {inf} | {len(lst)} |")

    md += [
        "",
        "---",
        "",
        "## Arquivos Mais Problemáticos (Top 20)",
        "",
        "| # | Arquivo | Erros | Warnings | Total |",
        "|--:|---------|------:|---------:|------:|",
    ]
    for rank, (fp, fi) in enumerate(top_files, 1):
        e = sum(1 for i in fi if i.severity == "error")
        w = sum(1 for i in fi if i.severity == "warning")
        md.append(f"| {rank} | `{fp}` | {e} | {w} | {len(fi)} |")

    md += ["", "---", "", "## Sugestões Automáticas", ""]
    for idx, s in enumerate(suggestions, 1):
        md.append(f"{idx}. {s}")

    md += ["", "---", "", "## Todos os Issues", ""]
    for label, sev_lst in [
        ("🔴 Erros", errors),
        ("🟡 Warnings", warnings),
        ("🔵 Infos", infos),
    ]:
        if not sev_lst:
            continue
        md += [f"### {label}", "", "| Arquivo | Linha | Código | Mensagem | Fonte |",
               "|---------|------:|--------|----------|-------|"]
        for iss in sev_lst[:200]:
            msg = iss.message.replace("|", "\\|")
            md.append(
                f"| `{iss.file}` | {iss.line} | `{iss.code}` | {msg} | {iss.source} |"
            )
        if len(sev_lst) > 200:
            md.append(
                f"\n> _{len(sev_lst) - 200} issue(s) adicionais omitidos. "
                "Veja `latest_report.json` para lista completa._"
            )
        md.append("")

    (out / "latest_report.md").write_text("\n".join(md), encoding="utf-8")


# ─────────────────────────────────────────────────────────────────────────────
# IMPRESSÃO DO RESUMO NO TERMINAL
# ─────────────────────────────────────────────────────────────────────────────

def print_summary(
    issues: list[Issue],
    py_files: list[Path],
    elapsed: float,
    cfg: AuditConfig,
    suggestions: list[str],
) -> None:
    errors   = [i for i in issues if i.severity == "error"]
    warnings = [i for i in issues if i.severity == "warning"]
    infos    = [i for i in issues if i.severity == "info"]
    score    = calculate_score(issues, len(py_files))

    by_file: dict[str, list[Issue]] = collections.defaultdict(list)
    for i in issues:
        by_file[i.file].append(i)

    by_cat: dict[str, list[Issue]] = collections.defaultdict(list)
    for i in issues:
        by_cat[i.category].append(i)

    SEP = cyan("\u2500" * 70)
    print(f"\n{SEP}")
    print(bold("  ARKLAND-Multi \u2014 PROJECT AUDIT REPORT"))
    print(
        f"  {dim(time.strftime('%d/%m/%Y %H:%M:%S'))}  |  "
        f"Tempo: {dim(f'{elapsed:.1f}s')}  |  "
        f"Score: {score_grade(score)}"
    )
    print(f"{SEP}\n")

    print(bold("  RESUMO"))
    print(f"    Arquivos  : {bold(str(len(py_files)))}")
    print(f"    Issues    : {bold(str(len(issues)))}")
    print(f"    Erros     : {red(str(len(errors)))}")
    print(f"    Warnings  : {yellow(str(len(warnings)))}")
    print(f"    Infos     : {cyan(str(len(infos)))}")
    print()

    print(bold("  ERROS POR CATEGORIA"))
    for cat, label in CATEGORY_LABELS.items():
        lst = by_cat.get(cat, [])
        if not lst:
            continue
        e = sum(1 for i in lst if i.severity == "error")
        w = sum(1 for i in lst if i.severity == "warning")
        bar = "\u25aa" * min(24, len(lst) // max(len(py_files) // 10, 1))
        print(
            f"    {label:<26} {red(f'E:{e:>4}')}  "
            f"{yellow(f'W:{w:>4}')}  {dim(bar)}"
        )
    print()

    top_files = sorted(by_file.items(), key=lambda x: -len(x[1]))[:10]
    print(bold("  TOP 10 ARQUIVOS MAIS PROBLEMÁTICOS"))
    for rank, (fp, fi) in enumerate(top_files, 1):
        e = sum(1 for i in fi if i.severity == "error")
        w = sum(1 for i in fi if i.severity == "warning")
        display = fp[-64:] if len(fp) > 64 else fp
        print(
            f"    {rank:>2}. {display:<66}  "
            f"{red(f'E:{e:>3}')}  {yellow(f'W:{w:>3}')}  "
            f"{dim(f'({len(fi)})')}"
        )
    print()

    if suggestions:
        print(bold("  SUGESTÕES AUTOMÁTICAS"))
        for idx, s in enumerate(suggestions, 1):
            print(f"    {cyan(str(idx))}. {s}")
        print()

    if cfg.verbose and errors:
        print(bold(f"  ERROS ({len(errors)})"))
        for i in errors[:60]:
            print(str(i))
        if len(errors) > 60:
            print(f"    ... e mais {len(errors)-60} erros — veja o relatório")
        print()

    print(f"{SEP}")
    out = cfg.root / cfg.output_dir
    print(f"  {green('✓')} Relatórios salvos em: {dim(str(out))}")
    print(
        f"    {dim('latest_report.txt')}  |  "
        f"{dim('latest_report.json')}  |  "
        f"{dim('latest_report.md')}"
    )
    print(f"{SEP}\n")


# ─────────────────────────────────────────────────────────────────────────────
# ORQUESTRADOR PRINCIPAL
# ─────────────────────────────────────────────────────────────────────────────

def run_audit(cfg: AuditConfig) -> int:
    t0 = time.time()
    SEP = cyan("\u2500" * 70)
    print(f"\n{SEP}")
    print(bold("  ARKLAND-Multi PROJECT AUDIT"))
    print(f"  Root: {dim(str(cfg.root))}")
    print(f"{SEP}\n")

    py_files = collect_python_files(cfg)
    print(f"  {cyan('\u2192')} {len(py_files)} arquivos Python encontrados\n")
    all_issues: list[Issue] = []

    # 1. Ruff
    print(f"  {bold('[1/5]')} Ruff  {dim('(linting + imports)...')}")
    if cfg.use_ruff:
        ruff_issues = run_ruff(cfg)
        all_issues.extend(ruff_issues)
        e = sum(1 for i in ruff_issues if i.severity == "error")
        w = sum(1 for i in ruff_issues if i.severity == "warning")
        print(f"        {green('✓')} {len(ruff_issues)} issues  "
              f"({red(f'E:{e}')} / {yellow(f'W:{w}')})")
    else:
        print(f"        {dim('pulado (--no-ruff)')}")

    # 2. MyPy
    print(f"\n  {bold('[2/5]')} MyPy  {dim('(tipagem estática)...')}")
    if cfg.use_mypy:
        mypy_issues = run_mypy(cfg)
        all_issues.extend(mypy_issues)
        e = sum(1 for i in mypy_issues if i.severity == "error")
        w = sum(1 for i in mypy_issues if i.severity == "warning")
        print(f"        {green('✓')} {len(mypy_issues)} issues  "
              f"({red(f'E:{e}')} / {yellow(f'W:{w}')})")
    else:
        print(f"        {dim('pulado (--no-mypy)')}")

    # 3. Pyright
    print(f"\n  {bold('[3/5]')} Pyright  {dim('(análise de tipos)...')}")
    if cfg.use_pyright:
        pyright_issues = run_pyright(cfg)
        all_issues.extend(pyright_issues)
        e = sum(1 for i in pyright_issues if i.severity == "error")
        w = sum(1 for i in pyright_issues if i.severity == "warning")
        print(f"        {green('✓')} {len(pyright_issues)} issues  "
              f"({red(f'E:{e}')} / {yellow(f'W:{w}')})")
    else:
        print(f"        {dim('pulado (--no-pyright)')}")

    # 4. AST próprio
    print(f"\n  {bold('[4/5]')} Análise AST  {dim('(estrutura + modularização)...')}")
    prog = Progress(len(py_files))
    for fp in py_files:
        prog.update(fp.name)
        all_issues.extend(ASTAnalyzer(fp, cfg.root, cfg).analyze())
    ast_issues = [i for i in all_issues if i.source == "ast"]
    e = sum(1 for i in ast_issues if i.severity == "error")
    w = sum(1 for i in ast_issues if i.severity == "warning")
    print(f"        {green('✓')} {len(ast_issues)} issues  "
          f"({red(f'E:{e}')} / {yellow(f'W:{w}')})")

    # 5. Imports circulares
    print(f"\n  {bold('[5/5]')} Dependências Circulares  {dim('(grafo de imports)...')}")
    circ = detect_circular_imports(py_files, cfg.root)
    all_issues.extend(circ)
    print(f"        {green('✓')} {len(circ)} ciclo(s) detectado(s)")

    # Relatórios
    elapsed = time.time() - t0
    suggestions = build_suggestions(all_issues)
    write_reports(all_issues, py_files, cfg, elapsed, suggestions)
    print_summary(all_issues, py_files, elapsed, cfg, suggestions)

    return 1 if any(i.severity == "error" for i in all_issues) else 0


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    _setup_windows_console()
    ap = argparse.ArgumentParser(
        description="ARKLAND-Multi Project Audit — scanner arquitetural profissional",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Exemplos:\n"
            "  python tools/project_audit.py\n"
            "  python tools/project_audit.py --verbose\n"
            "  python tools/project_audit.py --fix\n"
            "  python tools/project_audit.py --no-mypy --no-pyright\n"
            "  python tools/project_audit.py --max-func-lines 80\n"
            "  python tools/project_audit.py --root C:/caminho/do/projeto\n"
        ),
    )
    ap.add_argument("--fix",            action="store_true",
                    help="Executar ruff --fix automaticamente")
    ap.add_argument("--verbose", "-v",  action="store_true",
                    help="Mostrar todos os erros no terminal")
    ap.add_argument("--no-ruff",        action="store_true",
                    help="Pular Ruff")
    ap.add_argument("--no-mypy",        action="store_true",
                    help="Pular MyPy")
    ap.add_argument("--no-pyright",     action="store_true",
                    help="Pular Pyright")
    ap.add_argument("--max-file-lines",    type=int, default=500,
                    metavar="N", help="Linhas máximas por arquivo [500]")
    ap.add_argument("--max-func-lines",    type=int, default=50,
                    metavar="N", help="Linhas máximas por função [50]")
    ap.add_argument("--max-func-params",   type=int, default=7,
                    metavar="N", help="Parâmetros máximos por função [7]")
    ap.add_argument("--max-class-methods", type=int, default=30,
                    metavar="N", help="Métodos máximos por classe [30]")
    ap.add_argument("--output-dir",        default="tools/reports",
                    metavar="DIR", help="Diretório de saída [tools/reports]")
    ap.add_argument("--root",              default=".",
                    metavar="DIR", help="Raiz do projeto [.]")
    args = ap.parse_args()

    cfg = AuditConfig(
        root=Path(args.root).resolve(),
        use_ruff=           not args.no_ruff,
        use_mypy=           not args.no_mypy,
        use_pyright=        not args.no_pyright,
        fix=                args.fix,
        verbose=            args.verbose,
        max_file_lines=     args.max_file_lines,
        max_function_lines= args.max_func_lines,
        max_function_params=args.max_func_params,
        max_class_methods=  args.max_class_methods,
        output_dir=         Path(args.output_dir),
    )
    sys.exit(run_audit(cfg))


if __name__ == "__main__":
    main()
