#!/usr/bin/env python3
"""Verify exact source keys against vkgl table; optionally pass a table path."""
import ast
import pathlib
import re
import sys
ROOT = pathlib.Path(__file__).resolve().parents[1]
s = (ROOT / 'src/render.c').read_text(encoding='utf-8')
t = (pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / 'src/vkgl_spv.c').read_text(encoding='utf-8')
mac = {a: ast.literal_eval(b) for a, b in re.findall(r'^#define (SSAO_R|SSAO_FAR) ("[^"\n]*")', s, re.M)}
assert set(mac) == {'SSAO_R', 'SSAO_FAR'}
def source(name):
    m = re.search(r'static const char \*' + name + r'\s*=\s*(.*?);\s*$', s, re.M | re.S)
    if not m: raise ValueError('missing ' + name)
    pattern = r'"(?:\\.|[^"\\])*"|\bSSAO_(?:R|FAR)\b|/\*.*?\*/'
    if re.sub(pattern, '', m.group(1), flags=re.S).strip(): raise ValueError('unsupported C string expression: ' + name)
    return ''.join(mac[x] if x in mac else ast.literal_eval(x) for x in re.findall(pattern, m.group(1), re.S) if not x.startswith('/*'))
def key(v, f, attrs):
    h = 0xcbf29ce484222325
    for b in (v+'\0'+f+'\0'+' '.join(attrs)).encode(): h = ((h ^ b) * 0x100000001b3) & 0xffffffffffffffff
    return f'{h:016x}'
table = re.search(r'const vkgl_spv VKGL_SPV\[\] = \{(.*?)\n\};', t, re.S)
if not table: raise ValueError('missing table')
rows = re.findall(r'\{ "([0-9a-f]{16}) ([^"\n]*)",\s*(spv\d+v),\s*(\d+),\s*(spv\d+f),\s*(\d+),\s*(spv\d+v2),\s*(\d+),\s*(spv\d+f2),\s*(\d+)\s*\}', table.group(1))
if len({r[0] for r in rows}) != len(rows): raise ValueError('duplicate keys')
entries = {r[0]: r for r in rows}
v = source('VS_POST')
cases = [(name, v, source(name), ['aPos']) for name in ('FS_SSAO', 'FS_AO_BLUR', 'FS_UP')]
for b in (0, 1): cases.append((f'FS_DOWN bright={b}', v, f'#define BRIGHT {b}\n'+source('FS_DOWN'), ['aPos']))
for hq in (0, 1):
    for i in range(3):
        prefix = f'#define BLUR_TAPS {8 if i == 1 else 1}\n#define SHARPEN {int(i == 2)}\n'
        vs, fs = prefix + source('VS_BLUR'), prefix + f'#define HQ {hq}\n' + source('FS_BLUR')
        if len(vs.encode()) >= 2048 or len(fs.encode()) >= 4096: raise ValueError('snprintf truncation')
        cases.append((f'COMPOSITE HQ={hq} variant={i}', vs, fs, ['aPos', 'aUV', 'aAlpha']))
errors = 0
for name, vs, fs, attrs in cases:
    k = key(vs, fs, attrs); row = entries.get(k)
    print(name, k, 'present' if row else 'MISSING')
    if not row: errors += 1; continue
    for symbol, count in zip(row[2::2], row[3::2]):
        decl = re.search(r'static const uint32_t ' + symbol + r'\[(\d+)\] = \{\s*(0x[0-9a-fA-F]+)', t)
        if not decl or int(decl.group(1)) != int(count) or int(decl.group(2), 16) != 0x07230203:
            print('invalid SPIR-V array', symbol); errors += 1
    if name.startswith('COMPOSITE HQ=1') and 'uAO:7:' not in row[1]:
        print('missing uAO sampler'); errors += 1
    if name in ('FS_SSAO', 'FS_AO_BLUR'):
        path = ROOT / 'tools/vkprogs' / (k + '.txt')
        expected = '// attribs: ' + ' '.join(attrs) + '\n//----VS\n' + vs + '\n//----FS\n' + fs
        if not path.exists() or path.read_text(encoding='utf-8') != expected:
            print('dump missing or differs:', path); errors += 1
print(f'{len(cases)} cases; {errors} errors')
sys.exit(bool(errors))
