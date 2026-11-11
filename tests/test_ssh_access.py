from __future__ import annotations

import socket
import threading
import time
from pathlib import Path
from types import SimpleNamespace

import paramiko
import pytest

from src.ssh_access import SSHProfile, SSHProfileStore
from src.ssh_access.diagnostics import (
    APPROVED,
    ATTENTION,
    FAILED,
    NOT_CHECKED,
    run_local_diagnostics,
    run_remote_diagnostics,
)
from src.ssh_access.host_keys import HostKeyStore, fingerprint_sha256
from src.ssh_access.openssh_config import register_codex_alias, unregister_codex_alias
from src.ssh_access.service import ChangedHostKeyError, SSHService


def profile(**changes) -> SSHProfile:
    data = {
        "id": "profile-1",
        "name": "Laboratório",
        "host": "127.0.0.1",
        "username": "tester",
        "port": 2222,
        "alias": "arkland-lab",
        "auth_method": "key",
        "identity_file": "C:/keys/lab_ed25519",
    }
    data.update(changes)
    return SSHProfile(**data)


class _SocketContext:
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


class _FakeService:
    def __init__(self, *, trusted=True, inspect_error=None, auth_error=None, read=(0, "ARKLAND_SSH_READ_PROBE\n")):
        self.trusted = trusted
        self.inspect_error = inspect_error
        self.auth_error = auth_error
        self.read = read
        self.auth_calls = 0
        self.read_calls = 0

    def inspect_host(self, _profile):
        if self.inspect_error:
            raise self.inspect_error
        return SimpleNamespace(trusted=self.trusted, fingerprint="SHA256:lab-fingerprint", key=object())

    def authenticate(self, _profile, _password=None, _key_passphrase=None):
        self.auth_calls += 1
        if self.auth_error:
            raise self.auth_error
        return SimpleNamespace(close=lambda: None)

    def run_read_probe(self, _client):
        self.read_calls += 1
        return self.read

    def identify_remote_os(self, _client):
        return "Linux"


def _resolver(*_args, **_kwargs):
    return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("192.0.2.10", 2222))]


def _tcp(*_args, **_kwargs):
    return _SocketContext()


def test_profile_store_persists_metadata_without_secret_fields(tmp_path):
    store = SSHProfileStore(tmp_path / "profiles.json")
    item = profile()
    store.save([item])
    loaded = store.load()
    assert loaded == [item]
    raw = store.path.read_text(encoding="utf-8")
    assert "password" not in raw
    assert "passphrase" not in raw
    assert "private_key_contents" not in raw


def test_profile_store_rejects_duplicate_aliases_and_preserves_previous_file(tmp_path):
    store = SSHProfileStore(tmp_path / "profiles.json")
    store.save([profile()])
    before = store.path.read_bytes()
    with pytest.raises(ValueError, match="únicos"):
        store.save([profile(), profile(id="profile-2")])
    assert store.path.read_bytes() == before


def test_profile_validation_rejects_open_ssh_config_injection():
    invalid = profile(host="host.example\nProxyCommand evil")
    with pytest.raises(ValueError, match="quebras de linha"):
        invalid.validate()


def test_host_key_store_trusts_known_key_and_blocks_same_type_rotation(tmp_path):
    store = HostKeyStore(tmp_path / "known_hosts")
    first = paramiko.RSAKey.generate(1024)
    other = paramiko.RSAKey.generate(1024)
    store.trust("example.test", 22, first)
    assert store.get_for_type("example.test", 22, first.get_name()).asbytes() == first.asbytes()
    with pytest.raises(ValueError, match="diferente"):
        store.trust("example.test", 22, other)
    assert fingerprint_sha256(first).startswith("SHA256:")


def test_host_key_store_separates_nonstandard_ports(tmp_path):
    store = HostKeyStore(tmp_path / "known_hosts")
    key = paramiko.RSAKey.generate(1024)
    store.trust("example.test", 2222, key)
    assert store.get("example.test", 2222).asbytes() == key.asbytes()
    assert store.get("example.test", 22) is None


