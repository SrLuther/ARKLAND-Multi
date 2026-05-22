from __future__ import annotations


def sanitize_steam_name(name: str) -> str:
    """Limpa nomes corrompidos com fragmentos XML/CDATA deixados por versões antigas."""
    if not name:
        return ""
    # Tenta extrair o conteúdo real de um fragmento CDATA
    if "CDATA[" in name:
        try:
            extracted = name.split("CDATA[")[-1].split("]]>")[0].strip()
            if extracted:
                return extracted
        except Exception:
            pass
    # Descarta qualquer string que ainda contenha marcadores XML
    if "<" in name or ">" in name:
        return ""
    return name

