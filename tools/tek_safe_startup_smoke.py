"""Build the TEK UI in an isolated temporary profile without startup actions."""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="arkland-tek-safe-startup-") as temp_dir:
        os.environ["ARKLAND_SAFE_STARTUP_TEST"] = "1"
        os.environ["ARKLAND_SAFE_TEST_DATA"] = temp_dir

        from src.app_tek import ARKServerManagerApp

        app = ARKServerManagerApp()
        try:
            app.update_idletasks()
            assert app._safe_startup_test is True
            assert app.asm_config_manager.servers == []
            assert app.config_manager.servers == []
            assert Path(os.environ["APPDATA"]).resolve() == Path(temp_dir).resolve()
            print("TEK_UI_SAFE_STARTUP_OK: dashboard constructed; no profiles or startup jobs loaded")
        finally:
            app.destroy()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
