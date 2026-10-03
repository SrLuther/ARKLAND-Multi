"""Testes do bot oBobonic embutido: configuração, persistência, migração e helpers puros."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.config_manager import ConfigManager, ObobonicBotConfig  # noqa: E402
from src.discord_bot import legacy_import  # noqa: E402
from src.discord_bot.settings import (  # noqa: E402
    BotSettings,
    compute_invite_permissions,
    discord_app_id_from_token,
    discord_developer_url,
    discord_invite_url,
    mask_secret,
    parse_discord_id,
    redact,
    validate_token_value,
)
from src.obobonic_bot import (  # noqa: E402
    get_runner,
    save_bot_fields,
    save_panel_options,
    shutdown_obobonic_for_app,
    validate_bot_fields,
)

# Token FALSO (formato válido: 3 segmentos, 1º = base64 do client id)
FAKE_TOKEN = "fake.discord.token-for-tests"


@pytest.fixture()
def cm(tmp_path, monkeypatch) -> ConfigManager:
    monkeypatch.setenv("APPDATA", str(tmp_path))
    return ConfigManager()


def _config_file(tmp_path: Path) -> Path:
    return tmp_path / "ARKLAND-ServerManager" / "config.json"


# ── Persistência das opções do painel (bug: opção desmarcada «voltava» marcada) ──
class TestPanelOptionsPersistence:
    def test_unchecked_options_survive_restart(self, cm, tmp_path, monkeypatch):
        assert cm.config.obobonic.auto_start is True  # default marcado
        save_panel_options(cm, auto_start=False, auto_restart_on_crash=False)

        monkeypatch.setenv("APPDATA", str(tmp_path))
        reloaded = ConfigManager()  # "reiniciar o app"
        assert reloaded.config.obobonic.auto_start is False
        assert reloaded.config.obobonic.auto_restart_on_crash is False

    def test_checked_options_survive_restart(self, cm, tmp_path, monkeypatch):
        save_panel_options(cm, auto_start=True, auto_restart_on_crash=True)
        monkeypatch.setenv("APPDATA", str(tmp_path))
        reloaded = ConfigManager()
        assert reloaded.config.obobonic.auto_start is True
        assert reloaded.config.obobonic.auto_restart_on_crash is True

    def test_each_combination_roundtrips(self, cm, tmp_path, monkeypatch):
        for a in (True, False):
            for b in (True, False):
                save_panel_options(cm, auto_start=a, auto_restart_on_crash=b)
                monkeypatch.setenv("APPDATA", str(tmp_path))
                r = ConfigManager().config.obobonic
                assert (r.auto_start, r.auto_restart_on_crash) == (a, b)

    def test_save_uses_live_config_after_reload(self, cm):
        """Config recarregada (objeto novo) não pode deixar o painel gravando num objeto solto."""
        cm.load()  # substitui cm.config por um objeto novo
        save_panel_options(cm, auto_start=False, auto_restart_on_crash=True)
        data = json.loads(cm._config_file.read_text(encoding="utf-8"))
        assert data["obobonic"]["auto_start"] is False
        assert data["obobonic"]["auto_restart_on_crash"] is True

    def test_string_booleans_are_not_truthy(self, tmp_path, monkeypatch):
        cfg = tmp_path / "ARKLAND-ServerManager"
        cfg.mkdir(parents=True)
        (cfg / "config.json").write_text(
            json.dumps({"obobonic": {"auto_start": "false", "auto_restart_on_crash": "0"}}),
            encoding="utf-8",
        )
        monkeypatch.setenv("APPDATA", str(tmp_path))
        o = ConfigManager().config.obobonic
        assert o.auto_start is False
        assert o.auto_restart_on_crash is False

    def test_save_is_atomic_and_propagates_io_errors(self, cm, tmp_path, monkeypatch):
        save_panel_options(cm, auto_start=False, auto_restart_on_crash=False)
        good = _config_file(tmp_path).read_text(encoding="utf-8")

        monkeypatch.setattr("src.config_manager.time.sleep", lambda *_: None)

        def boom(*_a, **_k):
            raise PermissionError("arquivo bloqueado")

        monkeypatch.setattr("src.config_manager.os.replace", boom)
        with pytest.raises(OSError):
            save_panel_options(cm, auto_start=True, auto_restart_on_crash=True)
        # arquivo anterior intacto (não truncado) e memória coerente com o disco
        assert _config_file(tmp_path).read_text(encoding="utf-8") == good
        assert cm.config.obobonic.auto_start is False
        assert cm.config.obobonic.auto_restart_on_crash is False

    def test_corrupt_config_is_backed_up_before_reset(self, tmp_path, monkeypatch):
        d = tmp_path / "ARKLAND-ServerManager"
        d.mkdir(parents=True)
        (d / "config.json").write_text("{ não é json", encoding="utf-8")
        monkeypatch.setenv("APPDATA", str(tmp_path))
        ConfigManager()
        assert list(d.glob("config.json.corrupt-*"))


# ── Migração de config antiga (pasta externa) ────────────────────────────────
class TestLegacyConfigMigration:
    def _write_old(self, tmp_path: Path, obobonic: dict) -> None:
        d = tmp_path / "ARKLAND-ServerManager"
        d.mkdir(parents=True, exist_ok=True)
        (d / "config.json").write_text(json.dumps({"obobonic": obobonic}), encoding="utf-8")

    def test_old_config_keeps_options_and_ignores_folder(self, tmp_path, monkeypatch):
        self._write_old(tmp_path, {
            "project_path": r"C:\ARKLAND SERVER\oBobonicClean",
            "start_hidden": True,
            "auto_start": False,
            "auto_restart_on_crash": True,
            "health_check_before_start": True,
        })
        monkeypatch.setenv("APPDATA", str(tmp_path))
        o = ConfigManager().config.obobonic
        assert o.auto_start is False
        assert o.auto_restart_on_crash is True
        assert o.token == ""
        assert not hasattr(o, "project_path")
        assert not hasattr(o, "start_hidden")
        assert o.legacy_project_path == r"C:\ARKLAND SERVER\oBobonicClean"
        assert o.legacy_import_done is False

    def test_new_config_roundtrip_has_no_legacy_keys(self, cm, tmp_path):
        cm.save()
        data = json.loads(_config_file(tmp_path).read_text(encoding="utf-8"))["obobonic"]
        assert "project_path" not in data and "start_hidden" not in data
        assert "health_check_before_start" not in data

    def test_legacy_path_not_recaptured_after_import_done(self):
        o = ObobonicBotConfig.from_dict(
            {"project_path": "X:/velho", "legacy_import_done": True, "legacy_project_path": ""}
        )
        assert o.legacy_project_path == ""

    def test_unknown_or_null_values_are_tolerated(self):
        o = ObobonicBotConfig.from_dict({"token": None, "guild_id": 123, "bogus": 1})
        assert o.token == ""
        assert o.guild_id == "123"


# ── Importação única do bot antigo ───────────────────────────────────────────
class TestLegacyImport:
    def _old_project(self, tmp_path: Path) -> Path:
        old = tmp_path / "oBobonicClean"
        (old / ".bancos").mkdir(parents=True)
        (old / ".env").write_text(
            f"# comentário\nDISCORD_TOKEN={FAKE_TOKEN}\nGUILD_ID=111222333444\nLOBBY_CHANNEL_ID=\n",
            encoding="utf-8",
        )
        (old / "config.py").write_text(
            'GUILD_ID = get_int_env("GUILD_ID", 999999999)\n'
            'LOBBY_CHANNEL_ID = get_int_env("LOBBY_CHANNEL_ID", 555566667777)\n'
            'CANAL_LOGS_ID = get_int_env("CANAL_LOGS_ID", 888899990000)\n'
            'QUARANTINE_ROLE_ID = get_int_env("QUARANTINE_ROLE_ID", 121212121212)\n',
            encoding="utf-8",
        )
        (old / ".bancos" / "palavroes.txt").write_text("alfa\nbeta\n", encoding="utf-8")
        return old

    def test_collect_prefers_env_over_config_defaults(self, tmp_path):
        data = legacy_import.collect_legacy_values(self._old_project(tmp_path))
        assert data.values["token"] == FAKE_TOKEN
        assert data.values["guild_id"] == "111222333444"           # .env vence config.py
        assert data.values["lobby_channel_id"] == "555566667777"   # .env vazio → default do config.py
        assert data.values["logs_channel_id"] == "888899990000"
        assert data.values["quarantine_role_id"] == "121212121212"
        assert data.badwords_path is not None

    def test_placeholder_token_is_not_imported(self, tmp_path):
        old = tmp_path / "old"
        old.mkdir()
        (old / ".env").write_text("DISCORD_TOKEN=token_falso_para_dev\n", encoding="utf-8")
        data = legacy_import.collect_legacy_values(old)
        assert not data.has_token

    def test_apply_does_not_overwrite_by_default(self, tmp_path):
        data = legacy_import.collect_legacy_values(self._old_project(tmp_path))
        cfg = ObobonicBotConfig(guild_id="42")
        changed = legacy_import.apply_legacy_to_config(cfg, data)
        assert "guild_id" not in changed and cfg.guild_id == "42"
        assert cfg.token == FAKE_TOKEN
        assert "token" in changed

    def test_import_badwords_merges_without_losing_user_words(self, tmp_path):
        data = legacy_import.collect_legacy_values(self._old_project(tmp_path))
        dest = tmp_path / "dados"
        dest.mkdir()
        (dest / "palavroes.txt").write_text("minha\n", encoding="utf-8")
        assert legacy_import.import_badwords(data, dest) is True
        merged = (dest / "palavroes.txt").read_text(encoding="utf-8").split()
        assert merged == ["minha", "alfa", "beta"]
        # idempotente
        assert legacy_import.import_badwords(data, dest) is False

    def test_import_badwords_overwrite(self, tmp_path):
        data = legacy_import.collect_legacy_values(self._old_project(tmp_path))
        dest = tmp_path / "dados"
        dest.mkdir()
        (dest / "palavroes.txt").write_text("minha\n", encoding="utf-8")
        assert legacy_import.import_badwords(data, dest, overwrite=True) is True
        assert (dest / "palavroes.txt").read_text(encoding="utf-8").split() == ["alfa", "beta"]

    def test_offer_only_once_and_only_with_token(self, tmp_path):
        old = self._old_project(tmp_path)
        cfg = ObobonicBotConfig(legacy_project_path=str(old))
        assert legacy_import.should_offer_legacy_import(cfg) is True
        cfg.legacy_import_done = True
        assert legacy_import.should_offer_legacy_import(cfg) is False
        cfg2 = ObobonicBotConfig(legacy_project_path=str(old), token=FAKE_TOKEN)
        assert legacy_import.should_offer_legacy_import(cfg2) is False
        cfg3 = ObobonicBotConfig(legacy_project_path=str(tmp_path / "nao_existe"))
        assert legacy_import.should_offer_legacy_import(cfg3) is False

    def test_parse_env_text(self):
        env = legacy_import.parse_env_text('A=1\n# x\nexport B="dois"\nC = tres\nruim\n')
        assert env == {"A": "1", "B": "dois", "C": "tres"}


# ── Campos do painel / validação ─────────────────────────────────────────────
class TestBotFields:
    def test_validate_ok_and_errors(self):
        assert validate_bot_fields({"token": FAKE_TOKEN, "guild_id": "123456789", "command_prefix": "!"}) == []
        errs = validate_bot_fields({"token": "curto", "guild_id": "abc", "command_prefix": "a b"})
        assert len(errs) == 3

    def test_save_bot_fields_persists_and_strips(self, cm, tmp_path, monkeypatch):
        errors = save_bot_fields(
            cm,
            {"token": f"  {FAKE_TOKEN} ", "guild_id": " 123456789 ", "command_prefix": "?",
             "lobby_channel_id": "", "logs_channel_id": "987654321", "quarantine_role_id": "", "client_id": ""},
            enable_voice=False, enable_moderation=True,
        )
        assert errors == []
        monkeypatch.setenv("APPDATA", str(tmp_path))
        o = ConfigManager().config.obobonic
        assert o.token == FAKE_TOKEN and o.guild_id == "123456789"
        assert o.command_prefix == "?" and o.enable_voice is False and o.enable_moderation is True

    def test_save_bot_fields_rejects_without_writing(self, cm, tmp_path):
        before = cm.config.obobonic.guild_id
        errors = save_bot_fields(cm, {"guild_id": "xyz"})
        assert errors and cm.config.obobonic.guild_id == before


class TestSettingsHelpers:
    def test_token_validation(self):
        assert validate_token_value(FAKE_TOKEN)[0] is True
        assert validate_token_value("")[0] is False
        assert validate_token_value("token_falso_para_dev")[0] is False
        assert validate_token_value("a" * 30)[0] is False  # sem pontos

    def test_client_id_and_urls(self):
        import base64
        client_id = "42"
        segment = base64.b64encode(client_id.encode("ascii")).decode("ascii").rstrip("=")
        shaped = f"{segment}.not.a-discord-token"
        assert discord_app_id_from_token(shaped) == client_id
        assert client_id in discord_developer_url(shaped)
        url = discord_invite_url(shaped)
        assert url and f"client_id={client_id}" in url
        assert f"permissions={compute_invite_permissions()}" in url
        assert "scope=bot" in url
        assert "client_id=777" in discord_invite_url("", client_id="777")
        assert discord_invite_url("", "") is None

    def test_invite_permissions_cover_cogs(self):
        p = compute_invite_permissions()
        for bit in (1 << 4, 1 << 13, 1 << 24, 1 << 22, 1 << 23, 1 << 28):
            assert p & bit
        assert not p & 8  # nunca Administrator

    def test_mask_redact_parse_id(self):
        assert mask_secret("abcdefghij") == "abcd…ghij"
        assert FAKE_TOKEN not in redact(f"login {FAKE_TOKEN} ok", FAKE_TOKEN)
        assert parse_discord_id(" 123 ") == 123
        assert parse_discord_id("x") == 0 and parse_discord_id(None) == 0 and parse_discord_id(-5) == 0

    def test_settings_problems_and_warnings(self, tmp_path):
        s = BotSettings.from_config(ObobonicBotConfig(), data_dir=tmp_path)
        assert s.problems()
        s = BotSettings.from_config(ObobonicBotConfig(token=FAKE_TOKEN), data_dir=tmp_path)
        assert s.problems() == []
        assert len(s.warnings()) == 3
        assert s.command_prefix == "!"


# ── Ciclo de vida no app ─────────────────────────────────────────────────────
class TestAppLifecycle:
    def test_get_runner_is_singleton_per_app(self):
        app = SimpleNamespace()
        assert get_runner(app) is get_runner(app)

    def test_shutdown_without_runner_is_noop(self):
        shutdown_obobonic_for_app(SimpleNamespace())

    def test_shutdown_stops_runner(self):
        calls = []
        app = SimpleNamespace(_obobonic_runner=SimpleNamespace(shutdown=lambda: calls.append(1)))
        shutdown_obobonic_for_app(app)
        assert calls == [1]
