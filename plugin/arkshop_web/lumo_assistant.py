"""Lumo 2.0: reconhecimento determinístico e formatação de respostas.

Este módulo não acessa rede, Discord ou banco por conta própria. As fontes de
dados e o cliente Gateway são injetados pela aplicação para reutilizar os
serviços oficiais da ARKLAND e permitir testes sem publicar mensagens reais.
"""
from __future__ import annotations

import random
import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable

COLOR = 0x00FFFF
FOOTER = "Lumo • Assistente oficial da ARKLAND"
SITE_URL = "https://www.arkland.com.br/"
BETLAND_URL = SITE_URL + "#/sorteio"
POLLS_URL = SITE_URL + "#/polls"
LICENSES_URL = SITE_URL + "#/licencas"

# Community-channel notices. These describe navigation, not unverified live status.
COMMUNITY_ANNOUNCEMENTS = {
    'systems': ('Status dos sistemas | ARKLAND',
                'Quer acompanhar a situação dos serviços? Consulte a central de status para ver as informações disponíveis, revisões da equipe e incidentes registrados.\n\n[Consultar os sistemas](https://arkland.com.br/#/system-status)'),
    'catalog': ('Catálogo | Explore a ARKLAND',
                'Procurando itens, criaturas ou serviços? Explore o catálogo e confira as opções, valores e condições de cada resgate antes de escolher.\n\n[Abrir o catálogo](https://arkland.com.br/#/catalog)'),
    'tutorials': ('Tutoriais | Aprenda no seu ritmo',
                  'Uma dúvida sobre como jogar ou usar os recursos da ARKLAND? Consulte os tutoriais disponíveis e encontre orientações para sua jornada.\n\n[Ver tutoriais](https://arkland.com.br/#/tutoriais)'),
    'guide': ('Guia de conteúdo | Conheça o cluster',
              'Antes da próxima aventura, consulte o guia de conteúdo da ARKLAND. Conheça as informações disponíveis sobre os conteúdos do servidor e planeje seus próximos passos.\n\n[Explorar o guia](https://arkland.com.br/#/guia)'),
    'season': ('SeasonLand | Sua próxima jornada',
               'Conheça a SeasonLand e consulte no site a situação da temporada, suas regras, objetivos e recompensas disponíveis. Confira os detalhes antes de participar.\n\n[Conhecer a SeasonLand](https://arkland.com.br/#/season-pass)'),
    'suggestions': ('Sugestões | Ajude a construir a ARKLAND',
                    'Tem uma ideia para a comunidade? Visite a área de sugestões, confira o que já foi proposto e apresente sua ideia com contexto e exemplos.\n\n[Abrir sugestões](https://arkland.com.br/#/sugestoes)'),
    'teams': ('Equipes | Encontre seu grupo',
              'A jornada também é feita em equipe. Conheça as equipes da comunidade e consulte no portal as informações e opções disponíveis para participar.\n\n[Conhecer as equipes](https://arkland.com.br/#/teams-directory)'),
}

