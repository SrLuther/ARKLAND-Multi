"""
beacon_sync.py
Busca dados autoritativos de breeding da API Beacon (DevKit-sourced) e
imprime uma nova BREEDING_DATA pronta para colar em src/breeding_calculator.py.

Uso:
    python beacon_sync.py

Requer: requests  (pip install requests)
"""

import base64
import hashlib
import json
import os
import secrets
import time
import webbrowser

import requests

# ── Configuração ───────────────────────────────────────────────────────────────
CLIENT_ID   = "0e710efc-3fa1-4751-b668-aa046579365d"
API_BASE    = "https://api.usebeacon.app"
TOKEN_FILE  = "beacon_token.json"   # cache local do token

# ── PKCE helpers ───────────────────────────────────────────────────────────────

def _pkce_pair() -> tuple[str, str]:
    """Retorna (code_verifier, code_challenge)."""
    verifier  = secrets.token_urlsafe(64)
    digest    = hashlib.sha256(verifier.encode()).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
    return verifier, challenge


# ── Auth: Device Login flow ────────────────────────────────────────────────────

def _load_cached_token() -> dict | None:
    if not os.path.exists(TOKEN_FILE):
        return None
    with open(TOKEN_FILE, encoding="utf-8") as f:
        data = json.load(f)
    # verifica se ainda não expirou (com margem de 60 s)
    if data.get("expires_at", 0) > time.time() + 60:
        return data
    return None


def _save_token(token_resp: dict) -> dict:
    token_resp["expires_at"] = time.time() + token_resp.get("expires_in", 3600)
    with open(TOKEN_FILE, "w", encoding="utf-8") as f:
        json.dump(token_resp, f, indent=2)
    return token_resp


def authenticate() -> str:
    """Retorna um access_token válido (usa cache se disponível)."""
    cached = _load_cached_token()
    if cached:
        print("✓ Token em cache ainda válido.")
        return cached["access_token"]

    # 1. Iniciar Device Flow
    verifier, challenge = _pkce_pair()
    r = requests.post(f"{API_BASE}/v4/device", json={
        "client_id":              CLIENT_ID,
        "scope":                  "common",
        "code_challenge":         challenge,
        "code_challenge_method":  "S256",
    }, timeout=15)
    r.raise_for_status()
    device = r.json()

    user_code    = device["user_code"]
    verify_url   = device.get("verification_uri_complete") or device["verification_uri"]
    device_code  = device["device_code"]
    interval     = device.get("interval", 5)
    expires_in   = device.get("expires_in", 300)

    print(f"\n{'='*60}")
    print(f"  Abra no navegador: {verify_url}")
    print(f"  Código:            {user_code}")
    print(f"{'='*60}\n")
    try:
        webbrowser.open(verify_url)
    except Exception:
        pass

    # 2. Polling até autorizar
    deadline = time.time() + expires_in
    while time.time() < deadline:
        time.sleep(interval)
        poll = requests.post(f"{API_BASE}/v4/login", json={
            "grant_type":    "urn:ietf:params:oauth:grant-type:device_code",
            "device_code":   device_code,
            "client_id":     CLIENT_ID,
            "code_verifier": verifier,
        }, timeout=15)

        if poll.status_code in (200, 201):
            token_data = _save_token(poll.json())
            print("✓ Autenticado com sucesso!")
            return token_data["access_token"]

        body = poll.json() if poll.headers.get("content-type", "").startswith("application/json") else {}
        err  = body.get("error", "")

        if err == "authorization_pending":
            print("  Aguardando aprovação...", end="\r")
            continue
        if err == "slow_down":
            interval += 5
            continue
        if err in ("access_denied", "expired_token"):
            raise RuntimeError(f"Login recusado ou expirado: {err}")
        poll.raise_for_status()

    raise TimeoutError("Tempo limite de autenticação atingido.")


# ID do content pack base game ARK: Survival Evolved
_ARK_PRIME_PACK_ID = "30bbab29-44b2-4f4b-a373-6d4740d9d3b5"

# Prefixos de variantes que devem ser ignoradas (manter apenas base vanilla)
_VARIANT_PREFIXES = (
    "Aberrant ", "Corrupted ", "Tek ", "Alpha ", "Venom-",
    "Spectral ", "Spirit ", "Toxic ", "Zombie ", "Skeletal ",
    "Bionic ", "Resurrected ", "Primal ",
)


def fetch_creatures(token: str) -> list[dict]:
    """Busca criaturas Ark Prime (base game) da API Beacon."""
    headers: dict[str, str | bytes] = {"Authorization": f"Bearer {token}"}
    creatures = []
    page      = 1

    while True:
        r = requests.get(f"{API_BASE}/v4/ark/creatures", headers=headers,
                         params={"pageSize": 250, "page": page,
                                 "contentPackId": _ARK_PRIME_PACK_ID},
                         timeout=30)
        r.raise_for_status()
        data = r.json()

        if isinstance(data, list):
            batch = data
        else:
            batch = data.get("results") or data.get("data") or []

        if not batch:
            break
        creatures.extend(batch)

        # paginação: usa totalResults se disponível
        total_pages = data.get("pages") if isinstance(data, dict) else None
        if total_pages is not None and page >= total_pages:
            break
        if len(batch) < 250:
            break
        page += 1

    return creatures


