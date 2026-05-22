from __future__ import annotations
import json
import threading
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from ..app import ARKServerManagerApp


def fetch_mod_names_async(app: "ARKServerManagerApp", server_id: str, mod_ids: list) -> None:
    """Busca nomes dos mods via Steam API em background e atualiza a lista."""
    if not hasattr(app, "_fetching_mod_names"):
        app._fetching_mod_names: set = set()
    to_fetch = [mid for mid in mod_ids if mid not in app._fetching_mod_names]
    if not to_fetch:
        return
    app._fetching_mod_names.update(to_fetch)

    def _worker() -> None:
        names: dict = {}
        try:
            params: dict = {"itemcount": str(len(to_fetch))}
            for i, mid in enumerate(to_fetch):
                params[f"publishedfileids[{i}]"] = mid
            data = urllib.parse.urlencode(params).encode()
            req = urllib.request.Request(
                "https://api.steampowered.com"
                "/ISteamRemoteStorage/GetPublishedFileDetails/v1/",
                data=data,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                result = json.loads(resp.read().decode())
            for f in result.get("response", {}).get("publishedfiledetails", []):
                if f.get("result") == 1:
                    mid = str(f.get("publishedfileid", ""))
                    title = f.get("title", "").strip()
                    if mid and title:
                        names[mid] = title
        except Exception:
            pass
        finally:
            app._fetching_mod_names -= set(to_fetch)

        def _apply() -> None:
            srv = app.config_manager.get_server(server_id)
            if srv and names:
                srv.mod_names.update(names)
                app.config_manager.update_server(srv)
                app._refresh_mods_list(server_id)
        app.after(0, _apply)

    threading.Thread(target=_worker, daemon=True, name="ModNameFetch").start()