def test_register_codex_alias_preserves_existing_config_and_creates_backup(tmp_path):
    config = tmp_path / ".ssh" / "config"
    config.parent.mkdir()
    original = b"Host git.example\n    User git\n\nHost *\n    ServerAliveInterval 20\n"
    config.write_bytes(original)
    managed = tmp_path / "ARKLAND data" / "ssh" / "config.d"
    profile_config = register_codex_alias(profile(), config_path=config, managed_dir=managed)
    assert config.read_bytes().startswith(original)
    assert _has_one_backup(config, original)
    assert profile_config.exists()
    assert "StrictHostKeyChecking yes" in profile_config.read_text(encoding="utf-8")
    assert "UserKnownHostsFile" in profile_config.read_text(encoding="utf-8")


def _has_one_backup(config: Path, original: bytes) -> bool:
    return any(path.read_bytes() == original for path in config.parent.glob("config.arkland-backup-*"))


def test_register_codex_alias_refuses_existing_alias_without_changes(tmp_path):
    config = tmp_path / ".ssh" / "config"
    config.parent.mkdir()
    original = b"Host arkland-lab\n    HostName other.example\n"
    config.write_bytes(original)
    managed = tmp_path / "managed"
    with pytest.raises(ValueError, match="já existe"):
        register_codex_alias(profile(), config_path=config, managed_dir=managed)
    assert config.read_bytes() == original
    assert not managed.exists()


def test_register_codex_alias_rejects_password_auth(tmp_path):
    item = profile(auth_method="password", identity_file="")
    with pytest.raises(ValueError, match="requer autenticação por chave"):
        register_codex_alias(item, config_path=tmp_path / "config", managed_dir=tmp_path / "managed")
    assert not (tmp_path / "config").exists()


def test_unregister_codex_alias_archives_only_profile_file(tmp_path):
    config = tmp_path / ".ssh" / "config"
    managed = tmp_path / "managed"
    config.parent.mkdir()
    managed.mkdir()
    profile_file = managed / "profile-1.conf"
    content = b"Host arkland-lab\n    HostName 127.0.0.1\n"
    profile_file.write_bytes(content)
    backup = unregister_codex_alias(profile(), managed_dir=managed)
    assert not profile_file.exists()
    assert backup is not None and backup.read_bytes() == content
    assert not config.exists()


def test_local_diagnostic_reports_missing_ssh_client(monkeypatch, tmp_path):
    from src.ssh_access import diagnostics

    monkeypatch.setattr(diagnostics.shutil, "which", lambda _name: None)
    results = run_local_diagnostics(home=tmp_path, credential_store_check=lambda: False)
    by_name = {r.name: r for r in results}
    assert by_name["Cliente OpenSSH"].status == FAILED
    assert by_name["Versão OpenSSH"].status == NOT_CHECKED
    assert by_name["Chaves SSH locais"].status == ATTENTION
    assert by_name["Ambiente do Codex no VS Code"].status == NOT_CHECKED


def test_local_diagnostic_reports_available_client_and_key_without_exposing_contents(monkeypatch, tmp_path):
    from src.ssh_access import diagnostics

    ssh_dir = tmp_path / ".ssh"
    ssh_dir.mkdir()
    (ssh_dir / "id_ed25519").write_text("DO-NOT-READ", encoding="utf-8")
    (ssh_dir / "id_ed25519.pub").write_text("ssh-ed25519 public", encoding="utf-8")
    monkeypatch.setattr(diagnostics.shutil, "which", lambda name: f"C:/Windows/System32/OpenSSH/{name}.exe")

    def fake_run(args, **_kwargs):
        if args[1] == "-V":
            return SimpleNamespace(returncode=0, stderr="OpenSSH_for_Windows_9.5", stdout="")
        if args[1] == "-l":
            return SimpleNamespace(returncode=1, stderr="The agent has no identities.", stdout="")
        return SimpleNamespace(returncode=0, stderr="", stdout="hostname localhost\n")

    results = run_local_diagnostics(home=tmp_path, credential_store_check=lambda: True, run=fake_run)
    by_name = {r.name: r for r in results}
    assert by_name["Cliente OpenSSH"].status == APPROVED
    assert by_name["Versão OpenSSH"].detail == "OpenSSH_for_Windows_9.5"
    assert by_name["Chaves SSH locais"].status == APPROVED
    assert "DO-NOT-READ" not in " ".join(r.detail for r in results)
    assert by_name["Agente SSH"].status == ATTENTION
    assert by_name["Armazenamento seguro"].status == APPROVED


