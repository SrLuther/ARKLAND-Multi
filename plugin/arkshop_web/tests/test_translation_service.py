from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import json
import zipfile

import translation_service


class _AvailableModel:
    def __init__(self, pair, version, root: Path):
        self.from_code, self.to_code = pair
        self.package_version = version
        self.root = root

    def download(self):
        path = self.root / f"{self.from_code}-{self.to_code}-{self.package_version}.argosmodel"
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr(
                "metadata.json",
                json.dumps({
                    "from_code": self.from_code,
                    "to_code": self.to_code,
                    "package_version": self.package_version,
                }),
            )
        return path


class _InstalledModel:
    def __init__(self, pair, version, path):
        self.from_code, self.to_code = pair
        self.package_version = version
        self.package_path = Path(path)


class _FakeArgosPackage:
    def __init__(self, pairs, root: Path):
        self.available = [_AvailableModel(pair, "1.0", root) for pair in pairs]
        self.installed = []
        self.index_updates = 0

    def get_installed_packages(self):
        return list(self.installed)

    def update_package_index(self):
        self.index_updates += 1

    def get_available_packages(self):
        return self.available

    def install_from_path(self, archive):
        source, target, version = Path(archive).stem.split("-")
        package_dir = Path(archive).with_suffix("")
        self.installed = [pkg for pkg in self.installed if pkg.package_path != package_dir]
        self.installed.append(_InstalledModel((source, target), version, package_dir))

    def uninstall(self, package):
        self.installed.remove(package)


def test_translation_models_install_automatically_update_weekly_and_redownload(tmp_path, monkeypatch):
    fake = _FakeArgosPackage(translation_service._MODEL_PAIRS, tmp_path)
    monkeypatch.setattr(
        translation_service,
        "_runtime_modules",
        lambda: (fake, SimpleNamespace(), lambda _text: "pt"),
    )
    monkeypatch.setattr(translation_service, "_model_directory", lambda: tmp_path / "models")

    initial = translation_service.refresh_translation_models()
    assert initial == {"installed": 4, "updated": 0, "checked": True}
    assert len(fake.installed) == 4
    assert fake.index_updates == 1

    cached = translation_service.refresh_translation_models()
    assert cached == {"installed": 4, "updated": 0, "checked": False}
    assert fake.index_updates == 1

    fake.available = [_AvailableModel(pair, "2.0", tmp_path) for pair in translation_service._MODEL_PAIRS]
    updated = translation_service.refresh_translation_models(check_now=True)
    assert updated == {"installed": 4, "updated": 4, "checked": True}
    assert len(fake.installed) == 4
    assert {package.package_version for package in fake.installed} == {"2.0"}

    redownloaded = translation_service.refresh_translation_models(force_redownload=True)
    assert redownloaded["installed"] == 4
    assert len(fake.installed) == 4
    assert fake.index_updates == 3


def test_installed_models_remain_usable_when_index_is_unavailable(tmp_path, monkeypatch):
    fake = _FakeArgosPackage(translation_service._MODEL_PAIRS, tmp_path)
    fake.installed = [
        _InstalledModel(pair, "1.0", tmp_path / f"{pair[0]}-{pair[1]}-1.0")
        for pair in translation_service._MODEL_PAIRS
    ]
    monkeypatch.setattr(
        translation_service,
        "_runtime_modules",
        lambda: (fake, SimpleNamespace(), lambda _text: "pt"),
    )
    monkeypatch.setattr(translation_service, "_model_directory", lambda: tmp_path / "models")
    monkeypatch.setattr(translation_service, "_available_packages", lambda _package: None)

    result = translation_service.refresh_translation_models(check_now=True)

    assert result == {
        "installed": 4,
        "updated": 0,
        "checked": False,
        "warning_code": "ARGOS_INDEX_UNAVAILABLE",
    }
    assert len(fake.installed) == 4


def test_staged_packages_install_only_missing_pairs_idempotently(tmp_path):
    installed_pair, missing_pair = translation_service._MODEL_PAIRS[:2]
    already_installed = _InstalledModel(installed_pair, "1.0", tmp_path / "installed")

    class PackageManager:
        def __init__(self):
            self.installed = [already_installed]
            self.install_calls = []

        def get_installed_packages(self):
            return list(self.installed)

        def install_from_path(self, path):
            with zipfile.ZipFile(path) as archive:
                metadata = json.loads(archive.read("metadata.json"))
            pair = (metadata["from_code"], metadata["to_code"])
            self.install_calls.append(pair)
            self.installed.append(_InstalledModel(pair, "1.0", tmp_path / "newly-installed"))

    manager = PackageManager()
    paths = []
    for pair in (installed_pair, missing_pair):
        archive_path = tmp_path / f"{pair[0]}_{pair[1]}.argosmodel"
        with zipfile.ZipFile(archive_path, "w") as archive:
            archive.writestr("metadata.json", json.dumps({"from_code": pair[0], "to_code": pair[1]}))
        paths.append(archive_path)

    translation_service._install_staged_models(manager, tmp_path)

    assert manager.install_calls == [missing_pair]
    assert paths[0].exists()  # Installed models are not reinstalled or deleted.
    assert not paths[1].exists()  # Successfully installed staged archives are consumed.
