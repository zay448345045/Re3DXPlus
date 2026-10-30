/* Desktop check of src/car.c: start every course with AT and MT, drive it and print
 * what the app sees. cc -O1 -ffp-contract=off -DRC_FPT=double -Isrc -Isrc/phys
 * test/car_test.c src/car.c src/phys/rc_runtime.c src/phys/phys_rc.c -lm */
#include <stdio.h>
#include <stdlib.h>
#include <time.h>
#include "../src/car.h"

int main(int argc, char **argv) {
  char err[256];
  if (car_init(argc > 1 ? argv[1] : ".", err, sizeof err)) { puts(err); return 1; }
  car_state c;
  for (int manual = 0; manual < 2; manual++)
    for (int course = 0; course < CAR_COURSES; course++) {
      if (car_start(&c, course, manual, NULL)) { printf("course %d failed\n", course); return 1; }
      printf("%s course %d start pos %.1f %.1f %.1f yaw %.1f\n", manual ? "MT" : "AT", course, c.pos[0], c.pos[1],
             c.pos[2], c.yaw * 57.3f);
      car_input in = {0};
      clock_t t0 = clock();
      for (int i = 0; i < 600; i++) {
        in.throttle = 1.0f;
        /* manual: shift up near the limiter */
        in.shift_up = manual && c.rpm > 8500.0f;
        car_update(&c, &in);
        if (i % 120 == 119)
          printf("  %4d %5.1f km/h rpm %5.0f gear %d yaw %6.1f pos %.0f %.0f %.0f imp %.1f\n", i, car_kmh(&c), c.rpm,
                 c.gear, c.yaw * 57.3f, c.pos[0], c.pos[1], c.pos[2], c.impact);
        c.impact = 0;
      }
      printf("  %.1f us/frame\n", (double)(clock() - t0) / CLOCKS_PER_SEC * 1e6 / 600);
    }
  return 0;
}
