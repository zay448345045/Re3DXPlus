/* Compile with -DSOUND_SOURCE='"../src/sound.c"'; see reported commands.
 * Include implementation to install deterministic, permanent synthetic samples.
 * fixed writes PCM to stdout; stress has one game producer and one callback. */
#include <pthread.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#ifndef SOUND_SOURCE
#define SOUND_SOURCE "../src/sound.c"
#endif
#include SOUND_SOURCE
float car_kmh(const car_state *c) { (void)c; return 123.0f; }
static short pcm[SOUNDDB_NSETS][8][127];
static short effect_pcm[S_COUNT][127];
static void setup(void) {
  /* snd_init precedes publication and callback start. No later sample writes. */
  (void)snd_init("/nonexistent-audio-loop-fixture");
  for (int k = 0; k < SOUNDDB_NSETS; ++k) for (int i = 0; i < 8; ++i) {
    for (int n = 0; n < 127; ++n) pcm[k][i][n] = (short)(((k*113+i*619+n*137)%28000)-14000);
    ENGINE_SAMPLES[k][i].data = pcm[k][i];
    ENGINE_SAMPLES[k][i].n = 17 + (k*7+i*11)%110;
    ENGINE_SAMPLES[k][i].rate = 16000 + (k*101+i*701)%32000;
  }
  for (int i = S_SLIP; i < S_COUNT; ++i) {
    for (int n = 0; n < 127; ++n) effect_pcm[i][n] = (short)(((i*251+n*199)%22000)-11000);
    SAMPLES[i].data = effect_pcm[i]; SAMPLES[i].n = 61 + i%60; SAMPLES[i].rate = 22050 + i*17;
  }
}
static void update(int t) {
  car_state car = {0}; car_input in = {0};
  car.rpm = 900 + (t*83)%3000; car.slip = (t%101)/100.0f;
  car.wall_hit = (t%4) == 0; in.throttle = (t%31)/30.0f;
  if (t%7 == 0) snd_set_car((unsigned)(t%SOUNDDB_NTYPES), (t%3) ? 12 : 2);
  if (t%13 == 0) snd_quiet();
  snd_update(&car, &in, 1.0f/60.0f);
}
static void *mixer(void *unused) {
  (void)unused; short out[512];
  for (int i=0; i<30000; ++i) snd_mix(out, 1+(i%256));
  return NULL;
}
int main(int argc, char **argv) {
  setup();
  if (argc > 1 && !strcmp(argv[1], "single")) {
    short out[512];
    for (int i=0; i<30000; ++i) { update(i); snd_mix(out, 1+(i%256)); }
    puts("single-thread stress complete"); return 0;
  }
  if (argc > 1 && !strcmp(argv[1], "stress")) {
    pthread_t thread;
    if (pthread_create(&thread, NULL, mixer, NULL)) return 2;
    for (int i=0; i<30000; ++i) update(i);
    if (pthread_join(thread, NULL)) return 3;
    puts("stress complete"); return 0;
  }
  short out[9000];
  for (int i=0; i<1200; ++i) {
    update(i);
    if (i%17 == 0) snd_menu(SND_SELECT);
    if (i%73 == 0) snd_menu_loop(SND_TUNING_BAR, 1);
    if (i%73 == 23) snd_menu_loop(SND_TUNING_BAR, 0);
    int n = i%59 == 0 ? 4200 : 1+(i*37)%399;
    snd_mix(out,n);
    if (fwrite(out,sizeof(short),2*(size_t)n,stdout) != 2*(size_t)n) return 4;
  }
  return 0;
}
