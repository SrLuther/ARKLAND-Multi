"""Testes unitários para src/rcon_client.py.

Executar com:
    python -m pytest tests/ -v
ou:
    python -m unittest tests.test_rcon_client -v
"""
from __future__ import annotations

import socket
import struct
import threading
import unittest
from unittest.mock import MagicMock, patch, call

import sys
import os

# Garante que o pacote src esteja no path mesmo sem instalar o projeto
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.rcon_client import (
    RconClient,
    RconAuthError,
    RconConnectionError,
    RconError,
    _PACKET_TYPE_AUTH,
    _PACKET_TYPE_EXECCOMMAND,
)


# ── Utilitários para montar pacotes RCON falsos ──────────────────────────────

def _make_packet(pkt_id: int, pkt_type: int, body: str) -> bytes:
    """Cria um pacote RCON no formato Source Engine."""
    encoded = body.encode("utf-8")
    size    = 4 + 4 + len(encoded) + 2
    return struct.pack("<iii", size, pkt_id, pkt_type) + encoded + b"\x00\x00"


def _make_recv_bytes(*packets: bytes):
    """Retorna uma função recv() que devolve os bytes dos pacotes em sequência."""
    combined = b"".join(packets)
    buf      = bytearray(combined)

    def recv(n: int) -> bytes:
        chunk = bytes(buf[:n])
        del buf[:n]
        return chunk

    return recv


# ── Testes ──────────────────────────────────────────────────────────────────

class TestRconClientInit(unittest.TestCase):

    def test_raises_on_empty_host(self):
        with self.assertRaises(ValueError):
            RconClient("", 27020, "senha")

    def test_raises_on_whitespace_host(self):
        with self.assertRaises(ValueError):
            RconClient("   ", 27020, "senha")

    def test_raises_on_invalid_port_zero(self):
        with self.assertRaises(ValueError):
            RconClient("127.0.0.1", 0, "senha")

    def test_raises_on_invalid_port_too_high(self):
        with self.assertRaises(ValueError):
            RconClient("127.0.0.1", 65536, "senha")

    def test_raises_on_empty_password(self):
        with self.assertRaises(ValueError):
            RconClient("127.0.0.1", 27020, "")

    def test_valid_creation(self):
        c = RconClient("127.0.0.1", 27020, "senha123")
        self.assertFalse(c.is_connected)
        self.assertIsNone(c.connected_since)
        self.assertEqual(c.connected_seconds, 0.0)
        self.assertEqual(c.idle_seconds, float("inf"))
        self.assertEqual(c._consecutive_failures, 0)
        self.assertEqual(c._total_commands_sent, 0)


class TestRconClientConnect(unittest.TestCase):

    def _make_mock_socket(self, pkt_id: int, auth_ok: bool = True) -> MagicMock:
        """Cria um socket mock que responde à autenticação."""
        # AUTH_RESPONSE (type 2) com o ID correto = sucesso, -1 = falha
        resp_id = pkt_id if auth_ok else -1
        auth_resp = _make_packet(resp_id, 2, "")  # type 2 = AUTH_RESPONSE
        mock_sock = MagicMock()
        mock_sock.recv.side_effect = _make_recv_bytes(auth_resp)
        return mock_sock

    @patch("src.rcon_client.socket.socket")
    def test_connect_success(self, mock_socket_cls):
        # O primeiro pacote enviado é AUTH com id=1
        mock_sock = self._make_mock_socket(pkt_id=1, auth_ok=True)
        mock_socket_cls.return_value = mock_sock

        client = RconClient("127.0.0.1", 27020, "senha")
        client.connect()

        self.assertTrue(client.is_connected)
        self.assertIsNotNone(client.connected_since)

    @patch("src.rcon_client.socket.socket")
    def test_connect_wrong_password_raises_auth_error(self, mock_socket_cls):
        mock_sock = self._make_mock_socket(pkt_id=1, auth_ok=False)
        mock_socket_cls.return_value = mock_sock

        client = RconClient("127.0.0.1", 27020, "senhaErrada")
        with self.assertRaises(RconAuthError):
            client.connect()
        self.assertFalse(client.is_connected)

    @patch("src.rcon_client.socket.socket")
    def test_connect_refused_raises_connection_error(self, mock_socket_cls):
        mock_sock = MagicMock()
        mock_sock.connect.side_effect = ConnectionRefusedError("Refused")
        mock_socket_cls.return_value = mock_sock

        client = RconClient("127.0.0.1", 27020, "senha")
        with self.assertRaises(RconConnectionError):
            client.connect()
        self.assertFalse(client.is_connected)

    @patch("src.rcon_client.socket.socket")
    def test_disconnect_marks_disconnected(self, mock_socket_cls):
        mock_sock = self._make_mock_socket(pkt_id=1, auth_ok=True)
        mock_socket_cls.return_value = mock_sock

        client = RconClient("127.0.0.1", 27020, "senha")
        client.connect()
        self.assertTrue(client.is_connected)

        client.disconnect()
        self.assertFalse(client.is_connected)
        self.assertIsNone(client.connected_since)


