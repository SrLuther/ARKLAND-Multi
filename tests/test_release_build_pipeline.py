from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_every_pyinstaller_build_cleans_cached_analysis_before_packaging():
    build_script = (ROOT / "build.bat").read_text(encoding="utf-8")
    invocations = [line for line in build_script.splitlines() if "-m PyInstaller" in line]
    assert len(invocations) == 3
    assert all("--clean" in line for line in invocations)


def test_webstore_packages_pillow_required_by_lumo_asset_routes():
    spec = (ROOT / "ARKLAND-WebStore.spec").read_text(encoding="utf-8")
    requirements = (ROOT / "plugin" / "arkshop_web" / "requirements.txt").read_text(encoding="utf-8")
    assert "collect_all('PIL')" in spec
    assert "pil_binaries" in spec and "pil_datas" in spec and "pil_hiddenimports" in spec
    assert "'PIL'" not in spec.split("excludes=[", 1)[1].split("],", 1)[0]
    assert "Pillow" in requirements


def test_release_version_matches_update_manifest():
    import json
    import re

    app_version = re.search(
        r'^APP_VERSION:\s*str\s*=\s*"([^"]+)"$',
        (ROOT / "src" / "version.py").read_text(encoding="utf-8"),
        re.MULTILINE,
    )
    setup_version = re.search(
        r'^#define ReleaseVersion "([^"]+)"$',
        (ROOT / "setup.iss").read_text(encoding="utf-8"),
        re.MULTILINE,
    )
    manifest = json.loads((ROOT / "version.json").read_text(encoding="utf-8"))
    assert app_version is not None and setup_version is not None
    assert app_version.group(1) == manifest["version"] == setup_version.group(1)
