"""Contrato compartilhado e formatação do Chat Arkland (sem credenciais)."""
from __future__ import annotations

import copy
from datetime import datetime, timedelta, timezone
import html
import re
from string import Formatter
import unicodedata
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

try:
    BRAZIL = ZoneInfo("America/Sao_Paulo")
except ZoneInfoNotFoundError:
    BRAZIL = timezone(timedelta(hours=-3))

MESSAGES = {
    "Global": "[{hora}][{mapa}] {tag}{jogador} ({id}){tribo}: {mensagem}",
    "Discord": "[{hora}][Discord] {tag}{jogador}: {mensagem}",
    "PrivateFrom": "[Privado] {jogador} ({id}) → você: {mensagem}",
    "PrivateTo": "[Privado] Você → {destinatario} ({id}): {mensagem}",
    "Join": "{jogador} ({id}) entrou em {mapa}.",
    "Leave": "{jogador} ({id}) saiu de {mapa}.",
    "OnlineHeader": "Jogadores online: {total} · página {pagina}/{total_paginas}",
    "OnlinePlayer": "{jogador} ({id}){tribo}{mapa}{tempo}",
    "NoPermission": "Você não tem permissão para usar este comando.",
    "Spam": "Aguarde {segundos} segundo(s) antes de enviar outra mensagem global.",
    "PrivateUsage": "Use {comando} ID Mensagem. Exemplo: {comando} 125 Olá!",
    "ReplyUsage": "Use {comando} Mensagem. Exemplo: {comando} Obrigado pela ajuda!",
    "NoConversation": "Inicie uma conversa com {comando} ID Mensagem antes de usar {resposta}.",
    "InvalidId": "O ID informado é inválido ou não existe.",
    "Offline": "O jogador está desconectado ou transferindo de mapa. Tente novamente em instantes.",
    "SelfMessage": "Você não pode enviar uma mensagem privada para si mesmo.",
    "EmptyMessage": "Digite uma mensagem antes de enviar.",
    "TooLong": "A mensagem excede o tamanho máximo permitido.",
    "Disabled": "Esta funcionalidade está desativada pela administração.",
    "NotificationsOn": "Notificações de entrada e saída ativadas para você.",
    "NotificationsOff": "Notificações de entrada e saída desativadas para você.",
    "Unavailable": "O chat entre mapas está temporariamente indisponível; o chat nativo continua disponível.",
    "PendingIdentity": "Seu ID do chat ainda está sendo sincronizado. Tente novamente em instantes.",
    "DeliveryFailed": "Não foi possível confirmar a entrega da mensagem privada.",
}

DEFAULTS = {
    "SchemaVersion": 1, "ClusterName": "ARKLAND", "DisableChat": False,
    "DisableCrossServerChat": False, "UseCrossChat": True, "Debug": False,
    "PollRate": 1.0, "ShowMapName": True, "HideServerTagOnLocal": False,
    "ShowSteamName": False, "GlobalChatSpamDelaySec": 2.0,
    "AdminImmuneToMuteAndSpamDelay": True, "AdminGroups": ["Admins", "STAFF", "Mod"],
    "MaxMessageLength": 500, "MessageTtlSeconds": 30, "PresenceTtlSeconds": 45,
    "CrossMapNotifications": {"Enabled": True, "ToggleCommand": "/joinleave", "DisplayScale": 1.0,
        "DisplayTime": 5.0, "JoinDifferentColor": "#FFFFFFFF", "LeaveDifferentColor": "#FFFFFFFF",
        "JoinSameColor": "#64B464FF", "LeaveSameColor": "#A33232FF"},
    "OnlinePlayersCommand": {"Enabled": True, "Command": "/online", "ShowTribes": True,
        "ShowOnlineTime": True, "DisplayTime": 10.0, "DisplayScale": 0.5, "AmountPerPage": 15,
        "OnlyShowMapToGroups": ["Admins"], "RestrictCommandToPermissions": ["Default"]},
    "PrivateMessages": {"Enabled": True, "Command": "/pm", "ReplyCommand": "/r"},
    "BadWords": {"Enabled": False, "IgnoredLetters": [".", "-", "_", " "], "Words": []},
    "Discord": {"Enabled": True, "AllowDiscordToIngame": True, "ShowMap": True},
    "Colors": {"Message": "#FFFFFFFF", "Name": "#2ECC71FF", "Tribe": "#E67E21FF",
        "Tag": "#FFD700FF", "Map": "#F29E19CC", "Discord": "#7289DAFF", "Id": "#DDDDDDFF",
        "OverrideGraySelfNameColor": True, "HideTribeName": False},
    "ChatColors": [], "Tags": [], "Maps": {}, "Messages": MESSAGES,
}
_TOKEN_RE = re.compile(r"^[A-Za-z0-9_.:-]{1,100}$")
_COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}(?:[0-9a-fA-F]{2})?$")
_FIELDS = {field for value in MESSAGES.values() for _, field, _, _ in Formatter().parse(value) if field}


