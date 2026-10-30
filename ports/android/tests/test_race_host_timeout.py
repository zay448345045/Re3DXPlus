#!/usr/bin/env python3
"""Compile the current race-network statements from both platforms with mocks."""
from pathlib import Path
import re
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[3]
PRE = r"""
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#define NET_NAME 20
#define VS_PROFILE 12
#define CAR_RACE_RUN 7
static struct { int vs_race, vs_closed; struct { int finish; } menu;
  struct { struct { int state; float countdown; } race; } car; } G;
static int host, closed, network, polls, host_polls, silence_calls;
static double seconds;
static int net_is_open(void) { return network; }
static int vs_host_is_open(void) { return host; }
static int net_host_closed(void) { return closed; }
static double now_ms(void) { return 123000.0; }
static double net_silence(double now) { if (now != 123.0) abort(); ++silence_calls; return seconds; }
static void vs_name(char *s, size_t n) { snprintf(s, n, "test"); }
static void vs_profile(unsigned char *p) { memset(p, 0, VS_PROFILE); }
static void vs_host_poll(double now, const char *name) { (void)now; (void)name; ++host_polls; }
static void net_poll(double now, int active, const char *name, const unsigned char *profile, int size) {
  (void)now; (void)active; (void)name; (void)profile; (void)size; ++polls;
}
static void production_block(void) {
"""
POST = r"""
}
static void check(const char *label, int expected, int expected_polls, int expected_silence) {
  production_block();
  if (G.vs_closed != expected || polls != expected_polls || silence_calls != expected_silence) {
    fprintf(stderr, "%s: closed=%d polls=%d silence_calls=%d\n", label, G.vs_closed, polls, silence_calls);
    exit(1);
  }
}
static void reset(void) {
  memset(&G, 0, sizeof G); G.vs_race = 1; G.car.race.state = CAR_RACE_RUN;
  host = closed = polls = host_polls = silence_calls = 0; network = 1; seconds = 11;
}
int main(void) {
  reset(); host=1; check("local host 11s", 0, 1, 0);
  if (host_polls != 1) return 1;
  reset(); check("joiner 11s", 1, 1, 1);
  reset(); seconds=10; check("joiner exactly 10s", 0, 1, 1);
  reset(); host=1; closed=1; G.car.race.state=0; G.car.race.countdown=4;
  check("explicit CLOSED bypasses host and race gates", 1, 1, 0);
  reset(); G.car.race.state=0; check("not running", 0, 1, 0);
  reset(); G.car.race.countdown=0.01f; check("countdown positive", 0, 1, 0);
  reset(); G.car.race.countdown=0; check("countdown zero", 1, 1, 1);
  reset(); G.menu.finish=1; closed=1; check("finished gates CLOSED", 0, 1, 0);
  reset(); G.vs_closed=1; closed=1; check("already closed", 1, 1, 0);
  reset(); G.vs_race=0; closed=1; check("not versus", 0, 0, 0);
  reset(); network=0; closed=1; check("network not open", 0, 0, 0);
  puts("race host timeout cases passed");
  return 0;
}
"""

def extract(text, platform):
    frame = text.index('void app_frame(float dt) {')
    anchor = 'if (G.vs_race && net_is_open()) {'
    start = text.index(anchor, frame)
    # Strip C comments and strings, preserving positions, before balancing braces.
    masked = re.sub(r'/\*.*?\*/|//[^\n]*|"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'',
                    lambda m: ' ' * len(m.group()), text, flags=re.S)
    end, depth = start + len(anchor), 1
    while depth and end < len(masked):
        depth += (masked[end] == '{') - (masked[end] == '}')
        end += 1
    if depth:
        raise ValueError(f'{platform}: unterminated race network block')
    defines = re.findall(r'^#define\s+VS_GONE\s+([^/\n]+)', text, re.M)
    if len(defines) != 1:
        raise ValueError(f'{platform}: expected exactly one VS_GONE definition')
    return '#define VS_GONE ' + defines[0].strip() + '\n', text[start:end]

with tempfile.TemporaryDirectory(prefix='race-host-test-') as tmp:
    for platform in ('android', 'ipad'):
        source = ROOT / 'ports' / platform / 'src' / 'app.c'
        define, block = extract(source.read_text(), platform)
        c, exe = Path(tmp) / (platform + '.c'), Path(tmp) / platform
        c.write_text(define + PRE + block + POST)
        subprocess.run(['cc', '-std=c99', '-Wall', '-Wextra', '-Werror', str(c), '-o', str(exe)], check=True)
        print(platform, flush=True)
        subprocess.run([str(exe)], check=True)
