#!/usr/bin/env python3
"""Compile the actual iOS track classifier as a host C unit test."""
from pathlib import Path
import subprocess
import tempfile

src = (Path(__file__).resolve().parents[1] / "src/sound_ios.m").read_text()
start = src.index("static int track_group(")
end = src.index("\n@interface BgmErrors", start)
code = "#include <assert.h>\n#include <stdio.h>\n#include <string.h>\n" + src[start:end] + r"""
int main(void) {
  char name[32];
  assert(track_group(NULL) == 0);
  for (int i=1;i<=23;i++) { snprintf(name,sizeof name,"wm2_%02d",i); assert(track_group(name)==1); }
  for (int i=1;i<=12;i++) { snprintf(name,sizeof name,"wmr_%02d",i); assert(track_group(name)==2); }
  const char *bad[] = {"wm2_00", "wm2_24", "wmr_00", "wmr_13", "wm2_ 1", "wm2_1", "wm2_01x", "wm2_+1", "other", ""};
  for (unsigned i=0;i<sizeof bad/sizeof *bad;i++) assert(track_group(bad[i])==0);
  return 0;
}
"""
with tempfile.TemporaryDirectory() as d:
    source, exe = Path(d)/"test.c", Path(d)/"test"
    source.write_text(code)
    subprocess.run(["clang", "-std=c11", "-Wall", "-Werror", str(source), "-o", str(exe)], check=True)
    subprocess.run([str(exe)], check=True)
print("iOS BGM classifier: 35 tracks and invalid names passed")

# Exercise the actual cache/atomic function with a controlled scan, including
# concurrent first use and failure overriding an already-positive cache.
start = src.index("int ios_bgm_group_available(")
end = src.index("\nstatic int track_group", start)
cache_code = r"""
#include <assert.h>
#include <dispatch/dispatch.h>
#include <pthread.h>
static int failed_groups;
static int calls[3];
static int scan_bgm_group(int group) {
  __atomic_fetch_add(&calls[group], 1, __ATOMIC_SEQ_CST);
  return group == 1;
}
""" + src[start:end] + r"""
static void *worker(void *unused) {
  (void)unused;
  for (int i=0;i<5000;i++) { assert(ios_bgm_group_available(1)); assert(!ios_bgm_group_available(2)); }
  return NULL;
}
int main(void) {
  assert(ios_bgm_group_available(0));
  assert(!ios_bgm_group_available(-1) && !ios_bgm_group_available(3));
  pthread_t threads[8];
  for (int i=0;i<8;i++) assert(!pthread_create(&threads[i], NULL, worker, NULL));
  for (int i=0;i<8;i++) assert(!pthread_join(threads[i], NULL));
  assert(calls[1] == 1 && calls[2] == 1);
  __atomic_fetch_or(&failed_groups, 1 << 1, __ATOMIC_SEQ_CST);
  assert(!ios_bgm_group_available(1));
  assert(calls[1] == 1);
  return 0;
}
"""
with tempfile.TemporaryDirectory() as d:
    source, exe = Path(d)/"cache.c", Path(d)/"cache"
    source.write_text(cache_code)
    subprocess.run(["clang", "-std=c11", "-fblocks", "-Wall", "-Werror", str(source), "-o", str(exe)], check=True)
    subprocess.run([str(exe)], check=True)
print("iOS BGM cache: concurrent calls, missing group and failure override passed")
