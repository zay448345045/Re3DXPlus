#!/usr/bin/env python3
"""The port's GLSL ES 1.0 programs for Vulkan (src/vkgl.c, Android's renderer).

A program as gl_compile_program gets it (its vertex and fragment source and the attributes'
names, location i for the i-th) becomes GLSL ES 3.10 for Vulkan, compiled to SPIR-V by
glslangValidator:
  - preprocessed first (the #defines that pick a variant),
  - the attributes `layout(location = i) in`, the varyings in and out by their place in the
    vertex shader,
  - the uniforms other than samplers one std140 block (set 0, binding 0, both stages, all
    highp), the samplers bindings 1.. in their order of first declaration,
  - texture2D / textureCube texture, gl_FragColor an output,
  - GL's clip depth -1..1 made Vulkan's 0..1 at the end of the vertex shader, and y turned
    over for the screen (specialization constant 0, vkgl_flip_y: -1 in the screen's pipelines,
    whose framebuffer is the other way up from GL's).
A program is known by key(): FNV-1a 64 over the vertex source, a 0, the fragment source, a 0
and the attributes' names joined by spaces (vkgl.c's prog_key).
The compiler: glslangValidator if it is on the PATH, else glslc (the Android NDK has one, in
shader-tools/<host>/), or the one VKGLSL_CC names.

  vkglsl.py one <dump> <out prefix>   one program (a WMMT_DUMP_PROGS file): <prefix>.vert.spv,
                                      <prefix>.frag.spv, <prefix>.refl
  vkglsl.py table <dir> <out.c>       every dump in dir into vkgl_spv.c's table
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile

TYPES = {  # std140 (base alignment, size) and vkgl.c's type code
    'float': (4, 4, 1), 'vec2': (8, 8, 2), 'vec3': (16, 12, 3), 'vec4': (16, 16, 4),
    'int': (4, 4, 5), 'mat4': (16, 64, 6), 'bool': (4, 4, 5),
}
SAMPLERS = {'sampler2D': 7, 'samplerCube': 8}
PRECISIONS = ('lowp', 'mediump', 'highp')


def key(vs, fs, attribs):
    h = 0xcbf29ce484222325
    for b in vs.encode() + b'\0' + fs.encode() + b'\0' + ' '.join(attribs).encode():
        h ^= b
        h = (h * 0x100000001b3) & 0xffffffffffffffff
    return h


def read_dump(path):
    text = open(path, encoding='utf-8').read()
    head, rest = text.split('\n', 1)
    attribs = head[len('// attribs: '):].split() if head.startswith('// attribs:') else []
    vs, fs = rest.split('\n//----FS\n', 1)
    assert vs.startswith('//----VS\n')
    vs = vs[len('//----VS\n'):]
    return vs, fs, attribs


CC = os.environ.get('VKGLSL_CC') or ('glslangValidator' if shutil.which('glslangValidator') else 'glslc')
GLSLC = os.path.basename(CC).startswith('glslc')


def preprocess(src, stage, tmp):
    path = os.path.join(tmp, 'pp.' + stage)
    with open(path, 'w') as f:
        f.write(src)
    cmd = [CC, '-E', '-std=310es', '-fshader-stage=' + stage, path] if GLSLC else [CC, '-E', path]
    out = subprocess.run(cmd, capture_output=True, text=True)
    if out.returncode:
        raise SystemExit('preprocess failed (%s): %s%s' % (stage, out.stdout, out.stderr))
    return out.stdout


DECL = re.compile(r'\b(uniform|attribute|varying)\s+((?:(?:lowp|mediump|highp)\s+)?)(\w+)\s+([^;]+);')


def decls(src):
    """the declarations (kind, precision, type, [names]) and the source without them"""
    found = []

    def take(m):
        names = [n.strip() for n in m.group(4).split(',')]
        found.append((m.group(1), m.group(2).strip(), m.group(3), names))
        return ''
    return found, DECL.sub(take, src)


def end_of_main(src):
    i = src.index('void main')
    i = src.index('{', i)
    depth = 0
    for j in range(i, len(src)):
        if src[j] == '{':
            depth += 1
        elif src[j] == '}':
            depth -= 1
            if depth == 0:
                return j
    raise SystemExit('no end of main')


def translate(vs, fs, attribs, tmp):
    vs_pp, fs_pp = preprocess(vs, 'vert', tmp), preprocess(fs, 'frag', tmp)
    vd, vbody = decls(vs_pp)
    fd, fbody = decls(fs_pp)
    block, samplers = [], []  # (type, name); names
    for kind, prec, typ, names in vd + fd:
        if kind != 'uniform':
            continue
        for n in names:
            if typ in SAMPLERS:
                if n not in [s for s, _ in samplers]:
                    samplers.append((n, typ))
            elif n not in [b for _, b in block]:
                if typ not in TYPES or '[' in n:
                    raise SystemExit('uniform type %s' % typ)
                block.append((typ, n))
    varyings = []
    for kind, prec, typ, names in vd:
        if kind == 'varying':
            for n in names:
                varyings.append((prec, typ, n))
    vloc = {n: i for i, (_, _, n) in enumerate(varyings)}

    def head(stage):
        out = ['#version 310 es']
        if block:
            out.append('layout(std140, set = 0, binding = 0) uniform U {')
            out += ['  highp %s %s;' % (t, n) for t, n in block]
            out.append('};')
        # the samplers only in the fragment shader (vkgl.c's set layouts give them to it alone;
        # Adreno 540's driver failed to link the car's programs with them in both)
        if stage == 'frag':
            for i, (n, t) in enumerate(samplers):
                out.append('layout(set = 0, binding = %d) uniform highp %s %s;' % (i + 1, t, n))
        return out

    # vertex
    v = head('vert')
    v.append('layout(constant_id = 0) const float vkgl_flip_y = 1.0;')
    inputs = []
    for kind, prec, typ, names in vd:
        for n in names:
            if kind == 'attribute':
                loc = attribs.index(n) if n in attribs else None
                if loc is None:
                    raise SystemExit('attribute %s without a location' % n)
                inputs.append(loc)
                v.append('layout(location = %d) in %s %s %s;' % (loc, prec or 'highp', typ, n))
            elif kind == 'varying':
                v.append('layout(location = %d) out %s %s %s;' % (vloc[n], prec or 'highp', typ, n))
    for n, _ in samplers:
        if re.search(r'\b%s\b' % n, vbody):
            raise SystemExit('sampler %s in the vertex shader' % n)
    e = end_of_main(vbody)
    vbody = vbody[:e] + '  gl_Position.z = (gl_Position.z + gl_Position.w) * 0.5;\n  gl_Position.y *= vkgl_flip_y;\n' + vbody[e:]
    vsrc = '\n'.join(v) + '\n' + fix_body(vbody)
    # fragment
    f = head('frag')
    for kind, prec, typ, names in fd:
        for n in names:
            if kind == 'varying':
                if n not in vloc:
                    raise SystemExit('varying %s not written' % n)
                f.append('layout(location = %d) in %s %s %s;' % (vloc[n], prec or 'highp', typ, n))
    f.append('layout(location = 0) out mediump vec4 vkgl_FragColor;')
    fsrc = '\n'.join(f) + '\n' + fix_body(fbody).replace('gl_FragColor', 'vkgl_FragColor')
    # std140 offsets
    refl, off = [], 0
    for t, n in block:
        align, size, code = TYPES[t]
        off = (off + align - 1) // align * align
        refl.append((n, code, off))
        off += size
    size = (off + 15) // 16 * 16
    for i, (n, t) in enumerate(samplers):
        refl.append((n, SAMPLERS[t], i + 1))
    return vsrc, fsrc, refl, size, sorted(set(inputs))


def all_highp(src):
    return re.sub(r'\b(lowp|mediump)\b', 'highp', src)


def fix_body(src):
    # (the #line directives glslang -E leaves are fine; the version moves to the top)
    src = re.sub(r'^\s*#\s*version.*$', '', src, flags=re.M)
    src = re.sub(r'^\s*#\s*extension.*$', '', src, flags=re.M)
    src = re.sub(r'\btexture2D\s*\(', 'texture(', src)
    src = re.sub(r'\btextureCube\s*\(', 'texture(', src)
    return src


def compile_spv(src, stage, out, tmp, opt=False):
    path = os.path.join(tmp, 'x.' + stage)
    with open(path, 'w') as f:
        f.write(src)
    if GLSLC:
        # opt (the all-highp second try): optimised, functions inlined, locals to SSA; Adreno
        # 540's driver failed to link the car's programs as glslang leaves them, but -O on every
        # program broke the race's post-processing there (its colours, p148), so only those
        cmd = [CC] + (['-O'] if opt else []) + ['-fshader-stage=' + stage, '--target-env=vulkan1.0', '-o', out, path]
    else:
        cmd = [CC, '-V', '--target-env', 'vulkan1.0', '-o', out, path]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        numbered = '\n'.join('%4d %s' % (i + 1, l) for i, l in enumerate(src.split('\n')))
        raise SystemExit('compile failed (%s): %s%s\n%s' % (stage, r.stdout, r.stderr, numbered))


def one(dump, prefix):
    vs, fs, attribs = read_dump(dump)
    with tempfile.TemporaryDirectory() as tmp:
        vsrc, fsrc, refl, size, inputs = translate(vs, fs, attribs, tmp)
        compile_spv(vsrc, 'vert', prefix + '.vert.spv', tmp)
        compile_spv(fsrc, 'frag', prefix + '.frag.spv', tmp)
    with open(prefix + '.refl', 'w') as f:
        f.write(refl_text(key(vs, fs, attribs), refl, size, inputs))


def refl_text(k, refl, size, inputs):
    """vkgl.c's reflection line: key, block size, input mask, then name:code:offset each"""
    mask = sum(1 << i for i in inputs)
    return '%016x %d %d %s\n' % (k, size, mask, ' '.join('%s:%d:%d' % r for r in refl))


