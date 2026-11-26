"""Empacota somente o runtime e modelos sem segredos; não publica nem instala."""
from pathlib import Path
import hashlib
import json
import zipfile

base = Path(__file__).resolve().parent
root = base.parents[1]
version = (base / 'plugin_version.txt').read_text(encoding='utf-8').strip()
config = json.loads((base / 'configs/config.json').read_text(encoding='utf-8'))
assert config['Local']['ApiKey'] == '' and config['Local']['ServerKey'] == ''
assert config['Local']['ObserveOnly'] is True
dll = base / 'bin/ChatArkland.dll'
if not dll.is_file():
    raise SystemExit('Compile a DLL antes de empacotar.')
files = {'ChatArkland/ChatArkland.dll': dll, 'ChatArkland/config.json': base / 'configs/config.json',
         'ChatArkland/PluginInfo.json': base / 'configs/PluginInfo.json',
         'ChatArkland/README.md': base / 'README.md', 'ChatArkland/CHANGELOG.md': base / 'CHANGELOG.md'}
for path in (root / 'docs/CHAT_ARKLAND').glob('*.md'):
    files['documentacao/' + path.name] = path
for path in (base / 'migrations').glob('*.sql'):
    files['migracoes/' + path.name] = path
out = root / 'dist' / f'ChatArkland-{version}-experimental.zip'
out.parent.mkdir(parents=True, exist_ok=True)
manifest = {name: {'bytes': path.stat().st_size, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()} for name, path in files.items()}
with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as archive:
    for name, path in files.items():
        archive.write(path, name)
    archive.writestr('manifesto.json', json.dumps(manifest, ensure_ascii=False, indent=2))
with zipfile.ZipFile(out) as archive:
    assert archive.testzip() is None
    for name, metadata in manifest.items():
        data = archive.read(name)
        assert len(data) == metadata['bytes'] and hashlib.sha256(data).hexdigest() == metadata['sha256']
digest = hashlib.sha256(out.read_bytes()).hexdigest()
out.with_suffix('.zip.sha256').write_text(digest + '  ' + out.name + '\n', encoding='ascii')
print(str(out))
print('SHA-256 ' + digest)
