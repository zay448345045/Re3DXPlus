/* Standalone host test. Pass the data directory containing sound/engine/rx714.wav. */
#define WMMT_LOOP_ATOMICS_TEST 1
#include "sound.c"
#include <assert.h>
#include <pthread.h>
float car_kmh(const car_state *c) { (void)c; return 0.0f; }
static sample fixtures[2];
static void *producer(void *unused) {
  (void)unused;
  for (int i = 0; i < 300000; ++i) {
    LOOP_STORE(LOOPS[0].s, &fixtures[i & 1]);
    LOOP_STORE(LOOPS[0].vol, (i & 1) ? 0.3f : 0.1f);
    LOOP_STORE(LOOPS[0].pitch, (i & 1) ? 0.75f : 1.25f);
  }
  return NULL;
}
static void *consumer(void *unused) {
  (void)unused; short out[128];
  for (int i = 0; i < 30000; ++i) snd_mix(out, 64);
  return NULL;
}
int main(int argc, char **argv) {
  assert(argc == 2); char path[4096];
  snprintf(path, sizeof path, "%s/sound/engine/rx714.wav", argv[1]);
  assert(load_wav(&fixtures[0], path) == 0);
  assert(fixtures[0].n > 512 && fixtures[0].rate > 0);
  fixtures[1] = fixtures[0];
  assert(atomic_is_lock_free(&LOOPS[0].s));
  assert(atomic_is_lock_free(&LOOPS[0].vol));
  assert(atomic_is_lock_free(&LOOPS[0].pitch));
  /* Independent interpolation and limiter reference at original iOS gain. */
  LOOP_STORE(LOOPS[0].s, &fixtures[0]);
  LOOP_STORE(LOOPS[0].vol, 0.30f);
  LOOP_STORE(LOOPS[0].pitch, 1.0f);
  short out[512 * 2]; snd_mix(out, 512);
  float gain = 0, dg = 0.30f / 512.0f;
  double pos = 0, step = (double)fixtures[0].rate / SND_RATE;
  for (int i = 0; i < 512; ++i) {
    int p = (int)pos;
    if (p >= fixtures[0].n - 1) { pos = fmod(pos, fixtures[0].n - 1); p = (int)pos; }
    float t = (float)(pos - p);
    float x = gain * (fixtures[0].data[p] + (fixtures[0].data[p + 1] - fixtures[0].data[p]) * t);
    short expected = (short)(32767.0f * tanhf(x * (1.0f / 32767.0f)));
    assert(abs(out[2*i] - expected) <= 1 && out[2*i] == out[2*i+1]);
    gain += dg; pos += step;
  }
  for (int k = 0; k < SOUNDDB_NSETS; ++k) {
    const band *groups[2] = {SOUNDDB_SETS[k].engine_bands, SOUNDDB_SETS[k].muffler_bands};
    for (int j = 0; j < 2; ++j) {
      float r = band_rpm(groups[j], 1000000.0f), sum = 0;
      for (int i = 0; i < 4; ++i) sum += band_gain(&groups[j][i], r);
      if (r > 0) assert(isfinite(sum) && sum > 0);
    }
  }
#if defined(__APPLE__) && !defined(__ANDROID__)
  /* Exercise the actual game-side gain path, not just the mixer. */
  car_state car = {0}; car_input input = {0};
  E.rpm = 4000.0f; E.accel = 1000.0f; car.rpm = 4000.0f; car.slip = 0.5f;
  snd_update(&car, &input, 0.0f);
  float rpm = band_rpm(engine_set->engine_bands, E.rpm);
  for (int i = 0; i < 4; ++i)
    assert(fabsf(LOOP_LOAD(LOOPS[i].vol) - 0.30f * band_gain(&engine_set->engine_bands[i], rpm) * (0.55f + 0.45f * 0.2f)) < 1e-6f);
  assert(fabsf(LOOP_LOAD(LOOPS[S_SLIP].vol) - 0.225f) < 1e-6f);
  snd_quiet();
#endif
  pthread_t p, c;
  assert(!pthread_create(&p, NULL, producer, NULL));
  assert(!pthread_create(&c, NULL, consumer, NULL));
  assert(!pthread_join(p, NULL)); assert(!pthread_join(c, NULL));
  free(fixtures[0].data);
  puts("sound tests passed: real WAV, high RPM, lock-free loop stress");
  return 0;
}
