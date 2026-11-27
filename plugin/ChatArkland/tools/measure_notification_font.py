"""Generate static notification metrics from an operator-supplied server font.

Requires Pillow only for this development tool. Does not copy the font binary.
Usage: python measure_notification_font.py Roboto-Bold.ttf output_metrics.py
"""
from pathlib import Path
import argparse
import hashlib

from PIL import ImageFont


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('font', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    font = ImageFont.truetype(str(args.font), 1000, layout_engine=ImageFont.Layout.BASIC)
    chars = list(range(32, 127)) + list(range(160, 384)) + [0x2039, 0x203a, 0xff3b, 0xff3d]
    advances = {code: round(font.getlength(chr(code)), 3) for code in chars}
    digest = hashlib.sha256(args.font.read_bytes()).hexdigest()
    args.output.write_text('"""Roboto Bold glyph advances at 1000 units/em; no font binary distributed.\n'
        + 'Source server font SHA256: ' + digest + '\n"""\nADVANCES = ' + repr(advances) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
