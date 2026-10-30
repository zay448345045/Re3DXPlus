"""Run pieces of the arcade's i386 `main` under Unicorn, as a reference for the port.

Loads the two PT_LOAD segments, points every PLT import at a stub, and lets
Python implement the few libc calls the game code needs. Float-returning libm
functions push their result on the x87 stack like the real ABI.
"""
import math
import struct
import sys

from unicorn import Uc, UC_ARCH_X86, UC_MODE_32, UC_HOOK_CODE, UC_HOOK_MEM_UNMAPPED, UcError
from unicorn.x86_const import UC_X86_REG_EAX, UC_X86_REG_ESP, UC_X86_REG_EIP, UC_X86_REG_ECX, UC_X86_REG_EDX

import os
ELF = os.environ.get("WMMT_MAIN", os.path.join(os.path.dirname(os.path.abspath(__file__)), "main.elf"))
STUB_BASE = 0x20000000
SCRATCH = 0x20100000
HEAP_BASE = 0x30000000
HEAP_SIZE = 0x08000000
STACK_TOP = 0x7ff00000
STACK_SIZE = 0x00400000
RET_MAGIC = 0x20200000  # return address that ends a call()

FLOAT_RET = {"acos", "acosf", "asin", "asinf", "atan2f", "cos", "cosf", "exp", "fabsf", "fmodf", "frexp", "ldexp",
             "log", "log10", "log2", "pow", "powf", "sin", "sinf", "sqrt", "sqrtf", "tan", "tanf"}


def f32(b, o=0):
    return struct.unpack_from("<f", b, o)[0]


