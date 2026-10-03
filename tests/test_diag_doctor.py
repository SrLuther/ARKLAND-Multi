"""Doctor (src/diagnostics/doctor.py): cada checagem em cenário feliz e de erro."""
from __future__ import annotations

import time
import urllib.error
from collections import namedtuple
from pathlib import Path

import pytest

from _diag_synth import make_server_dir, tek_entry, write_config_dir
from src.diagnostics import doctor as dr
from src.diagnostics.doctor import (
    SEV_ERR, SEV_OK, SEV_WARN, CheckResult, DoctorContext, err, ok, run_doctor, summarize, worst_severity,
)


def _ctx(tmp_path, tek=None, classic=None, config=None) -> DoctorContext:
    cdir = write_config_dir(tmp_path / "cfg", tek=tek, classic=classic, config=config)
    return DoctorContext.from_config_dir(cdir)


def _by_id(results, fragment):
    return [r for r in results if fragment in r.id]


# ── runner ───────────────────────────────────────────────────────────────────

def test_runner_converte_excecao_em_erro_e_continua(tmp_path):
    def boom(ctx):
        raise RuntimeError("falha simulada")

    def fine(ctx):
        return ok("fine", "Fine", "tudo bem")

    res = run_doctor(_ctx(tmp_path), checks=[("boom", "Boom", boom), ("fine", "Fine", fine)], timeout=2)
    assert [r.id for r in res] == ["boom", "fine"]
    assert res[0].severity == SEV_ERR and "RuntimeError" in res[0].detail and "falha simulada" in res[0].detail
    assert res[1].severity == SEV_OK


def test_runner_timeout_vira_erro(tmp_path):
    def slow(ctx):
        time.sleep(3)
        return ok("slow", "Slow")

    t0 = time.time()
    res = run_doctor(_ctx(tmp_path), checks=[("slow", "Slow", slow)], timeout=0.2)
    assert time.time() - t0 < 2.5
    assert res[0].severity == SEV_ERR and "Tempo esgotado" in res[0].detail


def test_runner_aceita_lista_e_callback(tmp_path):
    seen = []

    def many(ctx):
        return [ok("a", "A"), err("b", "B", "x")]

    res = run_doctor(_ctx(tmp_path), checks=[("many", "Many", many)], timeout=2, on_result=seen.append)
    assert [r.id for r in res] == ["a", "b"] and len(seen) == 2
    assert summarize(res) == {SEV_OK: 1, SEV_WARN: 0, SEV_ERR: 1}
    assert worst_severity(res) == SEV_ERR
    assert "Resumo: 1 OK" in dr.format_report(res)


def test_registro_de_checagens_cobre_o_minimo():
    ids = {c[0] for c in dr.CHECKS}
    assert {"python_deps", "config_files", "steamcmd", "disk_space", "backup_paths", "ports_duplicated",
            "webstore", "server_install", "server_inis", "server_admin_password", "server_arkapi",
            "server_plugins", "server_permissions", "server_level_toggle"} <= ids


def test_checks_reais_nunca_levantam_com_ambiente_vazio(tmp_path):
    ctx = _ctx(tmp_path)
    res = run_doctor(ctx, timeout=10)
    assert res and all(isinstance(r, CheckResult) for r in res)
    assert not [r for r in res if "A checagem falhou" in r.detail]


# ── install_dir / INIs ───────────────────────────────────────────────────────

def test_install_ok(tmp_path):
    inst = make_server_dir(tmp_path / "srv")
    res = dr.check_server_install(_ctx(tmp_path, tek=[tek_entry(inst)]))
    assert res[0].severity == SEV_OK


def test_install_sem_exe_pasta_inexistente_e_vazio(tmp_path):
    no_exe = make_server_dir(tmp_path / "noexe", exe=False)
    entries = [
        tek_entry(no_exe, id_="11111111", name="SemExe"),
        tek_entry(tmp_path / "nao_existe", id_="22222222", name="Fantasma", server_port=7779, query_port=27017),
        tek_entry(Path(""), id_="33333333", name="Vazio", server_port=7781, query_port=27019),
    ]
    entries[2]["install_dir"] = ""
    res = dr.check_server_install(_ctx(tmp_path, tek=entries))
    assert [r.severity for r in res] == [SEV_ERR, SEV_ERR, SEV_ERR]
    assert "ShooterGameServer.exe" in res[0].detail and "inexistente" in res[1].detail
    assert "não configurado" in res[2].detail


