from __future__ import annotations

from pathlib import Path

import app as web_app


def test_public_version_endpoint_returns_release_metadata_without_cache():
    response = web_app.app.test_client().get("/api/version")

    assert response.status_code == 200
    release = response.get_json()
    expected = web_app._get_project_release()
    assert release["version"] == expected["version"]
    assert release["date"] == expected["date"]
    assert response.headers["Cache-Control"] == "no-store, max-age=0"


def test_statusbar_fetches_and_displays_the_site_release_version():
    html = (Path(__file__).resolve().parents[1] / "static" / "index.html").read_text(
        encoding="utf-8"
    )

    assert 'id="sb-version"' in html
    assert 'fetchJson("/api/version"' in html
    assert 'versionEl.textContent = version ? `WebStore v${version}`' in html
    assert "WebStore versão indisponível" in html
