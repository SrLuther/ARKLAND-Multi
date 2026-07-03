from pathlib import Path
import re
p = Path("src/version.py")
text = p.read_text(encoding="utf-8")
new_block = """    {
        \"version\": \"1.9.181\",
        \"date\": \"2026-07-02\",
        \"changes\": [
            \"Fix (Web Store / Mercado P2P): cryopod morta (DEAD/Carga 0s) \u2014 StripCryopodTimer em /confirmar, PrepareMarketCryopodForDelivery em /mercado, valida\u00e7\u00e3o e libera\u00e7\u00e3o do claim em falha (ShopCryoReader.cpp, ShopMarket.cpp).\",
            \"Fix (Loja / Cat\u00e1logo): corre\u00e7\u00f5es de blueprint path \u2014 Hide\u2192Leather, armadura Tek pasta TEK, estruturas tek em tek/; Nameless Venom; _KNOWN_BLUEPRINT_FIXES ampliado.\",
        ],
    },
    {
        \"version\": \"1.9.180\""""
text = re.sub(
    r'    \{\s*"version": "1\.9\.181",.*?"version": "1\.9\.180"',
    new_block,
    text,
    count=1,
    flags=re.DOTALL,
)
p.write_text(text, encoding="utf-8", newline="\n")
print("patched")