def _merge(base, update):
    if not isinstance(update, dict):
        raise ValueError("Bloco de configuração inválido.")
    result = copy.deepcopy(base)
    for key, value in update.items():
        if key not in base:
            raise ValueError(f"Configuração desconhecida: {key}.")
        result[key] = _merge(base[key], value) if isinstance(base[key], dict) and key not in {"Maps"} else copy.deepcopy(value)
    return result


def color(value: str) -> str:
    if not isinstance(value, str) or not _COLOR_RE.fullmatch(value):
        raise ValueError("Informe uma cor hexadecimal válida (#RRGGBB ou #RRGGBBAA).")
    return (value + "FF" if len(value) == 7 else value).upper()


def validate_config(raw: dict) -> dict:
    if not isinstance(raw, dict):
        raise ValueError("A configuração compartilhada deve ser um objeto.")
    result = _merge(DEFAULTS, raw)
    def validate_types(base, value, path=""):
        for key, expected in base.items():
            item = value[key]
            label = path + key
            if isinstance(expected, bool) and type(item) is not bool:
                raise ValueError(f"{label}: informe ativado ou desativado.")
            if isinstance(expected, dict) and key != "Maps":
                if not isinstance(item, dict):
                    raise ValueError(f"{label}: bloco inválido.")
                validate_types(expected, item, label + ".")
            elif isinstance(expected, str) and not isinstance(item, str):
                raise ValueError(f"{label}: texto inválido.")
            elif isinstance(expected, list) and not isinstance(item, list):
                raise ValueError(f"{label}: lista inválida.")
    validate_types(DEFAULTS, result)
    for key, low, high in (("PollRate", 0.1, 30), ("GlobalChatSpamDelaySec", 0, 120),
                            ("MaxMessageLength", 1, 500), ("MessageTtlSeconds", 5, 120), ("PresenceTtlSeconds", 15, 120)):
        value = result[key]
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not low <= value <= high:
            raise ValueError(f"{key}: informe um número entre {low} e {high}.")
    if not str(result["ClusterName"]).strip() or len(result["ClusterName"]) > 80:
        raise ValueError("O nome do cluster deve ter de 1 a 80 caracteres.")
    for key in ("MaxMessageLength", "MessageTtlSeconds", "PresenceTtlSeconds"):
        if int(result[key]) != result[key]:
            raise ValueError(f"{key}: informe um número inteiro.")
    if result["PresenceTtlSeconds"] < result["PollRate"] * 3 or result["MessageTtlSeconds"] < result["PollRate"] * 2 + 2:
        raise ValueError("Os prazos de presença/mensagem são menores que os intervalos necessários para esse PollRate.")
    for key in result["Colors"]:
        if key not in {"HideTribeName", "OverrideGraySelfNameColor"}:
            result["Colors"][key] = color(result["Colors"][key])
    for key in ("JoinDifferentColor", "LeaveDifferentColor", "JoinSameColor", "LeaveSameColor"):
        result["CrossMapNotifications"][key] = color(result["CrossMapNotifications"][key])
    commands = [result["CrossMapNotifications"]["ToggleCommand"], result["OnlinePlayersCommand"]["Command"],
                result["PrivateMessages"]["Command"], result["PrivateMessages"]["ReplyCommand"]]
    if len(set(commands)) != 4 or any(not re.fullmatch(r"/[a-zA-Z][a-zA-Z0-9_]{0,23}", command) for command in commands):
        raise ValueError("Os quatro comandos devem ser diferentes e começar com /.")
    for block in ("CrossMapNotifications", "OnlinePlayersCommand"):
        for key, low, high in (("DisplayScale", 0.1, 5), ("DisplayTime", 1, 60)):
            value = result[block][key]
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not low <= value <= high:
                raise ValueError(f"{block}.{key}: valor fora do intervalo {low}–{high}.")
    page_size = result["OnlinePlayersCommand"]["AmountPerPage"]
    if type(page_size) is not int or not 1 <= page_size <= 50:
        raise ValueError("A quantidade por página deve estar entre 1 e 50.")
    for group_list in (result["AdminGroups"], result["OnlinePlayersCommand"]["OnlyShowMapToGroups"], result["OnlinePlayersCommand"]["RestrictCommandToPermissions"]):
        if len(group_list) > 100 or any(not isinstance(item, str) or not _TOKEN_RE.fullmatch(item) for item in group_list):
            raise ValueError("Lista de grupos inválida.")
    words = result["BadWords"]["Words"]
    if len(words) > 1000 or any(not isinstance(word, str) or not 1 <= len(word.strip()) <= 80 for word in words):
        raise ValueError("A lista do filtro contém palavras inválidas ou excede 1.000 entradas.")
    result["BadWords"]["Words"] = list(dict.fromkeys(word.strip() for word in words))
    if len(result["BadWords"]["IgnoredLetters"]) > 20 or any(not isinstance(x, str) or len(x) != 1 or x.isalnum() for x in result["BadWords"]["IgnoredLetters"]):
        raise ValueError("Caracteres ignorados devem ser sinais individuais ou espaços.")
    if not isinstance(result["Maps"], dict) or len(result["Maps"]) > 1000:
        raise ValueError("Cadastro de mapas inválido.")
    for key, item in result["Maps"].items():
        if not _TOKEN_RE.fullmatch(key) or not isinstance(item, dict) or set(item) - {"Enabled", "Label", "Color"}:
            raise ValueError("Configuração de mapa inválida.")
        if type(item.get("Enabled", False)) is not bool or not isinstance(item.get("Label", ""), str) or len(item.get("Label", "")) > 100:
            raise ValueError("Nome ou participação do mapa inválidos.")
        item["Color"] = color(item.get("Color", result["Colors"]["Map"]))
    for collection in ("Tags", "ChatColors"):
        if len(result[collection]) > 200:
            raise ValueError(f"{collection}: limite de 200 regras.")
        allowed = {"Key", "Label", "Kind", "Priority", "Approved", "Enabled", "PermissionGroups", "LicenseGroups", "SteamIds", "TribeIds"} | ({"Color"} if collection == "Tags" else {"Colors"})
        seen = set()
        for item in result[collection]:
            if not isinstance(item, dict) or set(item) - allowed or not _TOKEN_RE.fullmatch(str(item.get("Key", ""))) or item["Key"] in seen:
                raise ValueError(f"{collection}: regra inválida ou chave repetida.")
            seen.add(item["Key"])
            if item.get("Kind") not in ({"admin", "license", "custom"} if collection == "Tags" else {"admin", "license", "custom", "everyone"}) or type(item.get("Priority", 0)) is not int or not 0 <= item.get("Priority", 0) <= 1000000:
                raise ValueError("Tipo ou prioridade de regra inválidos.")
            for flag in ("Approved", "Enabled"):
                if type(item.get(flag, False)) is not bool:
                    raise ValueError("Confirmação e ativação devem ser booleanas.")
            if not isinstance(item.get("Label", ""), str) or len(item.get("Label", "")) > 40 or (collection == "Tags" and not item.get("Label", "").strip()):
                raise ValueError("O nome da tag deve ter até 40 caracteres.")
            for field in ("PermissionGroups", "LicenseGroups", "SteamIds", "TribeIds"):
                values = item.get(field, [])
                if not isinstance(values, list) or len(values) > 200 or any(not isinstance(x, str) or not _TOKEN_RE.fullmatch(x) for x in values):
                    raise ValueError("Associação de regra inválida.")
            if "Color" in item:
                item["Color"] = color(item["Color"])
            overrides = item.get("Colors", {})
            if not isinstance(overrides, dict) or set(overrides) - set(result["Colors"]):
                raise ValueError("Cores da regra inválidas.")
            for field, value in overrides.items():
                if field in {"HideTribeName", "OverrideGraySelfNameColor"}:
                    if type(value) is not bool:
                        raise ValueError("Controle visual inválido.")
                else:
                    overrides[field] = color(value)
    for key, value in result["Messages"].items():
        if len(value) > 1000:
            raise ValueError(f"Messages.{key}: texto muito longo.")
        try:
            fields = [field for _, field, fmt, conv in Formatter().parse(value) if field]
            allowed_fields = {field for _, field, _, _ in Formatter().parse(MESSAGES[key]) if field}
            if any(field not in allowed_fields for field in fields) or any(fmt or conv for _, _, fmt, conv in Formatter().parse(value)):
                raise ValueError()
        except ValueError:
            raise ValueError(f"Messages.{key}: variável ou formatação inválida.") from None
    if not {"hora", "mapa", "jogador", "id", "mensagem"} <= set(re.findall(r"\{([^{}]+)\}", result["Messages"]["Global"])):
        raise ValueError("A mensagem global deve preservar horário, mapa, jogador, ID e mensagem.")
    return result


