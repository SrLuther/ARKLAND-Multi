"""Extract baked ASE HUD metrics, without distributing the font or its textures.

Usage: python measure_notification_font.py Roboto51.uasset output_metrics.py
Supports the reviewed UE4.5/405 tagged font package only; rejects other formats.
"""
from pathlib import Path
import argparse
import hashlib
import struct


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('font', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    data = args.font.read_bytes()
    if struct.unpack_from('<Iiii', data) != (0x9E2A83C1, -3, 864, 405):
        raise ValueError('Unreviewed asset format; expected ASE UE4.5/405 font package.')
    count, position = struct.unpack_from('<ii', data, 41)
    names = []
    for _ in range(count):
        size = struct.unpack_from('<i', data, position)[0]
        position += 4
        if not 1 <= size <= 1024:
            raise ValueError('Invalid font name table.')
        names.append(data[position:position + size - 1].decode('ascii'))
        position += size
    start = struct.unpack_from('<i', data, 24)[0]
    tag = data.find(struct.pack('<ii', names.index('Characters'), 0), start)
    if tag < 0 or struct.unpack_from('<i', data, tag + 8)[0] != names.index('ArrayProperty'):
        raise ValueError('Missing baked character array.')
    count = struct.unpack_from('<i', data, tag + 32)[0]
    if count != 256 or struct.unpack_from('<i', data, tag + 16)[0] != 4 + count * 21:
        raise ValueError('Unreviewed glyph layout.')
    advances = {code: struct.unpack_from('<iiiiBi', data, tag + 36 + code * 21)[2] for code in range(count)}
    tag = data.find(struct.pack('<ii', names.index('Kerning'), 0), start)
    if tag < 0 or struct.unpack_from('<i', data, tag + 8)[0] != names.index('IntProperty'):
        raise ValueError('Missing baked font kerning.')
    kerning = struct.unpack_from('<i', data, tag + 24)[0]
    digest = hashlib.sha256(data).hexdigest()
    args.output.write_text('"""Baked ASE Roboto51 (Sansation Bold) glyph widths in native asset units.\n'
        + 'Source asset SHA256: ' + digest + '\nNo font or texture binary distributed.\n"""\n'
        + 'KERNING = ' + repr(kerning) + '\nADVANCES = ' + repr(advances) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
