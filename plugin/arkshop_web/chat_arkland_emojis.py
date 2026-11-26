"""Portable basic emoticons and the eight verified native ASE chat images."""
from __future__ import annotations

import html
import re

# Only these local assets are emitted. No user-supplied path/attribute is rendered.
EMOJIS = [
    {"asset": "Emo_Smile", "unicode": "🙂", "ascii": [":-)", ":)"], "aliases": ["😊", "☺️", "☺"]},
    {"asset": "Emo_Sad", "unicode": "🙁", "ascii": [":-(", ":("], "aliases": ["☹️", "☹", "😞"]},
    {"asset": "Emo_Laugh", "unicode": "😄", "ascii": [":-D", ":D", ":-d", ":d"], "aliases": ["😀", "😃"]},
    {"asset": "Emo_Wink", "unicode": "😉", "ascii": [";-)", ";)"], "aliases": []},
    {"asset": "Emo_Tongue", "unicode": "😛", "ascii": [":-P", ":P", ":-p", ":p"], "aliases": ["😋"]},
    {"asset": "Emo_Evil", "unicode": "😈", "ascii": [">:-)", ">:)"], "aliases": []},
    {"asset": "Emo_Blank", "unicode": "😐", "ascii": [":-|", ":|"], "aliases": []},
    {"asset": "Emo_Eyes", "unicode": "😮", "ascii": [":-O", ":O", ":-o", ":o"], "aliases": ["😲"]},
]
_BY_ASSET = {row["asset"]: row for row in EMOJIS}
_BY_UNICODE = {row["unicode"]: row for row in EMOJIS}
_ALIASES = sorted(((value, row["unicode"]) for row in EMOJIS for value in row["aliases"]), key=lambda pair: -len(pair[0]))
_ASCII = sorted(((value, row["unicode"]) for row in EMOJIS for value in row["ascii"]), key=lambda pair: -len(pair[0]))
_NATIVE = re.compile(r'<img\s+src="Chat\.Image"\s+path="/Game/PrimalEarth/Emo/(Emo_[A-Za-z]+)\.\1"\s*/>')
_URL = re.compile(r'(?:[A-Za-z][A-Za-z0-9+.-]*://|www\.)[^\s<>]+')
_UNICODE = re.compile("|".join(re.escape(value) for value in _BY_UNICODE))


def _word(char):
    # Mirrors the native UTF-8 codec's conservative non-ASCII boundary rule.
    return char.isascii() and (char.isalnum() or char == "_") or ord(char) > 127


def normalize_emojis(value):
    text = str(value or "")
    text = _NATIVE.sub(lambda match: _BY_ASSET[match[1]]["unicode"] if match[1] in _BY_ASSET else match[0], text)
    for alias, canonical in _ALIASES:
        text = text.replace(alias, canonical)
    result, position = [], 0
    while position < len(text):
        url = _URL.match(text, position)
        if url:
            result.append(url[0])
            position = url.end()
            continue
        for token, canonical in _ASCII:
            after = position + len(token)
            if (text.startswith(token, position)
                    and (position == 0 or not _word(text[position-1]) and text[position-1] not in ":/")
                    and (after == len(text) or not _word(text[after]))):
                result.append(canonical)
                position = after
                break
        else:
            result.append(text[position])
            position += 1
    return "".join(result)


def native_image(asset):
    if asset not in _BY_ASSET:
        raise ValueError("Unsupported native chat image")
    return f'<img src="Chat.Image" path="/Game/PrimalEarth/Emo/{asset}.{asset}"/>'


def render_emojis(value, format_text=None):
    """Emit image runs outside color runs; every ordinary text run stays escaped."""
    text = normalize_emojis(value)
    format_text = format_text or (lambda value: html.escape(value, quote=False))
    result, start = [], 0
    for match in _UNICODE.finditer(text):
        if match.start() > start:
            result.append(format_text(text[start:match.start()]))
        result.append(native_image(_BY_UNICODE[match[0]]["asset"]))
        start = match.end()
    if start < len(text) or not result:
        result.append(format_text(text[start:]))
    return "".join(result)
