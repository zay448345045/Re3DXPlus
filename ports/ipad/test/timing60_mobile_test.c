/* cc -std=c99 -Wall -Wextra -Werror test/timing60_mobile_test.c -lm -o /tmp/timing60_mobile_test && /tmp/timing60_mobile_test */
#include "../src/timing60.h"
#include <assert.h>
#include <stdio.h>
typedef struct { timing60_sim sim; int up, down, delivered_up, delivered_down; } model;
static void reset(model *m) { timing60_sim_reset(&m->sim); }
static int frame(model *m, double dt, int paused, int first, int up, int down) {
  m->up += up; m->down += down;
  int in_up = m->up > 0, in_down = m->down > 0;
  m->up = m->down = 0; /* hud_input consumes edges */
  int steps = timing60_race_steps(&m->sim, dt, paused, first);
  if (!steps && !paused) { m->up += in_up; m->down += in_down; }
  if (steps) { m->delivered_up += in_up; m->delivered_down += in_down; }
  return steps;
}
static void frequency(int hz) {
  model m = {0}; int steps = 0;
  for (int i = 0; i < hz * 10; i++) steps += frame(&m, 1.0 / hz, 0, 0, 0, 0);
  assert(steps == 600);
}
int main(void) {
  frequency(60); frequency(90); frequency(120);
  model m = {0};
  assert(frame(&m, 1.0 / 120, 0, 0, 1, 0) == 0);
  assert(frame(&m, 1.0 / 120, 0, 0, 0, 1) == 1);
  assert(m.delivered_up == 1 && m.delivered_down == 1);
  assert(frame(&m, 0.05, 0, 0, 1, 0) == 3);
  assert(m.delivered_up == 2);
  assert(frame(&m, 1.0 / 120, 0, 0, 0, 0) == 0);
  assert(frame(&m, 10, 1, 0, 0, 0) == 0);
  assert(frame(&m, 1.0 / 120, 0, 0, 0, 0) == 0);
  reset(&m); /* resume resets fraction, iOS first callback dt discarded */
  assert(frame(&m, 0, 0, 0, 0, 0) == 0);
  assert(frame(&m, 1.0 / 60, 0, 0, 0, 0) == 1);
  assert(frame(&m, 0.1, 0, 1, 1, 0) == 0);
  assert(frame(&m, 0.1, 0, 1, 0, 0) == 0);
  assert(frame(&m, 1.0 / 60, 0, 0, 0, 0) == 1);
  assert(m.delivered_up == 3);
  reset(&m); assert(frame(&m, 1.0 / 120, 0, 0, 0, 0) == 0);
  assert(timing60_sim_steps(&m.sim, -1) == 0);
  assert(timing60_sim_steps(&m.sim, NAN) == 0);
  reset(&m); assert(timing60_sim_steps(&m.sim, 10) == 6);
  puts("timing60 mobile tests passed"); return 0;
}
