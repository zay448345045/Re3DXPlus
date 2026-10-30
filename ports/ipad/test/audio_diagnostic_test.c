/* Offline mixer/diagnostic smoke test; no device or AAudio is exercised. */
#include "sound.h"
#include <math.h>
#include <stdio.h>
float car_kmh(const car_state *c) { return c->speed * 3.6f; }
static double measure(short *b, int n) {
  double sum = 0;
  for (int i = 0; i < n; ++i) sum += (double)b[i * 2] * b[i * 2];
  return sqrt(sum / n);
}
int main(int argc, char **argv) {
  if (argc != 2 || snd_init(argv[1])) { fprintf(stderr, "sample load failed\n"); return 1; }
  short b[1024 * 2]; car_state c = {0}; car_input in = {0};
  snd_quiet(); snd_mix(b, 1024); snd_diag_callback(b, 1024);
  double silence = measure(b, 1024);
  c.rpm = 5000; in.throttle = 1;
  for (int i = 0; i < 120; i++) { snd_update(&c, &in, 1.0f / 60); snd_mix(b, 1024); snd_diag_callback(b, 1024); }
  double engine = measure(b, 1024);
  c.rpm = 20000; in.throttle = 0; c.slip = 1;
  for (int i = 0; i < 180; i++) { snd_update(&c, &in, 1.0f / 60); snd_mix(b, 1024); snd_diag_callback(b, 1024); }
  double slip = measure(b, 1024);
  printf("silence_rms=%.3f engine_rms=%.3f slip_rms=%.3f\n", silence, engine, slip);
  return silence == 0 && engine > 0 && slip > 0 ? 0 : 1;
}
