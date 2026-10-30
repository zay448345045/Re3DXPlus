#ifndef WMMT_TIMING60_H
#define WMMT_TIMING60_H
#include <stdint.h>
#include <math.h>
#define WMMT_PERIOD_NS 16666667LL
typedef struct { int64_t next; } timing60_pacer;
static inline void timing60_pacer_reset(timing60_pacer *p) { p->next = 0; }
static inline int64_t timing60_deadline(timing60_pacer *p, int64_t now) {
  if (!p->next) p->next = now;
  return p->next;
}
/* Preserve absolute phase after ordinary wakeup jitter. Skip deadlines too close
 * to this start; after a severe stall rebase rather than replay missed frames.
 * A half-period guard prevents rapid catch-up bursts, not all jitter. */
static inline void timing60_started(timing60_pacer *p, int64_t now) {
  if (now - p->next >= 4 * WMMT_PERIOD_NS) {
    p->next = now + WMMT_PERIOD_NS;
    return;
  }
  do { p->next += WMMT_PERIOD_NS; }
  while (p->next <= now + WMMT_PERIOD_NS / 2);
}
typedef struct { double fraction; } timing60_sim;
static inline void timing60_sim_reset(timing60_sim *s) { s->fraction = 0; }
static inline int timing60_sim_steps(timing60_sim *s, double dt) {
  if (!isfinite(dt) || dt < 0) dt = 0;
  if (dt > 0.1) dt = 0.1;
  s->fraction += dt * 60.0;
  int steps = (int)(s->fraction + 1e-7);
  s->fraction -= steps;
  if (s->fraction < 0) s->fraction = 0;
  return steps;
}
/* Discard timing around first draws and slow race/movie initialization. */
static inline int timing60_race_steps(timing60_sim *s, double dt, int paused, int first_frames) {
  if (paused || first_frames) {
    timing60_sim_reset(s);
    return 0;
  }
  return timing60_sim_steps(s, dt);
}
#endif
