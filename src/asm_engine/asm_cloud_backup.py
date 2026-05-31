"""
S5.1 — Cloud Backup Engine.
Suporta upload/download/listagem de backups para:
  - Amazon S3 / S3-compatible (via boto3 opcional)
  - Pasta de rede local / mapeada (sempre disponível)
Credenciais ficam em %APPDATA%\\ARKLAND-ServerManager\\cloud_credentials.json
NUNCA misturadas com asm_servers.json.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


class AsmCloudBackup:
    """
    Interface unificada para backup em nuvem ou pasta de rede.

    Uso:
        cb = AsmCloudBackup()
        cb.upload_backup(server_id, local_zip_path)
        items = cb.list_remote_backups(server_id)
        cb.download_backup(server_id, remote_name, dest_path)
    """

    _CREDS_FILE = (
        Path(os.environ.get("APPDATA", Path.home()))
        / "ARKLAND-ServerManager"
        / "cloud_credentials.json"
    )

    def __init__(self) -> None:
        self._creds: Dict[str, Any] = {}
        self._load_creds()

    # ── Credenciais ─────────────────────────────────────────────────────────

    def _load_creds(self) -> None:
        if self._CREDS_FILE.exists():
            try:
                with open(self._CREDS_FILE, encoding="utf-8") as fh:
                    self._creds = json.load(fh)
            except Exception:
                self._creds = {}

    def save_creds(self, provider: str, **kwargs: Any) -> None:
        """Salva credenciais de forma segura (apenas no disco local)."""
        self._CREDS_FILE.parent.mkdir(parents=True, exist_ok=True)
        self._creds["provider"] = provider
        self._creds.update(kwargs)
        with open(self._CREDS_FILE, "w", encoding="utf-8") as fh:
            json.dump(self._creds, fh, indent=2)
        # Restringe permissões no Windows (tenta; pode falhar em FAT32)
        try:
            import stat
            self._CREDS_FILE.chmod(stat.S_IRUSR | stat.S_IWUSR)
        except Exception:
            pass

    @property
    def provider(self) -> str:
        return self._creds.get("provider", "local")

    @property
    def is_configured(self) -> bool:
        if self.provider == "local":
            return bool(self._creds.get("local_path"))
        if self.provider == "s3":
            return all(
                self._creds.get(k)
                for k in ("bucket", "aws_access_key_id", "aws_secret_access_key", "region_name")
            )
        return False

    # ── Upload ───────────────────────────────────────────────────────────────

    def upload_backup(self, server_id: str, local_zip_path: str) -> str:
        """
        Envia backup para o destino configurado.
        Retorna o nome remoto do arquivo enviado.
        Raises: RuntimeError se não configurado / falha de upload.
        """
        if not self.is_configured:
            raise RuntimeError("Backup em nuvem não configurado.")
        src = Path(local_zip_path)
        if not src.exists():
            raise FileNotFoundError(f"Arquivo de backup não encontrado: {src}")

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        remote_name = f"{server_id}_{ts}_{src.name}"

        if self.provider == "local":
            self._upload_local(src, remote_name, server_id)
        elif self.provider == "s3":
            self._upload_s3(src, remote_name, server_id)
        else:
            raise RuntimeError(f"Provider desconhecido: {self.provider!r}")

        return remote_name

    def _upload_local(self, src: Path, remote_name: str, server_id: str) -> None:
        dest_dir = Path(self._creds["local_path"]) / server_id
        dest_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest_dir / remote_name)

    def _upload_s3(self, src: Path, remote_name: str, server_id: str) -> None:
        try:
            import boto3  # type: ignore[reportMissingModuleSource]
        except ImportError as exc:
            raise RuntimeError("boto3 não instalado. Execute: pip install boto3") from exc
        s3 = boto3.client(
            "s3",
            aws_access_key_id     = self._creds["aws_access_key_id"],
            aws_secret_access_key = self._creds["aws_secret_access_key"],
            region_name           = self._creds.get("region_name", "us-east-1"),
            endpoint_url          = self._creds.get("endpoint_url"),  # S3-compatible
        )
        key = f"{server_id}/{remote_name}"
        s3.upload_file(str(src), self._creds["bucket"], key)

    # ── Listagem ─────────────────────────────────────────────────────────────

    def list_remote_backups(self, server_id: str) -> List[Dict[str, Any]]:
        """
        Retorna lista de backups remotos para o servidor.
        Cada item: {"name": str, "size": int, "modified": str}
        """
        if not self.is_configured:
            return []
        if self.provider == "local":
            return self._list_local(server_id)
        if self.provider == "s3":
            return self._list_s3(server_id)
        return []

    def _list_local(self, server_id: str) -> List[Dict[str, Any]]:
        d = Path(self._creds["local_path"]) / server_id
        if not d.exists():
            return []
        result = []
        for p in sorted(d.iterdir(), reverse=True):
            if p.is_file():
                stat = p.stat()
                result.append({
                    "name":     p.name,
                    "size":     stat.st_size,
                    "modified": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
                })
        return result

    def _list_s3(self, server_id: str) -> List[Dict[str, Any]]:
        try:
            import boto3  # type: ignore[reportMissingModuleSource]
        except ImportError:
            return []
        s3 = boto3.client(
            "s3",
            aws_access_key_id     = self._creds["aws_access_key_id"],
            aws_secret_access_key = self._creds["aws_secret_access_key"],
            region_name           = self._creds.get("region_name", "us-east-1"),
            endpoint_url          = self._creds.get("endpoint_url"),
        )
        prefix = f"{server_id}/"
        try:
            resp = s3.list_objects_v2(Bucket=self._creds["bucket"], Prefix=prefix)
        except Exception:
            return []
        result = []
        for obj in resp.get("Contents", []):
            result.append({
                "name":     obj["Key"].removeprefix(prefix),
                "size":     obj["Size"],
                "modified": obj["LastModified"].strftime("%Y-%m-%d %H:%M:%S"),
            })
        return sorted(result, key=lambda x: x["modified"], reverse=True)

    # ── Download ─────────────────────────────────────────────────────────────

    def download_backup(self, server_id: str, remote_name: str, dest_path: str) -> None:
        """Baixa um backup remoto para `dest_path`."""
        if not self.is_configured:
            raise RuntimeError("Backup em nuvem não configurado.")
        if self.provider == "local":
            src = Path(self._creds["local_path"]) / server_id / remote_name
            shutil.copy2(src, dest_path)
        elif self.provider == "s3":
            self._download_s3(server_id, remote_name, dest_path)
        else:
            raise RuntimeError(f"Provider desconhecido: {self.provider!r}")

    def _download_s3(self, server_id: str, remote_name: str, dest_path: str) -> None:
        try:
            import boto3  # type: ignore[reportMissingModuleSource]
        except ImportError as exc:
            raise RuntimeError("boto3 não instalado.") from exc
        s3 = boto3.client(
            "s3",
            aws_access_key_id     = self._creds["aws_access_key_id"],
            aws_secret_access_key = self._creds["aws_secret_access_key"],
            region_name           = self._creds.get("region_name", "us-east-1"),
            endpoint_url          = self._creds.get("endpoint_url"),
        )
        key = f"{server_id}/{remote_name}"
        s3.download_file(self._creds["bucket"], key, dest_path)

    def delete_remote_backup(self, server_id: str, remote_name: str) -> None:
        """Remove backup remoto."""
        if not self.is_configured:
            return
        if self.provider == "local":
            p = Path(self._creds["local_path"]) / server_id / remote_name
            if p.exists():
                p.unlink()
        elif self.provider == "s3":
            try:
                import boto3  # type: ignore
                s3 = boto3.client(
                    "s3",
                    aws_access_key_id     = self._creds["aws_access_key_id"],
                    aws_secret_access_key = self._creds["aws_secret_access_key"],
                    region_name           = self._creds.get("region_name", "us-east-1"),
                    endpoint_url          = self._creds.get("endpoint_url"),
                )
                s3.delete_object(Bucket=self._creds["bucket"], Key=f"{server_id}/{remote_name}")
            except Exception:
                pass


# ── Singleton global ─────────────────────────────────────────────────────────
_instance: Optional[AsmCloudBackup] = None


def get_cloud_backup() -> AsmCloudBackup:
    global _instance
    if _instance is None:
        _instance = AsmCloudBackup()
    return _instance
