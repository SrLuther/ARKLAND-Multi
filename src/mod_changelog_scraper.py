"""
src/mod_changelog_scraper.py

Obtém a nota da atualização mais recente de um mod do Steam Workshop.

Estratégia:
  1. GET na página de changelog: steamcommunity.com/sharedfiles/filedetails/changelog/{mod_id}
  2. Parseia o HTML com html.parser (stdlib) procurando pelo primeiro bloco
     de texto dentro das divs de changelog conhecidas.
  3. Fallback gracioso: retorna "" se a página não existir ou não tiver notas.

Sem dependências externas — apenas urllib + html.parser da stdlib.
"""
from __future__ import annotations

import html as _html
import logging
import re
import urllib.error
import urllib.request
from html.parser import HTMLParser
from typing import Optional

_logger = logging.getLogger(__name__)

_WORKSHOP_CHANGELOG_URL = (
    "https://steamcommunity.com/sharedfiles/filedetails/changelog/{mod_id}"
)
_WORKSHOP_MOD_URL = (
    "https://steamcommunity.com/sharedfiles/filedetails/?id={mod_id}"
)

# Limite de caracteres para o corpo da nota no embed Discord
_MAX_CHANGELOG_CHARS = 1800


class _ChangelogHTMLParser(HTMLParser):
    """
    Extrai o texto do primeiro bloco de changelog encontrado.

    Steam Workshop usa três padrões conhecidos:
      - <div class="workshopAnnouncement">...</div>
      - <div class="detailBox">...</div>  (mods mais antigos)
      - <p class="workshopAnnouncementBody">...</p>

    O parser para assim que encontra o primeiro bloco completo para
    retornar apenas a entrada mais recente.
    """

    _TARGET_CLASSES = frozenset({
        "workshopannouncement",       # entrada principal de changelog
        "changenotedescription",      # variante observada em 2024+
        "workshopitemdescription",    # fallback: descrição geral
    })

    def __init__(self) -> None:
        super().__init__()
        self._depth: int = 0           # profundidade dentro do bloco alvo
        self._capturing: bool = False
        self._done: bool = False
        self._texts: list[str] = []
        self._skip_classes = frozenset({"workshopAnnouncementTitle", "changeNoteDate"})

    # ── HTMLParser overrides ──────────────────────────────────────────────────

    def handle_starttag(self, tag: str, attrs: list) -> None:
        if self._done:
            return
        attr_map = dict(attrs)
        cls_raw = attr_map.get("class", "")
        cls_lower = cls_raw.lower().replace("-", "").replace("_", "")

        if not self._capturing:
            # Verifica se a tag corrente inicia um bloco de changelog
            for target in self._TARGET_CLASSES:
                if target in cls_lower:
                    self._capturing = True
                    self._depth = 1
                    return
        else:
            self._depth += 1

    def handle_endtag(self, tag: str) -> None:
        if not self._capturing or self._done:
            return
        self._depth -= 1
        if self._depth <= 0:
            self._done = True

    def handle_data(self, data: str) -> None:
        if self._capturing and not self._done:
            stripped = data.strip()
            if stripped:
                self._texts.append(stripped)

    # ── Resultado ─────────────────────────────────────────────────────────────

    def get_changelog_text(self) -> str:
        return "\n".join(self._texts)


def _fetch_workshop_page(url: str, timeout: int = 12) -> str:
    """Baixa o HTML da página Steam Workshop. Retorna string vazia em caso de erro."""
    req = urllib.request.Request(
        url,
        headers={
            # User-Agent padrão de browser para evitar bloqueios
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "en-US,en;q=0.9",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw_bytes = resp.read()
            # Steam pode enviar em UTF-8 ou Latin-1; tenta UTF-8 primeiro
            try:
                return raw_bytes.decode("utf-8")
            except UnicodeDecodeError:
                return raw_bytes.decode("latin-1", errors="replace")
    except urllib.error.HTTPError as exc:
        _logger.debug("Workshop changelog HTTP %s para mod %s", exc.code, url)
    except Exception as exc:
        _logger.debug("Erro ao buscar changelog Workshop: %s", exc)
    return ""


def _clean_text(raw: str) -> str:
    """Normaliza espaços, remove linhas vazias duplas e decodifica entidades HTML."""
    text = _html.unescape(raw)
    # Remove marcação HTML residual (ex: <br>, <b> etc.) que o parser não capturou
    text = re.sub(r"<[^>]+>", "", text)
    # Compacta espaços horizontais sem apagar newlines
    lines = [re.sub(r"[ \t]+", " ", ln).strip() for ln in text.splitlines()]
    # Remove linhas que são apenas separadores de data/hora (ex: "12 Dec @ 3:00pm")
    date_re = re.compile(
        r"^(\d{1,2}\s+\w+|\w+\s+\d{1,2})(\s*@\s*\d{1,2}:\d{2}(am|pm))?$",
        re.IGNORECASE,
    )
    lines = [ln for ln in lines if ln and not date_re.match(ln)]
    # Remove linhas duplicadas consecutivas
    deduped: list[str] = []
    for ln in lines:
        if not deduped or ln != deduped[-1]:
            deduped.append(ln)
    return "\n".join(deduped)


def fetch_mod_changelog(mod_id: str) -> Optional[str]:
    """
    Retorna o texto da nota de atualização mais recente do mod no Steam Workshop.

    Retorna:
      - str com o texto (pode ser vazio se o autor não escreveu changelogs)
      - None se a requisição falhou completamente
    """
    url = _WORKSHOP_CHANGELOG_URL.format(mod_id=mod_id)
    html_body = _fetch_workshop_page(url)
    if not html_body:
        return None

    parser = _ChangelogHTMLParser()
    try:
        parser.feed(html_body)
    except Exception as exc:
        _logger.debug("Erro ao parsear changelog HTML do mod %s: %s", mod_id, exc)
        return None

    raw_text = parser.get_changelog_text()
    if not raw_text:
        # Página existe mas sem notas de atualização (autor não escreveu)
        return ""

    clean = _clean_text(raw_text)
    if len(clean) > _MAX_CHANGELOG_CHARS:
        clean = clean[:_MAX_CHANGELOG_CHARS].rsplit("\n", 1)[0] + "\n…"
    return clean


def workshop_url(mod_id: str) -> str:
    """URL da página principal do mod no Workshop."""
    return _WORKSHOP_MOD_URL.format(mod_id=mod_id)
