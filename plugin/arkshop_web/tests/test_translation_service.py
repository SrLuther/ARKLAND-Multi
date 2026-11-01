from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import translation_service


class _AvailableModel:
    def __init__(self, pair, version, root: Path):
        self.from_code, self.to_code = pair
        self.package_version = version
        self.root = root

    def download(self):
        path = self.root / f"{self.from_code}-{self.to_code}-{self.package_version}.argosmodel"
        path.write_bytes(b"model")
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
