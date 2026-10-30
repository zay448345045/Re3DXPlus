import importlib, os, pathlib, struct, sys, tempfile, unittest
from types import SimpleNamespace as S
from unittest import mock
import numpy as np
ROOT = pathlib.Path(__file__).resolve().parents[1]
def modules(port):
    for name in ("scene", "pack", "igb", "tex"): sys.modules.pop(name, None)
    sys.path.insert(0, str(ROOT / "ports" / port / "tools" / "stage"))
    try: return importlib.import_module("scene"), importlib.import_module("pack")
    finally: sys.path.pop(0)
class Fake:
    def __init__(self, objects): self.objects = objects
    def ref(self, x): return x
def fixture():
    rows = [(1.,2.,3.,126,26,0,255,.5,-.5,1.,.25,.75),(-2.,4.,7.,9,77,201,61,-1.,.25,0.,-.25,.5)]
    decl = bytes([0,1,0xc0,2,0x41,3,0x60,4,0x40,255])
    data = decl + b"".join(struct.pack("<3f4B5e", *r) for r in rows)
    vd = {3:{4:S(mem=data)},6:S(i32=26)}
    return Fake([vd]), {3:{2:S(i32=1),4:S(mem=struct.pack("<i",0))}}, rows
class ColorTest(unittest.TestCase):
    def test_contract(self):
        for port in ("android", "ipad"):
            with self.subTest(port=port):
                scene,pack=modules(port); f,va,rows=fixture(); v=scene.decode_vertices(f,va)
                rgba=np.array([r[3:7] for r in rows],dtype="u1")
                np.testing.assert_array_equal(v["color"],rgba[:,[2,1,0,3]])
                for key, sl in (("pos",slice(0,3)),("normal",slice(7,10)),("uv",slice(10,12))): np.testing.assert_array_equal(v[key],np.array([r[sl] for r in rows]))
                refs=[-1]*20; refs[0],refs[2],refs[11]=0,1,2
                oldf=Fake([S(mem=np.array([r[:3] for r in rows],dtype="<f4").tobytes()), S(mem=rgba.tobytes()), S(mem=np.array([r[10:] for r in rows],dtype="<f4").tobytes())])
                old=scene.decode_vertices_1_1(oldf,{2:S(mem=struct.pack("<20i",*refs)),3:S(i32=2)})
                np.testing.assert_array_equal(old["color"],rgba[:,[2,1,0,3]])
                np.testing.assert_array_equal(old["pos"],v["pos"]); np.testing.assert_array_equal(old["uv"],v["uv"])
                mesh=dict(verts=v,tris=np.array([[0,1,0]],dtype="u2"),image=None,matrix=np.eye(4,dtype="f4"),state={"blend":False},path=())
                with mock.patch.object(scene,"meshes",return_value=(f,[mesh])): result=pack.collect([(0,"synthetic")],None,[512]*3)[2][0][3]
                for key, expected in (("rgba",rgba),("pos",v["pos"]),("uv",v["uv"])): np.testing.assert_array_equal(result[key],expected)
                f.objects[0][6]=S(i32=25)
                with self.assertRaises(ValueError): scene.decode_vertices(f,va)
                with self.assertRaises(ValueError): scene.parse_decl(bytes([0,99,0x40,255,0]))
    @unittest.skipUnless(os.environ.get("STAGE_COLOR_IGB"),"set STAGE_COLOR_IGB")
    def test_real_asset(self):
        path=os.environ["STAGE_COLOR_IGB"]
        for port in ("android", "ipad"):
            with self.subTest(port=port):
                scene,pack=modules(port); modern=scene.decode_vertices
                def before(f,va):
                    v=modern(f,va)
                    if v is not None and "color" in v: v["color"]=v["color"][:,[2,1,0,3]]
                    return v
                library=pack.load_library(str(pathlib.Path(path).with_name('textures.igb')))
                with mock.patch.object(scene,"decode_vertices",side_effect=before): old=pack.collect([(0,path)],library,[512]*3)
                new=pack.collect([(0,path)],library,[512]*3)
                self.assertEqual(old[:2],new[:2]); self.assertGreater(len(new[1]),0)
                self.assertEqual(len(old[2]),len(new[2])); changed=0
                with tempfile.TemporaryDirectory(prefix="stage-color-") as tmp:
                    for label,result in (("before",old),("after",new)):
                        output = pathlib.Path(tmp) / ("stage_color_%s_%s.wpk" % (port, label))
                        pack.write(str(output),result[0],result[1],pack.split_by_chunk(result[2],4000),4000)
                for a,b in zip(old[2],new[2]):
                    self.assertEqual(a[:3],b[:3]); self.assertEqual(a[5],b[5])
                    for key in ("pos","uv"): np.testing.assert_array_equal(a[3][key],b[3][key])
                    np.testing.assert_array_equal(a[4],b[4]); x,y=a[3]["rgba"],b[3]["rgba"]
                    same=np.all(x==y,axis=1); swapped=np.all(x[:,[2,1,0,3]]==y,axis=1)
                    self.assertTrue(np.all(same|swapped)); changed+=np.count_nonzero(~same)
                self.assertGreater(changed,0); print(port,"meshes",len(new[2]),"changed vertices",changed)
if __name__=="__main__": unittest.main()
