from __future__ import annotations

from datetime import UTC, datetime, timedelta
from io import BytesIO
from pathlib import Path
import sys

from PIL import Image
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lumo_assets import cleanup_assets, resolve_asset, validate_and_store


def png_bytes(color="red"):
    output = BytesIO()
    Image.new("RGB", (16, 12), color).save(output, format="PNG")
    return output.getvalue()


def test_upload_validates_real_image_and_stores_random_safe_name(tmp_path):
    record = validate_and_store(tmp_path, BytesIO(png_bytes()), "../../portrait.png", "admin-1")
    assert record["original_name"] == "portrait.png"
    assert record["filename"].endswith(".png") and ".." not in record["filename"]
    assert record["width"] == 16 and record["height"] == 12
    assert resolve_asset(tmp_path, record).read_bytes() == png_bytes()


def test_upload_rejects_non_image_and_oversized_data(tmp_path):
    with pytest.raises(ValueError, match="imagem válida"):
        validate_and_store(tmp_path, BytesIO(b"MZ" + b"x" * 40), "fake.png", "admin")
    with pytest.raises(ValueError, match="8 MB"):
        validate_and_store(tmp_path, BytesIO(b"x" * (8 * 1024 * 1024 + 1)), "large.png", "admin")


def test_cleanup_uses_last_use_and_preserves_referenced_assets(tmp_path):
    old = (datetime.now(UTC) - timedelta(days=31)).isoformat()
    file_a = tmp_path / "old.png"
    file_b = tmp_path / "referenced.png"
    file_a.write_bytes(png_bytes())
    file_b.write_bytes(png_bytes("blue"))
    records = [
        {"id": "old", "filename": file_a.name, "uploaded_at": old, "references": []},
        {"id": "ref", "filename": file_b.name, "uploaded_at": old, "references": ["draft"]},
    ]
    kept, removed = cleanup_assets(tmp_path, records, retention_days=30)
    assert removed == ["old"]
    assert not file_a.exists()
    assert file_b.exists() and len(kept) == 1 and kept[0]["id"] == "ref"


def test_cleanup_keeps_recently_used_asset_even_when_upload_is_old(tmp_path):
    file = tmp_path / "used.png"
    file.write_bytes(png_bytes())
    old = (datetime.now(UTC) - timedelta(days=60)).isoformat()
    recent = (datetime.now(UTC) - timedelta(days=2)).isoformat()
    kept, removed = cleanup_assets(tmp_path, [{"id": "used", "filename": file.name, "uploaded_at": old, "last_used_at": recent}], retention_days=30)
    assert not removed and len(kept) == 1 and file.exists()