def test_inis_legiveis_ausentes_e_vazios(tmp_path):
    inst = make_server_dir(tmp_path / "ok")
    res = dr.check_server_inis(_ctx(tmp_path, tek=[tek_entry(inst)]))
    assert {r.severity for r in res} == {SEV_OK}

    ini_dir = inst / "ShooterGame" / "Saved" / "Config" / "WindowsServer"
    (ini_dir / "Game.ini").write_text("", encoding="utf-8")
    (ini_dir / "GameUserSettings.ini").unlink()
    res = dr.check_server_inis(_ctx(tmp_path, tek=[tek_entry(inst)]))
    by = {("GameUserSettings.ini" if "GameUserSettings" in r.id else "Game.ini"): r for r in res}
    assert by["GameUserSettings.ini"].severity == SEV_WARN and "Não existe" in by["GameUserSettings.ini"].detail
    assert by["Game.ini"].severity == SEV_WARN and "vazio" in by["Game.ini"].detail


def test_inis_utf16_sao_lidos(tmp_path):
    inst = make_server_dir(tmp_path / "u16")
    p = inst / "ShooterGame" / "Saved" / "Config" / "WindowsServer" / "Game.ini"
    p.write_bytes("[x]\nA=1\n".encode("utf-16"))
    res = dr.check_server_inis(_ctx(tmp_path, tek=[tek_entry(inst)]))
    assert [r.severity for r in res if "Game.ini" in r.id] == [SEV_OK]


# ── senha admin ──────────────────────────────────────────────────────────────

def test_admin_password(tmp_path):
    inst = make_server_dir(tmp_path / "a")
    inst2 = make_server_dir(tmp_path / "b")
    ctx = _ctx(tmp_path, tek=[
        tek_entry(inst, id_="aaaaaaaa", name="Com"),
        tek_entry(inst2, id_="bbbbbbbb", name="Sem", admin_password="   ", server_port=7779, query_port=27017),
    ])
    res = dr.check_admin_password(ctx)
    assert [r.severity for r in res] == [SEV_OK, SEV_ERR]
    assert "em branco" in res[1].detail


# ── ArkApi / plugins / Permissions ───────────────────────────────────────────

def test_arkapi_ausente_aviso_instalado_ok_sem_loader_aviso(tmp_path):
    none = make_server_dir(tmp_path / "n", arkapi=False)
    assert dr.check_arkapi(_ctx(tmp_path / "x1", tek=[tek_entry(none)]))[0].severity == SEV_WARN

    good = make_server_dir(tmp_path / "g", plugins={"Permissions": {"config": "{}"}})
    assert dr.check_arkapi(_ctx(tmp_path / "x2", tek=[tek_entry(good)]))[0].severity == SEV_OK

    noloader = make_server_dir(tmp_path / "nl", loader=False, plugins={"Foo": {"config": "{}"}})
    r = dr.check_arkapi(_ctx(tmp_path / "x3", tek=[tek_entry(noloader)]))[0]
    assert r.severity == SEV_WARN and "version.dll" in r.detail


def test_plugins_dll_pasta_e_config(tmp_path):
    inst = make_server_dir(tmp_path / "p", plugins={
        "Good": {"config": "{}"},
        "SemDll": {"dll": False, "config": "{}"},
        "SemConfig": {"config": None},
    })
    (inst / "ShooterGame" / "Binaries" / "Win64" / "ArkApi" / "Plugins" / "solta.dll").write_bytes(b"MZ")
    res = dr.check_plugins(_ctx(tmp_path, tek=[tek_entry(inst)]))
    by = {r.id.split("plugin.")[-1]: r for r in res if "plugin." in r.id}
    assert by["Good"].severity == SEV_OK
    assert by["SemDll"].severity == SEV_ERR and "SemDll.dll ausente" in by["SemDll"].detail
    assert by["SemConfig"].severity == SEV_WARN and "config.json ausente" in by["SemConfig"].detail
    loose = [r for r in res if "plugins_loose" in r.id]
    assert loose and loose[0].severity == SEV_WARN and "solta.dll" in loose[0].detail


def test_permissions_dll_presente(tmp_path):
    inst = make_server_dir(tmp_path / "pp", permissions=True, plugins={"CustomShop": {"config": "{}"}})
    r = dr.check_permissions_dll(_ctx(tmp_path, tek=[tek_entry(inst)]))[0]
    assert r.severity == SEV_OK and "Permissions.dll" in r.detail


