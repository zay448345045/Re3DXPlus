/* Compile twice with CAR_SOURCE naming either port's production car.c. */
#include <assert.h>
#include <float.h>
#include <stdlib.h>
#include CAR_SOURCE
uint8_t *rc_mem;
uint8_t *rc_va_slow(uint32_t a) { (void)a; abort(); }
static void sample(car_effect *e, unsigned pulse, float x, float y, float z) {
  memset(VA(P.eff), 0, 0x100);
  W8(P.eff + 0x84, pulse);
  WF(P.eff + 0x30, x); WF(P.eff + 0x34, y); WF(P.eff + 0x38, z);
  WF(P.eff + 0x68, 3.5f); WF(P.eff + 0x6c, 7.0f); WF(P.eff + 0x78, 9.0f);
  read_effect(e);
}
int main(void) {
  assert(!race_remain_valid(NAN) && !race_remain_valid(INFINITY));
  assert(!race_remain_valid(-1000.0f) && !race_remain_valid(FLT_MAX));
  assert(race_remain_valid(0.0f) && race_remain_valid(1.0f));
  assert(race_remain_valid(600000.0f) && race_remain_valid(700000.0f));
  rc_mem = calloc(1, 0x1000); assert(rc_mem); P.eff = RC_MEM_BASE;
  car_effect a = {0}, b = {0};
  sample(&a, 9, 3, 4, 0); assert(a.backfire_pulse == 9 && a.backfire_type == 1);
  assert(a.spark == 3.5f && a.at[0] == 7 && a.dir[0] == 9);
  sample(&b, 1, 0, 0, 2.9f); assert(b.backfire_type == 0 && a.backfire_pulse == 9);
  sample(&b, 0, 0, 0, 0); assert(!b.backfire_pulse && b.backfire_type == 0 && a.backfire_type == 1);
  sample(&b, 1, NAN, 0, 0); assert(b.backfire_type == -1);
  sample(&b, 1, INFINITY, 0, 0); assert(b.backfire_type == -1);
  sample(&b, 1, FLT_MAX, FLT_MAX, FLT_MAX); assert(b.backfire_type == -1);
  sample(&b, 1, 2147483648.0f, 0, 0); assert(b.backfire_type == -1);
  free(rc_mem); return 0;
}
