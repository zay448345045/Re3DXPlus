/* Desktop check of a race against a CPU rival (car_set_rival): the arcade's pilot drives the
 * player's car (WMMT_PILOT), the rival its own CRivalAI. Prints the state, the gap and where
 * both are. cc -O1 -DWMMT_EGL -DRC_FPT=double -Isrc -Isrc/phys test/rival_test.c src/car.c
 * src/phys/rc_runtime.c src/phys/phys_rc.c -lm
 * Arguments: data dir, course, rival ECarType, its pack (CARDB_PACKS index), ECharacter, level, frames;
 * env SERIES: the story race (ESeries). */
#include <stdio.h>
#include <math.h>
#include <stdlib.h>
#include "../src/car.h"
#include "../src/cardb.h"
#include "phys/rc_runtime.h"

int main(int argc, char **argv) {
  char err[256];
  if (argc < 8) { puts("rival_test data course type pack char level frames"); return 1; }
  if (car_init(argv[1], err, sizeof err)) { puts(err); return 1; }
  int pack = atoi(argv[4]);
  car_rival r = { (unsigned)atoi(argv[3]), { 0 }, (int)CARDB_TYRES[pack][6], atoi(argv[5]), atoi(argv[6]),
                 getenv("SERIES") ? atoi(getenv("SERIES")) : 0 };
  for (int i = 0; i < 6; ++i) r.tyres[i] = CARDB_TYRES[pack][i];
  car_spec me = CAR_SPEC_FD3S;
  if (getenv("SAME")) { /* the tyres tools/recomp/seq.py gives both cars, to compare with it */
    const float t[6] = { 690.0f, 320.0f, 1285.0f, 684.9f, 320.0f, -1065.2f };
    for (int i = 0; i < 6; ++i) me.tyres[i] = r.tyres[i] = t[i];
    me.spokes = r.spokes = 5;
  }
  car_rival rs[2] = { r, r };
  int t2, p2, c2; /* env RIVAL2=type,pack,char: a second rival in the race */
  if (getenv("RIVAL2") && sscanf(getenv("RIVAL2"), "%d,%d,%d", &t2, &p2, &c2) == 3) {
    rs[1].type = (unsigned)t2;
    rs[1].character = c2;
    rs[1].spokes = (int)CARDB_TYRES[p2][6];
    for (int i = 0; i < 6; ++i) rs[1].tyres[i] = CARDB_TYRES[p2][i];
    car_set_rivals(rs, 2);
  } else {
    car_set_rival(r.type ? &r : NULL);
  }
  car_state c;
  if (car_start(&c, atoi(argv[2]), 0, &me)) { puts("start failed"); return 1; }
  car_input in = { 0 };
  int frames = atoi(argv[7]);
  for (int i = 0; i < frames; i++) {
    in.throttle = 1.0f;
    car_update(&c, &in);
    if (i % (getenv("EVERY") ? atoi(getenv("EVERY")) : 120) == 0 || c.race.over) {
      printf("%5d state %d over %d cd %.1f time %.1f left %.1f remain %.0f gap %.1f won %d mt %d a %d | me %.0f %.0f %.0f %3.0f km/h rpm %.0f g %d | rival %d %.0f %.0f %.0f\n", i,
             c.race.state, c.race.over, c.race.countdown, c.race.total, c.race.time_left, c.race.remain, c.race.gap, c.race.won, c.race.map_text, c.race.area,
             c.pos[0], c.pos[1], c.pos[2], car_kmh(&c), c.rpm, c.gear, c.rival_shown[0], c.rival_body[0][12], c.rival_body[0][13], c.rival_body[0][14]);
      if (getenv("RIVAL2"))
        printf("      rival2 %d %.0f %.0f %.0f rot %.2f\n", c.rival_shown[1], c.rival_body[1][12], c.rival_body[1][13], c.rival_body[1][14], c.rival_tyre_rot[1][0]);
      if (getenv("DUMP")) {
        uint32_t t = M32(0x98028e4u) + 0x2c4u;
        printf("      trans at %u flag34 %u gear %u prev %u up", M32(t + 0x38), M32(t + 0x34), M32(t + 0x3c), M32(t + 0x40));
        for (int k = 0; k < 6; ++k) printf(" %.0f", MF(t + 0x44 + 4 * k));
        printf(" dn");
        for (int k = 0; k < 6; ++k) printf(" %.0f", MF(t + 0x5c + 4 * k));
        printf(" b74 %u", M8(t + 0x74));
        float best = 1e9f;
        for (int k = 0; k < c.n_traffic; ++k) {
          float dx = c.traffic[k].body[12] - c.pos[0], dz = c.traffic[k].body[14] - c.pos[2], d = dx * dx + dz * dz;
          if (d < best) best = d;
        }
        printf(" nearest traffic %.1f m\n", sqrtf(best) * 0.1f);
      }
      if (c.race.over) break;
    }
  }
  return 0;
}
