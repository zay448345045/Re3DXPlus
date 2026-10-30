/* Desktop check of the engine mixer: a throttle sweep with shifts, written to
 * sweep.wav. cc -O2 -I../src sndtest.c ../src/sound.c -lm */
#include <stdio.h>
#include <string.h>

#include "sound.h"

float car_kmh(const car_state *c) { return c->speed * 3.6f; }

static void put32(FILE *f, unsigned v) { fputc(v & 255, f); fputc(v >> 8 & 255, f); fputc(v >> 16 & 255, f); fputc(v >> 24, f); }

int main(int argc, char **argv) {
  if (snd_init(argc > 1 ? argv[1] : "..") != 0) fprintf(stderr, "some samples missing\n");
  static short buf[SND_RATE * 2 * 12];
  car_state c;
  memset(&c, 0, sizeof c);
  car_input in = { 0, 1, 0, 0, 0 };
  int frames = 0, per = SND_RATE / 60;
  float peak = 0;
  for (int f = 0; f < 60 * 12; ++f) {
    float t = f / 60.0f;
    /* rev 1000 -> 8000 over 3 s, shift (drop to 5500), rev again, then lift off at 9 s */
    float ph = t < 3 ? t / 3 : t < 6 ? (t - 3) / 3 : 1;
    c.rpm = t < 3 ? 1000 + 7000 * ph : t < 6 ? 5500 + 2500 * ph : t < 9 ? 8000 : 8000 - (t - 9) * 2000;
    if (f == 180) c.shift_event = 1;
    in.throttle = t < 9 ? 1 : 0;
    c.speed = t * 8;
    if (f == 400) c.impact = 25;
    c.slip = t > 7 && t < 8.5f ? 1 : 0;
    snd_update(&c, &in, 1.0f / 60.0f);
    snd_mix(buf + frames * 2, per);
    frames += per;
  }
  for (int i = 0; i < frames * 2; ++i) if (buf[i] > peak) peak = buf[i];
  FILE *o = fopen("sweep.wav", "wb");
  fwrite("RIFF", 1, 4, o); put32(o, 36 + frames * 4); fwrite("WAVEfmt ", 1, 8, o);
  put32(o, 16); put32(o, 1 | 2 << 16); put32(o, SND_RATE); put32(o, SND_RATE * 4); put32(o, 4 | 16 << 16);
  fwrite("data", 1, 4, o); put32(o, frames * 4); fwrite(buf, 4, frames, o); fclose(o);
  printf("%d frames, peak %.0f\n", frames, peak);
  return 0;
}
