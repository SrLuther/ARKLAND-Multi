"""beacon_client.py
Carrega e armazena em cache blueprints do ARK via API Beacon (usebeacon.app).
Inclui fluxo de autenticação OAuth Device Flow (PKCE) sem dependências externas.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
import time
import threading
import webbrowser
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

try:
    import requests as _requests
    _REQUESTS_OK = True
except ImportError:
    _requests = None  # type: ignore[assignment]
    _REQUESTS_OK = False

# ── Constantes ─────────────────────────────────────────────────────────────────
_API_BASE       = "https://api.usebeacon.app"
_CLIENT_ID      = "0e710efc-3fa1-4751-b668-aa046579365d"
_ARK_PRIME_ID   = "30bbab29-44b2-4f4b-a373-6d4740d9d3b5"
_PAGE_SIZE      = 250
_CACHE_TTL_DAYS = 7

_CACHE_FILE = (
    Path(os.environ.get("APPDATA", str(Path.home())))
    / "ARKLAND-ServerManager"
    / "beacon_blueprints_cache.json"
)


def _token_path() -> Path:
    # Sempre usa AppData — garante escrita mesmo sem admin (Program Files é read-only)
    return (
        Path(os.environ.get("APPDATA", str(Path.home())))
        / "ARKLAND-ServerManager"
        / "beacon_token.json"
    )


class BeaconBlueprintClient:
    """Carrega e pesquisa blueprints do ARK via Beacon API com cache local."""

    def __init__(self) -> None:
        self._blueprints: List[Dict[str, Any]] = []
        self._loaded = False

    # ── Auth ────────────────────────────────────────────────────────────────

    def _get_token(self) -> Optional[str]:
        path = _token_path()
        if not path.exists():
            return None
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            if data.get("expires_at", 0) > time.time() + 60:
                return data.get("access_token")
        except Exception:
            pass
        return None

    def is_authenticated(self) -> bool:
        return self._get_token() is not None

    def is_loaded(self) -> bool:
        return self._loaded

    # ── OAuth Device Flow ────────────────────────────────────────────────────

    @staticmethod
    def _pkce_pair() -> tuple:
        verifier  = secrets.token_urlsafe(64)
        digest    = hashlib.sha256(verifier.encode()).digest()
        challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
        return verifier, challenge

    def _save_token(self, token_resp: dict) -> None:
        token_resp["expires_at"] = time.time() + token_resp.get("expires_in", 3600)
        path = _token_path()
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(token_resp, f, indent=2)
        except Exception:
            pass

    def authenticate_async(
        self,
        on_code:    Callable[[str, str], None],
        on_success: Callable[[], None],
        on_error:   Callable[[str], None],
    ) -> None:
        """Inicia Device Flow em thread background.

        Callbacks (chamados na thread worker — use `widget.after(0, ...)` na UI):
          on_code(user_code, url)   — exibir código e URL ao usuário
          on_success()              — autenticação bem-sucedida, token salvo
          on_error(mensagem)        — falha
        """
        if not _REQUESTS_OK:
            on_error("Biblioteca 'requests' não encontrada.")
            return

        def _worker() -> None:
            assert _requests is not None
            try:
                verifier, challenge = self._pkce_pair()

                # 1. Iniciar Device Flow
                r = _requests.post(f"{_API_BASE}/v4/device", json={
                    "client_id":             _CLIENT_ID,
                    "scope":                 "common",
                    "code_challenge":        challenge,
                    "code_challenge_method": "S256",
                }, timeout=15)
                r.raise_for_status()
                device = r.json()

                user_code   = device["user_code"]
                verify_url  = device.get("verification_uri_complete") or device["verification_uri"]
                device_code = device["device_code"]
                interval    = int(device.get("interval", 5))
                expires_in  = int(device.get("expires_in", 300))

                on_code(user_code, verify_url)

                # 2. Abrir navegador automaticamente
                try:
                    webbrowser.open(verify_url)
                except Exception:
                    pass

                # 3. Polling
                deadline = time.time() + expires_in
                while time.time() < deadline:
                    time.sleep(interval)
                    poll = _requests.post(f"{_API_BASE}/v4/login", json={
                        "grant_type":    "urn:ietf:params:oauth:grant-type:device_code",
                        "device_code":   device_code,
                        "client_id":     _CLIENT_ID,
                        "code_verifier": verifier,
                    }, timeout=15)

                    if poll.status_code in (200, 201):
                        self._save_token(poll.json())
                        on_success()
                        return

                    body = poll.json() if "application/json" in poll.headers.get("content-type", "") else {}
                    err  = body.get("error", "")

                    if err == "authorization_pending":
                        continue
                    if err == "slow_down":
                        interval += 5
                        continue
                    if err in ("access_denied", "expired_token"):
                        on_error(f"Login recusado: {err}")
                        return
                    # outros erros HTTP
                    poll.raise_for_status()

                on_error("Tempo limite de autenticação atingido (5 min).")

            except Exception as exc:
                on_error(str(exc))

        threading.Thread(target=_worker, daemon=True).start()

    def _load_cache(self) -> bool:
        """Carrega cache local. Retorna True se o cache foi carregado com sucesso."""
        if not _CACHE_FILE.exists():
            return False
        try:
            with open(_CACHE_FILE, encoding="utf-8") as f:
                data = json.load(f)
            age_days = (time.time() - data.get("fetched_at", 0)) / 86400.0
            if age_days > _CACHE_TTL_DAYS:
                return False
            bps = data.get("blueprints")
            if isinstance(bps, list) and len(bps) > 0:
                self._blueprints = bps
                self._loaded = True
                return True
        except Exception:
            pass
        return False

    def _save_cache(self) -> None:
        try:
            _CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(
                    {"fetched_at": time.time(), "blueprints": self._blueprints},
                    f,
                    ensure_ascii=False,
                    separators=(",", ":"),
                )
        except Exception:
            pass

    # ── Fetch ───────────────────────────────────────────────────────────────

    def fetch_all(
        self,
        on_progress: Optional[Callable[[int, int], None]] = None,
    ) -> None:
        """Busca todos os blueprints Ark Prime da API (8 páginas ~1963 itens).

        Args:
            on_progress: callback(page, total_pages) chamado após cada página.
        Raises:
            RuntimeError: se requests não disponível ou token ausente/expirado.
        """
        if not _REQUESTS_OK:
            raise RuntimeError("Biblioteca 'requests' não encontrada. Execute: pip install requests")
        token = self._get_token()
        if token is None:
            raise RuntimeError(
                "Token de autenticação não encontrado ou expirado.\n"
                "Clique em 'Conectar com Beacon' para autenticar novamente."
            )
        assert _requests is not None
        headers: Dict[str, str | bytes] = {"Authorization": f"Bearer {token}"}
        all_blueprints: List[Dict[str, Any]] = []
        page = 1
        total_pages = 1
        while page <= total_pages:
            url = (
                f"{_API_BASE}/v4/ark/blueprints"
                f"?pageSize={_PAGE_SIZE}"
                f"&contentPackId={_ARK_PRIME_ID}"
                f"&page={page}"
            )
            resp = _requests.get(url, headers=headers, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            total_pages = int(data.get("pages", 1))
            all_blueprints.extend(data.get("results", []))
            if on_progress:
                on_progress(page, total_pages)
            page += 1
        self._blueprints = all_blueprints
        self._loaded = True
        self._save_cache()

    def ensure_loaded(
        self,
        force: bool = False,
        on_progress: Optional[Callable[[int, int], None]] = None,
    ) -> None:
        """Garante que os blueprints estejam carregados (cache ou API)."""
        if not force and self._load_cache():
            return
        self.fetch_all(on_progress=on_progress)

    # ── Search ──────────────────────────────────────────────────────────────

    def search(
        self,
        query: str = "",
        category: str = "all",
        max_results: int = 150,
    ) -> List[Dict[str, Any]]:
        """Filtra blueprints por texto e categoria.

        Args:
            query: texto de busca (case-insensitive, label ou classString).
            category: "all" | "items" (engramId) | "creatures" (creatureId).
            max_results: limite de resultados retornados.
        Returns:
            Lista filtrada de dicts blueprint.
        """
        results = self._blueprints

        # Filtro de categoria
        if category == "creatures":
            results = [bp for bp in results if bp.get("creatureId")]
        elif category == "items":
            results = [bp for bp in results if bp.get("engramId")]

        # Filtro de texto
        if query.strip():
            q = query.strip().lower()
            results = [
                bp for bp in results
                if q in bp.get("label", "").lower()
                or q in bp.get("classString", "").lower()
            ]

        return results[:max_results]


# ── Singleton ──────────────────────────────────────────────────────────────────
_CLIENT: Optional[BeaconBlueprintClient] = None


def get_beacon_client() -> BeaconBlueprintClient:
    """Retorna a instância singleton do BeaconBlueprintClient."""
    global _CLIENT
    if _CLIENT is None:
        _CLIENT = BeaconBlueprintClient()
    return _CLIENT
