import struct, io, sys
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, r'C:\Users\Ciano\Documents\arkland-multi\tools')
from ksmissions_parser import *

data = open(r'C:\Users\Ciano\Downloads\KsMissions\KsMissions\CustomShop.sav','rb').read()
doc = parse_sav(data)

body = io.BytesIO()
body.write(write_fstring(doc['inner_type']))
body.write(struct.pack('<i', len(doc['entries'])))
for entry in doc['entries']:
    for prop in entry:
        body.write(write_prop(prop))
    body.write(write_fstring('None'))
body_bytes = body.getvalue()

print(f'Original arr_size: 26227')
print(f'Recomputed body:   {len(body_bytes)}')
print(f'Diff: {len(body_bytes) - 26227}')

orig_body = data[64:26291]
if orig_body == body_bytes:
    print('Body match!')
elif len(orig_body) == len(body_bytes):
    for i,(a,b) in enumerate(zip(orig_body, body_bytes)):
        if a!=b:
            print(f'First diff at body offset {i}: orig={a:02x} new={b:02x}')
            print(f'  context orig: {orig_body[max(0,i-8):i+12].hex()}')
            print(f'  context new:  {body_bytes[max(0,i-8):i+12].hex()}')
            break
else:
    short = min(len(orig_body), len(body_bytes))
    for i in range(short):
        if orig_body[i] != body_bytes[i]:
            print(f'First diff at body offset {i}: orig={orig_body[i]:02x} new={body_bytes[i]:02x}')
            print(f'  context orig: {orig_body[max(0,i-8):i+12].hex()}')
            print(f'  context new:  {body_bytes[max(0,i-8):i+12].hex()}')
            break