def clean_text(value, limit=500):
    value = unicodedata.normalize("NFC", str(value or ""))
    value = " ".join("".join(c for c in value if unicodedata.category(c) not in {"Cc", "Cf"} or c in "\n\t").split())
    if len(value) > limit:
        raise ValueError(MESSAGES["TooLong"])
    return value


def censor(text: str, config: dict) -> str:
    policy = config["BadWords"]
    if not policy["Enabled"] or not policy["Words"]:
        return text
    translate = str.maketrans({"0": "o", "1": "i", "3": "e", "4": "a", "5": "s", "7": "t", "@": "a"})
    normalized, positions = [], []
    for index, char in enumerate(text):
        for part in unicodedata.normalize("NFKD", char.casefold().translate(translate)):
            if not unicodedata.combining(part):
                normalized.append(part)
                positions.append(index)
    joined = "".join(normalized)
    ignored = "[" + re.escape("".join(policy["IgnoredLetters"])) + "]*" if policy["IgnoredLetters"] else ""
    spans = []
    for word in policy["Words"]:
        target = "".join(c for c in unicodedata.normalize("NFKD", word.casefold().translate(translate)) if not unicodedata.combining(c))
        target = "".join(c for c in target if c not in policy["IgnoredLetters"])
        if not target:
            continue
        pattern = r"(?<!\w)" + ignored.join(re.escape(c) for c in target) + r"(?!\w)"
        for match in re.finditer(pattern, joined):
            spans.append((positions[match.start()], positions[match.end() - 1] + 1))
    chars = list(text)
    for start, end in spans:
        chars[start:end] = ["*"] * (end - start)
    return "".join(chars)