def test_permissions_dll_ausente_com_plugin_dependente_e_erro(tmp_path):
    inst = make_server_dir(tmp_path / "pe", plugins={"ArkEventHunt": {"config": "{}"}})
    r = dr.check_permissions_dll(_ctx(tmp_path, tek=[tek_entry(inst)]))[0]
    assert r.severity == SEV_ERR
    assert "ArkEventHunt" in r.detail
    expected = Path("ArkApi") / "Plugins" / "Permissions"
    assert str(expected) in r.hint


def test_permissions_dll_ausente_sem_dependentes_e_aviso(tmp_path):
    inst = make_server_dir(tmp_path / "pw", plugins={"Outro": {"config": "{}"}})
    r = dr.check_permissions_dll(_ctx(tmp_path, tek=[tek_entry(inst)]))[0]
    assert r.severity == SEV_WARN


def test_permissions_ignorado_sem_arkapi(tmp_path):
    inst = make_server_dir(tmp_path / "pn", arkapi=False)
    assert dr.check_permissions_dll(_ctx(tmp_path, tek=[tek_entry(inst)])) == []


def test_permissions_dll_em_caminho_errado_nao_conta(tmp_path):
    inst = make_server_dir(tmp_path / "pc", plugins={"CustomShop": {"config": "{}"}})
    wrong = inst / "ShooterGame" / "Binaries" / "Win64" / "ArkApi" / "Plugins" / "Permissions.dll"
    wrong.write_bytes(b"MZ")      # solta, fora de Permissions\
    assert dr.check_permissions_dll(_ctx(tmp_path, tek=[tek_entry(inst)]))[0].severity == SEV_ERR


# ── toggle de progressões de nível ───────────────────────────────────────────

RAMP = ("[/script/shootergame.shootergamemode]\n"
        "LevelExperienceRampOverrides=(ExperiencePointsForLevel[0]=5)\n"
        "OverrideMaxExperiencePointsPlayer=100\n"
        "OverridePlayerLevelEngramPoints=10\n")


def test_toggle_off_com_chaves_no_game_ini_e_erro(tmp_path):
    inst = make_server_dir(tmp_path / "t1", game_ini=RAMP)
    r = dr.check_level_toggle(_ctx(tmp_path, tek=[tek_entry(inst, progressions=False)]))[0]
    assert r.severity == SEV_ERR
    for key in ("LevelExperienceRampOverrides", "OverrideMaxExperiencePointsPlayer",
                "OverridePlayerLevelEngramPoints"):
        assert key in r.detail


def test_toggle_on_sem_rampa_e_aviso(tmp_path):
    inst = make_server_dir(tmp_path / "t2", game_ini="[/script/shootergame.shootergamemode]\nFoo=1\n")
    r = dr.check_level_toggle(_ctx(tmp_path, tek=[tek_entry(inst, progressions=True)]))[0]
    assert r.severity == SEV_WARN and "LevelExperienceRampOverrides" in r.detail


def test_toggle_consistente_on_e_off(tmp_path):
    on = make_server_dir(tmp_path / "t3", game_ini=RAMP)
    off = make_server_dir(tmp_path / "t4", game_ini="[/script/shootergame.shootergamemode]\n")
    res = dr.check_level_toggle(_ctx(tmp_path, tek=[
        tek_entry(on, id_="aaaaaaaa", name="On", progressions=True),
        tek_entry(off, id_="bbbbbbbb", name="Off", progressions=False, server_port=7779, query_port=27017),
    ]))
    assert [r.severity for r in res] == [SEV_OK, SEV_OK]
    assert "Consistente" in res[0].detail


def test_toggle_ignora_servidor_sem_o_campo_e_game_ini_inexistente(tmp_path):
    inst = make_server_dir(tmp_path / "t5", game_ini=None)
    assert dr.check_level_toggle(_ctx(tmp_path, tek=[tek_entry(inst)])) == []
    r = dr.check_level_toggle(_ctx(tmp_path / "y", tek=[tek_entry(inst, progressions=False)]))[0]
    assert r.severity == SEV_OK and "nada a comparar" in r.detail


def test_toggle_detecta_chaves_em_utf16(tmp_path):
    inst = make_server_dir(tmp_path / "t6")
    p = inst / "ShooterGame" / "Saved" / "Config" / "WindowsServer" / "Game.ini"
    p.write_bytes(RAMP.encode("utf-16"))
    assert dr.check_level_toggle(_ctx(tmp_path, tek=[tek_entry(inst, progressions=False)]))[0].severity == SEV_ERR


# ── portas ───────────────────────────────────────────────────────────────────