class TestRconClientSendCommand(unittest.TestCase):

    def _connected_client(self, responses: list[bytes]) -> RconClient:
        """Cria um cliente já 'conectado' com mock de socket."""
        # Monta auth_resp + respostas de comando
        auth_resp = _make_packet(1, 2, "")  # auth OK, id=1
        all_data  = auth_resp + b"".join(responses)

        mock_sock = MagicMock()
        mock_sock.recv.side_effect = _make_recv_bytes(all_data)
        mock_sock.gettimeout.return_value = 10.0

        with patch("src.rcon_client.socket.socket", return_value=mock_sock):
            client = RconClient("127.0.0.1", 27020, "senha")
            client.connect()
        return client

    def test_send_command_returns_response(self):
        resp_pkt = _make_packet(2, 0, "GoodResponse")  # id=2 (próximo após auth)
        client = self._connected_client([resp_pkt])
        result = client.send_command("ListPlayers")
        self.assertEqual(result, "GoodResponse")
        self.assertEqual(client._total_commands_sent, 1)

    def test_send_command_safe_success(self):
        resp_pkt = _make_packet(2, 0, "Saved")
        client = self._connected_client([resp_pkt])
        ok, result = client.send_command_safe("SaveWorld")
        self.assertTrue(ok)
        self.assertEqual(result, "Saved")

    def test_send_command_safe_returns_false_on_error(self):
        # Simula falha de leitura do socket após conectar
        auth_resp = _make_packet(1, 2, "")
        mock_sock = MagicMock()
        mock_sock.gettimeout.return_value = 10.0

        call_count = [0]
        def _recv(n: int) -> bytes:
            buf = bytearray(auth_resp)
            if call_count[0] < len(auth_resp):
                chunk = bytes(buf[call_count[0]:call_count[0]+n])
                call_count[0] += len(chunk)
                return chunk
            # Para o recv de execução: simula socket fechado
            return b""

        mock_sock.recv.side_effect = _recv
        with patch("src.rcon_client.socket.socket", return_value=mock_sock):
            client = RconClient("127.0.0.1", 27020, "senha")
            client.connect()

        ok, msg = client.send_command_safe("SaveWorld")
        self.assertFalse(ok)
        self.assertIn("encerrad", msg.lower())  # "Conexão encerrada pelo servidor."


