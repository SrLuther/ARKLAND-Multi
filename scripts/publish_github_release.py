"""Create a GitHub release and upload its Windows installer asset."""

from __future__ import annotations

import json
import sys
import urllib.request
from pathlib import Path


def main() -> int:
    token, version, installer_path, version_json_path = sys.argv[1:5]
    data = json.loads(Path(version_json_path).read_text(encoding="utf-8"))

    lines = ["## O que ha de novo\n"]
    lines.extend(f"- {change}" for change in data["changelog"])
    lines.append((
        "\n---\n**Instalacao silenciosa:** ARKLAND-Multi-Setup-v{version}.exe "
        "/VERYSILENT /SUPPRESSMSGBOXES /NORESTART /SP-"
    ).format(version=version))
    body = "\n".join(lines)

    headers = {
        "Authorization": "token " + token,
        "Accept": "application/vnd.github+json",
        "Content-Type": "application/json; charset=utf-8",
    }
    payload = json.dumps(
        {
            "tag_name": "v" + version,
            "name": "v" + version,
            "body": body,
            "draft": False,
            "prerelease": False,
        },
        ensure_ascii=True,
    ).encode("ascii")
    request = urllib.request.Request(
        "https://api.github.com/repos/SrLuther/ARKLAND-Multi/releases",
        data=payload,
        headers=headers,
    )
    with urllib.request.urlopen(request) as response:
        release = json.loads(response.read())

    upload_url = release["upload_url"].split("{")[0]
    upload_url += "?name=ARKLAND-Multi-Setup-v" + version + ".exe"
    asset_headers = {
        "Authorization": "token " + token,
        "Accept": "application/vnd.github+json",
        "Content-Type": "application/octet-stream",
    }
    asset_request = urllib.request.Request(
        upload_url,
        data=Path(installer_path).read_bytes(),
        headers=asset_headers,
    )
    with urllib.request.urlopen(asset_request) as response:
        asset = json.loads(response.read())

    print(release["html_url"])
    print(asset["browser_download_url"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