def test_remote_diagnostic_classifies_dns_and_port_failures_without_ssh_attempt():
    fake = _FakeService()
    dns_results = run_remote_diagnostics(profile(), fake, resolver=lambda *_a, **_k: (_ for _ in ()).throw(socket.gaierror("no DNS")), tcp_probe=_tcp)
    assert dns_results[0].status == FAILED
    assert all(row.status == NOT_CHECKED for row in dns_results[1:])

    tcp_results = run_remote_diagnostics(profile(), fake, resolver=_resolver,
                                         tcp_probe=lambda *_a, **_k: (_ for _ in ()).throw(ConnectionRefusedError("refused")))
    assert next(row for row in tcp_results if row.name == "Porta SSH").status == FAILED
    assert fake.auth_calls == 0


def test_remote_diagnostic_requires_host_trust_before_authentication():
    fake = _FakeService(trusted=False)
    results = run_remote_diagnostics(profile(), fake, resolver=_resolver, tcp_probe=_tcp)
    by_name = {r.name: r for r in results}
    assert by_name["Porta SSH"].status == APPROVED
    assert by_name["Serviço SSH"].status == APPROVED
    assert by_name["Identidade do host"].status == ATTENTION
    assert by_name["Autenticação"].status == NOT_CHECKED
    assert fake.auth_calls == 0


def test_remote_diagnostic_blocks_changed_host_key():
    error = ChangedHostKeyError(paramiko.RSAKey.generate(1024), paramiko.RSAKey.generate(1024))
    results = run_remote_diagnostics(profile(), _FakeService(inspect_error=error), resolver=_resolver, tcp_probe=_tcp)
    by_name = {r.name: r for r in results}
    assert by_name["Identidade do host"].status == FAILED
    assert by_name["Autenticação"].status == NOT_CHECKED


def test_remote_diagnostic_distinguishes_auth_failure_and_read_command_failure():
    failed_auth = run_remote_diagnostics(profile(), _FakeService(auth_error=paramiko.AuthenticationException()), resolver=_resolver, tcp_probe=_tcp)
    assert next(r for r in failed_auth if r.name == "Autenticação").status == FAILED
    assert next(r for r in failed_auth if r.name == "Comando de leitura").status == NOT_CHECKED

    failed_command = run_remote_diagnostics(profile(), _FakeService(read=(1, "permission denied")), resolver=_resolver, tcp_probe=_tcp)
    assert next(r for r in failed_command if r.name == "Comando de leitura").status == FAILED


def test_remote_diagnostic_reports_successful_read_probe_and_remote_os():
    results = run_remote_diagnostics(profile(), _FakeService(), resolver=_resolver, tcp_probe=_tcp)
    by_name = {r.name: r for r in results}
    assert by_name["Resolução de endereço"].status == APPROVED
    assert by_name["Porta SSH"].status == APPROVED
    assert by_name["Identidade do host"].status == APPROVED
    assert by_name["Autenticação"].status == APPROVED
    assert by_name["Comando de leitura"].status == APPROVED
    assert by_name["Sistema operacional remoto"].detail == "Linux"


class _LabSSHServer(paramiko.ServerInterface):
    def __init__(self):
        self.command = None
        self.shell = threading.Event()

    def get_allowed_auths(self, _username):
        return "password"

    def check_auth_password(self, username, password):
        return paramiko.AUTH_SUCCESSFUL if username == "tester" and password == "correct" else paramiko.AUTH_FAILED

    def check_channel_request(self, kind, _chanid):
        return paramiko.OPEN_SUCCEEDED if kind == "session" else paramiko.OPEN_FAILED_ADMINISTRATIVELY_PROHIBITED

    def check_channel_exec_request(self, _channel, command):
        self.command = command.decode("utf-8", errors="replace")
        return True

    def check_channel_pty_request(self, *_args):
        return True

    def check_channel_shell_request(self, _channel):
        self.shell.set()
        return True


