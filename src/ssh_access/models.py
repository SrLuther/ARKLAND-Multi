from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


_ALIAS_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")


@dataclass
class SSHProfile:
    id: str
    name: str
    host: str
    username: str
    port: int = 22
    alias: str = ""
    auth_method: str = "key"
    identity_file: str = ""
    server_id: str = ""

    def validate(self) -> None:
        for label, value in (("Nome", self.name), ("Host", self.host), ("Usuário", self.username)):
            if not value.strip() or any(ch in value for ch in "\r\n\x00"):
                raise ValueError(f"{label} é obrigatório e não pode conter quebras de linha.")
        if not 1 <= int(self.port) <= 65535:
            raise ValueError("A porta deve estar entre 1 e 65535.")
        if self.auth_method not in {"key", "password"}:
            raise ValueError("Método de autenticação inválido.")
        if self.auth_method == "key" and not self.identity_file.strip():
            raise ValueError("Selecione a chave privada para autenticação por chave.")
        if self.alias and not _ALIAS_RE.fullmatch(self.alias):
            raise ValueError("O alias SSH aceita letras, números, ponto, hífen e sublinhado.")
        if any(ch in self.identity_file for ch in "\r\n\x00"):
            raise ValueError("O caminho da chave não pode conter quebras de linha.")

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "SSHProfile":
        profile = cls(
            id=str(raw.get("id", "")),
            name=str(raw.get("name", "")),
            host=str(raw.get("host", "")),
            username=str(raw.get("username", "")),
            port=int(raw.get("port", 22)),
            alias=str(raw.get("alias", "")),
            auth_method=str(raw.get("auth_method", "key")),
            identity_file=str(raw.get("identity_file", "")),
            server_id=str(raw.get("server_id", "")),
        )
        profile.validate()
        return profile

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return {
            "id": self.id,
            "name": self.name,
            "host": self.host,
            "username": self.username,
            "port": int(self.port),
            "alias": self.alias,
            "auth_method": self.auth_method,
            "identity_file": self.identity_file,
            "server_id": self.server_id,
        }