class Emu:
    def __init__(self, trace_unknown=True):
        self.data = open(ELF, "rb").read()
        self.uc = Uc(UC_ARCH_X86, UC_MODE_32)
        self.trace_unknown = trace_unknown
        self._load()
        self._symbols()
        self._plt()
        self.heap = HEAP_BASE
        self.uc.mem_map(HEAP_BASE, HEAP_SIZE)
        self.uc.mem_map(STACK_TOP - STACK_SIZE, STACK_SIZE)
        self.uc.mem_map(RET_MAGIC, 0x1000)
        self.uc.hook_add(UC_HOOK_MEM_UNMAPPED, self._unmapped)
        self.unknown_calls = {}

    # ---- loading ----
    def _load(self):
        e_phoff, = struct.unpack_from("<I", self.data, 28)
        e_phentsize, e_phnum = struct.unpack_from("<HH", self.data, 42)
        for i in range(e_phnum):
            p_type, p_off, p_va, _, p_filesz, p_memsz, _, _ = struct.unpack_from("<8I", self.data, e_phoff + i * e_phentsize)
            if p_type != 1:
                continue
            lo, hi = p_va & ~0xfff, (p_va + p_memsz + 0xfff) & ~0xfff
            self.uc.mem_map(lo, hi - lo)
            self.uc.mem_write(p_va, self.data[p_off:p_off + p_filesz])

    def _symbols(self):
        """Dynamic symbols: name -> address, and the PLT relocations."""
        d = self.data
        e_shoff, = struct.unpack_from("<I", d, 32)
        e_shentsize, e_shnum, e_shstrndx = struct.unpack_from("<HHH", d, 46)
        secs = [struct.unpack_from("<10I", d, e_shoff + i * e_shentsize) for i in range(e_shnum)]
        shstr = secs[e_shstrndx]
        name = lambda off, base: d[base + off:d.index(b"\0", base + off)].decode()
        by = {name(s[0], shstr[4]): s for s in secs}
        dynsym, dynstr = by[".dynsym"], by[".dynstr"]
        self.syms, self.sym_names = {}, []
        for i in range(dynsym[5] // 16):
            st_name, st_value, st_size, st_info, _, st_shndx = struct.unpack_from("<IIIBBH", d, dynsym[4] + i * 16)
            n = name(st_name, dynstr[4])
            self.sym_names.append(n)
            if st_value and st_shndx:
                self.syms[n] = st_value
        rel = by[".rel.plt"]
        self.plt_rel = []
        for i in range(rel[5] // 8):
            r_off, r_info = struct.unpack_from("<II", d, rel[4] + i * 8)
            self.plt_rel.append((r_off, self.sym_names[r_info >> 8]))

    def _plt(self):
        self.uc.mem_map(STUB_BASE, 0x200000)
        self.stubs = {}
        for i, (got, n) in enumerate(self.plt_rel):
            addr = STUB_BASE + i * 16
            short = n.split("@")[0]
            self.stubs[addr] = short
            code = (b"\xdd\x05" + struct.pack("<I", SCRATCH) if short in FLOAT_RET else b"") + b"\xc3"
            self.uc.mem_write(addr, code)
            self.uc.mem_write(got, struct.pack("<I", addr))
        self.uc.hook_add(UC_HOOK_CODE, self._stub_hook, begin=STUB_BASE, end=STUB_BASE + len(self.plt_rel) * 16)

    def _unmapped(self, uc, access, address, size, value, data):
        eip = uc.reg_read(UC_X86_REG_EIP)
        print(f"unmapped access {access} at {address:#x} (eip {eip:#x})", file=sys.stderr)
        return False

    # ---- memory helpers ----
    def alloc(self, n, align=16):
        self.heap = (self.heap + align - 1) & ~(align - 1)
        p = self.heap
        self.heap += max(n, 1)
        self.uc.mem_write(p, b"\0" * max(n, 1))
        return p

    def rd(self, a, n):
        return bytes(self.uc.mem_read(a, n))

    def u32(self, a):
        return struct.unpack("<I", self.rd(a, 4))[0]

    def f(self, a):
        return struct.unpack("<f", self.rd(a, 4))[0]

    def wf(self, a, v):
        self.uc.mem_write(a, struct.pack("<f", v))

    def w32(self, a, v):
        self.uc.mem_write(a, struct.pack("<I", v & 0xffffffff))

    def cstr(self, a):
        out = b""
        while True:
            c = self.rd(a, 64)
            i = c.find(b"\0")
            if i >= 0:
                return (out + c[:i]).decode("latin1")
            out += c
            a += 64

    # ---- libc stubs ----
    def _args(self, n):
        esp = self.uc.reg_read(UC_X86_REG_ESP)
        return struct.unpack("<%dI" % n, self.rd(esp + 4, 4 * n))

    def _fargs(self, fmt):
        esp = self.uc.reg_read(UC_X86_REG_ESP)
        return struct.unpack("<" + fmt, self.rd(esp + 4, struct.calcsize("<" + fmt)))

    def _ret_float(self, v):
        self.uc.mem_write(SCRATCH, struct.pack("<d", v))

    def _stub_hook(self, uc, address, size, user):
        n = self.stubs.get(address)
        if n is None:
            return
        eax = 0
        if n in ("memcpy", "memmove", "wmemcpy"):
            dst, src, cnt = self._args(3)
            if n == "wmemcpy":
                cnt *= 4
            if cnt:
                uc.mem_write(dst, self.rd(src, cnt))
            eax = dst
        elif n in ("memset",):
            dst, c, cnt = self._args(3)
            if cnt:
                uc.mem_write(dst, bytes([c & 0xff]) * cnt)
            eax = dst
        elif n == "bzero":
            dst, cnt = self._args(2)
            uc.mem_write(dst, b"\0" * cnt)
        elif n in ("malloc", "_Znwj", "_Znaj"):
            eax = self.alloc(self._args(1)[0])
        elif n == "calloc":
            a, b = self._args(2)
            eax = self.alloc(a * b)
        elif n == "strlen":
            eax = len(self.cstr(self._args(1)[0]))
        elif n == "strcmp":
            a, b = self._args(2)
            sa, sb = self.cstr(a), self.cstr(b)
            eax = (sa > sb) - (sa < sb)
        elif n in ("sqrtf", "sinf", "cosf", "tanf", "fabsf", "asinf", "acosf"):
            x, = self._fargs("f")
            fn = {"sqrtf": lambda v: math.sqrt(v) if v >= 0 else float("nan"), "sinf": math.sin, "cosf": math.cos,
                  "tanf": math.tan, "fabsf": abs, "asinf": lambda v: math.asin(max(-1, min(1, v))),
                  "acosf": lambda v: math.acos(max(-1, min(1, v)))}[n]
            self._ret_float(fn(x))
        elif n in ("sqrt", "sin", "cos", "tan", "exp", "log", "log10", "log2", "asin", "acos"):
            x, = self._fargs("d")
            fn = {"sqrt": math.sqrt, "sin": math.sin, "cos": math.cos, "tan": math.tan, "exp": math.exp,
                  "log": math.log, "log10": math.log10, "log2": math.log2, "asin": math.asin, "acos": math.acos}[n]
            self._ret_float(fn(x))
        elif n == "atan2f":
            y, x = self._fargs("ff")
            self._ret_float(math.atan2(y, x))
        elif n == "fmodf":
            x, y = self._fargs("ff")
            self._ret_float(math.fmod(x, y))
        elif n == "powf":
            x, y = self._fargs("ff")
            self._ret_float(math.pow(x, y))
        elif n == "pow":
            x, y = self._fargs("dd")
            self._ret_float(math.pow(x, y))
        elif n in ("isnan", "isinf", "finite"):
            x, = self._fargs("d")
            eax = {"isnan": math.isnan(x), "isinf": math.isinf(x), "finite": math.isfinite(x)}[n]
        elif n in ("rand", "random"):
            eax = 12345
        elif n in ("__cxa_guard_acquire",):
            g, = self._args(1)
            eax = 0 if self.rd(g, 1)[0] else 1
        elif n == "__cxa_guard_release":
            g, = self._args(1)
            uc.mem_write(g, b"\1")
        else:
            self.unknown_calls[n] = self.unknown_calls.get(n, 0) + 1
            if self.trace_unknown and self.unknown_calls[n] <= 2:
                print("stub:", n, file=sys.stderr)
        uc.reg_write(UC_X86_REG_EAX, eax & 0xffffffff)

    # ---- calling ----
    def sym(self, name):
        return self.syms[name]

    def call(self, fn, *args, this_ecx=None, count=0):
        """cdecl call; args are ints (pointers) or Python floats (pushed as f32)."""
        if isinstance(fn, str):
            fn = self.sym(fn)
        esp = STACK_TOP - 0x1000
        words = []
        for a in args:
            if isinstance(a, float):
                words.append(struct.unpack("<I", struct.pack("<f", a))[0])
            else:
                words.append(a & 0xffffffff)
        esp -= 4 * len(words) + 4
        self.uc.mem_write(esp, struct.pack("<I", RET_MAGIC) + b"".join(struct.pack("<I", w) for w in words))
        self.uc.reg_write(UC_X86_REG_ESP, esp)
        if this_ecx is not None:
            self.uc.reg_write(UC_X86_REG_ECX, this_ecx)
        try:
            self.uc.emu_start(fn, RET_MAGIC, count=count)
        except UcError as e:
            eip = self.uc.reg_read(UC_X86_REG_EIP)
            raise RuntimeError(f"emulation failed in {fn:#x} at eip {eip:#x}: {e}")
        return self.uc.reg_read(UC_X86_REG_EAX)
