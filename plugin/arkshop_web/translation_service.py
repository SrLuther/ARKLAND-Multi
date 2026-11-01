"""Free offline ticket translation backed by locally installed Argos models."""
from __future__ import annotations

import os
import json
import logging
import urllib.request
from urllib.parse import urlparse
from pathlib import Path
from threading import Lock
from datetime import datetime, timedelta, timezone

_MODEL_PAIRS = (("en", "pb"), ("pb", "en"), ("en", "es"), ("es", "en"))
_MODEL_LOCK = Lock()
_INDEX_MIRRORS = (
    "https://cdn.jsdelivr.net/gh/argosopentech/argospm-index@main/index.json",
)


def _available_packages(argos_package):
    """Refresh Argos' package index, with a CDN mirror and cached fallback."""
    settings = getattr(argos_package, "settings", None)
    if settings is None:
        argos_package.update_package_index()
        return argos_package.get_available_packages()
    index_path = Path(settings.local_package_index)
    urls = [str(settings.remote_package_index), *_INDEX_MIRRORS]
    failures = []
    for url in dict.fromkeys(urls):
        try:
            request = urllib.request.Request(
                url, headers={"User-Agent": "ARKLAND-WebStore/1.11.14"}
            )
            with urllib.request.urlopen(request, timeout=25) as response:
                payload = response.read()
            data = json.loads(payload)
            if not isinstance(data, list) or not data:
                raise ValueError("índice vazio ou inválido")
            indexed_pairs = {
                (item.get("from_code"), item.get("to_code"))
                for item in data
                if isinstance(item, dict)
            }
            if not set(_MODEL_PAIRS).issubset(indexed_pairs):
                raise ValueError("índice não contém todos os modelos necessários")
            index_path.parent.mkdir(parents=True, exist_ok=True)
            temporary = index_path.with_suffix(index_path.suffix + ".tmp")
            temporary.write_bytes(payload)
            temporary.replace(index_path)
            return argos_package.get_available_packages()
        except Exception as exc:
            failures.append(f"{urlparse(url).hostname or 'index'}: {type(exc).__name__}")

    try:
        cached = argos_package.get_available_packages()
        if cached:
            logging.getLogger(__name__).warning(
                "Índice Argos indisponível nas fontes remotas; usando índice em cache (%s)",
                "; ".join(failures),
            )
            return cached
    except Exception as exc:
        failures.append(f"cache: {type(exc).__name__}")
    raise RuntimeError(
        "Não foi possível obter o índice dos modelos Argos. " + "; ".join(failures)
    )


def _runtime_modules():
    """Set the persistent model directory before Argos reads its settings."""
    from src.shop_integration import webstore_data_dir

    model_dir = Path(webstore_data_dir()) / "translation" / "argos-packages"
    model_dir.mkdir(parents=True, exist_ok=True)
    # Use Argos' lightweight MiniSBD path; Stanza would pull a large optional
    # Torch/SpaCy runtime that the Web Store does not need.
    os.environ.setdefault("ARGOS_STANZA_AVAILABLE", "false")
    os.environ.setdefault("ARGOS_PACKAGES_DIR", str(model_dir))
    os.environ.setdefault("ARGOS_PACKAGE_DIR", str(model_dir))

    import argostranslate.package as argos_package
    import argostranslate.translate as argos_translate
    from langdetect import DetectorFactory, detect

    DetectorFactory.seed = 0
    return argos_package, argos_translate, detect


def _model_directory() -> Path:
    from src.shop_integration import webstore_data_dir

    return Path(webstore_data_dir()) / "translation" / "argos-packages"


def _installed_by_pair(argos_package):
    installed = {}
    for package in argos_package.get_installed_packages():
        if (package.from_code, package.to_code) in _MODEL_PAIRS:
            installed.setdefault((package.from_code, package.to_code), []).append(package)
    return installed