GREETING_REPLIES = (
    "Olá, sobrevivente! Estou por aqui para ajudar na sua jornada pela ARKLAND.",
    "À disposição, sobrevivente! Que sua próxima aventura pelas ilhas seja incrível.",
    "Oi! Pode contar comigo para encontrar as informações da comunidade ARKLAND.",
    "Presente! Espero que suas criaturas e construções estejam prosperando.",
    "Olá! Que os obeliscos iluminem sua próxima jornada. Como posso ajudar?",
    "Pode chamar, sobrevivente. Estou aqui para facilitar sua vida na ARKLAND.",
    "Oi, sobrevivente! Preparado para mais uma aventura pelas nossas ilhas?",
    "Estou por aqui! Se precisar de informações da comunidade, é só perguntar.",
    "Olá! Espero que sua tribo esteja bem e que suas domesticações estejam seguras.",
    "Sempre à disposição. Vamos deixar sua jornada pela ARKLAND mais simples.",
    "Oi! Que bom encontrar você por aqui. Em que posso ajudar?",
    "Olá, sobrevivente! Explore com cuidado e conte comigo quando surgir uma dúvida.",
    "Pode falar comigo! Vou buscar as informações disponíveis para ajudar.",
    "Saudações da ARKLAND! Espero que seu dia nas ilhas esteja indo bem.",
    "Estou online para ajudar. Qual informação você está procurando?",
    "Olá! Que sua próxima expedição traga boas descobertas e grandes histórias.",
    "Oi, sobrevivente! Estou por aqui, sem precisar de sinalizador no obelisco.",
    "Conte comigo para encontrar os caminhos e informações da comunidade.",
    "Olá! Que suas construções resistam às tempestades e às criaturas da ilha.",
    "À disposição! Vamos descobrir juntos o que você precisa saber.",
    "Oi! Sua jornada na ARKLAND fica melhor quando ninguém fica com dúvida.",
    "Olá, sobrevivente! Estou por aqui para compartilhar informações úteis.",
    "Pode chamar. Vou responder com os dados que estiverem disponíveis no sistema.",
    "Saudações! Espero que sua aventura esteja rendendo boas histórias.",
    "Olá! Pronto para ajudar com informações da comunidade ARKLAND.",
    "Estou por aqui. Pergunte o que precisar sobre os serviços da comunidade.",
    "Oi, sobrevivente! Que sua jornada seja segura e sua tribo esteja em harmonia.",
    "Olá! Se precisar de uma informação, vou procurar a fonte correta para você.",
    "À disposição, sobrevivente. Vamos explorar essa dúvida juntos.",
    "Oi! Pode me chamar sempre que precisar de uma orientação da ARKLAND.",
)

TRIGGERS: dict[str, dict[str, Any]] = {
    "STATUS": {
        "label": "Status dos servidores",
        "aliases": ("servidor", "servidores", "mapa", "mapas", "status"),
    },
    "BETLAND": {
        "label": "Bet Land",
        "aliases": ("betland", "bet land", "sorteio", "premio do bet", "prêmio do bet"),
    },
    "LICENCAS": {
        "label": "Licenças",
        "aliases": ("licenca", "licencas", "license", "licenses"),
    },
    "VOTACAO": {
        "label": "Votações",
        "aliases": ("votacao", "votacoes", "votar", "enquete", "enquetes"),
    },
}

# Tópicos de texto simples do canal de chat compartilhado com o ARK. Estes
# gatilhos não alteram o canal global nem usam embeds.
GAME_CHAT_TOPICS: dict[str, tuple[str, ...]] = {
    "BETLAND": ("betland", "bet land", "sorteio"),
    "VOTACAO": ("votacao", "votacoes", "votar", "enquete", "enquetes"),
    "SEASON": ("seasonland", "temporada"),
    "SUPPORT": ("bug", "erro", "problema", "ticket", "suporte"),
    "SITE": ("site", "website", "arkland.com.br"),
    "LINK": ("vincular", "vinculacao", "vincular conta"),
    "STARTER": ("kit inicial", "starter kit"),
    "CATALOG": ("catalogo", "resgate", "resgates"),
    "STATUS": ("status", "servidor", "servidores", "mapa", "mapas"),
    "LIMIT": ("limite", "limites", "structures limit"),
    "LUMO": ("lumo",),
}

GAME_CHAT_REPLIES = {
    "SEASON": "Consulte as informações atuais da SeasonLand no site oficial: arkland.com.br.",
    "SUPPORT": "Precisa de ajuda? Abra um ticket pelo site arkland.com.br.",
    "SITE": "Site oficial ARKLAND: arkland.com.br.",
    "LINK": "Para vincular sua conta do Discord, acesse arkland.com.br e abra a área da sua conta.",
    "STARTER": "O kit inicial tem condições de elegibilidade. Confira os detalhes no catálogo em arkland.com.br.",
    "CATALOG": "O catálogo pode ter resgates gratuitos e pagos. Confira as opções atuais em arkland.com.br.",
    "STATUS": "Consulte o status e os avisos atuais dos serviços em arkland.com.br.",
    "LIMIT": "Consulte as regras e os limites de estruturas no site ou abra um ticket em arkland.com.br.",
    "LUMO": "Sou Lumo, assistente de informações da ARKLAND. Para suporte detalhado, abra um ticket em arkland.com.br.",
}