def test_portas_duplicadas(tmp_path):
    a = make_server_dir(tmp_path / "a")
    b = make_server_dir(tmp_path / "b")
    clash = dr.check_ports_duplicated(_ctx(tmp_path, tek=[
        tek_entry(a, id_="aaaaaaaa", name="A"),
        tek_entry(b, id_="bbbbbbbb", name="B", server_port=7779, query_port=27015, rcon_port=27021),
    ]))
    assert clash.severity == SEV_ERR and "UDP 27015" in clash.detail and "A" in clash.detail and "B" in clash.detail


def test_portas_duplicadas_entre_tek_e_classico_e_raw_socket(tmp_path):
    a = make_server_dir(tmp_path / "a")
    b = make_server_dir(tmp_path / "b")
    classic = {"id": "cccccccc", "name": "Classico", "install_dir": str(b),
               "server_port": 7778, "query_port": 27016, "rcon_port": 27022, "admin_password": "x"}
    res = dr.check_ports_duplicated(_ctx(tmp_path, tek=[tek_entry(a, raw_sockets=True)], classic=[classic]))
    assert res.severity == SEV_ERR and "UDP 7778" in res.detail      # raw = jogo+1


def test_portas_unicas_ok(tmp_path):
    a = make_server_dir(tmp_path / "a")
    b = make_server_dir(tmp_path / "b")
    res = dr.check_ports_duplicated(_ctx(tmp_path, tek=[
        tek_entry(a, id_="aaaaaaaa", name="A"),
        tek_entry(b, id_="bbbbbbbb", name="B", server_port=7779, query_port=27017, rcon_port=27021),
    ]))
    assert res.severity == SEV_OK


# ── globais ──────────────────────────────────────────────────────────────────

def test_config_json_invalido_e_erro_e_corrompidos_avisam(tmp_path):
    cdir = tmp_path / "cfg"
    cdir.mkdir()
    (cdir / "config.json").write_text("{ nao e json", encoding="utf-8")
    (cdir / "servers.json").write_text("[]", encoding="utf-8")
    (cdir / "config.json.corrupt-20260101").write_text("x", encoding="utf-8")
    res = dr.check_config_files(DoctorContext.from_config_dir(cdir))
    by = {r.id: r.severity for r in res}
    assert by["config_files.config.json"] == SEV_ERR
    assert by["config_files.servers.json"] == SEV_OK
    assert by["config_files.corrupt"] == SEV_WARN


def test_config_json_ausente_e_aviso(tmp_path):
    res = dr.check_config_files(_ctx(tmp_path))
    assert res[0].id == "config_files.config.json" and res[0].severity == SEV_WARN


def test_steamcmd(tmp_path):
    assert dr.check_steamcmd(_ctx(tmp_path, config={})).severity == SEV_WARN
    assert dr.check_steamcmd(_ctx(tmp_path, config={"steamcmd_path": str(tmp_path / "nada")})).severity == SEV_ERR
    folder = tmp_path / "steamcmd"
    folder.mkdir()
    (folder / "steamcmd.exe").write_bytes(b"MZ")
    assert dr.check_steamcmd(_ctx(tmp_path, config={"steamcmd_path": str(folder)})).severity == SEV_OK
    assert dr.check_steamcmd(_ctx(tmp_path, config={"steamcmd_path": str(folder / "steamcmd.exe")})).severity == SEV_OK


@pytest.mark.parametrize("free_gb,expected", [(1, SEV_ERR), (5, SEV_WARN), (50, SEV_OK)])
def test_disk_space(tmp_path, monkeypatch, free_gb, expected):
    Usage = namedtuple("Usage", "total used free")
    monkeypatch.setattr(dr.shutil, "disk_usage", lambda p: Usage(10**12, 0, int(free_gb * 1024 ** 3)))
    res = dr.check_disk_space(_ctx(tmp_path))
    assert res and {r.severity for r in res} == {expected}


def test_backup_paths(tmp_path, monkeypatch):
    monkeypatch.setenv("ARKLAND_BACKUP_ROOT", str(tmp_path / "bk"))
    # desativado e sem caminho → OK informativo
    assert {r.severity for r in dr.check_backup_paths(_ctx(tmp_path, config={}))} == {SEV_OK}
    # habilitado, pasta existente e gravável → OK
    good = tmp_path / "good"
    good.mkdir()
    cfg = {"backup": {"auto_backup": True, "backup_dir": str(good)}}
    assert dr.check_backup_paths(_ctx(tmp_path / "c1", config=cfg))[0].severity == SEV_OK
    # pasta ainda inexistente, mas pai existe → AVISO
    cfg = {"backup": {"auto_backup": True, "backup_dir": str(tmp_path / "novo" )}}
    assert dr.check_backup_paths(_ctx(tmp_path / "c2", config=cfg))[0].severity == SEV_WARN


