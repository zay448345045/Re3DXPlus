#!/usr/bin/env python3
"""Convert trusted user-supplied backfire IGB data into WPK2 and BFX1.

This is not a sandbox for malicious IGB files. Interpolation is approximate.

BFX1 little endian: <4sHHIII> magic, version, flags, frames, meshes,
nozzles. Flag 1 means interpolated frames are approximate. Mesh records:
<u32 WPK group, u32 geometry object, u32 attribute ordinal>, then UTF-8 variant and ASCII
ordinal instance path, then 17 row-major float32 child@parent matrices.
Nozzle records: length-prefixed car, muffler, slot, ordinal instance path,
then a row-major float32 translation-only matrix using the nozzle node's own
local translation (not its parent transforms). No names establish identity.
Car keys are <body>|<canonical original ID 0..119>; body permits ASCII letters,
digits, '_', '-', '/', ':'. Every record for the same body must use the same ID.
Input paths are read-only; output must be a new system-temp directory.
"""
import struct
import numpy as np

FRAMES = 17
LIMIT = 65535
MAX_RECORDS = 4096
MAX_BFX = 32 * 1024 * 1024
MAX_WPK = 128 * 1024 * 1024
VARIANTS = frozenset(('SAMLL_A', 'MIDDLE_A', 'LARGE_A', 'SMALL_B', 'MIDDLE_B', 'LARGE_B'))
SLOTS = frozenset(('MF_NULL_R1', 'MF_NULL_R2', 'MF_NULL_L1', 'MF_NULL_L2'))


def _text(s):
    if not isinstance(s, str):
        raise ValueError('text field is not a string')
    b = s.encode('utf-8')
    if not b or len(b) > 255 or b'\0' in b:
        raise ValueError('invalid text field')
    return struct.pack('<H', len(b)) + b


def _car_key(car):
    import re
    _text(car)
    match = re.fullmatch(r'([A-Za-z0-9_/:\-]+)\|(0|[1-9][0-9]{0,2})', car, flags=re.ASCII)
    if not match or int(match.group(2)) > 119:
        raise ValueError('invalid car key; expected body|id with id 0..119')
    return match.group(1), int(match.group(2))


def _check_car_id(car, bodies):
    body, car_id = _car_key(car)
    if body in bodies and bodies[body] != car_id:
        raise ValueError('conflicting car IDs for body ' + body)
    bodies[body] = car_id


def _path(path):
    if not isinstance(path, tuple) or len(path) > 256 or any(type(i) is not int or i < 0 or i > LIMIT for i in path):
        raise ValueError('invalid instance path')
    return _text('/'.join(str(i) for i in path) if path else '.')


def _matrix(value, shape):
    a = np.asarray(value, dtype=np.float64)
    if a.shape != shape or not np.isfinite(a).all() or np.max(np.abs(a)) > 1e12:
        raise ValueError('invalid matrix')
    return a.astype('<f4').tobytes()


def compose_frames(local, parent):
    """Compose exact caller-supplied frames; performs no interpolation."""
    a, b = np.asarray(local, dtype=np.float64), np.asarray(parent, dtype=np.float64)
    _matrix(a, (FRAMES, 4, 4)); _matrix(b, (FRAMES, 4, 4))
    out = a @ b
    _matrix(out, (FRAMES, 4, 4))
    return out


def encode_bfx(meshes, nozzles, approximate=True):
    """Encode explicitly prepared records; rejects ambiguous IDs and invalid floats."""
    if type(approximate) is not bool or not 1 <= len(meshes) <= MAX_RECORDS or len(nozzles) > MAX_RECORDS:
        raise ValueError('invalid counts or flags')
    parts = [struct.pack('<4sHHIII', b'BFX1', 1, int(approximate), FRAMES, len(meshes), len(nozzles))]
    groups, locations, keys, bodies = set(), set(), set(), {}
    for group, obj, attr, variant, path, matrices in meshes:
        if type(group) is not int or not 1 <= group <= 0xffffffff or group in groups or type(obj) is not int or not 0 <= obj <= 0xffffffff or type(attr) is not int or not 0 <= attr <= 0xffffffff:
            raise ValueError('invalid or duplicate WPK group/object')
        _path(path)
        if variant not in VARIANTS or (path, obj, attr) in locations:
            raise ValueError('invalid variant or duplicate mesh instance')
        groups.add(group); locations.add((path, obj, attr))
        parts.append(struct.pack('<III', group, obj, attr) + _text(variant) + _path(path) + _matrix(matrices, (FRAMES, 4, 4)))
    for car, muffler, slot, path, matrix in nozzles:
        _check_car_id(car, bodies)
        if muffler not in ('MUFFLER1', 'MUFFLER2') or slot not in SLOTS:
            raise ValueError('invalid muffler or nozzle')
        key = (car, muffler, slot)
        if key in keys:
            raise ValueError('duplicate car/muffler/nozzle')
        keys.add(key)
        parts.append(_text(car) + _text(muffler) + _text(slot) + _path(path) + _matrix(matrix, (4, 4)))
    if sum(map(len, parts)) > MAX_BFX:
        raise ValueError('output exceeds limit')
    return b''.join(parts)


