"""Free offline ticket translation backed by locally installed Argos models."""
from __future__ import annotations

import os
import json
import zipfile
import logging
import urllib.request
import tempfile
from urllib.parse import urlparse
from pathlib import Path
from threading import Lock
from datetime import datetime, timedelta, timezone

_MODEL_PAIRS = (("en", "pb"), ("pb", "en"), ("en", "es"), ("es", "en"))
_MODEL_LOCK = Lock()
_INDEX_MIRRORS = (
    "https://cdn.jsdelivr.net/gh/argosopentech/argospm-index@main/index.json",
)
_DIRECT_MODEL_FILES = {
    ("en", "pb"): ("translate-en_pb-1_9.argosmodel", "1.9"),
    ("pb", "en"): ("translate-pb_en-1_9.argosmodel", "1.9"),
    ("en", "es"): ("translate-en_es-1_0.argosmodel", "1.0"),
    ("es", "en"): ("translate-es_en-1_9.argosmodel", "1.9"),
}


class _DirectModelCandidate:
    """Known official Argos packages used when its index is unavailable."""

    def __init__(self, pair, filename, version):
        self.from_code, self.to_code = pair
        self.package_version = version
        self.links = [f"https://data.argosopentech.com/argospm/v1/{filename}"]

    def download(self):
        request = urllib.request.Request(
            self.links[0], headers={"User-Agent": "ARKLAND-WebStore/1.11.15"}
        )
        with urllib.request.urlopen(request, timeout=90) as response:
            payload = response.read()
        handle = tempfile.NamedTemporaryFile(
            prefix="arkland-translate-", suffix=".argosmodel", delete=False
        )
        try:
            handle.write(payload)
            return Path(handle.name)
        finally:
            handle.close()


def _direct_model_candidates():
    return [
        _DirectModelCandidate(pair, filename, version)
        for pair, (filename, version) in _DIRECT_MODEL_FILES.items()
    ]


def _available_packages(argos_package):
    """Refresh Argos' package index, with a CDN mirror and cached fallback."""
    settings = getattr(argos_package, "settings", None)
    if settings is None:
        try:
            argos_package.update_package_index()
            return argos_package.get_available_packages()
        except Exception as exc:
            logging.getLogger(__name__).warning(
                "Argos index refresh failed (%s); using official package links",
                type(exc).__name__,
            )
            return _direct_model_candidates()
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
            # Argos can temporarily remove a package pair from its catalog.
            # Keep the usable catalog and let refresh_translation_models retain
            # already-installed pairs while reporting only missing packages.
            if not indexed_pairs.intersection(_MODEL_PAIRS):
                raise ValueError("índice não contém modelos suportados")
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
            present = {(item.from_code, item.to_code) for item in cached}
            cached.extend(item for item in _direct_model_candidates() if (item.from_code, item.to_code) not in present)
            logging.getLogger(__name__).warning(
                "Argos index unavailable; using cache plus official package links (%s)",
                "; ".join(failures),
            )
            return cached
    except Exception as exc:
        failures.append(f"cache: {type(exc).__name__}")
    logging.getLogger(__name__).warning(
        "Argos index and cache unavailable; using fixed official package links (%s)",
        "; ".join(failures),
    )
    return _direct_model_candidates()


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

    # Allow production administrators to drop official .argosmodel archives
    # into the persistent package directory when browser upload is unavailable.
    for package_path in model_dir.glob("*.argosmodel"):
        try:
            with zipfile.ZipFile(package_path) as archive:
                metadata_item = None
                uncompressed_size = 0
                for item in archive.infolist():
                    member = Path(item.filename.replace("\\", "/"))
                    if member.is_absolute() or ".." in member.parts:
                        raise ValueError("caminho inválido no pacote")
                    uncompressed_size += item.file_size
                    if uncompressed_size > 500 * 1024 * 1024:
                        raise ValueError("pacote excede o limite após extração")
                    if item.filename.endswith("metadata.json"):
                        metadata_item = item
                if metadata_item is None:
                    raise ValueError("metadata.json ausente")
                metadata = json.loads(archive.read(metadata_item).decode("utf-8"))
            pair = (metadata.get("from_code"), metadata.get("to_code"))
            if pair not in _MODEL_PAIRS:
                raise ValueError(f"par de idiomas não suportado: {pair}")
            argos_package.install_from_path(package_path)
            package_path.unlink()
            logging.getLogger(__name__).info(
                "Installed manually staged Argos model %s (%s → %s)",
                package_path.name, pair[0], pair[1],
            )
        except Exception as exc:
            logging.getLogger(__name__).warning(
                "Could not install staged Argos model %s (%s)",
                package_path.name, type(exc).__name__,
            )

    DetectorFactory.seed = 0
    return argos_package, argos_translate, detect


def _model_directory() -> Path:
    from src.shop_integration import webstore_data_dir

    return Path(webstore_data_dir()) / "translation" / "argos-packages"


def install_translation_model(path: str | Path) -> dict:
    """Validate and install one manually uploaded Argos model package."""
    package_path = Path(path)
    if package_path.suffix.lower() != ".argosmodel" or package_path.stat().st_size > 100 * 1024 * 1024:
        raise ValueError("Envie um arquivo .argosmodel de até 100 MB.")
    with zipfile.ZipFile(package_path) as archive:
        total_uncompressed = 0
        metadata_item = None
        for item in archive.infolist():
            member = Path(item.filename.replace("\\", "/"))
            if member.is_absolute() or ".." in member.parts:
                raise ValueError("O pacote contém um caminho inválido.")
            total_uncompressed += item.file_size
            if total_uncompressed > 500 * 1024 * 1024:
                raise ValueError("O pacote excede o tamanho máximo permitido após extração.")
            if item.filename.endswith("metadata.json"):
                metadata_item = item
        if metadata_item is None:
            raise ValueError("O pacote não contém metadata.json.")
        metadata = json.loads(archive.read(metadata_item).decode("utf-8"))
    pair = (metadata.get("from_code"), metadata.get("to_code"))
    if pair not in _MODEL_PAIRS:
        raise ValueError("Este pacote não corresponde a um dos idiomas suportados.")
    with _MODEL_LOCK:
        argos_package, _argos_translate, _detect = _runtime_modules()
        argos_package.install_from_path(package_path)
    return {"from": pair[0], "to": pair[1]}


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
        present_pairs = {(item.from_code, item.to_code) for item in available}
        available.extend(
            item for item in _direct_model_candidates()
            if (item.from_code, item.to_code) not in present_pairs
        )
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
            if isinstance(candidate, _DirectModelCandidate) and newest is not None:
                should_install = should_install and parse_version(candidate.package_version) >= parse_version(newest.package_version)
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
