import json
from pathlib import Path

p = Path(__file__).resolve().parents[1] / "plugin/CustomShop/configs/config.json"
data = json.loads(p.read_text(encoding="utf-8"))
items = data.get("Items", {})
dinos = []
for k, v in items.items():
    if str(v.get("Type", "")).lower() != "dino":
        continue
    d = (v.get("Dinos") or [{}])[0]
    dinos.append({
        "id": k,
        "name": v.get("Name") or v.get("Description") or k,
        "price": int(v.get("Price", 0)),
        "level": int(d.get("Level", 1)),
        "blueprint": d.get("Blueprint", ""),
    })
dinos.sort(key=lambda x: -x["price"])
print(len(dinos))
for d in dinos:
    print(d["price"], d["name"], d["id"])
