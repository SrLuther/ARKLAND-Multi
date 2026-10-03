"""Fumaça da página «Diagnóstico» (customtkinter real; pula se não houver display)."""
from __future__ import annotations

import time
from types import SimpleNamespace

import pytest

ctk = pytest.importorskip("customtkinter")

from src.diagnostics import paths
from src.diagnostics.doctor import CheckResult
from src.pages import build_diagnostics as bd


@pytest.fixture(scope="module")
def _tk_root():
    # customtkinter não tolera criar/destruir várias raízes no mesmo processo → uma por módulo.
    try:
        r = ctk.CTk()
    except Exception as exc:  # noqa: BLE001 — sem display/Tcl
        pytest.skip(f"sem display: {exc}")
    r.withdraw()
    yield r
    try:
        r.destroy()
    except Exception:  # noqa: BLE001
        pass


@pytest.fixture()
def root(_tk_root, tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    for w in _tk_root.winfo_children():          # limpa páginas de testes anteriores
        w.destroy()
    for attr in ("_diagnostics_page", "config_manager", "asm_config_manager"):
        if hasattr(_tk_root, attr):
            delattr(_tk_root, attr)
    return _tk_root


def _pump(root, cond, timeout=15.0):
    """Roda o mainloop real (threads de fundo só podem agendar ``after`` com o mainloop ativo)."""
    end = time.time() + timeout
    state = {"ok": False}

    def tick():
        if cond():
            state["ok"] = True
            root.quit()
        elif time.time() > end:
            root.quit()
        else:
            root.after(20, tick)

    root.after(20, tick)
    root.mainloop()
    return state["ok"]


def _page(root, mode="tek"):
    root._active_mode = mode
    frame = ctk.CTkScrollableFrame(root)
    frame.pack(fill="both", expand=True)
    bd.build_diagnostics(root, frame)
    root.update()
    return root._diagnostics_page


@pytest.mark.parametrize("mode", ["primitive", "tek"])
def test_pagina_constroi_nos_dois_temas(root, mode):
    page = _page(root, mode)
    for attr in ("doctor_btn", "zip_btn", "discord_btn", "webstore_btn", "webhook_entry", "level_var"):
        assert hasattr(page, attr), attr
    assert page.discord_btn.cget("text").endswith("Enviar para Discord")
    assert "Web Store" in page.webstore_btn.cget("text")


def test_verificar_saude_mostra_resultados_coloridos(root, monkeypatch):
    page = _page(root)
    fake = [CheckResult("a", "Ruim", "ERRO", "detalhe", "dica"), CheckResult("b", "Meh", "AVISO", "d2"),
            CheckResult("c", "Bom", "OK", "d3")]
    import src.diagnostics.doctor as doctor_mod
    monkeypatch.setattr(doctor_mod, "run_doctor", lambda ctx, timeout=15, on_result=None, checks=None: fake)
    page._on_doctor()
    assert _pump(root, lambda: bool(page.results))
    text = page.doctor_status.cget("text")
    assert "1 OK" in text and "1 aviso" in text and "1 erro" in text
    assert page.busy is False
    colors = {w.cget("text"): w.cget("text_color") for w in page.results_frame.winfo_children()
              if isinstance(w, ctk.CTkLabel)}
    assert colors["✖ ERRO"] == bd._SEV_COLOR["ERRO"] and colors["✔ OK"] == bd._SEV_COLOR["OK"]


def test_gerar_zip_nao_bloqueia_e_cria_arquivo(root, monkeypatch, tmp_path):
    page = _page(root)
    opened = []
    monkeypatch.setattr(bd, "open_in_explorer", lambda p: opened.append(p))
    page.results = [CheckResult("x", "T", "OK", "d")]
    page._on_generate()
    assert page.busy is True
    assert _pump(root, lambda: bool(opened))
    zips = list(paths.diagnostics_dir().glob("*.zip"))
    assert len(zips) == 1 and opened[0] == zips[0]
    assert "Gerado" in page.zip_status.cget("text") and page.busy is False


def test_discord_exige_webhook_valido_e_confirmacao(root, monkeypatch):
    page = _page(root)
    sent = []
    monkeypatch.setattr(page, "_start_send", lambda *a, **k: sent.append(a))

    page.webhook_var.set("https://evil.test/hook")
    page._on_send_discord()
    assert not sent and "válida" in page.send_status.cget("text")

    page.webhook_var.set("https://discord.com/api/webhooks/123456789012345678/AbCdEf_ghIJkl")
    monkeypatch.setattr(bd.messagebox, "askyesno", lambda *a, **k: False)     # usuário cancela
    page._on_send_discord()
    assert not sent
    assert paths.load_prefs()["discord_webhook_url"].endswith("AbCdEf_ghIJkl")  # persistido

    asked = []
    monkeypatch.setattr(bd.messagebox, "askyesno", lambda title, msg, **k: asked.append(msg) or True)
    page._on_send_discord()
    assert len(sent) == 1
    assert "mascarados" in asked[0] and "SteamIDs" in asked[0]


def test_webstore_sem_config_mostra_mensagem_e_nao_envia(root, monkeypatch):
    page = _page(root)
    sent = []
    monkeypatch.setattr(page, "_start_send", lambda *a, **k: sent.append(a))
    shop = SimpleNamespace(mode="client", central_url="https://loja.test", public_url="https://loja.test",
                           host_ip="", port=27199, api_key="")
    root.config_manager = SimpleNamespace(config=SimpleNamespace(shop=shop))
    page._on_send_webstore()
    assert not sent and "API key" in page.send_status.cget("text")

    root.config_manager = None                       # configuração ilegível → mensagem, sem exceção
    page._on_send_webstore()
    assert not sent and "Não foi possível" in page.send_status.cget("text")


def test_falha_inesperada_no_envio_vira_mensagem(root, monkeypatch):
    page = _page(root)

    def boom():
        raise RuntimeError("explodiu")

    page._start_send("enviando…", boom)
    assert _pump(root, lambda: not page.busy)
    assert "Falha inesperada" in page.send_status.cget("text")


def test_falha_ao_gerar_zip_vira_mensagem_e_libera_botoes(root, monkeypatch):
    page = _page(root)

    def boom(*a, **k):
        raise OSError("disco cheio")

    monkeypatch.setattr(page, "_collect", boom)
    page._on_generate()
    assert _pump(root, lambda: not page.busy)
    text = page.zip_status.cget("text")
    assert "Falha ao gerar" in text and "disco cheio" in text


def test_mudar_nivel_de_log_persiste(root, monkeypatch):
    page = _page(root)
    called = []
    import src.diagnostics.logging_setup as ls
    monkeypatch.setattr(ls, "set_log_level", lambda v, persist=True: called.append(v))
    page._on_level_change("DEBUG")
    assert called == ["DEBUG"]
