"""Run with CLIPSKITTY_SCRIPT_HOST=1 and the bundled api.exe (Python 3.11).

Build api.fixed.exe without modifying the running executable. Preserve every
archive member except two string constants in video.cutter/video.encoding.
"""
import marshal
import struct
import types
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'resources/backend/api.exe'
TARGET = SOURCE.with_name('api.fixed.exe')
MAGIC = b'MEI\x0c\x0b\x0a\x0b\x0e'
COOKIE = struct.Struct('!8sIIII64s')
ENTRY = struct.Struct('!IIIIBc')
blob = SOURCE.read_bytes()
cookie_pos = blob.rfind(MAGIC)
assert cookie_pos >= 0
magic, package_len, toc_offset, toc_len, pyver, pylib = COOKIE.unpack_from(blob, cookie_pos)
assert pyver == 311 and cookie_pos + COOKIE.size == len(blob)
base = len(blob) - package_len
entries = []
pos = base + toc_offset
while pos < base + toc_offset + toc_len:
    entry_len, offset, length, unpacked, compressed, kind = ENTRY.unpack_from(blob, pos)
    name_bytes = blob[pos+ENTRY.size:pos+entry_len]
    entries.append((offset, length, unpacked, compressed, kind, name_bytes))
    pos += entry_len
assert pos == base + toc_offset + toc_len

changes = []
def replace_code(code, module):
    constants = []
    for value in code.co_consts:
        if isinstance(value, types.CodeType):
            value = replace_code(value, module)
        elif isinstance(value, str) and value == '-vsync':
            changes.append((module, code.co_name))
            value = '-fps_mode'
        elif module == 'video.encoding' and code.co_name == 'sampled_frames' and value == '0':
            # fps_mode requires the named mode, unlike legacy vsync's "0".
            value = 'passthrough'
        constants.append(value)
    return code.replace(co_consts=tuple(constants))

def patch_pyz(data):
    assert data[:4] == b'PYZ\x00'
    old_toc = marshal.loads(data[struct.unpack('!i', data[8:12])[0]:])
    output = bytearray(data[:12])
    new_toc = []
    for name, (kind, offset, length) in dict(old_toc).items():
        payload = data[offset:offset+length]
        if name in ('video.cutter', 'video.encoding'):
            original_code = marshal.loads(zlib.decompress(payload))
            payload = zlib.compress(marshal.dumps(replace_code(original_code, name)))
        new_toc.append((name, (kind, len(output), len(payload))))
        output.extend(payload)
    toc_pos = len(output)
    output.extend(marshal.dumps(new_toc))
    output[8:12] = struct.pack('!i', toc_pos)
    # Verify every archive payload against its original, or its expected patch.
    for (name, (_, offset, length)), (_, (_, old_off, old_len)) in zip(new_toc, dict(old_toc).items()):
        actual = bytes(output[offset:offset+length])
        if name not in ('video.cutter', 'video.encoding'):
            assert actual == data[old_off:old_off+old_len], name
        elif length:
            marshal.loads(zlib.decompress(actual))
    return bytes(output)

package = bytearray()
new_entries = []
for offset, length, unpacked, compressed, kind, name in entries:
    payload = blob[base+offset:base+offset+length]
    if name.rstrip(b'\0') == b'PYZ.pyz':
        assert compressed == 0 and unpacked == length
        payload = patch_pyz(payload)
        unpacked = len(payload)
    new_entries.append(ENTRY.pack(ENTRY.size+len(name), len(package), len(payload), unpacked, compressed, kind) + name)
    package.extend(payload)
assert changes == [('video.cutter', 'cut_clip'), ('video.encoding', 'sampled_frames')], changes
new_toc_offset = len(package)
new_toc_blob = b''.join(new_entries)
package.extend(new_toc_blob)
package.extend(COOKIE.pack(magic, len(package)+COOKIE.size, new_toc_offset, len(new_toc_blob), pyver, pylib))
TARGET.write_bytes(blob[:base] + package)
print('Patched:', changes)
print('Verified: all other PYZ payloads unchanged')
print('Created:', TARGET)
