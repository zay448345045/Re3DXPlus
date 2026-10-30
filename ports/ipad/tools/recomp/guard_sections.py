#!/usr/bin/env python3
"""Clamp the one section-manager underflow the recompiled physics inherited.

yt::CAreaProcessorJunction::MoveToPrev (emulated 0x89f8d9c) decrements the route's
section index without a lower bound.  At index 0 the next value is 0xffffffff, and the
function then reads area_array[-1] (an address in the 32-bit wrap) and stores whatever
32-bit word it finds there as the current area pointer.  The caller,
yt::CSectionManager::GetSectInfo_InterArea (0x89c4e14), adds that area's length at
+lots+0x20 and hands the result on, so a garbage area turns into an out-of-range read and
rc_fail_addr aborts the process.  The forward direction clamps instead (ReferAreaNext
returns nothing at the last area), so keeping the first known section is the symmetric
behaviour rather than a new game rule.

This script rewrites the generated src/phys/phys_rc.c in place: it inserts an early return
in exactly that function, before the index decrement, when the index is already 0.  It is
idempotent and refuses to guess: a missing or ambiguous pattern is an error.

Usage: guard_sections.py PATH/TO/phys_rc.c
Exit: 0 changed or already guarded, 2 unexpected input.
"""
import sys

SIGNATURE = "void f_89f8d9c(void) {"
NAME = "_ZN2yt22CAreaProcessorJunction10MoveToPrevERNS_18SAreaProcessorInfoE"
DEC_MARK = "/* 89f8da5: dec ecx */"
ARRAY_MARK = "/* 89f8daf: mov eax, dword ptr [eax + ecx*4] */"
MARKER = "PORT GUARD: Junction::MoveToPrev"

GUARD = """  /* %s: the original has no lower bound, so index 0 read area_array[-1] and
   * passed an arbitrary pointer on; keep the first known section instead. */
  if (ecx == 0) {
    esp = ebp; ebp = (uint32_t)(M32(esp)); esp += 8;
    rc_cpu.eax = eax; rc_cpu.ecx = ecx; rc_cpu.edx = edx; rc_cpu.esp = esp; rc_cpu.ebp = ebp; return;
  }
""" % MARKER


def main(argv):
    if len(argv) != 2:
        sys.stderr.write("usage: guard_sections.py PATH/TO/phys_rc.c\n")
        return 2
    path = argv[1]
    with open(path, "rb") as f:
        raw = f.read()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        sys.stderr.write("guard_sections: %s is not UTF-8 C source\n" % path)
        return 2

    if MARKER in text:
        if text.count(MARKER) != 1 or GUARD not in text:
            sys.stderr.write("guard_sections: %s has a damaged or partial guard\n" % path)
            return 2
        sys.stdout.write("guard_sections: %s already guarded\n" % path)
        return 0

    if text.count(SIGNATURE) != 1:
        sys.stderr.write("guard_sections: expected exactly one %r in %s\n" % (SIGNATURE, path))
        return 2
    start = text.index(SIGNATURE)
    line = text.rfind("\n", 0, start) + 1          # the signature's own line
    head = text.rfind("\n", 0, line - 1) + 1       # the comment line above it
    comment = text[head:line]
    if NAME not in comment:
        sys.stderr.write("guard_sections: %s: %r is not %s\n" % (path, SIGNATURE, NAME))
        return 2
    end = text.find("\n}\n", start)
    if end < 0:
        sys.stderr.write("guard_sections: %s: unterminated %s\n" % (path, SIGNATURE))
        return 2
    body = text[start:end]
    if body.count(DEC_MARK) != 1 or body.count(ARRAY_MARK) != 1:
        sys.stderr.write("guard_sections: %s: unexpected body of %s\n" % (path, NAME))
        return 2

    at = start + body.index(DEC_MARK)
    line_start = text.rfind("\n", 0, at) + 1
    patched = text[:line_start] + GUARD + text[line_start:]
    with open(path, "wb") as f:
        f.write(patched.encode("utf-8"))
    sys.stdout.write("guard_sections: guarded %s\n" % path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