def _dependencies():
    import importlib.util
    from pathlib import Path
    import sys
    here = Path(__file__).resolve().parent
    repo = here.parents[2]
    sys.path.insert(0, str(here / 'stage'))
    import scene, pack
    from igb import IGB
    spec = importlib.util.spec_from_file_location('_backfire_preflight', repo / 'tools' / 'backfire_pack.py')
    base = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(base)
    return repo, IGB, scene, pack, base


def load_checked(path, IGB, base):
    """Catch common truncation; legacy IGB parser is not a hostile-file sandbox."""
    base.preflight(path)
    f = IGB(path)
    declared = struct.unpack_from('<I', f.buf, 24)[0]
    actual = sum((len(o.mem) + 3) & ~3 for o in f.objects if o is not None and o.mem is not None)
    if actual != declared:
        raise ValueError('IGB memory region truncated or inconsistent')
    if any(len(field.raw) != field.size for o in f.objects if o is not None for field in o.fields.values()):
        raise ValueError('IGB object field truncated')
    return f


def extract_scene(f, effect, scene, base):
    """Traverse instances, not names: paths distinguish DAG occurrences and attributes."""
    infos = f.of_type('igSceneInfo')
    if len(infos) != 1 or infos[0][5] is None or f.ref(infos[0][5]) is None:
        raise ValueError('expected one valid scene root')
    meshes, nozzles, active, variants = [], [], set(), set()
    visits = [0]
    def walk(node, parent, path, variant, muffler, image, state):
        visits[0] += 1
        if len(path) > 256 or visits[0] > LIMIT or node.index in active or node.mem is not None:
            raise ValueError('cyclic or excessive scene hierarchy')
        active.add(node.index)
        name = f.string(node[2]) if node[2] is not None else ''
        if name is None: raise ValueError('invalid node name reference')
        if effect and node.type == 'igGroup' and name in VARIANTS:
            if variant is not None: raise ValueError('nested backfire variants')
            variant = name; variants.add(name)
        if not effect and name in ('MUFFLER1', 'MUFFLER2'):
            if muffler is not None: raise ValueError('nested muffler configuration')
            muffler = name
        matrix = base.matrix(node)
        anim = base.animation(f, node) if effect else None
        local = np.asarray(anim['local_matrices'], dtype=np.float64).reshape(FRAMES, 4, 4) if anim else np.repeat(matrix[None], FRAMES, axis=0)
        world = compose_frames(local, parent)
        attrs = scene.obj_list(f, f.ref(node[8])) if node.type in ('igAttrSet', 'igGeometry') else []
        state = dict(state)
        if node.type == 'igSimpleShader':
            attrs = scene.shader_attrs(f, node)
            state['movie'] = scene.movie(f, node, attrs)
        new_image = scene.texture_image(f, attrs)
        if new_image is not None: image = new_image
        for attr in attrs:
            if attr.type == 'igBlendStateAttr': state['blend'] = bool(attr[4].i32)
            elif attr.type == 'igBlendFunctionAttr': state['blend_func'] = (attr[4].i32, attr[5].i32)
        if effect and node.type == 'igGeometry':
            if variant is None: raise ValueError('geometry outside a backfire variant')
            for ordinal, attr in enumerate(attrs):
                if not attr.type.startswith('igGeometryAttr'): continue
                va = f.ref(attr[4])
                if va is None: raise ValueError('missing vertex array')
                vert = scene.decode_vertices_1_1(f, va) if va.type == 'igVertexArray1_1' else scene.decode_vertices(f, va)
                if vert is None or vert.get('pos') is None: raise ValueError('missing vertex data')
                tris = scene.decode_indices(f, attr, len(vert['pos']))
                meshes.append((node.index, ordinal, variant, path, image, state.copy(), vert, tris, world.copy()))
        if not effect and name in SLOTS and muffler:
            if node.type != 'igTransform': raise ValueError('nozzle is not an igTransform')
            translation = np.eye(4, dtype=np.float64)
            translation[3, :3] = matrix[3, :3]
            nozzles.append((muffler, name, path, translation))
        for i, child in enumerate(base.child_list(f, node)):
            walk(child, world, path + (i,), variant, muffler, image, state)
        active.remove(node.index)
    walk(f.ref(infos[0][5]), np.repeat(np.eye(4)[None], FRAMES, axis=0), (), None, None, None,
         {'blend': False, 'blend_func': (4, 5), 'movie': None})
    if effect and variants != VARIANTS: raise ValueError('missing expected variants: ' + ', '.join(sorted(VARIANTS - variants)))
    return meshes, nozzles


