from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_every_pyinstaller_build_cleans_cached_analysis_before_packaging():
    build_script = (ROOT / "build.bat").read_text(encoding="utf-8")
    invocations = [line for line in build_script.splitlines() if "-m PyInstaller" in line]
    assert len(invocations) == 3
    assert all("--clean" in line for line in invocations)


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
