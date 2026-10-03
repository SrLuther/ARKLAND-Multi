"""Coletor (src/diagnostics/collector.py) com dados sintéticos em tmp_path."""
from __future__ import annotations

import json
import os
import zipfile
from pathlib import Path

import pytest

from _diag_synth import (
    SECRET_ADMIN, SECRET_API_KEY, SECRET_PLUGIN_TOKEN, SECRET_SERVER_PW, SECRET_SMTP, SECRET_WEBHOOK,
    make_server_dir, tek_entry, write_config_dir,
)
from src.diagnostics import collector as col
from src.diagnostics.doctor import CheckResult
from src.diagnostics.redact import REDACTED

ALL_SECRETS = (SECRET_ADMIN, SECRET_API_KEY, SECRET_PLUGIN_TOKEN, SECRET_SERVER_PW, SECRET_SMTP,
               SECRET_WEBHOOK, "AbCdEf_ghIJkl-MNop0123456789")


@pytest.fixture()
def env(tmp_path, monkeypatch):
    appdata = tmp_path / "appdata"
    monkeypatch.setenv("APPDATA", str(appdata))
    cdir = appdata / "ARKLAND-ServerManager"

    inst = make_server_dir(
        tmp_path / "srv",
        permissions=True,
        plugins={
            "CustomShop": {"config": json.dumps({
                "Enabled": True, "ApiUrl": "https://loja.test",
                "ApiKey": SECRET_API_KEY, "Token": SECRET_PLUGIN_TOKEN, "Interval": 30})},
            "SemConfig": {"config": None},
        },
        game_ini="[/script/shootergame.shootergamemode]\nLevelExperienceRampOverrides=(ExperiencePointsForLevel[0]=5)\n",
    )
    arkapi_logs = inst / "ShooterGame" / "Binaries" / "Win64" / "ArkApi" / "Logs"
    arkapi_logs.mkdir(parents=True)
    (arkapi_logs / "ArkApi.log").write_text(
        f"[info] start\nAuthorization: Bearer {SECRET_PLUGIN_TOKEN}\n[info] done\n", encoding="utf-8")

    write_config_dir(
        cdir,
        tek=[tek_entry(inst, progressions=True)],
        config={
            "steamcmd_path": "C:/steamcmd",
            "shop": {"mode": "client", "api_key": SECRET_API_KEY, "central_url": "https://loja.test"},
            "smtp": {"host": "smtp.test", "password": SECRET_SMTP},
            "discord": {"webhook_url": SECRET_WEBHOOK, "enabled": True},
        },
    )
    # arquivo que deve ser pulado inteiro pelo nome
    (cdir / "discord_token.json").write_text(json.dumps({"x": SECRET_PLUGIN_TOKEN}), encoding="utf-8")

    logs = cdir / "logs"
    logs.mkdir()
    (logs / "arkland.log").write_text(
        "2026-01-01 | INFO | linha normal\n"
        f"2026-01-01 | INFO | password={SECRET_SMTP}\n"
        f"2026-01-01 | INFO | chave solta no meio do texto {SECRET_API_KEY} fim\n",
        encoding="utf-8")
    out = tmp_path / "out"
    return {"cdir": cdir, "inst": inst, "out": out, "tmp": tmp_path}


def _collect(env, **kw):
    kw.setdefault("run_doctor_checks", True)
    return col.collect_diagnostics(config_dir=env["cdir"], out_dir=env["out"], mode="tek", **kw)


def _read_all(path: Path) -> dict:
    with zipfile.ZipFile(path) as zf:
        assert zf.testzip() is None
        return {n: zf.read(n) for n in zf.namelist()}


def _find(entries: dict, fragment: str) -> str:
    matches = [n for n in entries if fragment in n]
    assert matches, f"{fragment!r} não está no zip: {sorted(entries)}"
    return entries[matches[0]].decode("utf-8")


def test_zip_contem_arquivos_esperados(env):
    res = _collect(env)
    assert res.path.parent == env["out"] and res.path.suffix == ".zip" and not res.over_limit
    entries = _read_all(res.path)
    names = set(entries)
    for expected in ("app_info.json", "README.txt", "redaction_info.json", "doctor.json", "doctor.txt",
                     "events.json", "logs/arkland.log", "config/config.json"):
        assert expected in names, expected
    assert any(n.endswith("/state.json") for n in names)
    assert any(n.endswith("/ini/GameUserSettings.ini") for n in names)
    assert any(n.endswith("/ini/Game.ini") for n in names)
    assert any(n.endswith("/arkapi/plugins.json") for n in names)
    assert any(n.endswith("/arkapi/plugins/CustomShop/config.json") for n in names)
    assert any("/arkapi/logs/" in n for n in names)
    assert sorted(res.files) == sorted(names)
    info = json.loads(entries["app_info.json"])
    assert info["servers_count"] == 1 and info["app_version"]
    doctor = json.loads(entries["doctor.json"])
    assert doctor["results"] and set(doctor["summary"]) >= {"OK", "AVISO", "ERRO"}


def test_nenhum_segredo_no_zip(env):
    res = _collect(env)
    for name, data in _read_all(res.path).items():
        text = data.decode("utf-8", errors="replace")
        for secret in ALL_SECRETS:
            assert secret not in text, f"{secret!r} vazou em {name}"