def recognize_game_topic(message: str, aliases: dict[str, Any] | None = None, enabled: dict[str, Any] | None = None) -> str | None:
    """Reconhece um tópico por palavra/frase completa; retorna o primeiro prioritário."""
    text = normalize_text(message)
    # Evita respostas a negações explícitas como "não fale do site".
    if re.search(r"\b(nao|nunca|pare de|sem falar|nao precisa)\b.{0,35}$", text):
        return None
    custom = aliases if isinstance(aliases, dict) else {}
    priority = ("BETLAND", "VOTACAO", "SEASON", "SUPPORT", "LINK", "STARTER", "CATALOG", "LIMIT", "STATUS", "SITE", "LUMO")
    for topic in priority:
        if isinstance(enabled, dict) and enabled.get(topic) is False:
            continue
        candidates = list(GAME_CHAT_TOPICS[topic])
        values = custom.get(topic, [])
        if isinstance(values, list):
            candidates.extend(str(value) for value in values[:30] if str(value).strip())
        if any(_contains_phrase(text, value) for value in candidates):
            return topic
    return None

_LICENSE_CONTEXT = re.compile(
    r"\b(licen[cs](?:a|as|e|es)?|comprar|pre[cç]o|custa|valor|rendimento|ganh[oa]|"
    r"retorno|investimento|vale a pena|dura[cç][aã]o|validade|renovar)\b", re.I,
)


def normalize_text(value: Any) -> str:
    raw = unicodedata.normalize("NFKD", str(value or "").casefold())
    return "".join(ch for ch in raw if not unicodedata.combining(ch))


def _contains_phrase(text: str, phrase: str) -> bool:
    phrase = normalize_text(phrase).strip()
    if not phrase:
        return False
    return bool(re.search(r"(?<!\w)" + re.escape(phrase) + r"(?!\w)", text))


@dataclass(frozen=True)
class TriggerMatch:
    key: str
    rule: str
    license_group: str = ""


def recognize_trigger(
    message: str,
    licenses: Iterable[dict[str, Any]] = (),
    aliases: dict[str, Any] | None = None,
    enabled: dict[str, Any] | None = None,
) -> TriggerMatch | None:
    """Reconhece apenas os quatro tópicos autorizados, sem substring acidental."""
    text = normalize_text(message)
    license_list = [item for item in licenses if isinstance(item, dict)]

    # Licença específica exige contexto econômico/menção explícita a licença;
    # evita disparar com "Encontrei um Spirit Rex".
    if _LICENSE_CONTEXT.search(text) and (enabled is None or enabled.get("LICENCAS") is not False):
        for item in license_list:
            group = str(item.get("group") or item.get("label") or "").strip()
            label = str(item.get("label") or group).strip()
            candidates = {group, label, str(item.get("item_id") or "")}
            candidates.update(str(x) for x in (item.get("aliases") or []) if x)
            if any(_contains_phrase(text, candidate) for candidate in candidates):
                return TriggerMatch("LICENCAS", "license_specific", group)
    def has_trigger(key: str, defaults: tuple[str, ...]) -> bool:
        if enabled is not None and enabled.get(key) is False:
            return False
        custom = (aliases or {}).get(key, [])
        words = list(defaults)
        if isinstance(custom, list):
            words.extend(str(x) for x in custom[:40] if str(x).strip())
        return any(_contains_phrase(text, word) for word in words)

    if has_trigger("BETLAND", ("betland", "bet land")):
        return TriggerMatch("BETLAND", "keyword_or_phrase")
    if has_trigger("VOTACAO", ("votacao", "votacoes", "votar", "enquete", "enquetes")):
        return TriggerMatch("VOTACAO", "keyword_or_phrase")
    if _LICENSE_CONTEXT.search(text) and (enabled is None or enabled.get("LICENCAS") is not False):
        return TriggerMatch("LICENCAS", "license_general")
    if has_trigger("STATUS", ("status", "servidor", "servidores", "mapa", "mapas")):
        return TriggerMatch("STATUS", "keyword_or_phrase")
    return None


def pick_greeting(previous: str = "", *, rng: random.Random | None = None) -> str:
    chooser = rng or random
    choices = [reply for reply in GREETING_REPLIES if reply != previous]
    return chooser.choice(choices or list(GREETING_REPLIES))


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError, OverflowError):
        return default


