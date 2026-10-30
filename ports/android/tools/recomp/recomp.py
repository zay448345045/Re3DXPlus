"""Static recompiler: translate selected i386 functions of the arcade `main` into C.

The generated code keeps the original machine model: global registers, the
original stack discipline and a flat 32-bit virtual memory window (rodata, data,
bss, heap and stack) addressed through VA(). That keeps the arcade's physics
bit-for-bit the same without hand-porting thousands of SSE instructions.

Usage: recomp.py out.c root_symbol...   (callees are pulled in transitively)
"""
import bisect
import re
import struct
import sys

import capstone
from capstone import x86_const as X

import os
ELF = os.environ.get("WMMT_MAIN", os.path.join(os.path.dirname(os.path.abspath(__file__)), "main.elf"))
data = open(ELF, "rb").read()

# ---- ELF helpers ----
e_shoff, = struct.unpack_from("<I", data, 32)
e_shentsize, e_shnum, e_shstrndx = struct.unpack_from("<HHH", data, 46)
secs = [struct.unpack_from("<10I", data, e_shoff + i * e_shentsize) for i in range(e_shnum)]
_shstr = secs[e_shstrndx]
_nm = lambda off, base: data[base + off:data.index(b"\0", base + off)].decode()
SEC = {_nm(s[0], _shstr[4]): s for s in secs}


def file_off(va):
    for s in secs:
        if s[1] != 8 and s[3] <= va < s[3] + s[5]:  # not NOBITS
            return va - s[3] + s[4]
    raise KeyError(hex(va))


def rd32(va):
    return struct.unpack_from("<I", data, file_off(va))[0]


