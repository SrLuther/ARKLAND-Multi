"""Exploração dos endpoints Beacon: configOptions, blueprints, engrams, lootDrops."""
import json
import requests

with open("beacon_token.json") as f:
    token = json.load(f)["access_token"]

headers: dict[str, str | bytes] = {"Authorization": f"Bearer {token}"}
BASE = "https://api.usebeacon.app"


def fetch(path, params=None):
    r = requests.get(f"{BASE}{path}", headers=headers, params=params, timeout=20)
    return r.json()


# configOptions
print("=== configOptions ===")
body = fetch("/v4/ark/configOptions", {"pageSize": 2})
print(f"Total: {body.get('totalResults')}")
for item in body.get("results", [])[:2]:
    print(json.dumps(item, indent=2, ensure_ascii=False))

# blueprints
print("\n=== blueprints ===")
body = fetch("/v4/ark/blueprints", {"pageSize": 2})
print(f"Total: {body.get('totalResults')}")
for item in body.get("results", [])[:1]:
    print(json.dumps(item, indent=2, ensure_ascii=False))

# engrams
print("\n=== engrams ===")
body = fetch("/v4/ark/engrams", {"pageSize": 2})
print(f"Total: {body.get('totalResults')}")
for item in body.get("results", [])[:1]:
    print(json.dumps(item, indent=2, ensure_ascii=False))

# lootDrops
print("\n=== lootDrops ===")
body = fetch("/v4/ark/lootDrops", {"pageSize": 2})
print(f"Total: {body.get('totalResults')}")
for item in body.get("results", [])[:1]:
    print(json.dumps(item, indent=2, ensure_ascii=False))

# spawnPoints
print("\n=== spawnPoints ===")
body = fetch("/v4/ark/spawnPoints", {"pageSize": 2})
print(f"Total: {body.get('totalResults')}")
for item in body.get("results", [])[:1]:
    print(json.dumps(item, indent=2, ensure_ascii=False))
