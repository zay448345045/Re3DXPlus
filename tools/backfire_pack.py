#!/usr/bin/env python3
"""Convert private backfire IGB inputs to sidecars. Never commit generated JSON.

Usage: backfire_pack.py effect.igb car.igb NEW_OUTPUT_DIRECTORY
This converter is best-effort, not a claim of complete engine equivalence.
"""
import argparse
import base64
import json
from pathlib import Path
import struct
import sys
import tempfile

import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent / 'stage'))
from igb import IGB, Obj
import scene
import pack_battle

MAX_INPUT = 32 * 1024 * 1024
MAX_COUNT = 65535
MAX_OUTPUT = 128 * 1024 * 1024
REPO = Path(__file__).resolve().parent.parent
NOZZLES = {'MF_NULL_R1', 'MF_NULL_R2', 'MF_NULL_L1', 'MF_NULL_L2'}


def preflight(path):
    """Reject unreasonable allocation-driving header fields before IGB()."""
    p = Path(path)
    size = p.stat().st_size
    if not 48 <= size <= MAX_INPUT: raise ValueError('input size outside bounds')
    b = p.read_bytes()
    h = struct.unpack_from('<12I', b)
    if h[10] != 0xfada or h[11] & 0xffff != 8: raise ValueError('expected little-endian IGB v8')
    def u32(p):
        if p < 0 or p + 4 > size: raise ValueError('truncated IGB')
        return struct.unpack_from('<I', b, p)[0]
    def region(p, n):
        if p < 0 or n < 0 or p + n > size: raise ValueError('invalid region')
    def names(p):
        length, count = u32(p), u32(p + 4)
        if length < 8 or count > MAX_COUNT: raise ValueError('invalid name table')
        region(p, length); q = p + 8
        for _ in range(count):
            n = u32(q); q += 4
            if q + n > p + length: raise ValueError('invalid name')
            q += n
        return p + length
    entlen, nent, molen, nmo, objlen = h[:5]
    mflen, nmf = h[8:10]
    if max(nent, nmo, nmf) > MAX_COUNT: raise ValueError('too many metadata entries')
    p = names(48); region(p, mflen)
    if nmf * 12 > mflen: raise ValueError('invalid field table')
    q = p + nmf * 12
    for i in range(nmf):
        q += u32(p + i * 12)
        if q > p + mflen: raise ValueError('invalid field name')
    p += mflen; align = u32(p)
    if align < 4: raise ValueError('invalid alignment')
    region(p, align); p += align; region(p, molen)
    if nmo * 24 > molen: raise ValueError('invalid object table')
    q = p + nmo * 24
    for i in range(nmo):
        n, _, _, nf, _, _ = struct.unpack_from('<IIIIiI', b, p + i * 24)
        if nf > MAX_COUNT or q + n + nf * 6 > p + molen: raise ValueError('invalid metadata')
        q += n
        for j in range(nf):
            if struct.unpack_from('<H', b, q + 6*j)[0] >= nmf: raise ValueError('invalid field reference')
        q += nf * 6
    p += molen
    if h[11] & (1 << 30): p = names(p)
    if h[11] & (1 << 28):
        n = u32(p)
        if n < 4: raise ValueError('invalid pool names')
        region(p, n); p += n
    region(p, entlen); q = p
    for _ in range(nent):
        typ, n = u32(q), u32(q+4)
        if typ >= nmo or n < 8 or q+n > p+entlen: raise ValueError('invalid directory entry')
        q += n
    p += entlen; n, count = u32(p), u32(p+4)
    if count > MAX_COUNT or n < 8 + count*2: raise ValueError('invalid index')
    region(p, n)
    if any(i >= nent for i in struct.unpack_from('<%dH' % count, b, p+8)): raise ValueError('invalid directory index')
    p += n + (4 if h[11] & (1 << 31) else 0)
    region(p, objlen)


def matrix(o):
    if o.type != 'igTransform' or o[8] is None: return np.eye(4)
    if len(o[8].raw) != 64: raise ValueError('invalid matrix')
    m = np.frombuffer(o[8].raw, '<f4').reshape(4,4).astype(float)
    if not np.isfinite(m).all(): raise ValueError('non-finite matrix')
    return m


def child_list(f, o):
    lst = f.ref(o[7]) if o[7] is not None else None
    if lst is None: return []
    if lst[2] is None or lst[4] is None: raise ValueError('invalid child list')
    n = lst[2].i32; mem = f.ref(lst[4])
    if n == 0: return []
    if n < 0 or n > MAX_COUNT or mem is None or mem.mem is None or len(mem.mem) < n*4: raise ValueError('invalid child list bounds')
    out = []
    for i in struct.unpack_from('<%di' % n, mem.mem):
        if i < 0 or i >= len(f.objects) or f.objects[i] is None: raise ValueError('invalid child reference')
        out.append(f.objects[i])
    return out


def keylist(f, field, fmt, width):
    o = f.ref(field)
    if o is None: return None
    if o[2] is None or o[4] is None: raise ValueError('invalid key list')
    n = o[2].i32; mem = f.ref(o[4])
    if n < 0 or n > MAX_COUNT or mem is None or mem.mem is None or len(mem.mem) < n*width: raise ValueError('invalid key bounds')
    v = np.array([struct.unpack_from('<'+fmt, mem.mem, i*width) for i in range(n)], dtype=float)
    if not np.isfinite(v).all(): raise ValueError('invalid keys')
    return v


