/* Desktop check of collision + car physics: drives the car from the C1 start
 * and prints its trajectory. cc -O2 -I../src sim.c ../src/car.c ../src/collide.c -lm */
#include <stdio.h>
#include <stdlib.h>

#include "car.h"

int main(int argc, char **argv) {
  col_world w;
  if (col_load(&w, argc > 1 ? argv[1] : "c1.wcl") != 0) {
    fprintf(stderr, "cannot load collision\n");
    return 1;
  }
  float steer = argc > 2 ? (float)atof(argv[2]) : 0.0f;
  car_state c;
  car_reset(&c, &w, 14065.481f, -14313.205f, 0.0f, 0.0f);
  printf("start y=%.1f\n", c.pos[1]);
  car_input in = { steer, 1.0f, 0.0f, 0, 0 };
  float dt = 1.0f / 60.0f;
  for (int i = 0; i <= 60 * 30; ++i) {
    car_update(&c, &in, &w, dt);
    if (i % 60 == 0)
      printf("t=%2ds pos=(%8.1f %6.1f %9.1f) yaw=%6.1f pitch=%5.2f %5.1f km/h gear %d rpm %4.0f %s%s\n",
             i / 60, c.pos[0], c.pos[1], c.pos[2], c.yaw * 57.3f, c.pitch * 57.3f, car_kmh(&c),
             c.gear, c.rpm, c.on_ground ? "" : "AIR ", c.wall_hit > 0 ? "WALL" : "");
  }
  col_free(&w);
  return 0;
}
