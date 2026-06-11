#!/usr/bin/env python3
"""Extrai rótulos PT legados de asm_server_panel.py."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
text = (ROOT / "src/asm_ui/asm_server_panel.py").read_text(encoding="utf-8")
pat = re.compile(
    r'_(?:float_entry|int_entry|str_entry|bool_check)\(\s*sf,\s*"([^"]+)"\s*,\s*"([a-z_0-9]+)"',
    re.M,
)
labels: dict[str, str] = {}
for label, field in pat.findall(text):
    labels.setdefault(field, label)

out = ROOT / "src/ui/legacy_pt_labels.py"
lines = [
    '"""Rótulos PT extraídos do painel legado — mesclados em server_field_labels."""',
    "from __future__ import annotations",
    "",
    "LEGACY_PT_LABELS: dict[str, str] = {",
]
for k in sorted(labels):
    v = labels[k].replace("\\", "\\\\").replace('"', '\\"')
    lines.append(f'    "{k}": "{v}",')
lines.append("}")
lines.append("")
out.write_text("\n".join(lines), encoding="utf-8")
print(f"Wrote {len(labels)} labels to {out}")
