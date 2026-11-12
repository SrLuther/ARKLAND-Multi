from pathlib import Path

from src.ark_ini import ArkIniManager
from src.pages import ini_save as ini_save_module
from src.pages.ini_save import ini_save
from src.server_config import ServerConfig


class _ConfigManager:
    def __init__(self, server):
        self.server = server

    def get_server(self, _server_id):
        return self.server

    def update_server(self, server):
        self.server = server


class _App:
    def __init__(self, server, widgets):
        self.config_manager = _ConfigManager(server)
        self._server_widgets = {server.id: widgets}
        self.messages = []

    def _ini_flush_current(self, *_args):
        pass

    def _global_log(self, message, level):
        self.messages.append((message, level))


def test_classic_ini_save_removes_deleted_mod_bucket_and_preserves_external(tmp_path, monkeypatch):
    srv = ServerConfig(
        id="server-1",
        install_dir=str(tmp_path),
        mod_ini_configs={
            "mod-1": {"gus_ini": "[VisibleMod]\nKeepThis=True"},
            "mod-removed": {"gus_ini": "[RemovedMod]\nOldOption=True"},
        },
    )
    gus_path = Path(tmp_path) / "ShooterGame/Saved/Config/WindowsServer/GameUserSettings.ini"
    gus_path.parent.mkdir(parents=True)
    gus_path.write_text("[ExternalPlugin]\nLeaveMe=1\n", encoding="utf-8")
    ArkIniManager(str(tmp_path)).apply_mod_ini_configs(srv.mod_ini_configs)

    widgets = {
        "_ini_gus_data": [
            {"section": "VisibleMod", "mod_id": "mod-1", "entries": [
                {"key": "KeepThis", "value": "True"},
            ]},
        ],
        "_ini_game_data": [],
    }
    app = _App(srv, widgets)
    monkeypatch.setattr(ini_save_module.messagebox, "showinfo", lambda *_a, **_k: None)

    ini_save(app, srv.id)

    assert "mod-removed" not in srv.mod_ini_configs
    gus_bytes = gus_path.read_bytes()
    assert not gus_bytes.startswith((b"\xff\xfe", b"\xfe\xff", b"\xef\xbb\xbf"))
    assert "[RemovedMod]" not in gus_bytes.decode("utf-8")
    text = gus_bytes.decode("utf-8")
    assert "KeepThis=True" in text
    assert "LeaveMe=1" in text


def test_classic_ini_save_does_not_clear_file_not_loaded_in_editor(tmp_path, monkeypatch):
    srv = ServerConfig(
        id="server-2",
        install_dir=str(tmp_path),
        mod_ini_configs={"mod-1": {"gus_ini": "[Existing]\nKeep=True"}},
    )
    gus_path = Path(tmp_path) / "ShooterGame/Saved/Config/WindowsServer/GameUserSettings.ini"
    gus_path.parent.mkdir(parents=True)
    ArkIniManager(str(tmp_path)).apply_mod_ini_configs(srv.mod_ini_configs)

    app = _App(srv, {})
    monkeypatch.setattr(ini_save_module.messagebox, "showinfo", lambda *_a, **_k: None)
    ini_save(app, srv.id)

    assert "mod-1" in srv.mod_ini_configs
    gus_bytes = gus_path.read_bytes()
    assert gus_bytes.startswith(b"\xff\xfe")
    assert "Keep=True" in gus_bytes.decode("utf-16")