dynsym, dynstr = SEC[".dynsym"], SEC[".dynstr"]
SYMS = {}
NAME2VA = {}
sym_names = []
for i in range(dynsym[5] // 16):
    st_name, st_value, st_size, st_info, _, st_shndx = struct.unpack_from("<IIIBBH", data, dynsym[4] + i * 16)
    n = _nm(st_name, dynstr[4])
    sym_names.append(n)
    if st_value and st_shndx and (st_info & 0xf) == 2:
        SYMS[st_value] = n
        NAME2VA[n] = st_value
FUNC_ADDRS = sorted(SYMS)
TEXT = SEC[".text"]

# Code outside the game logic (display, sound, network, files, debug text) is not translated:
# calls to it return 0 at once, as under the Unicorn reference (emu/seq.py stub_nonlogic).
import subprocess
_dem = subprocess.run(["c++filt", "-n"], input="\n".join(SYMS[a] for a in FUNC_ADDRS), capture_output=True, text=True).stdout
DEMANGLED = dict(zip(FUNC_ADDRS, _dem.split("\n")))
# YOURTMOVIE_CPP (with FEQuat*): the story's realtime movies, their cars driven by yt::CGhost from the
# recorded trails (yt::CSampler) and their key cameras; youTitle: the titles' rules (GetTitleList),
# fed the run's yt::CTitle log
LOGIC = ("yt::", "geo::", "Gap::Math::", "GetE", "SConfig", "std::", "__gnu_cxx::", "operator",
         "YOURTMOVIE_CPP::", "FEQuat", "youTitle::")
NOT_LOGIC = ("yt::CSE::", "yt::CTenSE", "yt::CMapRunner",
             "yt::CFloatEdit", "yt::Mes", "yt::CHitLogger", "yt::CWallLogger", "yt::Disp_",
             "yt::Output_", "yt::Print_")
# stubs that answer differently; the stack holds the return address, then the arguments
STUB_IMPL = {
    "_ZN2yt5CLinx8CheckAckEv": "eax = (eax & 0xffffff00u) | 1;",  # no link cabinet: always acked
    # the traffic's display models: rc_other_setup(slot, ECarType) / rc_other_free(slot) in the port
    "_ZN16clCarDispManager13setupOtherCarEii": "eax = (eax & 0xffffff00u) | (rc_other_setup(M32(esp + 8), M32(esp + 12)) & 0xff);",
    "_ZN16clCarDispManager12freeOtherCarEi": "rc_other_free(M32(esp + 8)); eax = 0;",
    # the cabinet link under yt::CLinx (clNet's race packets in the arcade): the port's transport
    "_Z7Receivev": "rc_link_receive(); eax = 0;",
    "_Z12GetSelfPcbIdv": "eax = rc_link_pcb;",
    "_Z13GetSendPacketv": "eax = rc_link_tx;",
    "_Z16GetReceivePacketi": "eax = rc_link_rx_packet(M32(esp + 4));",
    "_Z4Sendv": "rc_link_send(); eax = 0;",
}
# instructions before which the port supplies display-side data: rc_hook(address)
HOOKS = {
    0x898aa8d,  # CSeq::Init calls CSetting::GetSettingPt with the car model's STireDimension at ebp-0xd4
    0x898e699,  # CSeq::Init calls CRivalSetting::GetSettingPt (story) with the rival's STireDimension at [esp+0x14]
    0x8985a4a,  # CSeq::Exec calls CRivalSetting::GetSettingPt (10-in-a-row) with the next rival's at [esp+0xc]
}


# yt::CSampler records the player's run for ghosts: SamplingConfig, SamplingStart, Sampling stay off
NO_RECORD = {0x89e1130, 0x89e03e0, 0x89e0428}


def stubbed(a):
    n = DEMANGLED.get(a)
    if a in NO_RECORD:
        return True
    return TEXT[3] <= a < TEXT[3] + TEXT[5] and n is not None and (not n.startswith(LOGIC) or n.startswith(NOT_LOGIC))

PLT = {}
rel = SEC[".rel.plt"]
plt_base = SEC[".plt"][3]
for i in range(rel[5] // 8):
    r_off, r_info = struct.unpack_from("<II", data, rel[4] + i * 8)
    PLT[plt_base + 16 + 16 * i] = sym_names[r_info >> 8].split("@")[0]


def func_end(a):
    i = bisect.bisect_right(FUNC_ADDRS, a)
    return FUNC_ADDRS[i] if i < len(FUNC_ADDRS) else TEXT[3] + TEXT[5]


md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
md.detail = True

REG32 = {X.X86_REG_EAX: "eax", X.X86_REG_ECX: "ecx", X.X86_REG_EDX: "edx", X.X86_REG_EBX: "ebx",
         X.X86_REG_ESP: "esp", X.X86_REG_EBP: "ebp", X.X86_REG_ESI: "esi", X.X86_REG_EDI: "edi"}
REG16 = {X.X86_REG_AX: "eax", X.X86_REG_CX: "ecx", X.X86_REG_DX: "edx", X.X86_REG_BX: "ebx",
         X.X86_REG_SP: "esp", X.X86_REG_BP: "ebp", X.X86_REG_SI: "esi", X.X86_REG_DI: "edi"}
REG8L = {X.X86_REG_AL: "eax", X.X86_REG_CL: "ecx", X.X86_REG_DL: "edx", X.X86_REG_BL: "ebx"}
REG8H = {X.X86_REG_AH: "eax", X.X86_REG_CH: "ecx", X.X86_REG_DH: "edx", X.X86_REG_BH: "ebx"}
XMM = {getattr(X, "X86_REG_XMM%d" % i): i for i in range(8)}
ST = {getattr(X, "X86_REG_ST%d" % i): i for i in range(8)}

PLT_IMPL = {  # name -> C body using the stack args at esp (no return address pushed)
    # float libm calls are evaluated in double and rounded once by the caller's fstp, the same way the
    # Unicorn reference does it; that also makes results identical on ARM and x86
    "sqrtf": "fpush(sqrt((double)AF(0)));", "sinf": "fpush(sin((double)AF(0)));", "cosf": "fpush(cos((double)AF(0)));",
    "tanf": "fpush(tan((double)AF(0)));", "fabsf": "fpush(fabs((double)AF(0)));",
    "asinf": "fpush(asin(fmax(-1.0, fmin(1.0, (double)AF(0)))));",
    "acosf": "fpush(acos(fmax(-1.0, fmin(1.0, (double)AF(0)))));",
    "atan2f": "fpush(atan2((double)AF(0), (double)AF(1)));", "fmodf": "fpush(fmod((double)AF(0), (double)AF(1)));",
    "powf": "fpush(pow((double)AF(0), (double)AF(1)));",
    "sqrt": "fpush(sqrt(AD(0)));", "sin": "fpush(sin(AD(0)));",
    "cos": "fpush(cos(AD(0)));", "pow": "fpush(pow(AD(0), AD(2)));", "exp": "fpush(exp(AD(0)));",
    "log": "fpush(log(AD(0)));", "log10": "fpush(log10(AD(0)));", "asin": "fpush(asin(AD(0)));",
    "acos": "fpush(acos(AD(0)));", "tan": "fpush(tan(AD(0)));",
    "memcpy": "memmove(VA(A32(0)), VA(A32(1)), A32(2)); eax = A32(0);",
    "memmove": "memmove(VA(A32(0)), VA(A32(1)), A32(2)); eax = A32(0);",
    "memset": "memset(VA(A32(0)), (int)A32(1), A32(2)); eax = A32(0);",
    "isnan": "eax = isnan(AD(0)) ? 1 : 0;", "isinf": "eax = isinf(AD(0)) ? 1 : 0;",
    "finite": "eax = isfinite(AD(0)) ? 1 : 0;",
    "_Znwj": "eax = rc_alloc(A32(0));", "_Znaj": "eax = rc_alloc(A32(0));", "malloc": "eax = rc_alloc(A32(0));",
    "_ZdlPv": "", "_ZdaPv": "", "free": "",
    "_ZNSt8ios_base4InitC1Ev": "", "_ZNSt8ios_base4InitD1Ev": "",
    "rand": "eax = rc_rand();", "random": "eax = rc_rand();",
    "strlen": "eax = (uint32_t)strlen((const char *)VA(A32(0)));",
    "strcpy": "strcpy((char *)VA(A32(0)), (const char *)VA(A32(1))); eax = A32(0);",
    # rc_strcmp: the patched iOS SDK has no plain strcmp for armv7
    "strcmp": "eax = (uint32_t)rc_strcmp((const char *)VA(A32(0)), (const char *)VA(A32(1)));",
    # yt::CConfigLoader's files (data/carconfig), from rc_config_dir
    "fopen": "eax = rc_fopen(A32(0));", "fclose": "rc_fclose(A32(0)); eax = 0;",
    "fgets": "eax = rc_fgets(A32(0), A32(1), A32(2));", "sscanf": "eax = rc_sscanf(A32(0), A32(1), esp + 8);",
    "strstr": "eax = rc_strstr(A32(0), A32(1));", "strcat": "eax = rc_strcat(A32(0), A32(1));",
    # the realtime movies' tables and trails (data/rtmovie); their editor's saves are not needed
    "fread": "eax = rc_fread(A32(0), A32(1), A32(2), A32(3));", "feof": "eax = rc_feof(A32(0));",
    "fscanf": "eax = rc_fscanf(A32(0), A32(1), esp + 8);",
    "sprintf": "eax = rc_sprintf(A32(0), A32(1), esp + 8);",
    "fprintf": "eax = 0;", "fwrite": "eax = 0;",
    "printf": "eax = 0;", "puts": "eax = 0;",
    "__cxa_guard_acquire": "eax = *(uint8_t *)VA(A32(0)) ? 0 : 1;",
    "__cxa_guard_release": "*(uint8_t *)VA(A32(0)) = 1;",
    # youTitle's checks of the card's name (std::wstring::compare(const wchar_t *))
    "_ZNKSbIwSt11char_traitsIwESaIwEE7compareEPKw": "eax = rc_wcompare(A32(0), A32(1));",
}

GPRS = ("eax", "ecx", "edx", "ebx", "esp", "ebp", "esi", "edi")
CALLER_SAVED = ("eax", "ecx", "edx", "esp")

CC = {"e": "ZF", "z": "ZF", "ne": "!ZF", "nz": "!ZF", "b": "CF", "c": "CF", "nae": "CF", "ae": "!CF", "nb": "!CF",
      "nc": "!CF", "be": "(CF || ZF)", "na": "(CF || ZF)", "a": "(!CF && !ZF)", "nbe": "(!CF && !ZF)",
      "l": "(SF != OF)", "nge": "(SF != OF)", "ge": "(SF == OF)", "nl": "(SF == OF)",
      "le": "(ZF || SF != OF)", "ng": "(ZF || SF != OF)", "g": "(!ZF && SF == OF)", "nle": "(!ZF && SF == OF)",
      "s": "SF", "ns": "!SF", "p": "PF", "pe": "PF", "np": "!PF", "po": "!PF", "o": "OF", "no": "!OF"}


class Unsupported(Exception):
    pass


class Func:
    def __init__(self, start, end=None, name=None, entry_regs=None):
        self.start = start
        self.end = end or func_end(start)
        self.name = name or SYMS.get(start, "sub_%x" % start)
        self.insns = list(md.disasm(data[file_off(start):file_off(start) + (self.end - start)], start))
        self.callees = set()
        self.indirect = False
        self.fragment = end is not None  # a code range, not a whole function: falling off the end returns

    def cname(self):
        return "f_%x" % self.start


def cfunc(a):
    return "f_%x" % a


class Translator:
    def __init__(self):
        self.funcs = {}
        self.queue = []
        self.used_plt = set()
        self.problems = []
        self.stubs = set()

    def add(self, a, end=None, name=None):
        if end is None and stubbed(a):
            self.stubs.add(a)
            return
        if a in self.funcs or a in self.queue:
            return
        self.queue.append((a, end, name))

    # ---- operands ----
    def addr(self, op):
        m = op.mem
        parts = []
        if m.base:
            parts.append(REG32[m.base])
        if m.index:
            parts.append("%s*%d" % (REG32[m.index], m.scale) if m.scale != 1 else REG32[m.index])
        if m.disp or not parts:
            parts.append("0x%xu" % (m.disp & 0xffffffff))
        return "(uint32_t)(" + " + ".join(parts) + ")"

    def get(self, ins, op, size=None):
        size = size or op.size
        if op.type == X.X86_OP_IMM:
            return "0x%xu" % (op.imm & ((1 << (8 * size)) - 1))
        if op.type == X.X86_OP_REG:
            r = op.reg
            if r in REG32:
                return REG32[r]
            if r in REG16:
                return "(%s & 0xffff)" % REG16[r]
            if r in REG8L:
                return "(%s & 0xff)" % REG8L[r]
            if r in REG8H:
                return "((%s >> 8) & 0xff)" % REG8H[r]
            raise Unsupported("reg %s" % ins.reg_name(r))
        if op.type == X.X86_OP_MEM:
            return {1: "M8", 2: "M16", 4: "M32"}[size] + "(%s)" % self.addr(op)
        raise Unsupported("op")

    def put(self, ins, op, val, size=None):
        size = size or op.size
        if op.type == X.X86_OP_REG:
            r = op.reg
            if r in REG32:
                return "%s = (uint32_t)(%s);" % (REG32[r], val)
            if r in REG16:
                n = REG16[r]
                return "%s = (%s & 0xffff0000u) | ((uint32_t)(%s) & 0xffff);" % (n, n, val)
            if r in REG8L:
                n = REG8L[r]
                return "%s = (%s & 0xffffff00u) | ((uint32_t)(%s) & 0xff);" % (n, n, val)
            if r in REG8H:
                n = REG8H[r]
                return "%s = (%s & 0xffff00ffu) | (((uint32_t)(%s) & 0xff) << 8);" % (n, n, val)
            raise Unsupported("reg")
        if op.type == X.X86_OP_MEM:
            return "W%d(%s, %s);" % (size * 8, self.addr(op), val)
        raise Unsupported("put")

    def xget(self, op):
        """Low float of an xmm or a float in memory."""
        if op.type == X.X86_OP_REG:
            return "X[%d].f[0]" % XMM[op.reg]
        return "MF(%s)" % self.addr(op)

    # ---- main ----
    def run(self):
        while self.queue:
            a, end, name = self.queue.pop()
            if a in self.funcs:
                continue
            f = Func(a, end, name)
            self.funcs[a] = f
            f.code = self.translate(f)

    def translate(self, f):
        out = []
        targets = set()
        for ins in f.insns:
            if ins.group(capstone.CS_GRP_JUMP) and ins.operands[0].type == X.X86_OP_IMM:
                targets.add(ins.operands[0].imm)
        for ins in f.insns:
            if ins.address in targets:
                out.append("L_%x:;" % ins.address)
            try:
                c = self.insn(f, ins)
            except Unsupported as ex:
                c = 'rc_fail("%s at %x: %s");' % (str(ex), ins.address, (ins.mnemonic + " " + ins.op_str).replace('"', "'"))
                self.problems.append("%x %s %s  (%s)" % (ins.address, ins.mnemonic, ins.op_str, ex))
            if ins.address in HOOKS:
                c = "@SAVE@ rc_hook(0x%xu); " % ins.address + c
            out.append("  RC_T(0x%xu); " % ins.address + c + "  /* %x: %s %s */" % (ins.address, ins.mnemonic, ins.op_str.replace("*/", "* /")))
        out.append("  @SAVE@ return;" if f.fragment else '  rc_fail("fell off end of %s");' % f.name)
        return out

    def flags_logic(self, res, size):
        bits = 8 * size
        mask = (1 << bits) - 1
        return ("{ uint32_t r_ = (uint32_t)(%s) & 0x%xu; ZF = r_ == 0; SF = (r_ >> %d) & 1; CF = 0; OF = 0; PF = parity(r_); }"
                % (res, mask, bits - 1))

    def insn(self, f, ins):
        m = ins.mnemonic
        ops = ins.operands
        prefix = ""
        if m.startswith("rep ") or m.startswith("repz ") or m.startswith("repe "):
            prefix, m = "rep", m.split()[1]
        if m == "nop":
            return ";"
        if m == "mov":
            return self.put(ins, ops[0], self.get(ins, ops[1]))
        if m in ("movzx", "movsx"):
            s = ops[1].size
            v = self.get(ins, ops[1])
            if m == "movsx":
                v = "(uint32_t)(int32_t)(%s)(%s)" % ({1: "int8_t", 2: "int16_t"}[s], v)
            return self.put(ins, ops[0], v)
        if m == "lea":
            return self.put(ins, ops[0], self.addr(ops[1]))
        if m == "push":
            return "esp -= 4; W32(esp, %s);" % self.get(ins, ops[0], 4)
        if m == "pop":
            return "{ uint32_t v_ = M32(esp); esp += 4; %s }" % self.put(ins, ops[0], "v_")
        if m == "leave":
            return "esp = ebp; ebp = M32(esp); esp += 4;"
        if m == "ret":
            n = ops[0].imm if ops else 0
            return "esp += %d; @SAVE@ return;" % (4 + n)
        if m == "cld":
            return ";"
        if m == "cwde":
            return "eax = (uint32_t)(int32_t)(int16_t)(eax & 0xffff);"
        if m == "cdq":
            return "edx = (eax & 0x80000000u) ? 0xffffffffu : 0;"
        if m == "call":
            return self.call(f, ins)
        if m == "jmp":
            op = ops[0]
            if op.type == X.X86_OP_IMM:
                t = op.imm
                if f.start <= t < f.end:
                    return "goto L_%x;" % t
                if t in PLT:
                    return self.plt_call(PLT[t], tail=True)
                self.add(t)
                f.callees.add(t)
                return "@SAVE@ %s(); return;" % cfunc(t)
            if op.type == X.X86_OP_MEM and op.mem.index and op.mem.scale == 4 and not op.mem.base:
                return self.jump_table(f, ins, op)
            # tail call through a register or pointer
            f.indirect = True
            return "{ uint32_t t_ = %s; @SAVE@ rc_dispatch(t_); return; }" % self.get(ins, op, 4)
        if m.startswith("j"):
            cc = CC.get(m[1:])
            if cc is None:
                raise Unsupported("jcc")
            t = ops[0].imm
            if not (f.start <= t < f.end):
                raise Unsupported("jcc out of function")
            return "if (%s) goto L_%x;" % (cc, t)
        if m.startswith("set"):
            return self.put(ins, ops[0], "(%s) ? 1 : 0" % CC[m[3:]])
        if m.startswith("cmov"):
            return "if (%s) { %s }" % (CC[m[4:]], self.put(ins, ops[0], self.get(ins, ops[1])))
        if m in ("add", "sub", "cmp", "and", "or", "xor", "test", "adc", "sbb"):
            return self.alu(ins, m, ops)
        if m in ("inc", "dec"):
            s = ops[0].size
            bits = 8 * s
            a = self.get(ins, ops[0])
            op = "+" if m == "inc" else "-"
            # inc/dec keep CF
            return ("{ uint32_t a_ = %s; uint32_t r_ = (a_ %s 1) & 0x%xu; %s ZF = r_ == 0; SF = (r_ >> %d) & 1; "
                    "OF = %s; PF = parity(r_); }" % (a, op, (1 << bits) - 1, self.put(ins, ops[0], "r_"), bits - 1,
                                                     "(r_ == 0x%xu)" % (1 << (bits - 1)) if m == "inc" else "(a_ == 0x%xu)" % (1 << (bits - 1))))
        if m == "neg":
            s = ops[0].size
            bits = 8 * s
            a = self.get(ins, ops[0])
            return ("{ uint32_t a_ = %s; uint32_t r_ = (0u - a_) & 0x%xu; %s CF = a_ != 0; ZF = r_ == 0; SF = (r_ >> %d) & 1; "
                    "OF = a_ == 0x%xu; PF = parity(r_); }" % (a, (1 << bits) - 1, self.put(ins, ops[0], "r_"), bits - 1, 1 << (bits - 1)))
        if m == "not":
            return self.put(ins, ops[0], "~%s" % self.get(ins, ops[0]))
        if m in ("shl", "sar", "shr", "sal"):
            s = ops[0].size
            if s != 4:
                raise Unsupported("narrow shift")
            a = self.get(ins, ops[0])
            cnt = self.get(ins, ops[1]) if len(ops) > 1 else "1"
            if m in ("shl", "sal"):
                expr, cf = "a_ << c_", "(a_ >> (32 - c_)) & 1"
            elif m == "shr":
                expr, cf = "a_ >> c_", "(a_ >> (c_ - 1)) & 1"
            else:
                expr, cf = "(uint32_t)((int32_t)a_ >> c_)", "((int32_t)a_ >> (c_ - 1)) & 1"
            return ("{ uint32_t a_ = %s, c_ = (%s) & 31; if (c_) { uint32_t r_ = %s; CF = %s; %s ZF = r_ == 0; "
                    "SF = r_ >> 31; PF = parity(r_); OF = 0; } }" % (a, cnt, expr, cf, self.put(ins, ops[0], "r_")))
        if m == "imul":
            if len(ops) == 2:
                return "{ int64_t p_ = (int64_t)(int32_t)%s * (int32_t)%s; %s CF = OF = p_ != (int32_t)p_; }" % (
                    self.get(ins, ops[0]), self.get(ins, ops[1]), self.put(ins, ops[0], "(uint32_t)p_"))
            if len(ops) == 3:
                return "{ int64_t p_ = (int64_t)(int32_t)%s * (int32_t)%s; %s CF = OF = p_ != (int32_t)p_; }" % (
                    self.get(ins, ops[1]), self.get(ins, ops[2]), self.put(ins, ops[0], "(uint32_t)p_"))
            if ops[0].size != 4:
                raise Unsupported("imul1 narrow")
            return ("{ int64_t p_ = (int64_t)(int32_t)eax * (int32_t)%s; eax = (uint32_t)p_; edx = (uint32_t)((uint64_t)p_ >> 32); "
                    "CF = OF = p_ != (int32_t)p_; }" % self.get(ins, ops[0]))
        if m == "mul" and ops[0].size == 4:
            return ("{ uint64_t p_ = (uint64_t)eax * %s; eax = (uint32_t)p_; edx = (uint32_t)(p_ >> 32); CF = OF = edx != 0; }"
                    % self.get(ins, ops[0]))
        if m in ("div", "idiv") and ops[0].size == 4:
            if m == "div":
                return ("{ uint64_t n_ = ((uint64_t)edx << 32) | eax; uint32_t d_ = %s; eax = (uint32_t)(n_ / d_); edx = (uint32_t)(n_ %% d_); }"
                        % self.get(ins, ops[0]))
            return ("{ int64_t n_ = (int64_t)(((uint64_t)edx << 32) | eax); int32_t d_ = (int32_t)%s; eax = (uint32_t)(int32_t)(n_ / d_); "
                    "edx = (uint32_t)(int32_t)(n_ %% d_); }" % self.get(ins, ops[0]))
        if prefix == "rep" or m in ("movsd", "stosd", "movsb", "stosb"):
            return self.string_op(ins, m, prefix)
        return self.sse_x87(f, ins, m, ops)

    def alu(self, ins, m, ops):
        s = ops[0].size
        bits = 8 * s
        mask = (1 << bits) - 1
        a = self.get(ins, ops[0])
        b = self.get(ins, ops[1], s)
        if ops[1].type == X.X86_OP_IMM:
            b = "0x%xu" % (ops[1].imm & mask)
        sb = bits - 1
        if m in ("add", "adc"):
            carry = " + (uint64_t)CF" if m == "adc" else ""
            return ("{ uint32_t a_ = %s, b_ = %s; uint64_t w_ = (uint64_t)a_ + b_%s; uint32_t r_ = (uint32_t)w_ & 0x%xu; %s "
                    "CF = (w_ >> %d) & 1; ZF = r_ == 0; SF = (r_ >> %d) & 1; OF = (((~(a_ ^ b_)) & (a_ ^ r_)) >> %d) & 1; PF = parity(r_); }"
                    % (a, b, carry, mask, self.put(ins, ops[0], "r_"), bits, sb, sb))
        if m in ("sub", "cmp", "sbb"):
            borrow = " - (uint64_t)CF" if m == "sbb" else ""
            store = "" if m == "cmp" else self.put(ins, ops[0], "r_")
            return ("{ uint32_t a_ = %s, b_ = %s; uint64_t w_ = (uint64_t)a_ - b_%s; uint32_t r_ = (uint32_t)w_ & 0x%xu; %s "
                    "CF = (w_ >> 63) & 1; ZF = r_ == 0; SF = (r_ >> %d) & 1; OF = (((a_ ^ b_) & (a_ ^ r_)) >> %d) & 1; PF = parity(r_); }"
                    % (a, b, borrow, mask, store, sb, sb))
        op = {"and": "&", "or": "|", "xor": "^", "test": "&"}[m]
        if m == "xor" and ops[0].type == X.X86_OP_REG and ops[1].type == X.X86_OP_REG and ops[0].reg == ops[1].reg:
            return self.put(ins, ops[0], "0") + " ZF = 1; SF = 0; CF = 0; OF = 0; PF = 1;"
        store = "" if m == "test" else self.put(ins, ops[0], "r_")
        return "{ uint32_t r_ = (%s %s %s) & 0x%xu; %s ZF = r_ == 0; SF = (r_ >> %d) & 1; CF = 0; OF = 0; PF = parity(r_); }" % (
            a, op, b, mask, store, sb)

    def string_op(self, ins, m, prefix):
        if m in ("movsd", "movsb"):
            n = 4 if m == "movsd" else 1
            body = "memmove(VA(edi), VA(esi), %d); esi += %d; edi += %d;" % (n, n, n)
        elif m in ("stosd", "stosb"):
            n = 4 if m == "stosd" else 1
            body = "{ uint32_t v_ = eax; memcpy(VA(edi), &v_, %d); edi += %d; }" % (n, n)
        elif m == "cmpsb" and prefix == "rep":  # repe cmpsb: compare while equal, flags of the last pair
            return ("while (ecx) { uint32_t a_ = *(uint8_t *)VA(esi), b_ = *(uint8_t *)VA(edi), r_ = (a_ - b_) & 0xffu; "
                    "esi++; edi++; ecx--; CF = a_ < b_; ZF = r_ == 0; SF = (r_ >> 7) & 1; "
                    "OF = (((a_ ^ b_) & (a_ ^ r_)) >> 7) & 1; PF = parity(r_); if (!ZF) break; }")
        else:
            raise Unsupported("string op %s" % m)
        if prefix == "rep":
            return "while (ecx) { %s ecx--; }" % body
        return body

    def call(self, f, ins):
        op = ins.operands[0]
        if op.type == X.X86_OP_IMM:
            t = op.imm
            if t in PLT:  # leave the return address in the stack slot the real call would have used
                return "W32(esp - 4, 0x%xu); " % (ins.address + ins.size) + self.plt_call(PLT[t])
            self.add(t)
            f.callees.add(t)
            return "esp -= 4; W32(esp, 0x%xu); @SAVE@ %s(); @LOAD@" % (ins.address + ins.size, cfunc(t))
        # indirect: through a vtable or function pointer
        f.indirect = True
        return "{ uint32_t t_ = %s; esp -= 4; W32(esp, 0x%xu); @SAVE@ rc_dispatch(t_); @LOAD@ }" % (self.get(ins, op, 4), ins.address + ins.size)

    def plt_call(self, name, tail=False):
        self.used_plt.add(name)
        body = PLT_IMPL.get(name)
        if body is None:
            body = 'rc_unknown("%s");' % name
        if "eax =" not in body:
            body += " eax = 0;"  # like the reference's stubs, so register traces line up
        # args sit at esp (no return address pushed here)
        if tail:  # jmp to an import: drop our return address so the args sit at esp again
            return "esp += 4; { %s } @SAVE@ return;" % body
        return "{ %s }" % body

    def jump_table(self, f, ins, op):
        base = op.mem.disp & 0xffffffff
        idx = REG32[op.mem.index]
        cases = []
        k = 0
        while True:
            t = rd32(base + 4 * k)
            if not (f.start <= t < f.end):
                break
            cases.append((k, t))
            k += 1
        f._jt = getattr(f, "_jt", set()) | {t for _, t in cases}
        sw = " ".join("case %d: goto L_%x;" % (k, t) for k, t in cases)
        self.extra_targets = True
        return "switch (%s) { %s default: rc_fail(\"jump table\"); }" % (idx, sw)

    def sse_x87(self, f, ins, m, ops):
        if m == "movss":
            d, s = ops
            if d.type == X.X86_OP_REG and s.type == X.X86_OP_REG:
                return "X[%d].f[0] = X[%d].f[0];" % (XMM[d.reg], XMM[s.reg])
            if d.type == X.X86_OP_REG:
                return "X[%d].u[0] = M32(%s); X[%d].u[1] = X[%d].u[2] = X[%d].u[3] = 0;" % (
                    XMM[d.reg], self.addr(s), XMM[d.reg], XMM[d.reg], XMM[d.reg])
            return "W32(%s, X[%d].u[0]);" % (self.addr(d), XMM[s.reg])
        if m in ("movaps", "movups"):
            d, s = ops
            if d.type == X.X86_OP_REG and s.type == X.X86_OP_REG:
                return "X[%d] = X[%d];" % (XMM[d.reg], XMM[s.reg])
            if d.type == X.X86_OP_REG:
                return "memcpy(&X[%d], VA(%s), 16);" % (XMM[d.reg], self.addr(s))
            return "memcpy(VA(%s), &X[%d], 16);" % (self.addr(d), XMM[s.reg])
        if m in ("movd",):
            d, s = ops
            if d.type == X.X86_OP_REG and d.reg in XMM:
                return "X[%d].u[0] = %s; X[%d].u[1] = X[%d].u[2] = X[%d].u[3] = 0;" % (
                    XMM[d.reg], self.get(ins, s, 4), XMM[d.reg], XMM[d.reg], XMM[d.reg])
            return self.put(ins, d, "X[%d].u[0]" % XMM[s.reg], 4)
        if m in ("addss", "subss", "mulss", "divss"):
            o = {"addss": "+", "subss": "-", "mulss": "*", "divss": "/"}[m]
            return "X[%d].f[0] = X[%d].f[0] %s %s;" % (XMM[ops[0].reg], XMM[ops[0].reg], o, self.xget(ops[1]))
        if m in ("minss", "maxss"):
            d = XMM[ops[0].reg]
            return "{ float a_ = X[%d].f[0], b_ = %s; X[%d].f[0] = (a_ %s b_) ? a_ : b_; }" % (
                d, self.xget(ops[1]), d, "<" if m == "minss" else ">")
        if m == "sqrtss":
            return "X[%d].f[0] = sqrtf(%s);" % (XMM[ops[0].reg], self.xget(ops[1]))
        if m in ("xorps", "andps", "andnps", "orps"):
            d = XMM[ops[0].reg]
            if ops[1].type == X.X86_OP_REG:
                src = "X[%d].u" % XMM[ops[1].reg]
                pre = ""
            else:
                pre = "uint32_t s_[4]; memcpy(s_, VA(%s), 16); " % self.addr(ops[1])
                src = "s_"
            e = {"xorps": "X[%d].u[i_] ^ %s[i_]", "andps": "X[%d].u[i_] & %s[i_]",
                 "andnps": "~X[%d].u[i_] & %s[i_]", "orps": "X[%d].u[i_] | %s[i_]"}[m] % (d, src)
            return "{ %sfor (int i_ = 0; i_ < 4; i_++) X[%d].u[i_] = %s; }" % (pre, d, e)
        if m in ("comiss", "ucomiss"):
            return ("{ float a_ = X[%d].f[0], b_ = %s; if (a_ != a_ || b_ != b_) { ZF = PF = CF = 1; } else { ZF = a_ == b_; "
                    "CF = a_ < b_; PF = 0; } OF = SF = 0; }" % (XMM[ops[0].reg], self.xget(ops[1])))
        if m.startswith("cmp") and m.endswith("ss"):
            pred = m[3:-2]
            e = {"eq": "a_ == b_", "lt": "a_ < b_", "le": "a_ <= b_", "unord": "(a_ != a_ || b_ != b_)",
                 "neq": "!(a_ == b_)", "nlt": "!(a_ < b_)", "nle": "!(a_ <= b_)", "ord": "!(a_ != a_ || b_ != b_)"}[pred]
            d = XMM[ops[0].reg]
            return "{ float a_ = X[%d].f[0], b_ = %s; X[%d].u[0] = (%s) ? 0xffffffffu : 0; }" % (d, self.xget(ops[1]), d, e)
        if m == "cvttss2si":
            return "%s" % self.put(ins, ops[0], "cvtt(%s)" % self.xget(ops[1]))
        if m == "cvtss2si":
            return "%s" % self.put(ins, ops[0], "cvtr(%s)" % self.xget(ops[1]))
        if m == "cvtsi2ss":
            return "X[%d].f[0] = (float)(int32_t)%s;" % (XMM[ops[0].reg], self.get(ins, ops[1], 4))
        if m in ("cvtss2sd", "cvtsd2ss"):
            raise Unsupported("double sse")
        if m == "unpcklps":
            d = XMM[ops[0].reg]
            s = XMM[ops[1].reg]
            return "{ xmm_t a_ = X[%d], b_ = X[%d]; X[%d].u[0] = a_.u[0]; X[%d].u[1] = b_.u[0]; X[%d].u[2] = a_.u[1]; X[%d].u[3] = b_.u[1]; }" % (d, s, d, d, d, d)
        if m == "shufps":
            raise Unsupported("shufps")
        # ---- x87 ----
        if m == "fld":
            o = ops[0]
            if o.type == X.X86_OP_REG:
                return "fpush(ST(%d));" % ST[o.reg]
            return "fpush(%s);" % ("MF(%s)" if o.size == 4 else "MD(%s)" if o.size == 8 else "XX(%s)") % self.addr(o)
        if m in ("fstp", "fst"):
            o = ops[0]
            pop = " fpop();" if m == "fstp" else ""
            if o.type == X.X86_OP_REG:
                return "ST(%d) = ST(0);%s" % (ST[o.reg], pop)
            if o.size == 4:
                return "WF(%s, (float)ST(0));%s" % (self.addr(o), pop)
            if o.size == 8:
                return "WD(%s, ST(0));%s" % (self.addr(o), pop)
            raise Unsupported("fstp size")
        if m == "fld1":
            return "fpush(1.0);"
        if m == "fldz":
            return "fpush(0.0);"
        if m in ("ffreep",):
            return "fpop();"
        if m in ("fmul", "fadd", "fdiv", "fsub", "fdivr", "fsubr", "fmulp", "faddp", "fdivp", "fsubp", "fdivrp", "fsubrp"):
            return self.x87_arith(ins)
        if m == "fucompp":
            return "fcmp(ST(0), ST(1)); fpop(); fpop();"
        if m in ("fucomp", "fcomp", "fucom", "fcom"):
            o = ops[0] if ops else None
            v = "ST(1)" if o is None else "ST(%d)" % ST[o.reg] if o.type == X.X86_OP_REG else \
                ("MF(%s)" if o.size == 4 else "MD(%s)") % self.addr(o)
            return "fcmp(ST(0), %s);%s" % (v, " fpop();" if m.endswith("p") else "")
        if m in ("fucomip", "fcomip", "fucomi", "fcomi"):
            return ("{ fpt a_ = ST(0), b_ = ST(%d); if (a_ != a_ || b_ != b_) { ZF = PF = CF = 1; } else { ZF = a_ == b_; "
                    "CF = a_ < b_; PF = 0; } OF = SF = 0; }%s" % (ST[ops[1].reg] if len(ops) > 1 else ST[ops[0].reg],
                                                             " fpop();" if m.endswith("p") else ""))
        if m == "fnstsw":
            return self.put(ins, ops[0], "fsw()", 2)
        if m == "sahf":
            return "{ uint32_t h_ = (eax >> 8) & 0xff; CF = h_ & 1; PF = (h_ >> 2) & 1; ZF = (h_ >> 6) & 1; SF = (h_ >> 7) & 1; }"
        if m == "fabs":
            return "ST(0) = ST(0) < 0 ? -ST(0) : ST(0);"
        if m == "fsqrt":
            return "ST(0) = fsqrtx(ST(0));"
        if m == "fpatan":
            return "ST(1) = (fpt)atan2((double)ST(1), (double)ST(0)); fpop();"
        if m == "fsincos":
            return "{ fpt t_ = ST(0); ST(0) = (fpt)sin((double)t_); fpush((fpt)cos((double)t_)); }"
        if m == "fild":
            o = ops[0]
            t = {2: "int16_t", 4: "int32_t", 8: "int64_t"}[o.size]
            return "{ %s v_; memcpy(&v_, VA(%s), %d); fpush((fpt)v_); }" % (t, self.addr(o), o.size)
        if m == "fchs":
            return "ST(0) = -ST(0);"
        if m == "fxch":
            # capstone lists both registers (st(0), st(i)); the one that isn't st(0) is last
            i = ST[ops[-1].reg] if ops else 1
            return "{ fpt t_ = ST(0); ST(0) = ST(%d); ST(%d) = t_; }" % (i, i)
        if m.startswith("fcmov"):
            cc = {"b": "CF", "e": "ZF", "be": "(CF || ZF)", "u": "PF",
                  "nb": "!CF", "ne": "!ZF", "nbe": "(!CF && !ZF)", "nu": "!PF"}[m[5:]]
            return "if (%s) ST(0) = ST(%d);" % (cc, ST[ops[-1].reg])
        if m == "fistp":
            raise Unsupported("fistp")
        raise Unsupported("mnemonic %s" % m)

    def x87_arith(self, ins):
        b = bytes(ins.bytes)
        ops = ins.operands
        if len(ops) == 1 and ops[0].type == X.X86_OP_MEM:
            o = ops[0]
            v = ("MF(%s)" if o.size == 4 else "MD(%s)") % self.addr(o)
            reg = (b[1] >> 3) & 7
            e = ["ST(0) + v", "ST(0) * v", None, None, "ST(0) - v", "v - ST(0)", "ST(0) / v", "v / ST(0)"][reg]
            if e is None or b[0] not in (0xd8, 0xdc):
                raise Unsupported("x87 mem form")
            return "{ fpt v = %s; ST(0) = %s; }" % (v, e)
        op, mod = b[0], b[1]
        i = mod & 7
        kind = (mod >> 3) & 7  # 0 add 1 mul 4 sub 5 subr 6 div 7 divr  (D8: st0 = st0 op sti)
        if op == 0xd8:
            d, x, y = 0, "ST(0)", "ST(%d)" % i
        elif op in (0xdc, 0xde):
            # DC/DE: st(i) = st(i) op st(0); the sub/div encodings are swapped relative to D8
            d, x, y = i, "ST(%d)" % i, "ST(0)"
            kind = {4: 5, 5: 4, 6: 7, 7: 6}.get(kind, kind)
        else:
            raise Unsupported("x87 opcode %02x" % op)
        e = {0: "%s + %s" % (x, y), 1: "%s * %s" % (x, y), 4: "%s - %s" % (x, y), 5: "%s - %s" % (y, x),
             6: "%s / %s" % (x, y), 7: "%s / %s" % (y, x)}[kind]
        return "ST(%d) = %s;%s" % (d, e, " fpop();" if op == 0xde else "")

    # ---- output ----
    def emit(self, path, extra_funcs=()):
        fs = [self.funcs[a] for a in sorted(self.funcs)]
        with open(path, "w") as o:
            o.write("/* Generated by emu/recomp.py from the arcade's main; do not edit. */\n")
            o.write('#define RC_GENERATED\n#include "rc_runtime.h"\n\n')
            for f in fs:
                o.write("void %s(void); /* %s */\n" % (f.cname(), f.name))
            o.write("\n")
            for a in sorted(self.stubs):
                o.write("/* %s (stub) */\nvoid %s(void) {\n  uint32_t esp = rc_cpu.esp, eax = rc_cpu.eax;\n"
                        "  %s esp += 4;\n  rc_cpu.esp = esp; rc_cpu.eax = eax;\n}\n"
                        % (DEMANGLED[a].replace("*/", "* /"), cfunc(a), STUB_IMPL.get(SYMS[a], "eax = 0;")))
            o.write("\n")
            for f in fs:
                # Each function works on its own copies of the registers it uses (rc_runtime.h), and of
                # the flags, which never live across a call or return in compiler-generated code.
                code = [re.sub(r"\bX\[(\d)\]", r"X\1", l) for l in f.code]
                body = "\n".join(l.split("  /* ")[0] for l in code)
                gprs = [r for r in GPRS if re.search(r"\b%s\b" % r, body)]
                xmms = sorted({int(x) for x in re.findall(r"\bX(\d)\b", body)})
                save = " ".join(["rc_cpu.%s = %s;" % (r, r) for r in gprs] + ["rc_cpu.X[%d] = X%d;" % (i, i) for i in xmms])
                # after a call: the callee saved ebx, esi, edi and ebp (cdecl) and esp is back where it was,
                # less what a callee-pops-arguments return took
                load = " ".join(["%s = rc_cpu.%s;" % (r, r) for r in gprs if r in CALLER_SAVED] +
                                ["X%d = rc_cpu.X[%d];" % (i, i) for i in xmms])
                code = [l.replace("@SAVE@", save).replace("@LOAD@", load) for l in code]
                o.write("/* %s */\nvoid %s(void) {\n  RC_ENTRY(0x%xu);\n  RC_FLAGS;\n" % (f.name, f.cname(), f.start))
                if gprs:
                    o.write("  uint32_t %s;\n" % ", ".join("%s = rc_cpu.%s" % (r, r) for r in gprs))
                if xmms:
                    o.write("  xmm_t %s;\n" % ", ".join("X%d = rc_cpu.X[%d]" % (i, i) for i in xmms))
                # jump-table targets need labels too
                jt = getattr(f, "_jt", set())
                if jt:
                    have = {int(l[2:-2], 16) for l in code if l.startswith("L_")}
                    fixed = []
                    for l in code:
                        if "/* " in l:
                            a = int(l.split("/* ")[1].split(":")[0], 16)
                            if a in jt and a not in have:
                                fixed.append("L_%x:;" % a)
                        fixed.append(l)
                    code = fixed
                o.write("\n".join(code) + "\n}\n\n")
            o.write("void rc_dispatch(uint32_t t) {\n  switch (t) {\n")
            for f in fs:
                o.write("  case 0x%xu: %s(); return;\n" % (f.start, f.cname()))
            for a in sorted(self.stubs):
                o.write("  case 0x%xu: %s(); return;\n" % (a, cfunc(a)))
            o.write('  default: rc_fail_addr("indirect call", t);\n  }\n}\n')


if __name__ == "__main__":
    out = sys.argv[1]
    t = Translator()
    for r in sys.argv[2:]:
        if ":" in r:  # start:end:name for code that is not a symbol (inlined constructors)
            s, e, n = r.split(":")
            t.add(int(s, 16), int(e, 16), n)
        else:
            t.add(NAME2VA[r] if r in NAME2VA else int(r, 16))
    t.run()
    t.emit(out)
    print("functions:", len(t.funcs), "stubs:", len(t.stubs), "plt:", sorted(t.used_plt))
    print("problems:", len(t.problems))
    for p in t.problems[:60]:
        print("  ", p)
