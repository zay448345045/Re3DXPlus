"""Synthetic ELF32 bounds and area-name semantics for both standalone navipackers."""
import importlib.util
from pathlib import Path
import struct
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


def module(port):
    path = ROOT / "ports" / port / "tools" / "navipack.py"
    spec = importlib.util.spec_from_file_location("navipack_" + port, path)
    obj = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(obj)
    return obj


def fixture():
    data = bytearray(256)
    data[:7] = b"\x7fELF\x01\x01\x01"
    struct.pack_into("<I", data, 28, 52)
    struct.pack_into("<HH", data, 42, 32, 1)
    struct.pack_into("<8I", data, 52, 1, 128, 0x1000, 0, 128, 128, 0, 0)
    struct.pack_into("<II", data, 128, 0x1010, 0x1015)
    data[144:155] = b"ROAD\0OFF\0xx"
    return data


class ElfTest(unittest.TestCase):
    def test_both_ports(self):
        for port in ("android", "ipad"):
            with self.subTest(port=port), tempfile.TemporaryDirectory() as temp:
                mod = module(port)
                path = Path(temp) / "main"
                data = fixture()
                path.write_bytes(data)
                elf = mod.Elf(path)
                self.assertEqual(elf.u32(0x1000), 0x1010)
                self.assertEqual(elf.cstr(elf.u32(0x1000)), "ROAD")
                self.assertEqual(elf.cstr(elf.u32(0x1004)), "OFF")
                with self.assertRaises(ValueError):
                    elf.u32(0x107e)
                with self.assertRaises(ValueError):
                    elf.cstr(0x2000)
                data[-1] = 65
                path.write_bytes(data)
                with self.assertRaises(ValueError):
                    mod.Elf(path).cstr(0x107f)
                data[4] = 2
                path.write_bytes(data)
                with self.assertRaises(ValueError):
                    mod.Elf(path)
                data = fixture()
                struct.pack_into("<I", data, 28, 250)
                path.write_bytes(data)
                with self.assertRaises(ValueError):
                    mod.Elf(path)
                data = fixture()
                struct.pack_into("<I", data, 52 + 16, 129)
                path.write_bytes(data)
                with self.assertRaises(ValueError):
                    mod.Elf(path)


if __name__ == "__main__":
    unittest.main()
