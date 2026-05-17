"""Exploração detalhada dos endpoints Beacon para planejar integração."""
import json
import requests

with open("beacon_token.json") as f:
    token = json.load(f)["access_token"]

headers: dict[str, str | bytes] = {"Authorization": f"Bearer {token}"}
BASE = "https://api.usebeacon.app"


def fetch_all(path, extra_params=None):
    params = {"pageSize": 200, "page": 1}
    if extra_params:
        params.update(extra_params)
    results = []
    while True:
        r = requests.get(f"{BASE}{path}", headers=headers, params=params, timeout=20)
        d = r.json()
        results.extend(d["results"])
        if params["page"] >= d["pages"]:
            break
        params["page"] += 1
    return results


# === configOptions ===
all_opts = fetch_all("/v4/ark/configOptions")
print(f"Total configOptions carregados: {len(all_opts)}")
files = {}
for item in all_opts:
    files[item["file"]] = files.get(item["file"], 0) + 1
print("Distribuicao por arquivo:", json.dumps(files, indent=2))

gus = [x for x in all_opts if x["file"] == "GameUserSettings.ini"]
game = [x for x in all_opts if x["file"] == "Game.ini"]

print(f"\nGameUserSettings.ini ({len(gus)} opcoes) - headers:")
gus_headers = {}
for x in gus:
    h = x["header"]
    gus_headers[h] = gus_headers.get(h, 0) + 1
print(json.dumps(gus_headers, indent=2))

print(f"\nGame.ini ({len(game)} opcoes) - primeiros 15:")
for x in game[:15]:
    print(f"  [{x['header']}] {x['key']} ({x['valueType']}) -> {x['label']}")
    if x.get("description"):
        print(f"    Desc: {x['description'][:80]}")
    if x.get("constraints"):
        print(f"    Constraints: {x['constraints']}")

# === lootDrops ===
print("\n\n=== lootDrops ===")
r = requests.get(f"{BASE}/v4/ark/lootDrops", headers=headers,
                 params={"pageSize": 1, "contentPackId": "30bbab29-44b2-4f4b-a373-6d4740d9d3b5"})
d = r.json()
print(f"Total lootDrops (Ark Prime): {d['totalResults']}")
if d["results"]:
    print(json.dumps(d["results"][0], indent=2, ensure_ascii=False)[:1000])

# === gameVariables ===
print("\n\n=== gameVariables ===")
r = requests.get(f"{BASE}/v4/ark/gameVariables", headers=headers,
                 params={"pageSize": 3, "contentPackId": "30bbab29-44b2-4f4b-a373-6d4740d9d3b5"})
d = r.json()
print(f"Total gameVariables (Ark Prime): {d['totalResults']}")
for item in d.get("results", []):
    print(json.dumps(item, indent=2, ensure_ascii=False)[:600])

# === sentinel services ===
print("\n\n=== sentinel/services ===")
r = requests.get(f"{BASE}/v4/sentinel/services", headers=headers, params={"pageSize": 5})
print(f"Status: {r.status_code}")
print(r.text[:500])
