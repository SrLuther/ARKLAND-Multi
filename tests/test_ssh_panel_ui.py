from __future__ import annotations

from types import SimpleNamespace

from src.pages import ssh_panel


class _Widget:
    def __init__(self, *_args, text="", command=None, **_kwargs):
        self.text = text
        self.command = command
        self.options = {}
        self.children = []
        self.content = ""
        self.state = "normal"

    def grid(self, *_args, **_kwargs): pass
    def pack(self, *_args, **_kwargs): pass
    def grid_columnconfigure(self, *_args, **_kwargs): pass
    def grid_rowconfigure(self, *_args, **_kwargs): pass
    def configure(self, **kwargs):
        self.options.update(kwargs)
        self.state = kwargs.get("state", self.state)
        self.command = kwargs.get("command", self.command)
    def insert(self, _index, text): self.content += text
    def delete(self, *_args): self.content = ""
    def destroy(self): pass
    def winfo_exists(self): return True
    def winfo_children(self): return self.children
    def set(self, *_args): pass


class _Var:
    def __init__(self, value=""): self.value = value
    def get(self): return self.value
    def set(self, value): self.value = value


class _Terminal(_Widget):
    def __init__(self, *_args, **_kwargs): super().__init__()
    def disconnect(self): pass


def test_ssh_panel_local_diagnostic_button_runs_and_renders_result(monkeypatch, tmp_path):
    buttons = []
    textboxes = []
    scheduled = []

    def make_button(*args, **kwargs):
        button = _Widget(*args, **kwargs)
        buttons.append(button)
        return button

    for name in ("CTkFrame", "CTkLabel", "CTkScrollableFrame", "CTkTextbox",
                 "CTkToplevel", "CTkEntry", "CTkOptionMenu", "CTkCheckBox"):
        monkeypatch.setattr(ssh_panel.ctk, name, _Widget)
    monkeypatch.setattr(ssh_panel.ctk, "CTkButton", make_button)
    def make_textbox(*args, **kwargs):
        widget = _Widget(*args, **kwargs)
        textboxes.append(widget)
        return widget
    monkeypatch.setattr(ssh_panel.ctk, "CTkTextbox", make_textbox)
    monkeypatch.setattr(ssh_panel.ctk, "CTkFont", lambda **_kwargs: None)
    monkeypatch.setattr(ssh_panel.ctk, "StringVar", _Var)
    monkeypatch.setattr(ssh_panel.ctk, "BooleanVar", _Var)
    monkeypatch.setattr(ssh_panel, "TerminalView", _Terminal)

    class Store:
        path = tmp_path / "ssh-profiles.json"
        def load(self): return []
        def save(self, _profiles): pass

    class HostKeys:
        def get(self, *_args): return None

    class Vault:
        def get_secret(self, *_args): return None
        def set_secret(self, *_args): pass
        def delete_profile_secrets(self, *_args): pass

    monkeypatch.setattr(ssh_panel, "SSHProfileStore", Store)
    monkeypatch.setattr(ssh_panel, "HostKeyStore", HostKeys)
    monkeypatch.setattr(ssh_panel, "WindowsCredentialVault", Vault)
    monkeypatch.setattr(ssh_panel, "SSHService", lambda **_kwargs: object())
    monkeypatch.setattr(
        ssh_panel, "run_local_diagnostics",
        lambda: [SimpleNamespace(status="Aprovado", name="Cliente SSH", detail="OpenSSH disponível", owner="Local")],
    )
    monkeypatch.setattr(
        ssh_panel, "_worker",
        lambda _app, work_queue, label, fn, *args, **kwargs:
            work_queue.put((label, fn(*args, **kwargs), None)),
    )

    class Parent(_Widget):
        def after(self, _delay, callback): scheduled.append(callback)

    parent = Parent()
    app = SimpleNamespace(asm_config_manager=SimpleNamespace(servers=[]))
    ssh_panel.build_ssh_panel(app, parent)

    button = next(btn for btn in buttons if btn.text == "Verificar ambiente local")
    assert callable(button.command)
    button.command()
    assert button.state == "disabled"
    # Process one queued result on the UI side, as Tk's after loop does.
    scheduled.pop(0)()
    assert button.state == "normal"
    assert any("OpenSSH disponível" in widget.content for widget in textboxes)


def test_ssh_panel_source_has_readable_portuguese_text():
    source = ssh_panel.__file__
    text = open(source, encoding="utf-8").read()
    assert "mÃ¡quina" not in text
    assert "conexÃ£o" not in text
    assert "DiagnÃ³stico" not in text
    assert "máquina autorizada" in text
    assert "Diagnóstico SSH" in text
