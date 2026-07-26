"""Testes do parser / heurística de crash + offline AI enrich."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from src.crash_ai import _offline_enriched_diagnosis, needs_ai_upgrade
from src.crash_parser import (
    _build_log_crash_record,
    _extract_error_message,
    _interpret_crash,
)


def test_extract_error_prefers_assertion_over_bare_fatal():
    lines = [
        "Fatal error!",
        "Assertion failed: ptr != nullptr [File:Foo.cpp] [Line: 12]",
    ]
    msg = _extract_error_message(lines)
    assert "Assertion failed" in msg


def test_interpret_bare_fatal_mentions_auto_ai():
    d = _interpret_crash("Fatal error!", "")
    assert "IA integrada" in d or "ShooterGame.log" in d


def test_build_log_record_includes_preamble_errors(tmp_path: Path):
    log_file = tmp_path / "ShooterGame.log"
    log_file.write_text("x", encoding="utf-8")
    block = (
        "LogArk: Error: Mod XYZ failed to load\n"
        "Fatal error!\n"
        "CustomShop.dll!USomething::Tick()\n"
    )
    rec = _build_log_crash_record(block, 0, log_file, datetime(2026, 7, 26, 19, 0, 0))
    assert rec["culprit"].lower() == "customshop.dll"
    assert "CustomShop" in rec["diagnosis"] or "customshop" in rec["diagnosis"].lower()
    assert any("Mod XYZ" in ln or "Fatal" in ln for ln in rec["call_stack"])


def test_offline_enrich_bare_fatal():
    text = _offline_enriched_diagnosis(
        culprit="",
        log_tail=["Fatal error!"],
        log_context="",
    )
    assert "sem call stack" in text.lower() or "ShooterGame.log" in text


def test_needs_ai_upgrade_generic():
    assert needs_ai_upgrade("Causa não identificada. Consulte o call stack e o ShooterGame.log para mais detalhes.")
    assert needs_ai_upgrade("🤖 IA a analisar o crash… aguarde alguns segundos.")
    assert not needs_ai_upgrade("🤖 IA (nvidia):\nPlugin X causou access violation.")