def display_name(value: str) -> str:
    return clean_text(value, 128).translate(str.maketrans({"[": "［", "]": "］", "<": "‹", ">": "›", ":": "："}))


def select_style(config: dict, actor: dict, active_licenses: set[str]) -> tuple[dict | None, dict]:
    groups = set(actor.get("groups", [])) | {"Default"}
    def matches(rule):
        if not rule.get("Approved") or not rule.get("Enabled"):
            return False
        permission = bool(groups.intersection(rule.get("PermissionGroups") or (config["AdminGroups"] if rule["Kind"] == "admin" else [])))
        license_match = bool(active_licenses.intersection(rule.get("LicenseGroups", [])))
        identity_scope = actor.get("steam_id") in rule.get("SteamIds", []) or str(actor.get("tribe_id", "")) in rule.get("TribeIds", [])
        restricted_identity = bool(rule.get("SteamIds") or rule.get("TribeIds"))
        if rule["Kind"] == "license":
            restricted = restricted_identity or bool(rule.get("PermissionGroups"))
            return license_match and (not restricted or permission or identity_scope)
        if rule["Kind"] == "admin":
            return permission and (not restricted_identity or identity_scope)
        return rule["Kind"] == "everyone" or permission or license_match or identity_scope
    order = lambda rule: (0 if rule["Kind"] == "admin" else 1, rule.get("Priority", 0), rule["Key"])
    tags = sorted((rule for rule in config["Tags"] if matches(rule)), key=order)
    styles = sorted((rule for rule in config["ChatColors"] if matches(rule)), key=order)
    colors = {**config["Colors"], **(styles[0].get("Colors", {}) if styles else {})}
    return (tags[0] if tags else None), colors


def format_global(config: dict, actor: dict, public_id: str | None, map_label: str, body: str,
                  *, origin="game", tag=None, colors=None, now=None) -> dict:
    now = now or datetime.now(BRAZIL)
    stamp = now.astimezone(BRAZIL).strftime("%H:%M")
    name = display_name(actor.get("steam_name") if config["ShowSteamName"] and actor.get("steam_name") else actor.get("name") or "Sobrevivente")
    tribe = display_name(actor.get("tribe_name") or "")
    colors = colors or config["Colors"]
    body = censor(clean_text(body, config["MaxMessageLength"]), config)
    label = display_name(map_label)
    values = {"hora": stamp, "mapa": label, "tag": f"<{display_name(tag['Label'])}> " if tag else "",
              "jogador": name, "id": str(public_id or ""), "tribo": f" [{tribe}]" if tribe and not colors["HideTribeName"] else "", "mensagem": body}
    template = config["Messages"]["Global" if origin == "game" else "Discord"]
    if origin == "game" and not config["ShowMapName"]:
        template = template.replace("[{mapa}]", "")
    plain = template.format_map(values)
    def rich(value, paint):
        value = html.escape(str(value), quote=False)
        rgba = color(paint)
        channels = ",".join(f"{int(rgba[i:i+2], 16)/255:.4f}" for i in (1,3,5,7))
        return f"<RichColor Color=\"{channels}\">{value}</>"
    rich_values = {**values,
        "mapa": rich(label, colors["Map"] if origin == "game" else colors["Discord"]),
        "tag": rich(values["tag"], tag.get("Color", colors["Tag"])) if tag else "",
        "jogador": rich(name, colors["Name"]), "id": rich(values["id"], colors["Id"]),
        "tribo": rich(values["tribo"], colors["Tribe"]), "mensagem": rich(body, colors["Message"])}
    return {"plain": plain, "rich": template.format_map(rich_values), "body": body,
            "sender_name": name, "tag": tag["Label"] if tag else "", "public_id": public_id}