def test_backup_paths_unidade_inexistente(tmp_path, monkeypatch):
    # caminho cujo "pai" não existe em lugar nenhum → ERRO (usa raiz inexistente simulada)
    monkeypatch.setattr(Path, "exists", lambda self: False)
    monkeypatch.setattr(Path, "is_dir", lambda self: False)
    ctx = DoctorContext(config_dir=tmp_path, app_config={"backup": {"auto_backup": True, "backup_dir": "Z:\\nada\\bk"}})
    assert dr.check_backup_paths(ctx)[0].severity == SEV_ERR


def test_servers_present(tmp_path):
    assert dr.check_servers_present(_ctx(tmp_path)).severity == SEV_WARN
    inst = make_server_dir(tmp_path / "s")
    assert dr.check_servers_present(_ctx(tmp_path / "z", tek=[tek_entry(inst)])).severity == SEV_OK


def test_python_deps_tolera_modulo_discord_inexistente(tmp_path, monkeypatch):
    real = dr.importlib.import_module

    def fake(name, *a, **k):
        if name == "discord":
            raise ModuleNotFoundError("No module named 'discord'")
        return real(name, *a, **k)

    monkeypatch.setattr(dr.importlib, "import_module", fake)
    res = dr.check_python_deps(_ctx(tmp_path))
    by = {r.id: r for r in res}
    assert by["python_deps"].severity == SEV_OK              # obrigatórias seguem OK
    assert by["python_deps_optional"].severity == SEV_WARN and "discord" in by["python_deps_optional"].detail


def test_python_deps_obrigatoria_ausente_e_erro(tmp_path, monkeypatch):
    real = dr.importlib.import_module

    def fake(name, *a, **k):
        if name == "requests":
            raise ImportError("sem requests")
        return real(name, *a, **k)

    monkeypatch.setattr(dr.importlib, "import_module", fake)
    assert {r.id: r for r in dr.check_python_deps(_ctx(tmp_path))}["python_deps"].severity == SEV_ERR


class _Resp:
    def __init__(self, status=200):
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


SHOP = {"mode": "client", "api_key": "k-123456", "central_url": "https://loja.test", "public_url": "https://loja.test"}


def test_webstore_nao_configurada_e_ok_sem_rede(tmp_path, monkeypatch):
    def forbid(*a, **k):
        raise AssertionError("não deveria acessar a rede")

    monkeypatch.setattr(dr.urllib.request, "urlopen", forbid)
    r = dr.check_webstore(_ctx(tmp_path, config={"shop": {"api_key": ""}}))
    assert r.severity == SEV_OK and "ignorada" in r.detail


def test_webstore_alcancavel_e_inalcancavel(tmp_path, monkeypatch):
    monkeypatch.setattr(dr.urllib.request, "urlopen", lambda req, timeout=None: _Resp(200))
    r = dr.check_webstore(_ctx(tmp_path, config={"shop": SHOP}))
    assert r.severity == SEV_OK and "loja.test" in r.detail

    def down(req, timeout=None):
        raise urllib.error.URLError("sem rota")

    monkeypatch.setattr(dr.urllib.request, "urlopen", down)
    r = dr.check_webstore(_ctx(tmp_path, config={"shop": SHOP}))
    assert r.severity == SEV_WARN and "URLError" in r.detail

    def http500(req, timeout=None):
        raise urllib.error.HTTPError(req.full_url, 500, "x", {}, None)

    monkeypatch.setattr(dr.urllib.request, "urlopen", http500)
    assert dr.check_webstore(_ctx(tmp_path, config={"shop": SHOP})).severity == SEV_WARN


def test_nenhum_segredo_vaza_nos_resultados(tmp_path):
    from _diag_synth import SECRET_ADMIN, SECRET_SERVER_PW
    inst = make_server_dir(tmp_path / "leak", game_ini=RAMP)
    res = run_doctor(_ctx(tmp_path, tek=[tek_entry(inst, progressions=False)]), timeout=10)
    blob = " ".join(f"{r.title} {r.detail} {r.hint}" for r in res)
    assert SECRET_ADMIN not in blob and SECRET_SERVER_PW not in blob
