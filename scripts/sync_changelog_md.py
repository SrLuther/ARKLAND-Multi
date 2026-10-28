#!/usr/bin/env python3
"""
Gera CHANGELOG.md — Código padronizado e limpo ✅
"""
from __future__ import annotations

import ast
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


ROOT = Path(__file__).resolve().parent.parent
VERSION_PY = ROOT / "src" / "version.py"
OUTPUT = ROOT / "CHANGELOG.md"

_SECTION_MAP = (
    (re.compile(r"^(Novo|Feat|Feature)\b", re.IGNORECASE), "Feature"),
    (re.compile(r"^Melhoria\b", re.IGNORECASE), "Improvement"),
    (re.compile(r"^Fix\b", re.IGNORECASE), "Fix"),
    (re.compile(r"^Refactor\b", re.IGNORECASE), "Refactor"),
    (re.compile(r"^Docs|Documentação\b", re.IGNORECASE), "Refactor"),
    (re.compile(r"^Test\b", re.IGNORECASE), "Refactor"),
)


def _get_git_commits() -> list[str]:
    """Busca commits do Git, removendo mensagens de release."""
    try:
        result = subprocess.run(
            ["git", "log", "-n", "200", "--format=%s", "--no-merges"],
            cwd=ROOT,
            capture_output=True,
            encoding="utf-8",
            errors="surrogateescape",
            check=True
        )
        todos = [line.strip() for line in result.stdout.strip().split("\n") if line.strip()]
        filtro_release = re.compile(r"^release:\s+v[\d.]+$", re.IGNORECASE)
        return [c for c in todos if not filtro_release.match(c)]
    except subprocess.CalledProcessError as e:
        print(f"⚠️ Erro ao ler Git: {e}")
        return []


def _limpar_texto(texto: str) -> str:
    """Normaliza acentos e remove caracteres inválidos/surrogates."""
    if "â€" in texto or "Ã" in texto:
        try:
            texto = texto.encode("latin-1").decode("utf-8")
        except UnicodeError:
            pass
    return texto.encode("utf-8", errors="replace").decode("utf-8").strip()


def _load_changelog() -> tuple[list[dict], str]:
    """Carrega CHANGELOG e APP_VERSION de version.py, removendo BOM."""
    try:
        src = VERSION_PY.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError:
        src = VERSION_PY.read_text(encoding="utf-8", errors="replace")
    src = src.lstrip("\ufeff")
    tree = ast.parse(src)

    changelog: list[dict] | None = None
    app_version: str | None = None
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if (
                    isinstance(target, ast.Name)
                    and target.id == "CHANGELOG"
                ):
                    changelog = ast.literal_eval(node.value)
                elif (
                    isinstance(target, ast.Name)
                    and target.id == "APP_VERSION"
                    and isinstance(node.value, ast.Constant)
                ):
                    app_version = node.value.value
        elif isinstance(node, ast.AnnAssign):
            if (
                isinstance(node.target, ast.Name)
                and node.target.id == "CHANGELOG"
            ):
                changelog = ast.literal_eval(node.value)
            elif (
                isinstance(node.target, ast.Name)
                and node.target.id == "APP_VERSION"
                and isinstance(node.value, ast.Constant)
            ):
                app_version = node.value.value

    if changelog is None:
        raise RuntimeError("CHANGELOG não encontrado em src/version.py")
    if app_version is None:
        raise RuntimeError("APP_VERSION não encontrada em src/version.py")
    if not isinstance(changelog, list):
        raise TypeError("CHANGELOG deve ser uma lista")

    print(f"📋 Lidas {len(changelog)} versões — 5 primeiras:")
    for i, bloco in enumerate(changelog[:5], 1):
        print(f"   {i}. {bloco.get('version', '???')}")

    return changelog, app_version


def _increment_version(versao: str) -> str:
    partes = versao.split(".")
    if len(partes) == 3:
        return f"{partes[0]}.{partes[1]}.{int(partes[2]) + 1}"
    return f"{versao}.1"


def _bucket(mudanca: str) -> str:
    return next(
        (secao for padrao, secao in _SECTION_MAP if padrao.search(mudanca)),
        "Other"
    )


