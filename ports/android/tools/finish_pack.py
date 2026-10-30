#!/usr/bin/env python3
"""Append finish art to a private WCP1 copy; needs Pillow and local original assets."""
import argparse, math, os, struct, zlib, zipfile
from pathlib import Path
from PIL import Image

DIGITS = tuple(range(0x268, 0x272))
MENU_DIGITS = tuple(range(102153, 102163))
METRE = 0x272

TABLE, COUNT = 0x9551560, 0x1f9b
RECORD = struct.Struct('<iH6f4h4h')
ANIMS = ('cons_g_last_000m', 'cons_g_last_saigo')

def take(data, pos, n):
    if n < 0 or pos+n > len(data): raise ValueError('truncated bank')
    return data[pos:pos+n], pos+n

def bank(data, card, base_ids=frozenset(), base_names=frozenset()):
    pos = 0
    head, pos = take(data, pos, 16 if card else 8)
    if card:
        magic, ver, ns, na = struct.unpack('<4sIII', head)
        if magic != b'WCP1' or ver != 1 or not na: raise ValueError('bad WCP header')
    else:
        magic, ns = struct.unpack('<4sI', head)
        if magic != b'WMN3': raise ValueError('bad WMN header')
    if ns > 65535: raise ValueError('too many sprites')
    ids, names, sprites, anims = set(), set(), [], []
    for _ in range(ns):
        start=pos; hdr,pos=take(data,pos,12); sid,w,h,z=struct.unpack('<iHHI',hdr)
        if sid < 0 or sid in ids or sid in base_ids or not w or not h or w > 2048 or h > 2048: raise ValueError('sprite collision or dimensions')
        pix,pos=take(data,pos,z or w*h*4)
        if z:
            d=zlib.decompressobj(); raw=d.decompress(pix,w*h*4+1)
            if len(raw)!=w*h*4 or not d.eof or d.unused_data or d.unconsumed_tail: raise ValueError('invalid compressed sprite')
        ids.add(sid); sprites.append(data[start:pos])
    if not card:
        h,pos=take(data,pos,4); na,=struct.unpack('<I',h)
    if na>4096: raise ValueError('too many animations')
    for _ in range(na):
        start=pos; h,pos=take(data,pos,56); name,nf,nr=struct.unpack('<48sII',h)
        if b'\0' not in name: raise ValueError('bad animation name')
        name=name.split(b'\0')[0].decode('ascii')
        if not name or name in names or name in base_names or not nf or nf>10000 or nr>200000: raise ValueError('animation collision or size')
        frames,pos=take(data,pos,nf*8)
        if any(s>nr or n>nr-s for s,n in struct.iter_unpack('<II',frames)): raise ValueError('bad frame range')
        records,pos=take(data,pos,nr*(RECORD.size if card else 44))
        if card:
            for r in RECORD.iter_unpack(records):
                if r[0] not in ids and r[0] not in base_ids: raise ValueError('missing sprite')
                if r[1]>2 or not all(math.isfinite(v) for v in r[2:8]): raise ValueError('bad record')
        names.add(name); anims.append(data[start:pos])
    if pos != len(data): raise ValueError('trailing bank bytes')
    return ids,names,sprites,anims

class Elf:
    def __init__(self,path):
        self.data=path.read_bytes()
        if self.data[:6]!=b'\x7fELF\x01\x01': raise ValueError('expected ELF32 little endian')
        ph,=struct.unpack_from('<I',self.data,28); size,n=struct.unpack_from('<HH',self.data,42)
        self.segs=[]
        for i in range(n):
            t,o,v,_,sz,_,_,_=struct.unpack_from('<8I',self.data,ph+i*size)
            if t==1: self.segs.append((v,o,sz))
    def off(self,va):
        for v,o,n in self.segs:
            if v<=va<v+n:return o+va-v
        raise ValueError(f'unmapped ELF address {va:x}')
    def sprite(self,sid):
        o=self.off(TABLE+sid*44); ptr,=struct.unpack_from('<I',self.data,o); start=self.off(ptr)
        name=self.data[start:self.data.index(b'\0',start)].decode('ascii')
        if not name.startswith('data/sprite/') or '..' in Path(name).parts: raise ValueError('unsafe sprite name')
        size=tuple(round(x) for x in struct.unpack_from('<2f',self.data,o+16))
        if min(size)<=0 or max(size)>2048: raise ValueError('bad source dimensions')
        return name,size

def animation(path):
    data=path.read_bytes(); nf,_=struct.unpack_from('<II',data)
    if not nf or nf>10000: raise ValueError('bad frame count')
    raw,pos=take(data,8,nf*8); frames=list(struct.iter_unpack('<II',raw))
    nr=max(s+n for s,n in frames)
    if nr>200000: raise ValueError('too many source records')
    raw,pos=take(data,pos,nr*64); records=[]
    for r in struct.iter_unpack('<i6f4i4ii',raw):
        if not 0<=r[0]<COUNT or not all(math.isfinite(x) for x in r[1:7]): raise ValueError('bad source record')
        records.append(RECORD.pack(r[0],{8:1,9:2}.get(r[15],0),*r[1:7],*(max(-32768,min(32767,x)) for x in r[7:15])))
    return frames,records

def image_record(record):
    sid, w, h, n = struct.unpack_from('<iHHI', record)
    data = record[12:]
    raw = zlib.decompress(data) if n else data
    return sid, Image.frombytes('RGBA', (w, h), raw)