def animation(f, o):
    sq = f.ref(o[10]) if o.type == 'igTransform' and o[10] is not None else None
    if sq is None: return None
    if not sq.type.startswith('igTransformSequence'): raise ValueError('unsupported transform sequence')
    times = keylist(f, sq[11], 'q', 8)
    if times is None or not len(times): raise ValueError('missing sequence times')
    times = times[:,0] / 1e9
    if np.any(np.diff(times) <= 0): raise ValueError('invalid sequence times')
    channels = [keylist(f, sq[i], fmt, width) for i, fmt, width in ((2,'3f',12),(3,'4f',16),(4,'3f',12))]
    if any(a is not None and len(a) not in (0,1,len(times)) for a in channels): raise ValueError('unsupported key count')
    n = object.__new__(pack_battle.Node); n.static = matrix(o); n.seq = (times, *channels)
    mats = [n.local(i*.01) for i in range(17)]
    if not all(np.isfinite(m).all() for m in mats): raise ValueError('invalid animated matrix')
    return {'sequence_type': sq.type, 'local_matrices': [m.reshape(-1).tolist() for m in mats]}


def hierarchy(f, animated):
    info = f.of_type('igSceneInfo')
    if len(info) != 1 or info[0][5] is None: raise ValueError('expected one scene root')
    root = f.ref(info[0][5])
    if root is None: raise ValueError('missing scene root')
    nodes, nozzles, active = [], [], set()
    def walk(o, parent, world, path, depth):
        if depth > 256 or o.index in active or len(nodes) >= MAX_COUNT: raise ValueError('cyclic or excessive hierarchy')
        active.add(o.index)
        name = f.string(o[2]) if o[2] is not None else None
        m = matrix(o); world = m @ world; path = path + ([name] if name else [])
        item = {'id': len(nodes), 'object_id': o.index, 'name': name, 'type': o.type, 'parent': parent, 'local_matrix': m.reshape(-1).tolist()}
        if animated:
            a = animation(f, o)
            if a is not None: item['animation'] = a
        nodes.append(item)
        if name in NOZZLES and any(x in ('MUFFLER1','MUFFLER2') for x in path):
            nozzles.append({'name':name, 'node_id':item['id'], 'path':path, 'matrix':world.reshape(-1).tolist()})
        for child in child_list(f,o): walk(child,item['id'],world,path,depth+1)
        active.remove(o.index)
    walk(root,None,np.eye(4),[],0)
    return nodes,nozzles


def convert(effect, car):
    preflight(effect); preflight(car)
    ef, cf = IGB(effect), IGB(car)
    nodes,_ = hierarchy(ef, True); car_nodes,nozzles = hierarchy(cf, False)
    attrs = [{'id':o.index,'type':o.type,'fields':{str(k):{'type':v.type,'hex':v.raw.hex()} for k,v in o.fields.items()}} for o in ef.objects if o is not None and o.mem is None and ('Attr' in o.type or o.type == 'igSimpleShader')]
    images = []
    for image_obj, im in zip(ef.of_type('igImage'), ef.images()):
        im['id'] = image_obj.index
        data = im.pop('data'); im['data_base64'] = base64.b64encode(data).decode() if data is not None else None
        images.append(im)
    _, meshes = scene.meshes(effect); out = []
    for m in meshes:
        image = m['image']; state = {k:(v.index if isinstance(v, Obj) else v) for k,v in m['state'].items()}
        out.append({'name':m['name'],'path':m['path'],'matrix':m['matrix'].reshape(-1).tolist(),'image':image.index if isinstance(image, Obj) else image,'state':state,'vertices':{k:v.tolist() for k,v in m['verts'].items()},'triangles':m['tris'].tolist()})
    return {'schema':'re3dx.backfire','version':1,'matrix_convention':'row-major row-vector; child @ parent','frame_seconds':.01,'frame_count':17,'effect':{'nodes':nodes,'attributes':attrs,'images':images,'meshes':out},'car':{'nodes':car_nodes,'nozzles':nozzles},'limitations':['Animation interpolation is approximate; unknown material fields are retained raw.','Nozzle matrices are model-local.']}


def main():
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('effect'); p.add_argument('car'); p.add_argument('output_directory'); a=p.parse_args()
    target=Path(a.output_directory).resolve()
    temp_root = Path(tempfile.gettempdir()).resolve()
    if target == REPO or REPO in target.parents or temp_root not in target.parents: p.error('output must be a new directory under the system temporary directory, outside the repository')
    if target.exists(): p.error('output directory must not exist')
    try:
        data=json.dumps(convert(a.effect,a.car),allow_nan=False,separators=(',',':')).encode()
        if len(data)>MAX_OUTPUT: raise ValueError('output too large')
        target.mkdir(); (target/'backfire.json').write_bytes(data)
    except (ValueError,OSError,IndexError,KeyError,TypeError,struct.error,ZeroDivisionError) as exc: p.exit(1,'backfire_pack: %s\n'%exc)

if __name__ == '__main__': main()