class _LocalSSHServer:
    def __init__(self):
        self.host_key = paramiko.RSAKey.generate(2048)
        self.listener = socket.socket()
        self.listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.listener.bind(("127.0.0.1", 0))
        self.listener.listen(5)
        self.listener.settimeout(0.2)
        self.port = self.listener.getsockname()[1]
        self.stop_event = threading.Event()
        self.thread = threading.Thread(target=self._serve, daemon=True)
        self.thread.start()

    def _serve_one(self, sock):
        transport = paramiko.Transport(sock)
        transport.add_server_key(self.host_key)
        server = _LabSSHServer()
        try:
            transport.start_server(server=server)
            deadline = time.monotonic() + 12
            while time.monotonic() < deadline and transport.is_active() and not self.stop_event.is_set():
                channel = transport.accept(0.1)
                if channel is None:
                    continue
                request_deadline = time.monotonic() + 3
                while time.monotonic() < request_deadline and not channel.closed:
                    if server.command is not None:
                        command, server.command = server.command, None
                        if command.startswith("echo "):
                            channel.send("ARKLAND_SSH_READ_PROBE\n")
                            channel.send_exit_status(0)
                        elif command == "uname -s":
                            channel.send("Linux\n")
                            channel.send_exit_status(0)
                        else:
                            channel.send_stderr("command not available in SSH test lab\n")
                            channel.send_exit_status(1)
                        channel.close()
                        break
                    if server.shell.is_set():
                        server.shell.clear()
                        channel.send("SSH LAB READY\n")
                        while not self.stop_event.is_set() and not channel.closed:
                            if channel.recv_ready():
                                data = channel.recv(4096)
                                if data:
                                    channel.send(data)
                                else:
                                    break
                            time.sleep(0.01)
                        break
                    time.sleep(0.01)
        except Exception:
            pass
        finally:
            transport.close()

    def _serve(self):
        while not self.stop_event.is_set():
            try:
                conn, _ = self.listener.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            threading.Thread(target=self._serve_one, args=(conn,), daemon=True).start()

    def close(self):
        self.stop_event.set()
        self.listener.close()
        self.thread.join(timeout=2)


def test_real_local_ssh_server_diagnostics_and_terminal(tmp_path):
    lab = _LocalSSHServer()
    try:
        item = profile(host="127.0.0.1", port=lab.port, auth_method="password", identity_file="")
        store = HostKeyStore(tmp_path / "known_hosts")
        service = SSHService(host_keys=store, vault=SimpleNamespace(get_secret=lambda *_: "correct"), timeout=3)
        first = service.inspect_host(item)
        assert not first.trusted
        service.trust_host(item, first.key)
        results = run_remote_diagnostics(item, service, password="correct", resolver=_resolver,
                                         tcp_probe=lambda address, timeout: socket.create_connection(address, timeout=timeout))
        by_name = {r.name: r for r in results}
        assert by_name["Serviço SSH"].status == APPROVED
        assert by_name["Identidade do host"].status == APPROVED
        assert by_name["Autenticação"].status == APPROVED
        assert by_name["Comando de leitura"].status == APPROVED
        assert by_name["Sistema operacional remoto"].detail == "Linux"

        connection = service.open_shell(item, password="correct", width=90, height=25)
        connection.send("olá ARKLAND")
        deadline = time.monotonic() + 3
        output = b""
        while time.monotonic() < deadline:
            output += connection.recv()
            if "olá ARKLAND".encode() in output:
                break
            time.sleep(0.02)
        assert "olá ARKLAND".encode() in output
        connection.resize(110, 32)
        connection.close()
    finally:
        lab.close()