def build_response(match: TriggerMatch, data: dict[str, Any], config: dict[str, Any]) -> tuple[str, str]:
    """Retorna (título, descrição); dados ausentes/falhas nunca viram valores fictícios."""
    if match.key == "STATUS":
        channel_id = str(config.get("lumo_status_channel_id") or config.get("status_channel_id") or "").strip()
        systems = data.get("systems", []) if isinstance(data, dict) else []
        incidents = data.get("incidents", []) if isinstance(data, dict) else []
        if not data.get("ok"):
            raise RuntimeError("A central de status está temporariamente indisponível.")
        if not isinstance(systems, list):
            systems = []
        unverified = sum(1 for item in systems if isinstance(item, dict) and (
            item.get("maturity") == "NAO_AVALIADO" or item.get("operational") in {"NAO_MONITORADO", "STATUS_DESCONHECIDO"}
        ))
        lines = ["Olá, sobrevivente! Consulte o painel central para ver o estágio e as condições atuais dos serviços ARKLAND:", SITE_URL + "#/system-status"]
        lines.append(f"\nRegistros públicos: {len(systems)}. {unverified} ainda aguardam avaliação ou monitoramento.")
        cluster = next((item for item in systems if isinstance(item, dict) and item.get("system_key") == "ark-cluster"), {})
        maps = cluster.get("instances", []) if isinstance(cluster, dict) else []
        if maps:
            status_labels = {"ONLINE":"Online", "INICIANDO":"Iniciando", "ATUALIZANDO":"Atualizando", "PARADO":"Parado",
                             "ONLINE_SEM_LISTAGEM":"Online, sem listagem", "ONLINE_LAN":"Online na rede local", "QUERY_PENDENTE":"Aguardando query"}
            lines.append("\n\nMapas (último estado recebido do gerenciador):")
            for item in maps[:12]:
                state = str(item.get("operational") or "STATUS_DESCONHECIDO")
                lines.append(f"\n• {str(item.get('display_name') or item.get('map_name') or 'Servidor')[:120]} — {status_labels.get(state, state.replace('_', ' ').lower())}")
        else:
            lines.append("\n\nAinda não há estado recente dos mapas recebido do gerenciador.")
        active = [item for item in incidents if isinstance(item, dict)][:5]
        if active:
            lines.append("\nIncidentes ou manutenções em andamento:")
            lines.extend(f"\n• {str(item.get('title') or 'Incidente')[:160]} — {str(item.get('state') or '').replace('_', ' ').lower()}" for item in active)
        if channel_id.isdigit():
            lines.append(f"\n\nAcompanhe também o canal de status: <#{channel_id}>.")
        lines.append("\nO painel pode ter atraso em relação às fontes operacionais.")
        return "Status dos sistemas ARKLAND", "".join(lines)

    if match.key == "BETLAND":
        campaign = data.get("campaign") if isinstance(data, dict) else None
        if not data.get("ok"):
            raise RuntimeError("A consulta do Bet Land está temporariamente indisponível.")
        if not data.get("enabled") or not campaign or str(campaign.get("status") or "").upper() != "ACTIVE":
            return "Bet Land | ARKLAND", "No momento não há um sorteio aberto, sobrevivente. Consulte as novidades no site oficial: " + BETLAND_URL
        prize = _safe_int(campaign.get("prize_amber_total"), -1)
        random_price = _safe_int(campaign.get("amber_random_price"), -1)
        reserve_price = _safe_int(campaign.get("amber_reserve_price"), -1)
        draw = str(campaign.get("draw_at_display") or "").strip()
        remaining = _safe_int(campaign.get("seconds_remaining"), -1)
        if prize < 0 or random_price < 0 or reserve_price < 0 or not draw or remaining < 0:
            raise RuntimeError("Os dados atuais do sorteio estão incompletos.")
        duration = f"{remaining // 86400}d {(remaining % 86400) // 3600}h {((remaining % 3600) // 60)}min"
        title = str(campaign.get("title") or "Bet Land | Sorteio aberto")[:256]
        description = (
            f"Olá, sobrevivente! O prêmio atual é **{prize:,} Âmbares**.\n\n"
            f"**Sorteio:** {draw}\n**Tempo restante:** {duration}\n"
            f"**Aposta aleatória:** {random_price:,} Âmbares · **Reserva:** {reserve_price:,} Âmbares\n\n"
            f"Consulte as regras e participe pelo site oficial: {BETLAND_URL}"
        ).replace(",", ".")
        return title, description

    if match.key == "LICENCAS":
        if match.rule == "license_general":
            return "Licenças ARKLAND", (
                "Olá, sobrevivente! As licenças podem aumentar seus ganhos de Âmbares enquanto você joga. "
                "O bônus é concedido a cada ciclo de 30 minutos online, conforme as características de cada licença.\n\n"
                f"Consulte opções, valores e benefícios no site oficial: {LICENSES_URL}"
            )
        licenses = data.get("licenses") if isinstance(data, dict) else None
        target = normalize_text(match.license_group)
        item = next((x for x in licenses or [] if normalize_text(x.get("group") or x.get("label")) == target), None)
        if not item:
            raise RuntimeError("Não encontrei dados atualizados para essa licença.")
        name = str(item.get("label") or item.get("group") or "Licença")
        price = _safe_int(item.get("price_amber"), -1)
        reward = _safe_int(item.get("bonus_per_cycle"), -1)
        days = _safe_int(item.get("days"), 0)
        if price < 0 or reward < 0:
            raise RuntimeError("O preço ou o rendimento dessa licença não está disponível no catálogo atual.")
        if reward:
            cycles = (price + reward - 1) // reward
            hours = cycles * 0.5
            payback = f"{cycles} ciclos ({hours:g} horas online)"
        else:
            payback = "não calculável: o catálogo não informa bônus adicional por ciclo"
        validity = f"Validade: {days} dias." if days > 0 else "Validade: permanente ou não informada no catálogo."
        description = (
            f"**Valor:** {price:,} Âmbares\n**Bônus adicional:** {reward:,} Âmbares por ciclo de 30 minutos online\n"
            f"**Retorno teórico pelo bônus desta licença:** {payback}\n{validity}\n\n"
            "O cálculo é uma estimativa e não garante retorno; considera somente o bônus adicional desta licença.\n"
            f"Consulte os detalhes no site oficial: {LICENSES_URL}"
        ).replace(",", ".")
        return f"Licença {name}", description

    if match.key == "VOTACAO":
        if not data.get("ok"):
            raise RuntimeError("A consulta de votações está temporariamente indisponível.")
        polls = [p for p in data.get("polls", []) if p.get("is_open")]
        if not polls:
            return "Votações abertas | ARKLAND", "No momento, não temos votações abertas, sobrevivente. Assim que uma estiver disponível, compartilharei a novidade por aqui."
        lines = ["Olá, sobrevivente! Estas votações estão abertas:"]
        for poll in polls[:10]:
            reward = _safe_int(poll.get("reward_amber"), 0)
            end = str(poll.get("ends_at") or "").replace("T", " ").replace("+00:00", " UTC")
            title = str(poll.get("title") or "Votação")[:200]
            poll_url = SITE_URL + f"#/polls/{_safe_int(poll.get('id'))}"
            lines.append(f"\n**{title}**\nRecompensa configurada: {reward:,} Âmbares".replace(",", ".") + (f"\nDisponível até: {end}" if end else "") + f"\n[Abrir esta votação]({poll_url})")
        lines.append(f"\nParticipe pelo site oficial: {POLLS_URL}")
        return "Votações abertas | ARKLAND", "\n".join(lines)

    raise ValueError("Gatilho não autorizado.")


def make_embed_payload(title: str, description: str, *, now: datetime | None = None) -> dict[str, Any]:
    title = str(title or "").strip()[:256]
    description = str(description or "").strip()
    if not description:
        raise ValueError("A resposta do Lumo ficou vazia.")
    if len(description) > 4096 or len(title) + len(description) + len(FOOTER) > 6000:
        raise ValueError("A resposta excede os limites de embed do Discord.")
    stamp = (now or datetime.now(timezone.utc)).astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    payload: dict[str, Any] = {"description": description, "color": COLOR, "footer": {"text": FOOTER}, "timestamp": stamp}
    if title:
        payload["title"] = title
    return payload