class TestRconClientRetry(unittest.TestCase):

    def test_send_command_with_retry_succeeds_after_failures(self):
        """Deve ter sucesso na 3ª tentativa após 2 falhas de conexão."""
        client = RconClient("127.0.0.1", 27020, "senha")

        attempt = [0]

        def _safe(cmd: str):
            attempt[0] += 1
            if attempt[0] < 3:
                return (False, "timeout")
            return (True, "players")

        def _connect_locked():
            client._connected = True

        client.send_command_safe  = lambda c: _safe(c)  # type: ignore
        client._RconClient__lock  = client._lock         # alias interno

        with patch.object(client, "send_command_safe", side_effect=_safe):
            with patch.object(client, "_RconClient__lock", threading.Lock()):
                with patch.object(client, "_connect_locked", side_effect=_connect_locked):
                    ok, result = client.send_command_with_retry(
                        "ListPlayers", retries=3, retry_delay=0
                    )

        self.assertTrue(ok)
        self.assertEqual(result, "players")

    def test_send_command_with_retry_fails_all(self):
        """Deve retornar False após esgotar todas as tentativas."""
        client = RconClient("127.0.0.1", 27020, "senha")

        with patch.object(client, "send_command_safe", return_value=(False, "timeout")):
            with patch.object(client, "_connect_locked", return_value=None):
                ok, result = client.send_command_with_retry(
                    "SaveWorld", retries=2, retry_delay=0
                )

        self.assertFalse(ok)
        self.assertIn("2 tentativa", result)


class TestRconClientPing(unittest.TestCase):

    def test_ping_returns_false_when_disconnected(self):
        client = RconClient("127.0.0.1", 27020, "senha")
        result = client.ping()
        self.assertFalse(result)

    def test_ping_returns_false_when_socket_raises(self):
        client = RconClient("127.0.0.1", 27020, "senha")
        client._connected = True
        mock_sock = MagicMock()
        mock_sock.gettimeout.return_value = 10.0
        mock_sock.sendall.side_effect = OSError("broken pipe")
        client._sock = mock_sock

        result = client.ping()
        self.assertFalse(result)

    def test_ping_returns_true_when_response_matches(self):
        client = RconClient("127.0.0.1", 27020, "senha")
        client._connected = True
        client._pkt_id    = 0  # próximo id será 1

        # Simula resposta com id=1
        resp_pkt = _make_packet(1, 0, "")
        mock_sock = MagicMock()
        mock_sock.gettimeout.return_value = 10.0
        mock_sock.recv.side_effect = _make_recv_bytes(resp_pkt)
        client._sock = mock_sock

        result = client.ping()
        self.assertTrue(result)


class TestPacketBuilding(unittest.TestCase):

    def test_send_packet_format(self):
        """Verifica que o pacote enviado segue o formato RCON correto."""
        client = RconClient("127.0.0.1", 27020, "senha")
        client._connected = True
        sent_data = bytearray()
        mock_sock = MagicMock()
        mock_sock.sendall.side_effect = lambda data: sent_data.extend(data)
        client._sock = mock_sock

        client._send_packet(42, _PACKET_TYPE_EXECCOMMAND, "TestCmd")

        # Verifica estrutura: size(4) + id(4) + type(4) + body + \x00\x00
        (size,)   = struct.unpack("<i", bytes(sent_data[:4]))
        (pkt_id,) = struct.unpack("<i", bytes(sent_data[4:8]))
        (ptype,)  = struct.unpack("<i", bytes(sent_data[8:12]))
        body      = bytes(sent_data[12:-2]).decode("utf-8")
        tail      = bytes(sent_data[-2:])

        self.assertEqual(pkt_id, 42)
        self.assertEqual(ptype,  _PACKET_TYPE_EXECCOMMAND)
        self.assertEqual(body,   "TestCmd")
        self.assertEqual(tail,   b"\x00\x00")
        self.assertEqual(size,   4 + 4 + len("TestCmd") + 2)

    def test_recv_exact_raises_on_closed_socket(self):
        client = RconClient("127.0.0.1", 27020, "senha")
        client._connected = True
        mock_sock = MagicMock()
        mock_sock.recv.return_value = b""  # socket fechado
        client._sock = mock_sock

        with self.assertRaises(RconConnectionError) as ctx:
            client._recv_exact(4)
        self.assertIn("encerrada", str(ctx.exception))


if __name__ == "__main__":
    unittest.main(verbosity=2)
