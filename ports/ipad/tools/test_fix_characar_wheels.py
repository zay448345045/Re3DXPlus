import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import struct
import contextlib
import io

import numpy as np
from PIL import Image

spec = importlib.util.spec_from_file_location("wheel_fix", Path(__file__).with_name("fix_characar_wheels.py"))
f = importlib.util.module_from_spec(spec)
spec.loader.exec_module(f)


def fixture(fmt=1, group=0x100, material=False):
    w = h = 8
    if fmt == 0: value = (3 << 11) | (12 << 5) | 28
    elif fmt == 1: value = (1 << 12) | (5 << 8) | (14 << 4) | 15
    else: value = (3 << 11) | (10 << 6) | (28 << 1) | 1
    tex = struct.pack("<H", value) * (w*h)
    to, co, bo = 32, 96, 132
    end = 160
    pixels = end
    vo = pixels + len(tex)
    io = vo + 32
    header = struct.pack("<4sIIIfIII", b"WPK3", 1, 1, 1, 0., to, co, bo)
    tbl = struct.pack("<48sHHIII", b"rim.dds", w, h, fmt, pixels, len(tex))
    chunk = struct.pack("<6fIII", *([0.]*6), 0, 1, group)
    batch = struct.pack("<HHIIIIBBHHH", 0, 0, vo, 1, io, 1, 1 if material else 0, 0, 0 if material else 65535, 65535, 0)
    return header+tbl+chunk+batch+tex+bytes(32)+b"\0\0"


def wheel():
    return {"verts":{"uv":np.array([[0.,0.], [1.,0.], [1.,1.], [0.,1.]])}, "tris":np.array([[0,1,2],[0,2,3]])}


class RepairTests(unittest.TestCase):
    def test_swap_bitfields_and_involution(self):
        for fmt in (0,1,2):
            raw = np.arange(65536, dtype="<u2").tobytes()
            flipped = f.swap16(raw, fmt)
            self.assertEqual(raw, f.swap16(flipped, fmt))
            mask = (0x07e0, 0x0f0f, 0x07c1)[fmt]
            a = np.frombuffer(raw, "<u2"); b = np.frombuffer(flipped, "<u2")
            self.assertTrue(np.array_equal(a & mask, b & mask))

    def test_positive_and_double_run_all_formats(self):
        with tempfile.TemporaryDirectory() as d:
            for fmt in (0,1,2):
                original = fixture(fmt); t = f.parse_wpk(original)[0][0]
                rgb, alpha = f.decode16(original, t)
                ref = np.dstack((rgb[:,:,[2,1,0]].astype("uint8"), alpha.astype("uint8")))[::-1]
                path = Path(d)/("r%d.tga"%fmt); Image.fromarray(ref).save(path)
                refs = {("rim",8,8):[path]}
                with patch.object(f, "source_wheels", return_value=({"rim.dds":[wheel()]},set(),set())):
                    fixed, report = f.process(original, "unused", refs)
                    self.assertEqual(report[0]["status"], "swap", report)
                    start, end = t["off"], t["off"]+t["size"]
                    self.assertEqual(original[:start],fixed[:start]); self.assertEqual(original[end:],fixed[end:])
                    repeated, report2 = f.process(fixed, "unused", refs)
                    self.assertEqual(repeated, fixed); self.assertNotEqual(report2[0]["status"], "swap")

    def test_missing_ambiguous_and_reused(self):
        original = fixture(); mesh = {"rim.dds":[wheel()]}
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)/"rim.tga"; Image.new("RGBA",(8,8),(238,85,17,255)).save(p)
            for source, refs in [((mesh,set(),set()), {}), ((mesh,set(),set()), {("rim",8,8):[p,p]}), ((mesh,{"rim.dds"},set()), {("rim",8,8):[p]}), ((mesh,set(),{"rim.dds"}), {("rim",8,8):[p]})]:
                with patch.object(f, "source_wheels", return_value=source):
                    out, report = f.process(original, "unused", refs)
                self.assertEqual(out, original); self.assertEqual(report[0]["status"], "unknown")
            for data in (fixture(group=2), fixture(material=True)):
                with patch.object(f,"source_wheels",return_value=(mesh,set(),set())):
                    out, report = f.process(data, "unused", {("rim",8,8):[p]})
                self.assertEqual(out,data); self.assertEqual(report[0]["status"],"unknown")

    def test_grey_and_ambiguous(self):
        mask = np.ones((8,8),bool); a = np.full((8,8),255)
        p = np.full((8,8,3),120,dtype=np.int16)
        gray = np.full((8,8,4),120,dtype=np.uint8); gray[:,:,3]=255
        self.assertEqual(f.classify(p,a,gray,mask)["status"],"unknown")
        rgb = np.zeros((8,8,3),dtype=np.int16); rgb[:]=[100,40,180]
        mismatch = np.zeros((8,8,4),dtype=np.uint8); mismatch[:]=[230,90,20,255]
        self.assertEqual(f.classify(rgb,a,mismatch,mask)["status"],"unknown")

    def test_alpha_uv_and_existing_output(self):
        rgb = np.empty((8,8,3), dtype=np.int16); rgb[:] = [17,85,238]
        ref = np.empty((8,8,4), dtype=np.uint8); ref[:] = [238,85,17,255]
        mask = np.ones((8,8), dtype=bool)
        self.assertEqual(f.classify(rgb, np.zeros((8,8)), ref, mask)["status"], "unknown")
        self.assertEqual(f.classify(rgb, np.full((8,8),255), ref[:4], mask)["status"], "unknown")
        bad = wheel(); bad["verts"]["uv"][0,0] = 1.5
        with self.assertRaises(ValueError): f.uv_mask([bad],8,8)
        with tempfile.TemporaryDirectory() as d:
            root = Path(d); (root/"characar").mkdir(); (root/"changewheel").mkdir()
            (root/"input").mkdir(); (root/"exists").mkdir()
            with self.assertRaises(SystemExit): f.main([str(root),str(root/"input"),str(root/"exists")])

    def test_malformed(self):
        data=fixture()
        for bad in (b"", data[:100], data[:32]+b"\0"*64+data[96:]):
            with self.assertRaises(ValueError): f.parse_wpk(bad)
        bad=bytearray(data); struct.pack_into("<I",bad,92,1)
        with self.assertRaises(ValueError): f.parse_wpk(bad)
        with self.assertRaises(ValueError): f.uv_mask([{"verts":{}, "tris":np.array([[0,1,2]])}],8,8)

