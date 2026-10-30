/* Desktop check of the online versus: a machine joins the server (tools/vs_server.py), the
 * first to join starts a race once `players` are in, and each drives with the arcade's pilot
 * (WMMT_PILOT=1) at 60 frames a second. Prints both cars as each machine sees them.
 * cc -O1 -DWMMT_EGL -DRC_FPT=double -Isrc -Isrc/phys test/vs_test.c src/car.c src/net.c
 * src/phys/rc_runtime.c src/phys/phys_rc.c -lm
 * Arguments: data dir, server, name, players, ramp, km, frames. Env DELAY: this machine starts
 * its race that many seconds late (the arcade's link waits for every machine before the count). */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <unistd.h>
#include "../src/car.h"
#include "../src/cardb.h"
#include "../src/net.h"

static double now(void) {
  struct timespec t;
  clock_gettime(CLOCK_MONOTONIC, &t);
  return (double)t.tv_sec + t.tv_nsec * 1e-9;
}

static void link_send(const unsigned char *p, int len, void *ctx) { (void)ctx; net_race_send(p, len); }
static void link_receive(void *ctx) { (void)ctx; net_race_receive(); }

int main(int argc, char **argv) {
  char err[256];
  if (argc < 8) { puts("vs_test data server name players ramp km frames"); return 1; }
  if (car_init(argv[1], err, sizeof err)) { puts(err); return 1; }
  int players = atoi(argv[4]), ramp = atoi(argv[5]), km = atoi(argv[6]), frames = atoi(argv[7]);
  srand((unsigned)time(NULL) ^ (unsigned)getpid());
  if (net_open(argv[2], NET_PORT, (uint32_t)rand())) { puts("net_open failed"); return 1; }
  /* the profile: the car (CARDB pack of the FD3S) */
  unsigned char profile[4] = { 0, 0, 0, 0 };
  net_go go;
  double t0 = now();
  for (;;) {
    net_poll(now(), 0, argv[3], profile, sizeof profile);
    const net_lobby *l = net_lobby_now();
    static int said;
    if (l->connected && l->me == l->host && l->n >= players && !said) {
      int all = 1;
      for (int i = 0; i < l->n; ++i) all &= l->player[i].status == 0;
      if (all) { printf("host: starting with %d\n", l->n); net_start(ramp, km); said = 1; }
    }
    if (net_take_go(&go)) break;
    if (now() - t0 > 30) { puts("no race"); return 1; }
    usleep(16000);
  }
  printf("GO race %u seed %u ramp %d km %d machines %d me pcb %d\n", go.race, go.seed, go.ramp, go.km, go.n, go.pcb);
  /* a slower machine: its race starts this much later (env DELAY, seconds) */
  for (double d0 = now(); getenv("DELAY") && now() - d0 < atof(getenv("DELAY"));) {
    net_poll(now(), 1, argv[3], profile, sizeof profile);
    usleep(16000);
  }
  car_link_car others[CAR_LINK_MACHINES - 1];
  int n = 0;
  for (int k = 0; k < go.n; ++k) {
    if (k == go.pcb) continue;
    car_link_car *o = &others[n++];
    memset(o, 0, sizeof *o);
    o->pcb = k;
    o->type = CAR_SPEC_FD3S.type;
    for (int i = 0; i < 6; ++i) o->tyres[i] = CAR_SPEC_FD3S.tyres[i];
    o->spokes = CAR_SPEC_FD3S.spokes;
    o->power = 10, o->handling = 10;
    printf("  other pcb %d: %s\n", k, go.player[k].name);
  }
  car_link_io io = { link_send, link_receive, NULL };
  car_set_versus(go.pcb, others, n, go.ramp, (float)go.km, go.seed, &io);
  car_state c;
  car_spec me = CAR_SPEC_FD3S;
  me.power = me.handling = 10;
  if (car_start(&c, 0, 0, &me)) { puts("start failed"); return 1; }
  car_input in = { 0 };
  double next = now();
  for (int i = 0; i < frames; i++) {
    net_poll(now(), 1, argv[3], profile, sizeof profile);
    in.throttle = 1.0f;
    car_update(&c, &in);
    if (i % (getenv("EVERY") ? atoi(getenv("EVERY")) : 60) == 0 || c.race.over) {
      printf("%5d place %d won %d st %d/%d over %d cd %.1f t %.1f left %.1f remain %.0f | me %.0f %.0f %.0f %3.0f km/h | r0 %d %.0f %.0f %.0f | r1 %d %.0f %.0f %.0f\n", i,
             c.race.vs_place, c.race.won, c.race.play_state, c.race.state, c.race.over, c.race.countdown, c.race.total, c.race.time_left, c.race.remain, c.pos[0], c.pos[1], c.pos[2], car_kmh(&c),
             c.rival_shown[0], c.rival_body[0][12], c.rival_body[0][13], c.rival_body[0][14],
             c.rival_shown[1], c.rival_body[1][12], c.rival_body[1][13], c.rival_body[1][14]);
      fflush(stdout);
      if (c.race.over && !getenv("ON")) break;
    }
    next += 1.0 / 60.0;
    double w = next - now();
    if (w > 0) usleep((useconds_t)(w * 1e6));
  }
  net_close();
  return 0;
}
