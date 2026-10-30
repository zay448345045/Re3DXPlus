import importlib.util
import struct
import unittest
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[2]

def load(platform):
    path = ROOT / platform / 'tools/backfire_effect_pack.py'
    spec = importlib.util.spec_from_file_location('bfx_' + platform, path)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    return m

class Tests(unittest.TestCase):
    def test_both_implementations(self):
        for platform in ('android', 'ipad'):
            m = load(platform)
            a = np.repeat(np.eye(4)[None], 17, axis=0)
            b = a.copy(); a[:, 3, 0] = 3; b[:, 0, 0] = 2
            out = m.compose_frames(a, b)
            self.assertEqual(out[0, 3, 0], 6)
            rows = [(1, 9, 0, 'SAMLL_A', (2, 1), out), (2, 9, 1, 'SAMLL_A', (2, 1), out), (3, 9, 0, 'SAMLL_A', (3, 1), out)]
            nozzles = [('car|1', 'MUFFLER1', 'MF_NULL_R1', (0, 1), np.eye(4))]
            blob = m.encode_bfx(rows, nozzles)
            self.assertEqual(struct.unpack_from('<4sHHIII', blob), (b'BFX1', 1, 1, 17, 3, 1))
            self.assertEqual(struct.unpack_from('<III', blob, 20), (1, 9, 0))
            self.assertEqual(blob, m.encode_bfx(rows, nozzles))
            with self.assertRaises(ValueError): m.encode_bfx(rows + [rows[0]], nozzles)
            with self.assertRaises(ValueError): m.encode_bfx(rows, nozzles * 2)
            with self.assertRaises(ValueError): m.encode_bfx([(1, 9, 0, 'SAMLL_A', (-1,), out)], [])
            out[0, 0, 0] = float('nan')
            with self.assertRaises(ValueError): m.encode_bfx([(1, 9, 0, 'SAMLL_A', (1,), out)], [])
            with self.assertRaises(ValueError): m.compose_frames(a, out)

    def test_runtime_limits(self):
        from unittest.mock import patch
        for platform in ('android', 'ipad'):
            m = load(platform)
            frame = np.repeat(np.eye(4)[None], 17, axis=0)
            row = (1, 5, 0, 'SAMLL_A', (65535,), frame)
            nozzle = lambda key, slot='MF_NULL_R1': (key, 'MUFFLER1', slot, (), np.eye(4))
            for key in ('a|0', 'cars/a:aero-x|119', 'x'*253+'|0'):
                m.encode_bfx([row], [nozzle(key)])
            for key in ('x', '|0', 'a|120', 'a|01', 'a|-1', 'a|1|2', 'a |1', 'é|1', 'x'*254+'|0'):
                with self.subTest(platform=platform, key=key), self.assertRaises(ValueError):
                    m.encode_bfx([row], [nozzle(key)])
            with self.assertRaises(ValueError): m.encode_bfx([row], [nozzle('a|1'), nozzle('a|2', 'MF_NULL_L1')])
            with self.assertRaises(ValueError): m.encode_bfx([row], [nozzle('a|1'), nozzle('a|1')])
            with self.assertRaises(ValueError): m.encode_bfx([(1, 5, 0, 'SAMLL_A', (65536,), frame)], [])
            m._path((1,)*127)  # 253 bytes
            with self.assertRaises(ValueError): m._path((1,)*129)
            self.assertEqual(len(m._text('x'*255)), 257)
            with self.assertRaises(ValueError): m._text('é'*128)
            with self.assertRaises(ValueError): m.encode_bfx([row]*4097, [])
            with self.assertRaises(ValueError): m.encode_bfx([row], [nozzle('a|1')]*4097)
            many = [(i+1, 5, 0, 'SAMLL_A', (i,), frame) for i in range(4096)]
            m.encode_bfx(many, [])
            m.encode_bfx([row], [nozzle('car%d|0' % i) for i in range(4096)])
            with patch.object(m, 'MAX_BFX', 20):
                with self.assertRaises(ValueError): m.encode_bfx([row], [])

    def test_instance_dfs_and_nozzle_local_translation(self):
        import types
        m = load('android')
        class Node:
            def __init__(self, idx, typ, name, children=(), tx=0):
                self.index, self.type, self.mem = idx, typ, None
                self.name, self.children, self.tx = name, children, tx
            def __getitem__(self, n):
                return self.name if n == 2 else None
        nozzle = Node(2, 'igTransform', 'MF_NULL_R1', tx=3)
        parent = Node(1, 'igTransform', 'MUFFLER1', (nozzle,), tx=8)
        root = Node(0, 'igGroup', 'root', (parent,))
        info = types.SimpleNamespace(__getitem__=lambda n: root)
        class Info:
            def __getitem__(self, n): return root if n == 5 else None
        class Fake:
            def of_type(self, name): return [Info()]
            def ref(self, x): return x
            def string(self, x): return x
        def matrix(node):
            a = np.eye(4); a[3, 0] = node.tx; return a
        base = types.SimpleNamespace(matrix=matrix, child_list=lambda f, n: n.children)
        scene = types.SimpleNamespace(obj_list=lambda f, x: [], texture_image=lambda f, attrs: None)
        meshes, results = m.extract_scene(Fake(), False, scene, base)
        self.assertEqual(meshes, [])
        self.assertEqual(results[0][2], (0, 0))
        self.assertEqual(results[0][3][3, 0], 3)
        self.assertEqual(results[0][3][0, 0], 1)
        nozzle.children = (root,)
        with self.assertRaises(ValueError): m.extract_scene(Fake(), False, scene, base)

    def test_animated_dag_mesh_instances(self):
        import types
        m = load('android')
        class Node:
            def __init__(self, i, kind, name, children=(), attrs=()):
                self.index, self.type, self.name = i, kind, name
                self.children, self.attrs, self.mem = children, attrs, None
            def __getitem__(self, key): return self.name if key == 2 else self.attrs if key == 8 else None
        geometry_attr = Node(90, 'igGeometryAttr2', '', attrs='va')
        geometry_attr.__class__ = type('GeometryAttr', (Node,), {'__getitem__': lambda self, key: 'va' if key == 4 else None})
        shared = Node(50, 'igGeometry', 'mesh', attrs=[geometry_attr])
        dynamic = Node(20, 'igTransform', 'animated', children=[shared])
        variants = [Node(i+1, 'igGroup', name, children=[dynamic]) for i,name in enumerate(sorted(m.VARIANTS))]
        root = Node(0, 'igGroup', 'root', children=variants)
        class Info:
            def __getitem__(self, key): return root if key == 5 else None
        class Fake:
            def of_type(self, kind): return [Info()]
            def ref(self, obj): return types.SimpleNamespace(type='new') if obj == 'va' else obj
            def string(self, obj): return obj
        def animation(f, node):
            if node is not dynamic: return None
            frames = np.repeat(np.eye(4)[None],17,axis=0); frames[:,3,0] = np.arange(17)
            return {'local_matrices': frames.reshape(17,16)}
        base = types.SimpleNamespace(matrix=lambda o: np.eye(4), animation=animation, child_list=lambda f,o: o.children)
        verts = {'pos': np.zeros((3,3)), 'uv': np.zeros((3,2))}
        scene = types.SimpleNamespace(obj_list=lambda f, lst: lst or [], texture_image=lambda f, a: None,
                                      decode_vertices=lambda f,va: verts, decode_indices=lambda f,a,n: np.array([[0,1,2]]))
        meshes,_ = m.extract_scene(Fake(), True, scene, base)
        self.assertEqual(len(meshes), 6)
        self.assertEqual(len({x[3] for x in meshes}), 6)
        for mesh in meshes: self.assertEqual(mesh[8][16,3,0], 16)

    def test_truncated_memory_rejected(self):
        import types
        m = load('android')
        header = bytearray(48); struct.pack_into('<I', header, 24, 8)
        base = types.SimpleNamespace(preflight=lambda path: None)
        fake = types.SimpleNamespace(buf=header, objects=[types.SimpleNamespace(mem=b'1234', fields={})])
        with self.assertRaisesRegex(ValueError, 'memory region'): m.load_checked('unused', lambda path: fake, base)
        fake.objects[0].mem = b'12345678'
        self.assertIs(m.load_checked('unused', lambda path: fake, base), fake)

    def test_allow_empty_car_cli(self):
        import contextlib
        import io
        import tempfile
        from unittest.mock import patch
        for platform in ('android', 'ipad'):
            m = load(platform)
            good = [('MUFFLER1', 'MF_NULL_R1', (0,), np.eye(4))]
            def extract(value, effect, scene, base):
                if effect: return (['mesh'], [])
                if value == 'broken': raise ValueError('malformed body')
                return ([], good if value == 'good' else [])
            saved = []
            def write(f, meshes, cars, output, pack):
                if any(not entries for _, entries in cars): raise ValueError('no muffler nozzles found for empty')
                saved.append(cars)
                return (1, sum(len(e) for _, e in cars), 1)
            with tempfile.TemporaryDirectory() as d, patch.object(m, '_dependencies', return_value=(Path('/nonexistent'), None, None, None, None)), patch.object(m, 'load_checked', side_effect=lambda path, *args: path), patch.object(m, 'extract_scene', side_effect=extract), patch.object(m, 'write_effect', side_effect=write):
                def run(name, *args):
                    err = io.StringIO()
                    with contextlib.redirect_stderr(err), contextlib.redirect_stdout(io.StringIO()):
                        try: m.main(['effect', str(Path(d)/name), *args]); status = 0
                        except SystemExit as e: status = e.code
                    return status, err.getvalue()
                status, err = run('strict', '--car', 'empty|1=empty')
                self.assertNotEqual(status, 0); self.assertIn('no muffler nozzles', err)
                status, err = run('mixed', '--allow-empty-car', '--car', 'empty|1=empty', '--car', 'good|2=good', '--car', 'empty2|3=empty')
                self.assertEqual(status, 0); self.assertIn('WARN: no muffler nozzles for empty|1;', err); self.assertIn('WARN: no muffler nozzles for empty2|3;', err)
                self.assertEqual([car for car, _ in saved[-1]], ['good|2'])
                status, err = run('all-empty', '--allow-empty-car', '--car', 'empty|1=empty')
                self.assertEqual(status, 0); self.assertEqual(saved[-1], [])
                status, err = run('duplicate', '--allow-empty-car', '--car', 'empty|1=empty', '--car', 'empty|1=good')
                self.assertNotEqual(status, 0); self.assertIn('duplicate car ID', err)
                status, err = run('invalid', '--allow-empty-car', '--car', 'invalid=empty')
                self.assertNotEqual(status, 0); self.assertIn('invalid car key', err)
                status, err = run('conflict', '--allow-empty-car', '--car', 'same|1=empty', '--car', 'same|2=good')
                self.assertNotEqual(status, 0); self.assertIn('conflicting car IDs', err)
                status, err = run('broken', '--allow-empty-car', '--car', 'bad|4=broken')
                self.assertNotEqual(status, 0); self.assertIn('malformed body', err)

    def test_wpk_local_geometry(self):
        import tempfile
        from PIL import Image
        m = load('android')
        _, _, _, pack, _ = m._dependencies()
        class ImageObj: index = 5
        original = pack.decode_image
        pack.decode_image = lambda f, image: Image.new('RGBA', (2, 2), (255, 0, 0, 128))
        try:
            pos = np.array([[1,2,3],[4,5,6],[7,8,9]], dtype=np.float32)
            uv = np.array([[0,0],[1,0],[0,1]], dtype=np.float32)
            tri = np.array([[0,1,2]], dtype=np.int32)
            matrices = np.repeat(np.eye(4)[None], 17, axis=0); matrices[:,3,0] = 50
            state = {'blend': True, 'blend_func': (4,5), 'movie': None}
            mesh = (6, 0, 'SAMLL_A', (1,), ImageObj(), state, {'pos':pos, 'uv':uv}, tri, matrices)
            nozzle = ('car|1', [('MUFFLER1','MF_NULL_R1',(0,),np.eye(4))])
            with tempfile.TemporaryDirectory() as d:
                self.assertEqual(m.write_effect(None, [mesh], [nozzle], d, pack), (1,1,1))
                data = (Path(d) / 'backfire.wpk').read_bytes()
                h = struct.unpack_from('<4sIIIfIII', data); self.assertEqual(h[:4], (b'WPK2',1,1,1))
                _, flags, vo, nv, _, ni = struct.unpack_from('<HHIIII', data, h[7])
                self.assertEqual((flags,nv,ni), (1,3,3))
                actual = np.frombuffer(data, dtype=pack.VERTEX, count=nv, offset=vo)
                np.testing.assert_array_equal(actual['pos'], pos)
                np.testing.assert_array_equal(actual['uv'], uv)
        finally:
            pack.decode_image = original

if __name__ == '__main__': unittest.main()