class Field:
    def __init__(self, value): self.i32 = value


class SourceImage:
    def __init__(self, order=100, fmt=15, name="rim.dds"):
        self.fields = {6: Field(order), 11: Field(fmt), 22: name}
    def __getitem__(self, key): return self.fields.get(key)


class SourceFile:
    def __init__(self, images): self.images = images
    def string(self, value): return value
    def of_type(self, kind): return self.images if kind == "igImage" else []


def source_mesh(image):
    return {"image": image, "path": ("WHEEL_L",), "state": {}}


class EngineOrderTests(unittest.TestCase):
    def run_source(self, data, images, meshes=None, encoded=None):
        sf = SourceFile(images)
        meshes = meshes if meshes is not None else [source_mesh(images[0])]
        t = f.parse_wpk(data)[0][0]
        encoded = encoded if encoded is not None else data[t["off"]:t["off"]+t["size"]]
        with patch.object(f.scene, "meshes", return_value=(sf, meshes)), patch.object(f.pack, "decode_image", return_value=object()), patch.object(f.pack, "encode16", return_value=(8, 8, 1, encoded)):
            return f.process_engine_order(data, "fixture")

    def test_positive_repeat_and_exact_bytes(self):
        data = fixture(); img = SourceImage(); t = f.parse_wpk(data)[0][0]
        result, rows = self.run_source(data, [img])
        self.assertEqual(rows[0]["status"], "swap")
        start, end = t["off"], t["off"] + t["size"]
        self.assertEqual(result[:start], data[:start]); self.assertEqual(result[end:], data[end:])
        self.assertEqual(result[start:end], f.swap16(data[start:end], 1))
        variant = source_mesh(img); variant['path'] = ('WHEEL_FL',)
        variant_result, _ = self.run_source(data, [img], [variant])
        self.assertEqual(variant_result, result)
        again, rows = self.run_source(result, [img], encoded=data[start:end])
        self.assertEqual(again, result); self.assertEqual(rows[0]["status"], "unknown")

    def test_reject_order_format_conflict_different_and_reuse(self):
        data = fixture(); img = SourceImage()
        scenarios = [([SourceImage(order=107)], None, None), ([SourceImage(fmt=14)], None, None),
                     ([img, SourceImage()], None, None), ([img], None, bytes(128)),
                     ([img], [source_mesh(img), {"image": img, "path": ("TIRE",), "state": {}}], None),
                     ([img], [source_mesh(img), {"image": None, "path": ("TIRE",), "state": {"env_image":img}}], None)]
        for images, meshes, encoded in scenarios:
            result, rows = self.run_source(data, images, meshes, encoded)
            self.assertEqual(result, data); self.assertEqual(rows[0]["status"], "unknown")
        with self.assertRaises(ValueError): self.run_source(data, [img], [source_mesh(None)])
        for data2 in (fixture(group=2), fixture(material=True)):
            result, rows = self.run_source(data2, [img]); self.assertEqual(result, data2); self.assertEqual(rows[0]["status"], "unknown")

    def test_lua_is_required_and_no_partial_success(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d); folder = root/"data"/"characar"/"a"; folder.mkdir(parents=True)
            (root/"input").mkdir(); (root/"input"/"a.wpk").write_bytes(fixture())
            (folder/"tire2.igb").write_bytes(b"ignored")
            (folder/"car.lua").write_text('TireStatus = {}', encoding='utf8')
            with contextlib.redirect_stdout(io.StringIO()) as stdout:
                code = f.main(['--source-engine-order', str(root/'data'), str(root/'input'), str(root/'out')])
            self.assertEqual(code, 1); self.assertIn('"error"', stdout.getvalue())
            (folder/"car.lua").write_text('TireStatus = { file = { "data/characar/a/tire2.igb" } }', encoding='utf8')
            self.assertEqual(f.source_from_lua(root/'data', 'a'), folder/'tire2.igb')
            (root/'input'/'b.wpk').write_bytes(fixture())
            with patch.object(f, 'process_engine_order', return_value=(fixture(), [{'status':'unchanged'}])), contextlib.redirect_stdout(io.StringIO()) as stdout:
                code = f.main(['--source-engine-order', str(root/'data'), str(root/'input'), str(root/'out2')])
            self.assertEqual(code, 1)
            self.assertTrue((root/'out2'/'a.wpk').exists())
            self.assertFalse((root/'out2'/'b.wpk').exists())
            self.assertIn('"error"', stdout.getvalue())


if __name__ == "__main__": unittest.main()