def encode_image(sid, image):
    compressed = zlib.compress(image.tobytes(), 9)
    return struct.pack('<iHHI', sid, *image.size, len(compressed)) + compressed


def replacements(menu_sprites, sprites):
    """Use menu digits as substitute art, not an exact original restoration."""
    menu = {struct.unpack_from('<i', r)[0]: r for r in menu_sprites}
    existing = {struct.unpack_from('<i', r)[0]: r for r in sprites}
    if not set(MENU_DIGITS) <= menu.keys() or not set(DIGITS + (METRE,)) <= existing.keys():
        raise ValueError('missing required finish or menu digit IDs')
    out = {}
    for target, source in zip(DIGITS, MENU_DIGITS):
        _, image = image_record(menu[source])
        _, old = image_record(existing[target])
        if image.size != (32, 32) or old.size != (44, 44):
            raise ValueError('unexpected digit dimensions')
        out[target] = encode_image(target, image.resize((44, 44), Image.Resampling.LANCZOS))
    if len({image_record(out[i])[1].tobytes() for i in DIGITS}) != 10:
        raise ValueError('menu digit glyphs are not all distinct')
    _, metre = image_record(existing[METRE])
    if metre.size != (44, 44): raise ValueError('unexpected metre dimensions')
    pixels = metre.load()
    removed = 0
    for y in range(44):
        for x in range(44):
            r, g, b, a = pixels[x, y]
            if r > 180 and g == 0 and b == 0 and a == 255:
                if x not in (0, 43) and y not in (0, 43):
                    raise ValueError('red pixel outside metre border')
                pixels[x, y] = (0, 0, 0, 0)
                removed += 1
    if not removed: raise ValueError('metre border has no red pixels')
    out[METRE] = encode_image(METRE, metre)
    return out, removed


def menu_bytes(path):
    if zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as z:
            matches = [i for i in z.infolist() if i.filename == 'menu.bin']
            if len(matches) != 1: raise ValueError('zip must contain exactly one root menu.bin')
            return z.read(matches[0])
    return path.read_bytes()


def repair(menu_path, original, output):
    base, names, menu_sprites, _ = bank(menu_bytes(menu_path), False)
    data = original.read_bytes()
    ids, _, sprites, anims = bank(data, True, base, names)
    patches, removed = replacements(menu_sprites, sprites)
    sprites = [patches.get(struct.unpack_from('<i', r)[0], r) for r in sprites]
    result = data[:16] + b''.join(sprites) + b''.join(anims)
    bank(result, True, base, names)
    with os.fdopen(os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'wb') as f: f.write(result)
    print(f'substitute menu digits (not exact original art); removed {removed} border pixels; {len(ids)} sprites')


def build(root,menu,story,original,output):
    base,bnames,menu_sprites,_=bank(menu_bytes(menu),False)
    st,snames,_,_=bank(story.read_bytes(),False,base,bnames)
    if snames: raise ValueError('story bank must be sprites-only')
    base |= st
    ids,names,sprites,anims=bank(original.read_bytes(),True,base,bnames)
    if set(ANIMS)&(names|bnames): raise ValueError('finish animation already exists')
    required=set(range(0x268,0x273)); elf=Elf(root/'main')
    for name in ANIMS:
        frames,recs=animation(root/'data/anime'/f'{name}.anm')
        required.update(RECORD.unpack(r)[0] for r in recs)
        anims.append(struct.pack('<48sII',name.encode(),len(frames),len(recs))+b''.join(struct.pack('<II',*f) for f in frames)+b''.join(recs))
    # Existing IDs lack source provenance; never silently substitute unrelated artwork.
    if required & (base | ids): raise ValueError("finish sprite ID collision; cannot prove identity")
    for sid in sorted(required):
        name,size=elf.sprite(sid)
        with Image.open(root/name) as im:
            im=im.convert('RGBA')
            if im.size!=size: im=im.resize(size,Image.Resampling.LANCZOS)
            z=zlib.compress(im.tobytes(),9)
        sprites.append(struct.pack('<iHHI',sid,*size,len(z))+z)
    patches, removed = replacements(menu_sprites, sprites)
    sprites = [patches.get(struct.unpack_from('<i', r)[0], r) for r in sprites]
    print(f'substitute menu digits (not exact original art); removed {removed} border pixels')
    if len(base)+len(sprites)>65535 or len(bnames)+len(anims)>4096: raise ValueError('runtime count limit exceeded')
    data=struct.pack('<4sIII',b'WCP1',1,len(sprites),len(anims))+b''.join(sprites)+b''.join(anims)
    if len(data)>256*1024*1024: raise ValueError('runtime size limit exceeded')
    bank(data,True,base,bnames)
    with os.fdopen(os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'wb') as f: f.write(data)
    print(f'WCP1: {len(sprites)} sprites, {len(anims)} animations, {len(data)} bytes')

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--repair', action='store_true', help='repair an already-finished WCP1; arguments: menu[.zip] original output')
    p.add_argument('paths', nargs='+', type=Path)
    a=p.parse_args()
    if a.repair:
        if len(a.paths) != 3: p.error('--repair needs menu original output')
        repair(*a.paths)
    else:
        if len(a.paths) != 5: p.error('build needs root menu story original output')
        build(*a.paths)
if __name__=='__main__': main()
