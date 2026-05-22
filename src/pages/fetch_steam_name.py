from __future__ import annotations
import threading
import re


def fetch_steam_name(steam_id: str, callback) -> None:
    """Busca o nome do perfil Steam em thread separada e chama callback(name_or_none)."""
    def _worker():
        try:
            url = f"https://steamcommunity.com/profiles/{steam_id}?xml=1"
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=8) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
            # Extrai <steamID><![CDATA[Nome]]></steamID>
            m = re.search(r"<steamID><!\[CDATA\[(.*?)\]\]></steamID>", raw)
            name = m.group(1).strip() if m else None
            callback(name)
        except Exception:
            callback(None)
    threading.Thread(target=_worker, daemon=True).start()

