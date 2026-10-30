"""Ground truth (needs the arcade main, see x86emu.ELF): run the arcade's own race sequence (yt::CSeq::Init / Exec) under Unicorn.

Everything outside the physics/game-logic namespaces is patched to `xor eax,eax; ret`
so display, sound, network and file systems are skipped.
"""
import struct, subprocess, sys
from unicorn import UC_HOOK_CODE
from x86emu import Emu

ALLOW = ("yt::", "geo::", "Gap::Math::", "GetE", "SConfig", "std::", "__gnu_cxx::", "operator")
DENY = ("yt::CLinx", "yt::CLx", "yt::SLx", "yt::CSE::", "yt::CTenSE", "yt::CTitle", "yt::CMapRunner", "yt::CFloatEdit",
        "yt::Mes", "yt::CSampler", "yt::CHitLogger", "yt::CWallLogger", "yt::Disp_", "yt::Output_", "yt::Print_")


def demangle_all(names):
    out = subprocess.run(["c++filt"], input="\n".join(names), capture_output=True, text=True).stdout.split("\n")
    return dict(zip(names, out))


def stub_nonlogic(e):
    """Patch every .text function outside the game-logic namespaces to `xor eax,eax; ret`."""
    dem = demangle_all(list(e.syms))
    n = 0
    text_lo, text_hi = 0x8422bc0, 0x8422bc0 + 0xeb7e14
    for name, a in e.syms.items():
        if not (text_lo <= a < text_hi):
            continue
        dn = dem.get(name, name)
        if dn.startswith(ALLOW) and not dn.startswith(DENY):
            continue
        e.uc.mem_write(a, b"\x31\xc0\xc3")
        n += 1
    e.uc.mem_write(e.syms["_ZN2yt5CLinx8CheckAckEv"], b"\xb0\x01\xc3")  # no link cabinet: always acked
    e.uc.mem_map(0, 0x10000)  # tolerate null-pointer use by skipped subsystems
    return n


def run_logic_ctors(e):
    """Static constructors of the game-logic translation units (tunable tables, float-edit params, ...).
    The physics reads globals these fill in; without them the tyres push the car sideways."""
    for i in range(0x75c // 4):
        a = e.u32(0x097eae44 + 4 * i)
        if 0x8970000 <= a < 0x8a00000:
            e.call(a)


class Seq:
    def __init__(self, stage=363, car=5, power=24, handling=10, trans=1, mode=2, area_id=28, dist=20000.0, lat=0.0, v0=None, ctors=True, verbose=False):
        e = self.e = Emu(trace_unknown=verbose)
        self.stubbed = stub_nonlogic(e)
        if ctors:
            run_logic_ctors(e)
        cfg = self.cfg = e.alloc(0x200)
        e.w32(cfg + 0x0, car)
        e.w32(cfg + 0x8, power)
        e.w32(cfg + 0xc, handling)
        e.w32(cfg + 0x10, trans)
        e.w32(cfg + 0x1c, stage)      # SConfigRaceField.stage
        e.w32(cfg + 0x24, area_id)    # .area (EAreaId; 28 = TkC1_In)
        e.wf(cfg + 0x28, dist)        # distance into the area, mm
        e.wf(cfg + 0x30, lat)         # lateral offset, mm
        e.w32(cfg + 0x34, mode)       # 2 = TimeAttack
        # The tyre layout normally comes from clCarDispManager (display side, stubbed here):
        # fill the same FD3S STireDimension the recompiled harness uses, right before GetSettingPt.
        def tire(uc, addr, size, user):
            from unicorn.x86_const import UC_X86_REG_EBP
            t = uc.reg_read(UC_X86_REG_EBP) - 0xd4
            uc.mem_write(t, struct.pack("<6fI", 690.0, 320.0, 1285.0, 684.9, 320.0, -1065.2, 5))
        e.uc.hook_add(UC_HOOK_CODE, tire, begin=0x898aa8d, end=0x898aa8d)
        if v0 is not None:  # override the start speed CSeq passes to SetFirstPos (TA: 33333 mm/s)
            def first(uc, addr, size, user):
                from unicorn.x86_const import UC_X86_REG_ESP
                uc.mem_write(uc.reg_read(UC_X86_REG_ESP) + 12, struct.pack("<f", v0))
            e.uc.hook_add(UC_HOOK_CODE, first, begin=0x89ba05c, end=0x89ba05c)
        e.call("_ZN2yt4CSeq4InitERK11SConfigPlay", cfg)
        self.m = e.u32(0x98028e4)
        self.inp = e.alloc(0x100)        # clGameInput
        self.inp_ptr = e.alloc(4)        # std::auto_ptr<clGameInput>
        e.w32(self.inp_ptr, self.inp)

    def step(self, steer=0.0, accel=0.0, brake=0.0, lever=1):
        e = self.e
        e.wf(self.inp, steer)
        e.wf(self.inp + 4, accel)
        e.wf(self.inp + 8, brake)
        e.w32(self.inp + 0x14, lever)
        e.call("_ZN2yt4CSeq4ExecERKSt8auto_ptrI11clGameInputE", self.inp_ptr)

    def heading(self):
        """Body yaw in degrees, from the display matrix (same convention as rc/drive.c)."""
        import math
        d = self.disp = getattr(self, "disp", None) or self.e.alloc(0x300)
        self.e.call(0x89b45d0, self.m, d)
        M = struct.unpack("<16f", self.e.rd(d + 4, 64))
        return math.degrees(math.atan2(-M[8], -M[10]))

    def io(self):
        return struct.unpack("<3fI", self.e.rd(self.e.u32(0x98028e0), 16))

    def pos(self):
        return [self.e.f(self.m + 0xa98 + 4 * k) for k in range(3)]


if __name__ == "__main__":
    s = Seq(verbose=True)
    print("stubbed", s.stubbed, "machine", hex(s.m))
    print("pos", s.pos())
    import math
    prev = s.pos()
    for i in range(240):
        s.step(accel=1.0)
        p = s.pos()
        if i % 20 == 19:
            dx, dz = p[0] - prev[0], p[2] - prev[2]
            print(i, "hdg %.0f" % s.heading(), "io", ["%.2f" % v for v in s.io()[:3]], s.io()[3], "kmh %.1f" % (s.e.f(s.m + 0xadc) * 0.0036), "move %.0f deg %.1f mm/f" % (math.degrees(math.atan2(dx, dz)), math.hypot(dx, dz)), [round(x / 100) for x in p])
        prev = p
