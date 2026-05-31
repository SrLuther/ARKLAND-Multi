"""
Parser/serializador para arquivos .sav do plugin KsMissions (ARK)
Formato: UE4 property serialization (GVAS-like, sem header padrão)
"""
import struct
import io
import sys
import json
from pathlib import Path


# ── Primitivos ──────────────────────────────────────────────────────────────

def read_fstring(d: bytes, p: int) -> tuple[str, int]:
    sz = struct.unpack_from('<i', d, p)[0]; p += 4
    if sz == 0:
        return '', p
    if sz > 0:
        s = d[p:p + sz - 1].decode('utf-8', 'replace'); p += sz
    else:
        sz2 = -sz
        s = d[p:p + sz2 * 2 - 2].decode('utf-16-le', 'replace'); p += sz2 * 2
    return s, p


def write_fstring(s: str) -> bytes:
    if not s:
        return struct.pack('<i', 0)
    b = s.encode('utf-8') + b'\x00'
    return struct.pack('<i', len(b)) + b


def read_int32(d: bytes, p: int) -> tuple[int, int]:
    return struct.unpack_from('<i', d, p)[0], p + 4


def read_int64(d: bytes, p: int) -> tuple[int, int]:
    return struct.unpack_from('<q', d, p)[0], p + 8


# ── Propriedades individuais ────────────────────────────────────────────────

def read_prop(d: bytes, p: int) -> tuple[dict | None, int]:
    name, p = read_fstring(d, p)
    if name in ('None', ''):
        return None, p
    ptype, p = read_fstring(d, p)
    fsize, p = read_int64(d, p)
    start = p
    if ptype == 'ObjectProperty':
        val, p = read_fstring(d, p)
    elif ptype == 'IntProperty':
        v, p = read_int32(d, p)
        val = v
    elif ptype == 'StrProperty':
        v, p = read_fstring(d, p)
        val = v
    elif ptype == 'FloatProperty':
        v = struct.unpack_from('<f', d, p)[0]; p += 4
        val = v
    elif ptype == 'BoolProperty':
        v = struct.unpack_from('<B', d, p)[0]; p += 1
        val = bool(v)
    else:
        # tipo desconhecido — preserva bytes brutos
        val = d[p:p + fsize]; p += fsize
    return {'name': name, 'type': ptype, 'val': val, '_fsize': fsize}, p


def write_prop(prop: dict) -> bytes:
    n, t, v = prop['name'], prop['type'], prop['val']
    if t == 'ObjectProperty':
        vb = write_fstring(v)
    elif t == 'IntProperty':
        vb = struct.pack('<i', int(v))
    elif t == 'StrProperty':
        vb = write_fstring(v)
    elif t == 'FloatProperty':
        vb = struct.pack('<f', float(v))
    elif t == 'BoolProperty':
        vb = struct.pack('<B', int(bool(v)))
    else:
        vb = v  # bytes brutos preservados
    return write_fstring(n) + write_fstring(t) + struct.pack('<q', len(vb)) + vb


# ── Parser principal ────────────────────────────────────────────────────────

def parse_sav(data: bytes) -> dict:
    """Parseia um .sav do KsMissions para dict Python."""
    pos = 0
    root_class, pos = read_fstring(data, pos)
    prop_name, pos = read_fstring(data, pos)
    prop_type, pos = read_fstring(data, pos)

    if prop_type == 'ArrayProperty':
        arr_size, pos = read_int64(data, pos)
        inner_type, pos = read_fstring(data, pos)
        count, pos = read_int32(data, pos)
        extra = b''

        entries = []
        for _ in range(count):
            entry = []
            while True:
                prop, pos = read_prop(data, pos)
                if prop is None:
                    break
                entry.append(prop)
            entries.append(entry)

        tail = data[pos:]
        return {
            'root_class': root_class,
            'prop_name': prop_name,
            'prop_type': prop_type,
            'inner_type': inner_type,
            '_extra': extra,
            'entries': entries,
            '_tail': tail,
        }
    else:
        # Formato simples (ex: GamblingData, versão única)
        props = []
        prop, pos = read_prop(data, pos)
        while prop is not None:
            props.append(prop)
            prop, pos = read_prop(data, pos)
        return {
            'root_class': root_class,
            'prop_name': prop_name,
            'prop_type': prop_type,
            'props': props,
            '_tail': data[pos:],
        }


def serialize_sav(doc: dict) -> bytes:
    """Serializa de volta para bytes binários compatíveis com KsMissions."""
    out = io.BytesIO()
    out.write(write_fstring(doc['root_class']))
    out.write(write_fstring(doc['prop_name']))
    out.write(write_fstring(doc['prop_type']))

    if doc['prop_type'] == 'ArrayProperty':
        # Serializa o corpo primeiro para calcular o tamanho
        body = io.BytesIO()
        body.write(write_fstring(doc['inner_type']))
        body.write(struct.pack('<i', len(doc['entries'])))
        for entry in doc['entries']:
            for prop in entry:
                body.write(write_prop(prop))
            body.write(write_fstring('None'))
        body_bytes = body.getvalue()
        out.write(struct.pack('<q', len(body_bytes)))
        out.write(body_bytes)
    else:
        # Formato simples
        body = io.BytesIO()
        for prop in doc.get('props', []):
            body.write(write_prop(prop))
        body.write(write_fstring('None'))
        body_bytes = body.getvalue()
        out.write(struct.pack('<q', len(body_bytes)))
        out.write(body_bytes)

    out.write(doc.get('_tail', b''))
    return out.getvalue()


# ── Helpers de export/import ────────────────────────────────────────────────

def doc_to_json(doc: dict) -> list[dict]:
    """Converte entries para lista de dicts simples (para JSON/UI)."""
    result = []
    for entry in doc.get('entries', []):
        row = {}
        for prop in entry:
            row[prop['name']] = prop['val']
        result.append(row)
    return result


def json_to_entries(doc: dict, rows: list[dict]) -> None:
    """Atualiza os valores das entries a partir de uma lista de dicts."""
    for entry, row in zip(doc['entries'], rows):
        for prop in entry:
            if prop['name'] in row:
                prop['val'] = row[prop['name']]


# ── CLI de teste ────────────────────────────────────────────────────────────

if __name__ == '__main__':
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(
        r'C:\Users\Ciano\Downloads\KsMissions\KsMissions\CustomShop.sav'
    )
    data = path.read_bytes()
    doc = parse_sav(data)

    # Round-trip test
    out = serialize_sav(doc)
    match = data == out
    print(f'Arquivo : {path.name}  ({len(data)} bytes)')
    print(f'Round-trip: {"OK ✓" if match else "FALHOU ✗"}')
    if not match:
        for i, (a, b) in enumerate(zip(data, out)):
            if a != b:
                print(f'  Primeiro diff em byte {i}: orig={a:02x} novo={b:02x}')
                break
        if len(data) != len(out):
            print(f'  Tamanhos diferem: {len(data)} vs {len(out)}')

    # Exporta amostras
    entries_json = doc_to_json(doc)
    print(f'\nEntradas ({len(entries_json)}):')
    for i, e in enumerate(entries_json[:5]):
        print(f'  [{i}] {json.dumps(e, ensure_ascii=False)}')
    if len(entries_json) > 5:
        print(f'  ... +{len(entries_json)-5} mais')