def table(d, out):
    rows = []
    with tempfile.TemporaryDirectory() as tmp:
        seen = set()
        for name in sorted(os.listdir(d)):
            if not name.endswith('.txt'):
                continue
            vs, fs, attribs = read_dump(os.path.join(d, name))
            k = key(vs, fs, attribs)
            if k in seen:
                continue
            seen.add(k)
            vsrc, fsrc, refl, size, inputs = translate(vs, fs, attribs, tmp)
            words = []
            # as written, then all highp (vkgl.c's second try when a driver refuses the first)
            for src, stage, opt in ((vsrc, 'vert', False), (fsrc, 'frag', False), (all_highp(vsrc), 'vert', True),
                                    (all_highp(fsrc), 'frag', True)):
                spv = os.path.join(tmp, 'o.spv')
                compile_spv(src, stage, spv, tmp, opt)
                b = open(spv, 'rb').read()
                words.append([int.from_bytes(b[i:i + 4], 'little') for i in range(0, len(b), 4)])
            rows.append((k, refl_text(k, refl, size, inputs).strip(), words))
    with open(out, 'w') as f:
        f.write('/* made by tools/vkglsl.py table: the programs\' SPIR-V for vkgl.c */\n')
        f.write('#include "vkgl.h"\n\n')
        for i, (k, refl, (vw, fw, vw2, fw2)) in enumerate(rows):
            for tag, w in (('v', vw), ('f', fw), ('v2', vw2), ('f2', fw2)):
                f.write('static const uint32_t spv%d%s[%d] = {' % (i, tag, len(w)))
                for j, x in enumerate(w):
                    f.write(('\n  ' if j % 8 == 0 else ' ') + '0x%08x,' % x)
                f.write('\n};\n')
        f.write('const vkgl_spv VKGL_SPV[] = {\n')
        for i, (k, refl, (vw, fw, vw2, fw2)) in enumerate(rows):
            f.write('  { "%s", spv%dv, %d, spv%df, %d, spv%dv2, %d, spv%df2, %d },\n'
                    % (refl, i, len(vw), i, len(fw), i, len(vw2), i, len(fw2)))
        f.write('};\nconst int VKGL_N_SPV = %d;\n' % len(rows))


if __name__ == '__main__':
    if len(sys.argv) == 4 and sys.argv[1] == 'one':
        one(sys.argv[2], sys.argv[3])
    elif len(sys.argv) == 4 and sys.argv[1] == 'table':
        table(sys.argv[2], sys.argv[3])
    else:
        raise SystemExit(__doc__)
