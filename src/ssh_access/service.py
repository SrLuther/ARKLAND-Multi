from __future__ import annotations

import socket
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import paramiko

from .credential_vault import WindowsCredentialVault
from .host_keys import HostKeyStore, fingerprint_sha256, host_key_name
from .models import SSHProfile


class UnknownHostKeyError(paramiko.SSHException):
    def __init__(self, key: paramiko.PKey | None = None):
        self.key = key
        self.fingerprint = fingerprint_sha256(key) if key is not None else ""
        super().__init__(f"Host key desconhecida: {self.fingerprint}".rstrip())


class ChangedHostKeyError(paramiko.SSHException):
    def __init__(self, known: paramiko.PKey, received: paramiko.PKey):
        self.known_fingerprint = fingerprint_sha256(known)
        self.received_fingerprint = fingerprint_sha256(received)
        super().__init__("A identidade do servidor SSH mudou. Conexão bloqueada.")


@dataclass
class RemoteHostInspection:
    key: paramiko.PKey
    fingerprint: str
    trusted: bool


class SSHConnection:
    def __init__(self, client: paramiko.SSHClient, channel: paramiko.Channel):
        self.client = client
        self.channel = channel

    def send(self, data: str) -> None:
        if self.channel.closed:
            raise paramiko.SSHException("A sessão SSH está encerrada.")
        self.channel.send(data)

    def resize(self, width: int, height: int) -> None:
        if not self.channel.closed:
            self.channel.resize_pty(width=max(20, width), height=max(5, height))

    def recv(self, size: int = 65536) -> bytes:
        if self.channel.recv_ready():
            return self.channel.recv(size)
        return b""

    def close(self) -> None:
        try:
            self.channel.close()
        finally:
            self.client.close()


class SSHService:
    def __init__(
        self,
        host_keys: HostKeyStore | None = None,
        vault: WindowsCredentialVault | None = None,
        *,
        timeout: float = 10.0,
    ) -> None:
        self.host_keys = host_keys or HostKeyStore()
        self.vault = vault or WindowsCredentialVault()
        self.timeout = timeout

    def inspect_host(self, profile: SSHProfile) -> RemoteHostInspection:
        profile.validate()
        transport = paramiko.Transport((profile.host, int(profile.port)))
        try:
            transport.start_client(timeout=self.timeout)
            received = transport.get_remote_server_key()
        except socket.timeout as exc:
            raise TimeoutError("Tempo esgotado ao negociar com o serviço SSH remoto.") from exc
        except OSError as exc:
            raise ConnectionError(f"Não foi possível alcançar o serviço SSH: {exc}") from exc
        except paramiko.SSHException as exc:
            raise paramiko.SSHException(f"A porta respondeu, mas não foi possível negociar SSH: {exc}") from exc
        finally:
            transport.close()
        known = self.host_keys.get_for_type(profile.host, profile.port, received.get_name())
        if known is None:
            return RemoteHostInspection(received, fingerprint_sha256(received), False)
        if known.asbytes() != received.asbytes():
            raise ChangedHostKeyError(known, received)
        return RemoteHostInspection(received, fingerprint_sha256(received), True)

    def trust_host(self, profile: SSHProfile, key: paramiko.PKey) -> None:
        self.host_keys.trust(profile.host, profile.port, key)

    def _new_client(
        self,
        profile: SSHProfile,
        password: str | None = None,
        key_passphrase: str | None = None,
    ) -> paramiko.SSHClient:
        profile.validate()
        expected = self.host_keys.get(profile.host, profile.port)
        if expected is None:
            raise UnknownHostKeyError()
        client = paramiko.SSHClient()
        client.load_system_host_keys()
        if self.host_keys.path.exists():
            client.load_host_keys(str(self.host_keys.path))
        client.set_missing_host_key_policy(paramiko.RejectPolicy())
        options: dict = {
            "hostname": profile.host,
            "port": int(profile.port),
            "username": profile.username,
            "timeout": self.timeout,
            "banner_timeout": self.timeout,
            "auth_timeout": self.timeout,
            "allow_agent": False,
            "look_for_keys": False,
        }
        if profile.auth_method == "password":
            password = password if password is not None else self.vault.get_secret(profile.id, "password")
            if not password:
                raise PermissionError("Nenhuma senha SSH está disponível no cofre do Windows.")
            options["password"] = password
        else:
            passphrase = key_passphrase
            if passphrase is None:
                passphrase = self.vault.get_secret(profile.id, "key-passphrase")
            options["key_filename"] = str(Path(profile.identity_file).expanduser())
            if passphrase:
                options["passphrase"] = passphrase
        try:
            client.connect(**options)
        except paramiko.BadHostKeyException as exc:
            known = self.host_keys.get(profile.host, profile.port)
            client.close()
            if known is not None:
                raise ChangedHostKeyError(known, exc.key) from exc
            raise
        except Exception:
            client.close()
            raise
        return client

    def authenticate(
        self,
        profile: SSHProfile,
        password: str | None = None,
        key_passphrase: str | None = None,
    ) -> paramiko.SSHClient:
        """Connect only after host identity was explicitly trusted."""
        return self._new_client(profile, password, key_passphrase)

    def test_authentication(
        self,
        profile: SSHProfile,
        password: str | None = None,
        key_passphrase: str | None = None,
    ) -> None:
        client = self.authenticate(profile, password, key_passphrase)
        client.close()

    def run_read_probe(self, client: paramiko.SSHClient, timeout: float = 8.0) -> tuple[int, str]:
        """Runs a harmless echo command to verify an authenticated command session."""
        _stdin, stdout, stderr = client.exec_command("echo ARKLAND_SSH_READ_PROBE", timeout=timeout)
        channel = stdout.channel
        deadline = time.monotonic() + timeout
        while not channel.exit_status_ready() and time.monotonic() < deadline:
            time.sleep(0.05)
        if not channel.exit_status_ready():
            channel.close()
            raise TimeoutError("O servidor autenticou, mas o comando de leitura excedeu o tempo limite.")
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        return channel.recv_exit_status(), out + err

    def identify_remote_os(self, client: paramiko.SSHClient, timeout: float = 5.0) -> str | None:
        """Try read-only platform commands without assuming the remote shell."""
        commands = ("uname -s", "cmd /c ver", "powershell.exe -NoProfile -Command \"[System.Environment]::OSVersion.VersionString\"")
        for command in commands:
            try:
                _stdin, stdout, _stderr = client.exec_command(command, timeout=timeout)
                channel = stdout.channel
                deadline = time.monotonic() + timeout
                while not channel.exit_status_ready() and time.monotonic() < deadline:
                    time.sleep(0.05)
                if not channel.exit_status_ready():
                    channel.close()
                    continue
                output = stdout.read().decode("utf-8", errors="replace").strip()
                if channel.recv_exit_status() == 0 and output:
                    return output[:240]
            except (OSError, paramiko.SSHException, TimeoutError):
                continue
        return None

    def open_shell(
        self,
        profile: SSHProfile,
        *,
        password: str | None = None,
        key_passphrase: str | None = None,
        width: int = 100,
        height: int = 30,
    ) -> SSHConnection:
        client = self.authenticate(profile, password, key_passphrase)
        try:
            channel = client.get_transport().open_session(timeout=self.timeout)
            channel.get_pty(term="xterm-256color", width=width, height=height)
            channel.invoke_shell()
            return SSHConnection(client, channel)
        except Exception:
            client.close()
            raise

