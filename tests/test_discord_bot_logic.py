"""Lógica pura dos cogs portados (sem discord.py / sem conectar ao Discord)."""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.discord_bot import logic, storage  # noqa: E402


class TestBadwords:
    def test_parse_dedupes_lowercases_and_skips_blank(self):
        assert logic.parse_badwords("Merda\n\n  PUTA \nmerda\n") == ["merda", "puta"]

    def test_compile_uses_word_boundaries(self):
        rx = logic.compile_badwords(["cu", "burro"])
        assert rx is not None
        assert rx.search("você é um BURRO")
        assert rx.search("vai pro cu")
        assert not rx.search("curso de culinária")  # "cu" dentro de outra palavra
        assert logic.compile_badwords([]) is None
        assert logic.compile_badwords(["  ", ""]) is None

    def test_regex_escapes_special_chars(self):
        rx = logic.compile_badwords(["a+b"])
        assert rx is not None and rx.search("isto é a+b mesmo")
        assert not rx.search("aab")

    def test_default_list_matches_original_words(self):
        rx = logic.compile_badwords(logic.DEFAULT_BADWORDS)
        assert rx is not None and rx.search("seu imbecil")
        assert "pnc" in logic.DEFAULT_BADWORDS


class TestClassifyMessage:
    def setup_method(self):
        self.rx = logic.compile_badwords(["idiota"])

    def test_invite_variants(self):
        for text in ("entra em discord.gg/abc", "https://discord.com/invite/xyz", "DISCORD.GG/ABC"):
            assert logic.classify_message(text, self.rx) == logic.VIOLATION_INVITE

    def test_badword(self):
        assert logic.classify_message("que idiota", self.rx) == logic.VIOLATION_BADWORD

    def test_invite_has_priority_over_badword(self):
        assert logic.classify_message("idiota discord.gg/x", self.rx) == logic.VIOLATION_INVITE

    def test_clean_and_no_badword_filter(self):
        assert logic.classify_message("bom dia", self.rx) is None
        assert logic.classify_message("idiota", None) is None
        assert logic.classify_message("", self.rx) is None


class TestVoiceLogic:
    def test_name_and_limit(self):
        assert logic.temp_channel_name("Ana") == "Sala de 🗣️ Ana"
        assert logic.VOICE_USER_LIMIT == 10

    def test_lobby_join(self):
        assert logic.is_lobby_join(5, 5) is True
        assert logic.is_lobby_join(6, 5) is False
        assert logic.is_lobby_join(None, 5) is False
        assert logic.is_lobby_join(0, 0) is False  # lobby não configurado

    def test_should_delete_temp_channel(self):
        tracked = {10: 1}
        assert logic.should_delete_temp_channel(10, 5, tracked, 0) is True
        assert logic.should_delete_temp_channel(10, 5, tracked, 2) is False   # ainda tem gente
        assert logic.should_delete_temp_channel(11, 5, tracked, 0) is False   # não rastreado
        assert logic.should_delete_temp_channel(5, 5, {5: 1}, 0) is False     # nunca o lobby


class TestAdminLogic:
    def test_limit_range(self):
        assert logic.limpezageral_limit_ok(1) and logic.limpezageral_limit_ok(1000)
        assert not logic.limpezageral_limit_ok(0) and not logic.limpezageral_limit_ok(1001)

    def test_resolve_extension_module(self):
        pkg = "src.discord_bot"
        assert logic.resolve_extension_module("voicemanager", pkg) == "src.discord_bot.voice_manager"
        assert logic.resolve_extension_module("VoiceManager.py", pkg) == "src.discord_bot.voice_manager"
        assert logic.resolve_extension_module("moderation", pkg) == "src.discord_bot.moderation"
        assert logic.resolve_extension_module("admin", pkg) == "src.discord_bot.admin"

    def test_other_cogs_are_not_loadable(self):
        for name in ("ark", "tickets", "os", "../x", ""):
            assert logic.resolve_extension_module(name, "src.discord_bot") is None

    def test_reaction_confirmed(self):
        assert logic.reaction_confirmed("✅") and not logic.reaction_confirmed("❌")


class TestStorage:
    def test_ensure_data_dir_seeds_once(self, tmp_path):
        d = tmp_path / "obobonic"
        storage.ensure_data_dir(d)
        words = storage.load_badwords(d)
        assert "merda" in words
        (d / storage.BADWORDS_FILENAME).write_text("custom\n", encoding="utf-8")
        storage.ensure_data_dir(d)  # não sobrescreve edição do usuário
        assert storage.load_badwords(d) == ["custom"]

    def test_load_badwords_missing_raises(self, tmp_path):
        try:
            storage.load_badwords(tmp_path)
        except FileNotFoundError:
            return
        raise AssertionError("esperava FileNotFoundError")

    def test_temp_channels_roundtrip_and_bad_file(self, tmp_path):
        assert storage.load_temp_channels(tmp_path) == {}
        storage.save_temp_channels(tmp_path, {1: 2, 3: 4})
        assert storage.load_temp_channels(tmp_path) == {1: 2, 3: 4}
        (tmp_path / storage.VOICE_STATE_FILENAME).write_text("lixo{", encoding="utf-8")
        assert storage.load_temp_channels(tmp_path) == {}
        (tmp_path / storage.VOICE_STATE_FILENAME).write_text('{"x": 1, "5": "7"}', encoding="utf-8")
        assert storage.load_temp_channels(tmp_path) == {5: 7}