def _render(entries: list[dict]) -> str:
    """Gera o conteúdo completo do CHANGELOG.md."""
    versao_topo = entries[0].get("version", "indefinida")
    linhas = [
        "# Changelog",
        "",
        f"<!-- Gerado: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} -->",
        f"<!-- Total de versões: {len(entries)} | Primeira: {versao_topo} -->",
        "",
        "<!-- markdownlint-disable MD024 -->",
        "",
    ]

    for entry in entries:
        ver = entry.get("version", "sem-versao")
        data = entry.get("date", "????-??-??")
        mudancas = entry.get("changes", [])

        linhas.append(f"## [{ver}] - {data}")
        linhas.append("")

        secoes: dict[str, list[str]] = {}
        for mudanca in mudancas:
            limpo = _limpar_texto(str(mudanca))
            secoes.setdefault(_bucket(limpo), []).append(limpo)

        for nome in ("Feature", "Improvement", "Fix", "Refactor", "Other"):
            itens = secoes.get(nome)
            if not itens:
                continue
            linhas.append(f"### {nome}")
            linhas.append("")
            for item in itens:
                linhas.append(f"- {item}")
            linhas.append("")

    return "\n".join(linhas).rstrip() + "\n"


def _atualizar_version_py(nova_versao: str, data_hoje: str, itens_novos: list[str]) -> None:
    """Insere bloco novo no topo e atualiza APP_VERSION/BUILD_DATE."""
    with VERSION_PY.open("r", encoding="utf-8-sig") as f:
        conteudo = f.read()

    itens_formatados = ",\n".join(
        f'            "{_limpar_texto(item)}"' for item in itens_novos
    )
    bloco_novo = f"""    {{
        "version": "{nova_versao}",
        "date": "{data_hoje}",
        "changes": [
{itens_formatados}
        ]
    }},"""

    marca = "CHANGELOG"
    idx = conteudo.find(marca)
    if idx == -1:
        raise RuntimeError("Não encontrado: CHANGELOG")
    abre_chave = conteudo.find("[", idx)
    if abre_chave == -1:
        raise RuntimeError("Não encontrado: [ após CHANGELOG")
    fim_linha = conteudo.find("\n", abre_chave)
    if fim_linha == -1:
        fim_linha = abre_chave + 1

    parte1 = conteudo[:fim_linha + 1]
    parte2 = conteudo[fim_linha + 1:]
    novo_conteudo = f"{parte1}{bloco_novo}\n{parte2}"

    novo_conteudo = re.sub(
        r'(APP_VERSION\s*[:=]\s*str\s*=\s*")[^"]+(")',
        lambda m: f"{m.group(1)}{nova_versao}{m.group(2)}",
        novo_conteudo,
        count=1
    )
    novo_conteudo = re.sub(
        r'(BUILD_DATE\s*[:=]\s*str\s*=\s*")[^"]+(")',
        lambda m: f"{m.group(1)}{data_hoje}{m.group(2)}",
        novo_conteudo,
        count=1
    )

    with VERSION_PY.open("w", encoding="utf-8", newline="\n") as f:
        f.write(novo_conteudo)

    print(f"✅ version.py → {nova_versao}")


def main() -> int:
    print("📖 Carregando...")
    entries, app_versao = _load_changelog()
    print(f"   Versão do app: {app_versao}")

    conteudo = _render(entries)
    if OUTPUT.exists():
        OUTPUT.unlink()
        print("🗑️ Arquivo antigo removido")
    OUTPUT.write_text(conteudo, encoding="utf-8")
    print(f"✅ Gravado em: {OUTPUT}")

    verificacao = OUTPUT.read_text(encoding="utf-8")
    versao_topo = entries[0].get("version", "???")
    if versao_topo in verificacao:
        print(f"✅ CONFIRMADO: '{versao_topo}' presente no topo!")
    else:
        print("⚠️ ATENÇÃO: versão do topo não encontrada")
        print(f"   Início do arquivo: {verificacao[:300]}")
        return 1

    # The release pipeline sets APP_VERSION and its changelog entry before
    # rendering. Do not interpret those not-yet-released commits as a second
    # release while _release.ps1 is in progress.
    if "--render-only" in sys.argv[1:]:
        print("\nℹ️ Render-only: nenhuma versão automática será criada.")
        return 0

    commits_git = _get_git_commits()
    existentes = set()
    for versao in entries:
        for mudanca in versao.get("changes", []):
            existentes.add(_limpar_texto(str(mudanca)))

    novos = [msg for msg in commits_git if _limpar_texto(msg) not in existentes]
    if not novos:
        print("\nℹ️ Nenhum commit novo. Arquivo atualizado com todas as versões.")
        return 0

    proxima_versao = _increment_version(app_versao)
    data_atual = datetime.now().strftime("%Y-%m-%d")
    print(f"\n🆕 Versão nova: {proxima_versao} — {len(novos)} itens")
    _atualizar_version_py(proxima_versao, data_atual, novos)

    entries, _ = _load_changelog()
    OUTPUT.write_text(_render(entries), encoding="utf-8")
    print(f"✅ Concluído! {app_versao} → {proxima_versao}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
