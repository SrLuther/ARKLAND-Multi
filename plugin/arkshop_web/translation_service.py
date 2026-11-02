"""Provider-neutral ticket translation service with an Azure Translator adapter."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import http.client
import json
import logging
import math
import os
import socket
import time
from typing import Callable
from urllib.parse import urlencode, urlsplit
import uuid

_SUPPORTED_LANGUAGES = frozenset({"pt", "en", "es"})
_logger = logging.getLogger(__name__)


class TranslationServiceError(RuntimeError):
    """Safe diagnostic metadata; never contains request credentials or text."""

    def __init__(self, code: str, stage: str, message: str,
                 *, http_status: int | None = None, request_id: str | None = None,
                 source_language: str | None = None,
                 target_language: str | None = None):
        super().__init__(message)
        self.code = code
        self.stage = stage
        self.http_status = http_status
        self.request_id = request_id
        self.source_language = source_language
        self.target_language = target_language


@dataclass(frozen=True)
class TranslationResult:
    translated_text: str
    source_language: str | None
    target_language: str
    provider: str
    confidence: float | None
    request_id: str | None
    metered_characters: int | None
    duration_ms: int
    http_status: int | None
    skipped: bool = False

    def as_dict(self) -> dict:
        return {
            "translated_text": self.translated_text,
            "source_language": self.source_language,
            "target_language": self.target_language,
            "provider": self.provider,
            "confidence": self.confidence,
            "request_id": self.request_id,
            "metered_characters": self.metered_characters,
            "duration_ms": self.duration_ms,
            "http_status": self.http_status,
            "skipped": self.skipped,
        }


def _config(config_override: dict | None = None) -> dict[str, str]:
    override = config_override if isinstance(config_override, dict) else {}
    key = (str(override.get("key") or "").strip()
           or (os.environ.get("AZURE_TRANSLATOR_KEY") or "").strip())
    endpoint = (str(override.get("endpoint") or "").strip()
                or (os.environ.get("AZURE_TRANSLATOR_ENDPOINT") or
                    "https://api.cognitive.microsofttranslator.com").strip()).rstrip("/")
    region = (str(override.get("region") or "").strip()
              or (os.environ.get("AZURE_TRANSLATOR_REGION") or "").strip())
    version = (os.environ.get("AZURE_TRANSLATOR_API_VERSION") or "3.0").strip()
    parts = urlsplit(endpoint)
    if not key:
        raise TranslationServiceError(
            "AZURE_TRANSLATOR_NOT_CONFIGURED", "configuration",
            "O Azure Translator não está configurado.",
        )
    if (parts.scheme != "https" or not parts.hostname or parts.username or parts.password
            or parts.query or parts.fragment):
        raise TranslationServiceError(
            "AZURE_TRANSLATOR_NOT_CONFIGURED", "configuration",
            "O endpoint do Azure Translator é inválido.",
        )
    try:
        parts.port
    except ValueError as exc:
        raise TranslationServiceError(
            "AZURE_TRANSLATOR_NOT_CONFIGURED", "configuration",
            "A porta do endpoint do Azure Translator é inválida.",
        ) from exc
    if not version:
        raise TranslationServiceError(
            "AZURE_TRANSLATOR_NOT_CONFIGURED", "configuration",
            "A versão da API Azure Translator não está configurada.",
        )
    return {"key": key, "endpoint": endpoint, "region": region, "version": version}


def translator_status(*, limit_override=None, thresholds_override=None,
                      config_override: dict | None = None) -> dict:
    """Safe configuration view. The key itself is never returned."""
    try:
        config = _config(config_override)
        key_set = bool(config["key"])
        endpoint = config["endpoint"]
        region = config["region"]
    except TranslationServiceError:
        override = config_override if isinstance(config_override, dict) else {}
        key_set = bool(str(override.get("key") or os.environ.get("AZURE_TRANSLATOR_KEY") or "").strip())
        endpoint = (str(override.get("endpoint") or os.environ.get("AZURE_TRANSLATOR_ENDPOINT") or
                        "https://api.cognitive.microsofttranslator.com").strip().rstrip("/"))
        region = str(override.get("region") or os.environ.get("AZURE_TRANSLATOR_REGION") or "").strip()
    parts = urlsplit(endpoint)
    try:
        valid_port = parts.port
        port_valid = True
    except ValueError:
        valid_port = None
        port_valid = False
    valid_endpoint = (parts.scheme == "https" and bool(parts.hostname) and not parts.username
                      and not parts.password and not parts.query and not parts.fragment and port_valid)
    return {
        "provider": "azure",
        "configured": key_set and valid_endpoint,
        "key_configured": key_set,
        "endpoint": (f"https://{parts.hostname}" + (f":{valid_port}" if valid_port else "") + parts.path.rstrip("/")) if valid_endpoint else "inválido",
        "region": region or None,
        "api_version": (os.environ.get("AZURE_TRANSLATOR_API_VERSION") or "3.0").strip(),
        "monthly_character_limit": monthly_character_limit(limit_override),
        "limit_configured": monthly_character_limit(limit_override) > 0,
        "alert_thresholds": alert_thresholds(thresholds_override),
    }


def monthly_character_limit(override=None) -> int:
    raw = (os.environ.get("AZURE_TRANSLATOR_MONTHLY_CHARACTER_LIMIT") or "").strip() if override is None else override
    if not raw:
        return 0
    try:
        return max(0, int(raw))
    except (TypeError, ValueError):
        _logger.error("Invalid AZURE_TRANSLATOR_MONTHLY_CHARACTER_LIMIT; monthly cap disabled")
        return 0


def alert_thresholds(override=None) -> list[int]:
    raw = os.environ.get("AZURE_TRANSLATOR_ALERT_THRESHOLDS", "70,85,95,100") if override is None else override
    if isinstance(raw, (list, tuple, set)):
        raw = ",".join(str(value) for value in raw)
    raw = str(raw or "")
    values = set()
    for part in raw.split(","):
        try:
            value = int(part.strip())
        except (TypeError, ValueError):
            continue
        if 1 <= value <= 100:
            values.add(value)
    return sorted(values)


def _path_for(endpoint: str, version: str, target: str, source: str | None) -> tuple[str, str, int]:
    parts = urlsplit(endpoint)
    base_path = parts.path.rstrip("/")
    if base_path.endswith("/translator/text/v3.0"):
        api_path = base_path + "/translate"
    elif base_path.endswith("/translate"):
        api_path = base_path
    elif not base_path and (parts.hostname or "").endswith(".cognitiveservices.azure.com"):
        api_path = "/translator/text/v3.0/translate"
    else:
        api_path = base_path + "/translate"
    query = {"api-version": version, "to": target}
    if source:
        query["from"] = source
    return parts.hostname or "", api_path + "?" + urlencode(query), (parts.port or 443)


def _retry_delay(value: str | None, attempt: int) -> float:
    if value:
        try:
            return min(5.0, max(0.0, float(value)))
        except ValueError:
            try:
                dt = parsedate_to_datetime(value)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return min(5.0, max(0.0, (dt - datetime.now(timezone.utc)).total_seconds()))
            except (TypeError, ValueError, OverflowError):
                pass
    return min(1.5, 0.35 * (2 ** max(0, attempt - 1)))


def _max_retries() -> int:
    try:
        return min(2, max(0, int(os.environ.get("AZURE_TRANSLATOR_MAX_RETRIES", "1"))))
    except (TypeError, ValueError):
        return 1


class AzureTranslator:
    """Azure Translator Text API v3 adapter."""

    def translate(self, text: str, target_language: str,
                  source_language: str | None = None, *,
                  config_override: dict | None = None,
                  trace_id: str | None = None,
                  before_attempt: Callable[[int], bool] | None = None,
                  after_attempt: Callable[[dict], None] | None = None) -> TranslationResult:
        text = str(text or "")
        target = str(target_language or "").strip().lower()
        source = str(source_language or "").strip().lower() or None
        if target not in _SUPPORTED_LANGUAGES:
            raise TranslationServiceError("TRANSLATION_BAD_REQUEST", "validation",
                                          "Idioma de destino não suportado.", target_language=target)
        if source and source not in _SUPPORTED_LANGUAGES:
            source = None
        if not text.strip():
            raise TranslationServiceError("TRANSLATION_BAD_REQUEST", "validation",
                                          "O texto está vazio.", source_language=source,
                                          target_language=target)
        if len(text) > 5000:
            raise TranslationServiceError("TRANSLATION_BAD_REQUEST", "validation",
                                          "O limite por tradução é de 5.000 caracteres.",
                                          source_language=source, target_language=target)
        if source == target:
            return TranslationResult(text, source, target, "none", 1.0, None, 0, 0, None, True)

        config = _config(config_override)
        host, path, port = _path_for(config["endpoint"], config["version"], target, source)
        trace_id = trace_id or str(uuid.uuid4())
        body = json.dumps([{"Text": text}], ensure_ascii=False).encode("utf-8")
        headers = {
            "Ocp-Apim-Subscription-Key": config["key"],
            "Content-Type": "application/json; charset=UTF-8",
            "Content-Length": str(len(body)),
            "X-ClientTraceId": trace_id,
        }
        if config["region"]:
            headers["Ocp-Apim-Subscription-Region"] = config["region"]

        transient_statuses = {408, 429, 500, 502, 503, 504}
        retries = _max_retries()
        attempt = 0
        while True:
            attempt += 1
            if before_attempt and not before_attempt(len(text)):
                raise TranslationServiceError("AZURE_TRANSLATOR_MONTHLY_LIMIT", "quota",
                                              "O limite mensal de tradução foi atingido.",
                                              source_language=source, target_language=target)
            started = time.monotonic()
            response_headers: dict[str, str] = {}
            status = 0
            request_id = None
            metered = None
            try:
                connection = http.client.HTTPSConnection(host, port=port, timeout=5)
                try:
                    connection.request("POST", path, body=body, headers=headers)
                    if connection.sock:
                        connection.sock.settimeout(15)
                    response = connection.getresponse()
                    status = int(response.status)
                    response_headers = {k.lower(): v for k, v in response.getheaders()}
                    request_id = response_headers.get("x-requestid") or response_headers.get("x-ms-request-id")
                    raw = response.read(1024 * 1024)
                finally:
                    connection.close()
                duration_ms = int((time.monotonic() - started) * 1000)
                try:
                    metered_raw = response_headers.get("x-metered-usage")
                    metered = int(metered_raw) if metered_raw is not None else None
                except (TypeError, ValueError):
                    metered = None
                if status in transient_statuses and attempt <= retries:
                    if after_attempt:
                        after_attempt({"success": False, "reserved_characters": len(text),
                                       "metered_characters": metered, "http_status": status,
                                       "request_id": request_id, "duration_ms": duration_ms,
                                       "source_language": source, "target_language": target,
                                       "error_code": "AZURE_TRANSLATOR_RATE_LIMITED" if status == 429 else "AZURE_TRANSLATOR_UNAVAILABLE"})
                    time.sleep(_retry_delay(response_headers.get("retry-after"), attempt))
                    continue
                if status < 200 or status >= 300:
                    code = {
                        400: "AZURE_TRANSLATOR_BAD_REQUEST",
                        401: "AZURE_TRANSLATOR_AUTH_FAILED",
                        403: "AZURE_TRANSLATOR_FORBIDDEN",
                        429: "AZURE_TRANSLATOR_RATE_LIMITED",
                    }.get(status, "AZURE_TRANSLATOR_UNAVAILABLE" if status >= 500 or status == 408 else "TRANSLATION_FAILED")
                    if after_attempt:
                        after_attempt({"success": False, "reserved_characters": len(text),
                                       "metered_characters": metered, "http_status": status,
                                       "request_id": request_id, "duration_ms": duration_ms,
                                       "source_language": source, "target_language": target,
                                       "error_code": code})
                    raise TranslationServiceError(code, "translate", "O Azure Translator recusou a requisição.",
                                                  http_status=status, request_id=request_id,
                                                  source_language=source, target_language=target)
                try:
                    payload = json.loads(raw.decode("utf-8"))
                    result = payload[0]
                    translation = result["translations"][0]["text"]
                    detected = result.get("detectedLanguage") or {}
                    detected_language = source or detected.get("language")
                    confidence = detected.get("score")
                    if not isinstance(detected_language, str) or not detected_language.strip():
                        raise ValueError("Unsupported detected language")
                    if not isinstance(translation, str) or not translation:
                        raise ValueError("Missing translated text")
                    if confidence is not None:
                        confidence = float(confidence)
                        if not math.isfinite(confidence) or not 0.0 <= confidence <= 1.0:
                            raise ValueError("Invalid language confidence")
                except (ValueError, TypeError, KeyError, IndexError, UnicodeDecodeError) as exc:
                    if after_attempt:
                        after_attempt({"success": False, "reserved_characters": len(text),
                                       "metered_characters": metered, "http_status": status,
                                       "request_id": request_id, "duration_ms": duration_ms,
                                       "source_language": source, "target_language": target,
                                       "error_code": "AZURE_TRANSLATOR_INVALID_RESPONSE"})
                    raise TranslationServiceError("AZURE_TRANSLATOR_INVALID_RESPONSE", "response",
                                                  "A resposta do tradutor não pôde ser interpretada.",
                                                  http_status=status, request_id=request_id,
                                                  source_language=source, target_language=target) from exc
                if after_attempt:
                    after_attempt({"success": True, "reserved_characters": len(text),
                                   "metered_characters": metered, "http_status": status,
                                   "request_id": request_id, "duration_ms": duration_ms,
                                   "source_language": detected_language, "target_language": target,
                                   "error_code": None})
                return TranslationResult(translation, detected_language, target, "azure",
                                         confidence, request_id, metered, duration_ms, status)
            except TranslationServiceError:
                raise
            except (socket.timeout, TimeoutError, http.client.HTTPException, OSError) as exc:
                duration_ms = int((time.monotonic() - started) * 1000)
                code = "AZURE_TRANSLATOR_TIMEOUT" if isinstance(exc, (socket.timeout, TimeoutError)) else "AZURE_TRANSLATOR_UNAVAILABLE"
                if after_attempt:
                    after_attempt({"success": False, "reserved_characters": len(text),
                                   "metered_characters": None, "http_status": status or None,
                                   "request_id": request_id, "duration_ms": duration_ms,
                                   "source_language": source, "target_language": target,
                                   "error_code": code})
                if attempt <= retries:
                    time.sleep(_retry_delay(None, attempt))
                    continue
                raise TranslationServiceError(code, "translate", "O Azure Translator está indisponível.",
                                              http_status=status or None, request_id=request_id,
                                              source_language=source, target_language=target) from exc


class TranslationService:
    """Application-facing abstraction; Azure is the currently selected provider."""
    def __init__(self, provider: AzureTranslator | None = None):
        self.provider = provider or AzureTranslator()

    def translate(self, text: str, target_language: str,
                  source_language: str | None = None, **kwargs) -> TranslationResult:
        return self.provider.translate(text, target_language, source_language, **kwargs)


_service = TranslationService()


def translate(text: str, target_language: str,
              source_language: str | None = None, **kwargs) -> TranslationResult:
    return _service.translate(text, target_language, source_language, **kwargs)
