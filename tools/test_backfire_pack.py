import importlib.util
from pathlib import Path
import struct
import tempfile
import unittest

import numpy as np

PATH = Path(__file__).resolve().parent / 'backfire_pack.py'
spec = importlib.util.spec_from_file_location('backfire_pack', PATH)
bp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bp)

class Field:
    def __init__(self, value): self.i32 = value

class Obj:
    def __init__(self, index, typ, fields): self.index, self.type, self.fields, self.mem = index, typ, fields, None
    def __getitem__(self, i): return self.fields.get(i)

class Fake:
    def __init__(self, objects, names): self.objects, self.names = objects, names
    def ref(self, field): return self.objects[field.i32] if field is not None and field.i32 >= 0 else None
    def string(self, field): return self.names[field.i32]
    def of_type(self, name): return [o for o in self.objects if o is not None and o.type == name]

def transform(index, name, x, children=None):
    m=np.eye(4,dtype='<f4'); m[3,0]=x
    field=Field(0); field.raw=m.tobytes()
    d={2:Field(name),8:field}
    if children is not None: d[7]=Field(children)
    return Obj(index,'igTransform',d)

class Tests(unittest.TestCase):
    def test_bad_and_oversized(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'bad.igb'; p.write_bytes(b'abc')
            with self.assertRaises(ValueError): bp.preflight(p)
            with p.open('wb') as f: f.truncate(bp.MAX_INPUT+1)
            with self.assertRaises(ValueError): bp.preflight(p)
            p.write_bytes(struct.pack('<12I', *([0]*10+[0xfada,8])))
            with self.assertRaises(ValueError): bp.preflight(p)

    def test_parent_composition_and_scope(self):
        root=transform(0,0,2,3); nozzle=transform(1,1,3)
        listing=Obj(3,'igNodeList',{2:Field(1),4:Field(4)})
        mem=Obj(4,'memory',{}); mem.mem=struct.pack('<i',1)
        info=Obj(2,'igSceneInfo',{5:Field(0)})
        f=Fake([root,nozzle,info,listing,mem],['MUFFLER1','MF_NULL_R1'])
        nodes, nozzles=bp.hierarchy(f,False)
        self.assertEqual(len(nodes),2); self.assertEqual(nozzles[0]['matrix'][12],5)
        self.assertEqual(nozzles[0]['path'],['MUFFLER1','MF_NULL_R1'])
        mem.mem=struct.pack('<i',0)
        with self.assertRaises(ValueError): bp.hierarchy(f,False)

    def test_child_bounds(self):
        root=transform(0,0,0,2); info=Obj(1,'igSceneInfo',{5:Field(0)})
        listing=Obj(2,'igNodeList',{2:Field(999),4:Field(3)}); mem=Obj(3,'memory',{}); mem.mem=b''
        with self.assertRaises(ValueError): bp.hierarchy(Fake([root,info,listing,mem],['root']),False)

if __name__ == '__main__': unittest.main()
