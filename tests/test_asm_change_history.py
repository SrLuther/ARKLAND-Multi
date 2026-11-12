from __future__ import annotations

import json

from src.asm_engine.asm_change_history import (
    get_asm_change_logger,
    record_asm_server_changes,
    snapshot_asm_server,
)
from src.asm_engine.asm_server_config import AsmServerConfig


def test_tek_history_records_safe_changes_and_excludes_secrets(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "src.asm_engine.asm_change_history.default_manager_log_dir",
        lambda: tmp_path,
    )
    before_cfg = AsmServerConfig(
        id="server-tek", name="Before", max_players=70,
        server_password="old-password", admin_password="admin-secret",
        discord_webhook_url="https://example.invalid/token",
        admin_ids=["private-steam-id"],
        custom_game_ini_raw="SensitiveRaw=old-secret\n",
    )
    after_cfg = AsmServerConfig.from_dict(before_cfg.to_dict())
    after_cfg.name = "After"
    after_cfg.max_players = 80
    after_cfg.server_password = "new-password"
    after_cfg.custom_game_ini_raw = "SensitiveRaw=new-secret\n"

    before = snapshot_asm_server(before_cfg)
    after = snapshot_asm_server(after_cfg)
    count = record_asm_server_changes(
        before_cfg.id, before, after,
        before_profile=before_cfg.to_dict(), after_profile=after_cfg.to_dict(),
    )

    assert count == 4
    logger = get_asm_change_logger(before_cfg.id)
    assert logger.log_path.name == "tek_server-tek_changes.jsonl"
    entries = logger.read_all()
    assert {entry["label"] for entry in entries} == {
        "name", "max_players", "server_password (valores omitidos)",
        "custom_game_ini_raw (valores omitidos)",
    }
    serialized = logger.log_path.read_text(encoding="utf-8")
    for secret in (
        "old-password", "admin-secret", "new-password", "private-steam-id",
        "SensitiveRaw", "example.invalid",
    ):
        assert secret not in serialized
    assert all(json.loads(line)["tab"] == "TEK" for line in serialized.splitlines())
