"""Windows Credential Manager adapter. Never stores secrets in profile JSON."""
from __future__ import annotations

import ctypes
import os
from ctypes import wintypes


class _CREDENTIALW(ctypes.Structure):
    _fields_ = [
        ("Flags", wintypes.DWORD),
        ("Type", wintypes.DWORD),
        ("TargetName", wintypes.LPWSTR),
        ("Comment", wintypes.LPWSTR),
        ("LastWritten", wintypes.FILETIME),
        ("CredentialBlobSize", wintypes.DWORD),
        ("CredentialBlob", ctypes.POINTER(ctypes.c_byte)),
        ("Persist", wintypes.DWORD),
        ("AttributeCount", wintypes.DWORD),
        ("Attributes", ctypes.c_void_p),
        ("TargetAlias", wintypes.LPWSTR),
        ("UserName", wintypes.LPWSTR),
    ]


class WindowsCredentialVault:
    CRED_TYPE_GENERIC = 1
    CRED_PERSIST_LOCAL_MACHINE = 2

    @staticmethod
    def _target(profile_id: str, purpose: str) -> str:
        return f"ARKLAND-ServerManager:SSH:{profile_id}:{purpose}"

    def _api(self):
        if os.name != "nt":
            raise OSError("O cofre de credenciais SSH está disponível somente no Windows.")
        return ctypes.WinDLL("Advapi32.dll", use_last_error=True)

    def set_secret(self, profile_id: str, purpose: str, secret: str) -> None:
        if not secret:
            self.delete_secret(profile_id, purpose)
            return
        api = self._api()
        api.CredWriteW.argtypes = [ctypes.POINTER(_CREDENTIALW), wintypes.DWORD]
        api.CredWriteW.restype = wintypes.BOOL
        encoded = secret.encode("utf-16-le")
        blob = (ctypes.c_byte * len(encoded)).from_buffer_copy(encoded)
        cred = _CREDENTIALW()
        cred.Type = self.CRED_TYPE_GENERIC
        cred.TargetName = self._target(profile_id, purpose)
        cred.CredentialBlobSize = len(encoded)
        cred.CredentialBlob = ctypes.cast(blob, ctypes.POINTER(ctypes.c_byte))
        cred.Persist = self.CRED_PERSIST_LOCAL_MACHINE
        cred.UserName = "ARKLAND"
        if not api.CredWriteW(ctypes.byref(cred), 0):
            raise ctypes.WinError(ctypes.get_last_error())

    def get_secret(self, profile_id: str, purpose: str) -> str | None:
        api = self._api()
        api.CredReadW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.POINTER(ctypes.POINTER(_CREDENTIALW))]
        api.CredReadW.restype = wintypes.BOOL
        api.CredFree.argtypes = [ctypes.c_void_p]
        api.CredFree.restype = None
        out = ctypes.POINTER(_CREDENTIALW)()
        if not api.CredReadW(self._target(profile_id, purpose), self.CRED_TYPE_GENERIC, 0, ctypes.byref(out)):
            error = ctypes.get_last_error()
            if error == 1168:  # ERROR_NOT_FOUND
                return None
            raise ctypes.WinError(error)
        try:
            cred = out.contents
            raw = ctypes.string_at(cred.CredentialBlob, cred.CredentialBlobSize)
            return raw.decode("utf-16-le")
        finally:
            api.CredFree(out)

    def delete_secret(self, profile_id: str, purpose: str) -> None:
        api = self._api()
        api.CredDeleteW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD]
        api.CredDeleteW.restype = wintypes.BOOL
        if not api.CredDeleteW(self._target(profile_id, purpose), self.CRED_TYPE_GENERIC, 0):
            error = ctypes.get_last_error()
            if error != 1168:
                raise ctypes.WinError(error)

    def delete_profile_secrets(self, profile_id: str) -> None:
        for purpose in ("password", "key-passphrase"):
            self.delete_secret(profile_id, purpose)
