#!/usr/bin/env python3
"""Offline sidecar tests: python3 test/test_story_cutin_bank.py. Requires cc, zlib and zip."""
import os, pathlib, platform, shutil, struct, subprocess, tempfile, zipfile, zlib
PROJECT=pathlib.Path(__file__).resolve().parents[1]
HARNESS = '#include <assert.h>\n#include <stdio.h>\n#include <stdlib.h>\n#include <string.h>\n#define GL_FUNC_REVERSE_SUBTRACT 0x800B\n#define GL_FUNC_ADD 0x8006\nvoid glBlendEquation(unsigned int);\n#include "anm.c"\nstatic void base(void) {\n memset(&A,0,sizeof A); A.nsprites=1; A.base_sprites=1;\n A.tex=calloc(1,sizeof *A.tex); A.offset=calloc(1,sizeof *A.offset); A.zsize=calloc(1,sizeof *A.zsize); A.used=calloc(1,sizeof *A.used); A.size=calloc(1,sizeof *A.size); A.ids=calloc(1,sizeof *A.ids); A.cols=calloc(1,sizeof *A.cols); A.ids[0]=17; A.size[0][0]=13;\n}\nint main(int argc, char **argv) {\n base(); load_extra(argv[1]);\n if (!strcmp(argv[2], "valid")) { assert(A.nsprites==2); assert(A.ids[0]==17 && A.size[0][0]==13); assert(A.ids[1]==200000 && A.size[1][0]==1); assert(A.extra_file); assert(anm_sprite(200000)==1); }\n else { assert(A.nsprites==1); assert(A.ids[0]==17 && A.size[0][0]==13); assert(!A.extra_file); }\n return 0;\n}\n'

def sprite(sid=200000, payload=None, w=1, h=1):
    if payload is None: payload=zlib.compress(b"abcd")
    return struct.pack("<iHHI", sid,w,h,len(payload))+payload

def bank(*sprites, anims=0):
    return b"WMN3"+struct.pack("<I",len(sprites))+b"".join(sprites)+struct.pack("<I",anims)

def main():
    with tempfile.TemporaryDirectory(prefix="wmmt-cutin-test-") as tmp:
        root=pathlib.Path(tmp); src=root/"test.c"; src.write_text(HARNESS)
        host=root/"host"; android=root/"android"
        linker="-Wl,-dead_strip" if platform.system()=="Darwin" else "-Wl,--gc-sections"
        args=[os.environ.get("CC","cc"),"-U__APPLE__","-std=c99","-ffunction-sections","-fdata-sections","-I",str(PROJECT/"src"),"-I",str(PROJECT/"test"),str(src),linker,"-lz","-lm"]
        subprocess.run(args+["-o",str(host)],check=True)
        subprocess.run(args+["-D__ANDROID__","-o",str(android)],check=True)
        def check(exe, directory, valid):
            subprocess.run([str(exe),str(directory),"valid" if valid else "invalid"],check=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        base=root/"base"; base.mkdir(); path=base/"story-cutin.bin"
        cases=[(bank(sprite()),True),(bank(sprite(17)),False),(bank(sprite(),sprite()),False),
               (bank(sprite(payload=b"bad")),False),(bank(sprite(w=0)),False),
               (bank(sprite(w=2049)),False),(bank(sprite(),anims=1),False),
               (bank(sprite())+b"x",False),(bank(sprite())[:-5],False),
               (b"WMN3"+struct.pack("<I",65535),False)]
        for contents,valid in cases: path.write_bytes(contents); check(host,base,valid)
        path.unlink(); check(host,base,False)
        data=root/"wmmt"; data.mkdir(); side=root/"wmmt-sidecars"; side.mkdir()
        legacy=data/"story-cutin.bin"; preferred=side/"story-cutin.bin"
        check(android,data,False)
        legacy.write_bytes(bank(sprite())); check(android,data,True)
        preferred.write_bytes(b"bad"); check(android,data,False)
        preferred.write_bytes(bank(sprite())); legacy.write_bytes(b"bad"); check(android,data,True)
        preferred.unlink(); check(android,data,False)
        packaged=root/"re3dxplus-data"/"hash-uuid"; packaged.mkdir(parents=True)
        preferred.write_bytes(bank(sprite())); check(android,packaged,True)
        if not shutil.which("zip"): raise RuntimeError("zip command not found")
        script=(PROJECT/"build_android.sh").read_text(); start=script.index("# Optional independent cut-in sprites;"); end=script.index("# Independent, pinned sidecar.",start); snippet=script[start:end]
        build=root/"build-test"; (build/"data").mkdir(parents=True); (build/"out/apk").mkdir(parents=True)
        asset=build/"data/story-cutin.bin"; archive=build/"out/base.apk"
        def package(explicit,exists):
            if exists: asset.write_bytes(b"test asset")
            elif asset.exists(): asset.unlink()
            with zipfile.ZipFile(archive,"w") as z: z.writestr("base",b"x")
            env=os.environ.copy(); env.pop("STORY_CUTIN_BIN",None); env["OUT"]="out"
            if explicit is not None: env["STORY_CUTIN_BIN"]=explicit
            p=subprocess.run(["sh","-e","-c",snippet],cwd=build,env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
            with zipfile.ZipFile(archive) as z: found="assets/story-cutin.bin" in z.namelist()
            return p.returncode,found
        assert package(None,True)==(0,True)
        assert package(None,False)==(0,False)
        assert package("missing.bin",True)[0]!=0
        assert package("",True)[0]!=0
        assert package("data/story-cutin.bin",True)==(0,True)
        print("11 bank, 6 Android path, 5 packaging checks passed")

if __name__=="__main__": main()
