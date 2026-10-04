"""Formato do texto de dano do ArkPlayer: 9000 → 9k, 27000 → 27k."""

import os
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HEADER = ROOT / "plugin/ArkPlayer/src/DamageFormat.h"
DAMAGE = ROOT / "plugin/ArkPlayer/src/PlayerDamage.cpp"

CASES = {
    2563000: "2.6kk",
    999: "999",
    1000000: "1kk",
    999500: "999.5k",
    95863: "95.9k",
    9000: "9k",
    27000: "27k",
    36000: "36k",
    100000000: "100kk",
    1000: "1k",
    1500: "1.5k",
}


def format_damage(amount: int) -> str:
    """Espelho de ArkPlayer::FormatDamageAmount."""
    if amount <= 0:
        return "0"
    ks = 0
    n = amount
    while n >= 1000 and ks < 8:
        nxt = n // 1000
        rem = n % 1000
        if nxt >= 1000:
            n = nxt
            ks += 1
            continue
        ks += 1
        tenth = (rem + 50) // 100
        n = nxt
        if tenth >= 10:
            n += 1
            tenth = 0
        if n >= 1000:
            continue
        out = str(n)
        if tenth:
            out += "." + str(tenth)
        out += "k" * ks
        return out
    return str(n)


def test_format_damage_examples():
    for amount, expected in CASES.items():
        got = format_damage(amount)
        assert got == expected
        assert "," not in got
        assert " " not in got


def test_plugin_sends_screen_text_and_keeps_damage():
    src = DAMAGE.read_text(encoding="utf-8")
    assert "FormatDamageAmount" in src
    assert "ClientServerSOTFNotificationCustom" not in src
    assert "ClientServerChatDirectMessage" not in src
    assert "SendChatMessage" not in src
    assert "pc->ClientAddFloatingText" in src
    assert "bShowFloatingDamageTextField()" in src
    assert "flag = true" in src
    assert re.search(r"(?<![\w])flag = false", src) is None
    assert "return applied" in src
    assert "damage =" not in src
    # O inteiro nativo (9,000) não é encaminhado.
    assert "Hook_AShooterPlayerController_ClientAddFloatingDamageText" in src
    assert "void Hook_AShooterPlayerController_ClientAddFloatingDamageText(AShooterPlayerController*, FVector_NetQuantize, int, int) {}" in src


def _vcvars64() -> Path:
    program_files_x86 = os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")
    vswhere = Path(program_files_x86) / "Microsoft Visual Studio/Installer/vswhere.exe"
    if not vswhere.is_file():
        raise FileNotFoundError(vswhere)
    vs = subprocess.check_output(
        [
            str(vswhere),
            "-latest",
            "-requires",
            "Microsoft.VisualStudio.Component.VC.Tools.x86.x64",
            "-property",
            "installationPath",
        ],
        text=True,
    ).strip()
    bat = Path(vs) / "VC/Auxiliary/Build/vcvars64.bat"
    if not bat.is_file():
        raise FileNotFoundError(bat)
    return bat


def test_cpp_format_matches_header(tmp_path: Path):
    driver = tmp_path / "damage_format_test.cpp"
    lines = [
        '#include "DamageFormat.h"',
        "#include <iostream>",
        "int main() {",
        "    struct Case { long long v; const char* e; };",
        "    const Case cases[] = {",
    ]
    for amount, expected in CASES.items():
        lines.append(f'        {{{amount}, "{expected}"}},')
    lines.extend(
        [
            "    };",
            "    int fail = 0;",
            "    for (const auto& c : cases) {",
            "        const std::string got = ArkPlayer::FormatDamageAmount(c.v);",
            "        if (got != c.e) {",
            "            std::cerr << c.v << \" got '\" << got << \"' expected '\" << c.e << \"'\\n\";",
            "            fail = 1;",
            "        }",
            "    }",
            "    return fail;",
            "}",
            "",
        ]
    )
    driver.write_text("\n".join(lines), encoding="utf-8")
    exe = tmp_path / "damage_format_test.exe"
    vcvars = _vcvars64()
    cmd = (
        f'call "{vcvars}" >nul && '
        f'cl /nologo /EHsc /std:c++17 /I"{HEADER.parent}" '
        f'/Fe:"{exe}" "{driver}"'
    )
    proc = subprocess.run(cmd, shell=True, cwd=tmp_path, capture_output=True, text=True)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    run = subprocess.run([str(exe)], capture_output=True, text=True)
    assert run.returncode == 0, run.stderr