def filter_vanilla(creatures: list[dict]) -> list[dict]:
    """Mantém apenas criaturas base vanilla (sem variantes) e deduplica por nome."""
    seen: set[str] = set()
    result = []
    for c in creatures:
        label = c.get("label") or ""
        # ignora variantes
        if any(label.startswith(p) for p in _VARIANT_PREFIXES):
            continue
        # ignora nomes já vistos (deduplicação)
        key = label.lower().strip()
        if key in seen:
            continue
        seen.add(key)
        result.append(c)
    return result


# ── Inspecção dos campos ───────────────────────────────────────────────────────

def inspect_sample(creatures: list[dict]) -> None:
    """Imprime as chaves do primeiro item para identificar os nomes dos campos."""
    if not creatures:
        print("Nenhuma criatura retornada.")
        return
    sample = creatures[0]
    print("\n--- AMOSTRA (primeira criatura) ---")
    print(json.dumps(sample, indent=2, ensure_ascii=False)[:3000])
    print("-----------------------------------\n")


# ── Conversão para BREEDING_DATA ───────────────────────────────────────────────

# Nomes reais dos campos (confirmados via PHP source)
_FIELD_MAP = {
    "mating":       ["minMatingInterval", "maxMatingInterval"],
    "incubation":   ["incubationTime"],
    "maturation":   ["matureTime"],
}


def _get(d: dict, keys: list[str], default=None):
    for k in keys:
        if k in d:
            return d[k]
    return default


def build_breeding_data(creatures: list[dict]) -> list[tuple]:
    """Converte a lista de criaturas da API para o formato BREEDING_DATA."""
    result = []
    skipped = []

    # diagnóstico: quantas têm dados de breeding
    with_mature  = [c for c in creatures if c.get("matureTime") is not None]
    with_incub   = [c for c in creatures if c.get("incubationTime") is not None]
    with_mating  = [c for c in creatures if c.get("minMatingInterval") is not None]
    print(f"[DIAG] matureTime != null : {len(with_mature)}")
    print(f"[DIAG] incubationTime != null: {len(with_incub)}")
    print(f"[DIAG] minMatingInterval != null: {len(with_mating)}")
    if with_mature:
        print(f"[DIAG] Exemplo com dados: {with_mature[0].get('label')} — "
              f"incub={with_mature[0].get('incubationTime')} "
              f"mature={with_mature[0].get('matureTime')} "
              f"mating={with_mature[0].get('minMatingInterval')}")

    for c in creatures:
        name   = c.get("label") or c.get("name") or "?"
        mature = c.get("matureTime")
        incub  = c.get("incubationTime")  # null para mamíferos
        mating = c.get("minMatingInterval")

        if mature is None or mating is None:
            skipped.append(name)
            continue

        # egg = tem incubationTime ; mammal = incubationTime é null
        if incub is not None:
            tipo = "egg"
        else:
            tipo  = "mammal"
            incub = c.get("gestationTime") or 0  # fallback

        result.append((name, tipo, int(mating), int(incub), int(mature)))

    if skipped and len(skipped) < len(creatures):
        print(f"\n[AVISO] {len(skipped)} criaturas sem dados completos (puladas).")

    return result


def print_breeding_data(data: list[tuple]) -> None:
    if not data:
        print("Nenhum dado gerado — veja a amostra acima e ajuste _FIELD_MAP.")
        return

    print("\n# ── BREEDING_DATA gerada pelo beacon_sync.py ──────────────────")
    print("BREEDING_DATA: list[tuple] = [")
    print("    # (nome, tipo, mating_s, incub_ou_gest_s, maturation_s)")

    eggs    = sorted([d for d in data if d[1] == "egg"],    key=lambda x: x[0])
    mammals = sorted([d for d in data if d[1] == "mammal"], key=lambda x: x[0])

    if eggs:
        print("    # ── Egg layers ────────────────────────────────────────────")
        for nome, tipo, mat, inc, matur in eggs:
            print(f'    ({nome!r:<36}, "egg",    {mat:>7}, {inc:>10}, {matur:>10}),')

    if mammals:
        print("    # ── Mammals ───────────────────────────────────────────────")
        for nome, tipo, mat, inc, matur in mammals:
            print(f'    ({nome!r:<36}, "mammal", {mat:>7}, {inc:>10}, {matur:>10}),')

    print("]")
    print(f"\n# Total: {len(data)} criaturas ({len(eggs)} egg, {len(mammals)} mammal)")


# ── Main ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=== Beacon Data Sync ===")
    token     = authenticate()
    all_creatures = fetch_creatures(token)
    print(f"✓ {len(all_creatures)} criaturas recebidas (Ark Prime).")

    creatures = filter_vanilla(all_creatures)
    print(f"✓ {len(creatures)} criaturas vanilla após filtro.")

    data = build_breeding_data(creatures)
    print_breeding_data(data)
