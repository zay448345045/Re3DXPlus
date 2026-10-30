/* Exercise real WAVs at the observed high-RPM silence boundary. */
#include "sound.h"
#include <stdio.h>
#include <math.h>
float car_kmh(const car_state *c) { return c->speed * 3.6f; }
int main(int argc, char **argv) {
  if (argc != 2 || snd_init(argv[1])) return 2;
  car_state c = {0}; car_input in = {0}; short b[2048];
  c.rpm = 9518.3f; in.throttle = 1.0f; c.slip = 0;
  for (int i = 0; i < 150; ++i) { snd_update(&c, &in, 1.0f/60.0f); snd_mix(b, 1024); }
  double sum = 0;
  for (int i = 0; i < 1024; ++i) sum += (double)b[2*i] * b[2*i];
  printf("rpm=%.1f slip=0 throttle=1 engine_only_rms=%.2f\n", c.rpm, sqrt(sum/1024));
  return 0;
}
