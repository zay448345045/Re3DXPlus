#!/usr/bin/env python3
"""Append finish art to a private WCP1 copy; needs Pillow and local original assets."""
import argparse, math, struct, zlib
from pathlib import Path

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

def build(root,menu,story,original,output):
    try: from PIL import Image
    except ImportError as e: raise SystemExit('Pillow is required in your Python environment') from e
    base,bnames,_,_=bank(menu.read_bytes(),False)
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
    if len(base)+len(sprites)>65535 or len(bnames)+len(anims)>4096: raise ValueError('runtime count limit exceeded')
    data=struct.pack('<4sIII',b'WCP1',1,len(sprites),len(anims))+b''.join(sprites)+b''.join(anims)
    if len(data)>256*1024*1024: raise ValueError('runtime size limit exceeded')
    bank(data,True,base,bnames)
    with output.open('xb') as f: f.write(data)
    print(f'WCP1: {len(sprites)} sprites, {len(anims)} animations, {len(data)} bytes')

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for a in ('root','menu','story','original','output'): p.add_argument(a,type=Path)
    a=p.parse_args();build(a.root,a.menu,a.story,a.original,a.output)
if __name__=='__main__': main()