def write_effect(f, meshes, cars, output, pack):
    from pathlib import Path
    output = Path(output)
    if not meshes or len(meshes) > MAX_RECORDS: raise ValueError('invalid mesh count')
    textures, order, cells, records = {}, [], {}, []
    for group_id, (obj, attr, variant, path, image, state, vert, tris, matrices) in enumerate(meshes, 1):
        if image is None or isinstance(image, str): raise ValueError('unresolved external or missing texture')
        key = 'image_%d' % image.index
        if key not in textures:
            im = pack.decode_image(f, image)
            if im is None or not 1 <= im.width <= 4096 or not 1 <= im.height <= 4096: raise ValueError('bad texture')
            textures[key] = pack.encode16(im, 4096); order.append(key)
        pos = np.asarray(vert['pos']); n = len(pos)
        uv = np.asarray(vert.get('uv'))
        tri = np.asarray(tris)
        if not 1 <= n <= LIMIT or pos.shape != (n, 3) or not np.isfinite(pos).all() or np.max(np.abs(pos)) > 1e12:
            raise ValueError('bad positions')
        if uv.ndim != 2 or uv.shape[0] != n or uv.shape[1] < 2 or not np.isfinite(uv).all() or np.max(np.abs(uv)) > 1e12:
            raise ValueError('bad UVs')
        if tri.ndim != 2 or tri.shape[1] != 3 or not 1 <= len(tri) <= LIMIT or not np.issubdtype(tri.dtype, np.integer) or tri.min() < 0 or tri.max() >= n:
            raise ValueError('bad triangles')
        if state['movie'] is not None: raise ValueError('texture movie unsupported')
        v = np.zeros(n, pack.VERTEX); v['pos'] = pos; v['uv'] = uv[:, :2]
        if 'color' in vert:
            col = np.asarray(vert['color'])
            if col.shape != (n, 4) or col.dtype != np.uint8: raise ValueError('bad vertex color')
            v['rgba'] = col[:, [2, 1, 0, 3]]
        else: v['rgba'] = 255
        flags = (2 if state['blend_func'][1] == pack.BLEND_ONE else 1) if state['blend'] else 0
        cells[(group_id, 0, 0)] = [(key, flags, v, tri, None)]
        records.append((group_id, obj, attr, variant, path, matrices))
    nozzles, bodies, car_keys = [], {}, set()
    for car, entries in cars:
        _check_car_id(car, bodies)
        if car in car_keys: raise ValueError('duplicate car ID')
        car_keys.add(car)
        if not entries: raise ValueError('no muffler nozzles found for ' + car)
        nozzles.extend((car, muffler, slot, path, matrix) for muffler, slot, path, matrix in entries)
    data = encode_bfx(records, nozzles)
    pack.write(str(output / 'backfire.wpk'), textures, order, cells, 0)
    if (output / 'backfire.wpk').stat().st_size > MAX_WPK: raise ValueError('WPK exceeds size limit')
    (output / 'backfire.bfx').write_bytes(data)
    return len(records), len(nozzles), len(order)


def main(argv=None):
    import argparse
    from pathlib import Path
    import tempfile
    import sys
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('effect'); ap.add_argument('output_dir'); ap.add_argument('--car', action='append', required=True, metavar='BODY|ID=BODY_IGB')
    ap.add_argument('--allow-empty-car', action='store_true', help='warn and skip each body without muffler nozzles')
    a = ap.parse_args(argv)
    repo, IGB, scene, pack, base = _dependencies()
    out = Path(a.output_dir).resolve(); temp = Path(tempfile.gettempdir()).resolve()
    if temp not in out.parents or out == repo or repo in out.parents or out.exists(): ap.error('output must be absent, under system temp, and outside the repository')
    try:
        cars, ids, bodies = [], set(), {}
        for item in a.car:
            car, sep, path = item.partition('=')
            if not sep or not car or not path or car in ids: raise ValueError('invalid or duplicate car ID')
            _check_car_id(car, bodies); ids.add(car)
            _, entries = extract_scene(load_checked(path, IGB, base), False, scene, base)
            if not entries and a.allow_empty_car:
                print('WARN: no muffler nozzles for %s; skipping body' % car, file=sys.stderr)
                continue
            cars.append((car, entries))
        f = load_checked(a.effect, IGB, base); meshes, _ = extract_scene(f, True, scene, base)
        out.mkdir()
        try:
            counts = write_effect(f, meshes, cars, out, pack)
        except Exception:
            for name in ('backfire.wpk', 'backfire.bfx'):
                p = out / name
                if p.exists(): p.unlink()
            out.rmdir()
            raise
        print('Wrote %d mesh groups, %d nozzles, %d textures to %s' % (*counts, out))
    except (ValueError, OSError, IndexError, KeyError, TypeError, struct.error, ZeroDivisionError, OverflowError, AttributeError) as exc:
        ap.exit(1, 'backfire_effect_pack: %s\n' % exc)


if __name__ == '__main__': main()
