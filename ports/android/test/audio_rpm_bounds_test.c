/* Tests all 30 immutable table sets and actual game-thread target publication. */
#include <assert.h>
#include <math.h>
#include <stdio.h>
#include "../src/sound.c"
float car_kmh(const car_state *c) { (void)c; return 0; }
static void check_group(const band *bands, float r) {
  int highest = -1;
  for (int i=0; i<4; ++i) {
    const band *b = &bands[i];
    if (b->r0 == 10000 && b->r1 == 10000 && b->r2 == 10000 && b->r3 == 10000) continue;
    if (highest < 0 || b->r3 > highest) highest = b->r3;
  }
  assert(highest > 0);
  float adjusted = band_rpm(bands,r);
  assert(isfinite(adjusted));
  if (r < highest) {
    assert(adjusted == r);
    for (int i=0; i<4; ++i) {
      assert(band_gain(&bands[i], adjusted) == band_gain(&bands[i], r));
      assert(band_pitch(&bands[i], adjusted) == band_pitch(&bands[i], r));
    }
  }
  if (r >= 1000) {
    float sum=0;
    for (int i=0; i<4; ++i) sum += band_gain(&bands[i], adjusted);
    assert(sum > 0);
  }
}
int main(void) {
  const float inputs[] = {0, 1000, 4500, 8999, 9000, 9001, 9518.3f, 10000, 1000000, INFINITY, -INFINITY, NAN, -1};
  for (int k=0; k<SOUNDDB_NSETS; ++k) {
    engine_set = &SOUNDDB_SETS[k];
    const band *groups[] = {engine_set->engine_bands,engine_set->muffler_bands};
    for (int g=0; g<2; ++g) {
      for (int r=0; r<9000; ++r) check_group(groups[g], (float)r);
      check_group(groups[g], 9000); check_group(groups[g], 9001); check_group(groups[g], 10000);
    }
    for (unsigned j=0; j<sizeof(inputs)/sizeof(inputs[0]); ++j) {
      car_state car={0}; car_input in={0}; car.rpm=inputs[j]; in.throttle=1;
      E.rpm=1000; E.accel=5000; E.accel_target=5000; E.throttle_on=1; E.tick=0;
      snd_update(&car,&in,0.05f);
      float eng=0,muf=0;
      assert(isfinite(E.rpm) && E.rpm >= 0);
      for (int i=0; i<4; ++i) {
        float ev=LOOP_LOAD(LOOPS[S_ENG0+i].vol), mv=LOOP_LOAD(LOOPS[S_MUF0+i].vol);
        float ep=LOOP_LOAD(LOOPS[S_ENG0+i].pitch), mp=LOOP_LOAD(LOOPS[S_MUF0+i].pitch);
        assert(isfinite(ev) && isfinite(mv) && isfinite(ep) && isfinite(mp)); eng+=ev; muf+=mv;
      }
      if (inputs[j] >= 1000) assert(eng > 0 && muf > 0);
    }
  }
  puts("RPM bounds: 30 sets passed");
  return 0;
}