def test_mascara_preserva_estrutura_e_valores_nao_sensiveis(env):
    entries = _read_all(_collect(env).path)
    gus = _find(entries, "ini/GameUserSettings.ini")
    assert f"ServerAdminPassword={REDACTED}" in gus and f"ServerPassword={REDACTED}" in gus
    plugin_cfg = json.loads(_find(entries, "plugins/CustomShop/config.json"))
    assert plugin_cfg["ApiKey"] == REDACTED and plugin_cfg["Token"] == REDACTED
    assert plugin_cfg["Enabled"] is True and plugin_cfg["Interval"] == 30 and plugin_cfg["ApiUrl"] == "https://loja.test"
    cfg = json.loads(entries["config/config.json"])
    assert cfg["shop"]["api_key"] == REDACTED and cfg["smtp"]["password"] == REDACTED
    assert cfg["discord"]["webhook_url"] == REDACTED
    assert cfg["steamcmd_path"] == "C:/steamcmd" and cfg["smtp"]["host"] == "smtp.test"
    arkapi_log = _find(entries, "arkapi/logs/")
    assert "[info] start" in arkapi_log and SECRET_PLUGIN_TOKEN not in arkapi_log


def test_varredura_por_valor_pega_segredo_solto_no_log(env):
    """O valor de api_key aparece no log sem a chave ao lado — só a varredura por valor pega."""
    text = _find(_read_all(_collect(env).path), "logs/arkland.log")
    assert SECRET_API_KEY not in text and "linha normal" in text and REDACTED in text


def test_arquivos_com_nome_sensivel_sao_pulados(env):
    entries = _read_all(_collect(env).path)
    assert not any("discord_token" in n for n in entries)


def test_estado_do_servidor_nao_inclui_senha_e_traz_toggle_e_permissions(env):
    entries = _read_all(_collect(env).path)
    state = json.loads(_find(entries, "/state.json"))
    assert state["admin_password_set"] is True and "admin_password" not in state
    assert state["player_level_progressions_enabled"] is True
    assert state["server_exe_present"] is True and state["install_dir_exists"] is True
    assert state["ini_files"]["Game.ini"]["exists"] is True
    plugins = json.loads(_find(entries, "arkapi/plugins.json"))
    assert plugins["permissions_dll_present"] is True and plugins["version_dll_present"] is True
    names = {p["name"]: p for p in plugins["plugins"]}
    assert names["CustomShop"]["main_dll_present"] and names["CustomShop"]["config_present"]
    assert names["SemConfig"]["config_present"] is False


def test_doctor_results_injetados_sao_usados(env):
    fake = [CheckResult("x", "Teste", "ERRO", "detalhe falso", "dica")]
    res = _collect(env, doctor_results=fake)
    assert res.doctor_summary == {"OK": 0, "AVISO": 0, "ERRO": 1}
    doctor_txt = _find(_read_all(res.path), "doctor.txt")
    assert "detalhe falso" in doctor_txt


def test_sem_servidores_nem_logs_ainda_gera_pacote(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path / "ad"))
    res = col.collect_diagnostics(config_dir=tmp_path / "vazio", out_dir=tmp_path / "o", mode="classic",
                                  run_doctor_checks=False)
    entries = _read_all(res.path)
    assert "app_info.json" in entries and not any(n.startswith("servers/") for n in entries)


def test_servidor_com_install_dir_inexistente_nao_aborta(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path / "ad"))
    cdir = write_config_dir(tmp_path / "cfg", tek=[tek_entry(tmp_path / "nao_existe")])
    res = col.collect_diagnostics(config_dir=cdir, out_dir=tmp_path / "o", mode="tek", run_doctor_checks=False)
    state = json.loads(_find(_read_all(res.path), "/state.json"))
    assert state["install_dir_exists"] is False


def test_nome_do_zip_nao_colide(env):
    a = _collect(env)
    b = _collect(env)
    assert a.path != b.path and a.path.exists() and b.path.exists()


def test_limite_de_tamanho_reduz_logs(env, monkeypatch):
    monkeypatch.setattr(col, "DEFAULT_LOG_BUDGET_BYTES", 400_000)
    big = "\n".join(os.urandom(24).hex() for _ in range(25_000))       # ~1,2 MB pouco compressível
    (env["cdir"] / "logs" / "arkland.log").write_text(big, encoding="utf-8")
    unlimited = _collect(env, max_zip_bytes=50 * 1024 * 1024, run_doctor_checks=False)
    limit = unlimited.size // 2
    res = _collect(env, max_zip_bytes=limit, run_doctor_checks=False)
    assert not res.over_limit and res.size <= limit
    log = _find(_read_all(res.path), "logs/arkland.log")
    assert "truncado" in log
    assert len(log) < 400_000


def test_over_limit_sinalizado_e_zip_mantido(env):
    res = _collect(env, max_zip_bytes=300, run_doctor_checks=False)
    assert res.over_limit and res.path.exists()
    assert any("acima do limite" in w for w in res.warnings)
    assert not list(env["out"].glob("*.part"))


def test_discord_max_menor_que_webstore_max():
    assert col.DISCORD_MAX_ZIP_BYTES < col.DEFAULT_MAX_ZIP_BYTES


def test_tail_bytes_alinha_no_inicio_de_linha(tmp_path):
    p = tmp_path / "x.log"
    p.write_text("\n".join(f"linha-{i:04d}" for i in range(100)), encoding="utf-8")
    data, truncated = col._tail_bytes(p, 55)
    assert truncated and data.decode().startswith("linha-")
    data, truncated = col._tail_bytes(p, 10_000)
    assert not truncated and data.decode().startswith("linha-0000")