def _download_model(candidate) -> Path:
    """Download a model, falling back to Argos' public package mirror.

    Some hosting networks reject argos-net.com while allowing the official
    data.argosopentech.com mirror. Argos' downloader does not retry alternate
    hosts after an HTTP error, so retry the same package filename on that mirror.
    """
    try:
        return candidate.download()
    except Exception:
        original_links = candidate.links
        model_name = Path(urlparse(original_links[0]).path).name if original_links else ""
        if not model_name.endswith(".argosmodel"):
            raise
        candidate.links = [f"https://data.argosopentech.com/argospm/v1/{model_name}"]
        try:
            return candidate.download()
        finally:
            candidate.links = original_links


def refresh_translation_models(*, force_redownload: bool = False, check_now: bool = False) -> dict:
    """Check the official model index and install missing/newer models locally."""
    with _MODEL_LOCK:
        argos_package, _argos_translate, _detect = _runtime_modules()
        installed = _installed_by_pair(argos_package)
        model_dir = _model_directory()
        checked_file = model_dir.parent / "last_checked.json"
        try:
            last_checked = datetime.fromisoformat(
                json.loads(checked_file.read_text(encoding="utf-8")).get("checked_at", "")
            )
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            last_checked = None

        missing = [pair for pair in _MODEL_PAIRS if not installed.get(pair)]
        due = last_checked is None or datetime.now(timezone.utc) - last_checked >= timedelta(days=7)
        if not force_redownload and not check_now and not missing and not due:
            return {"installed": len(_MODEL_PAIRS), "updated": 0, "checked": False}

        available = _available_packages(argos_package)
        installed_count = 0
        updated_count = 0
        from packaging.version import parse as parse_version

        for pair in _MODEL_PAIRS:
            current = installed.get(pair, [])
            candidate = next(
                (item for item in available if (item.from_code, item.to_code) == pair),
                None,
            )
            if candidate is None:
                if current:
                    installed_count += 1
                    continue
                raise RuntimeError(f"Modelo gratuito indisponível: {pair[0]} → {pair[1]}")

            newest = max(current, key=lambda item: parse_version(item.package_version), default=None)
            should_install = force_redownload or newest is None or parse_version(candidate.package_version) > parse_version(newest.package_version)
            if not should_install:
                installed_count += 1
                continue

            downloaded = _download_model(candidate)
            argos_package.install_from_path(downloaded)
            Path(downloaded).unlink(missing_ok=True)
            refreshed = _installed_by_pair(argos_package).get(pair, [])
            newest_installed = max(
                refreshed,
                key=lambda item: parse_version(item.package_version),
                default=None,
            )
            for old in current:
                if newest_installed and old.package_path != newest_installed.package_path:
                    argos_package.uninstall(old)
            installed_count += 1
            if newest is not None:
                updated_count += 1

        checked_file.parent.mkdir(parents=True, exist_ok=True)
        checked_file.write_text(
            json.dumps({"checked_at": datetime.now(timezone.utc).isoformat()}, ensure_ascii=False),
            encoding="utf-8",
        )
        return {"installed": installed_count, "updated": updated_count, "checked": True}


def translate_offline(text: str, target: str) -> str:
    """Translate among Portuguese, English and Spanish without sending text out."""
    if target not in {"pt", "en", "es"}:
        raise ValueError("Idioma de destino inválido")

    argos_package, argos_translate, detect = _runtime_modules()
    try:
        refresh_translation_models()
    except Exception:
        # Once installed, keep translation available offline if the update source is down.
        if len(_installed_by_pair(argos_package)) < len(_MODEL_PAIRS):
            raise
        source = detect(text)
    else:
        source = detect(text)
    if source not in {"pt", "en", "es"}:
        raise ValueError("O idioma de origem não é compatível")
    argos_source = "pb" if source == "pt" else source
    argos_target = "pb" if target == "pt" else target
    if argos_source == argos_target:
        return text
    return argos_translate.translate(text, argos_source, argos_target)
