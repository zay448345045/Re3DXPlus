/* Track collision: ground height queries and wall push-out against a .wcl file. */
#ifndef COLLIDE_H
#define COLLIDE_H

#include <stdint.h>
#include <stddef.h>

typedef struct {
  float v[9];
  uint32_t kind; /* 0 ground, 1 wall */
} col_tri;

typedef struct {
  void *map;
  size_t map_size;
  float cell, x0, z0;
  int gw, gh;
  const uint32_t *cells; /* first, count pairs */
  const col_tri *tris;
  const uint32_t *list;
  uint32_t n_tri;
} col_world;

int col_load(col_world *w, const char *path);
void col_free(col_world *w);

/* Highest ground surface at (x, z) not above y_top. Returns 1 and fills *y
 * (and the surface normal if n != NULL) when found. */
int col_ground(const col_world *w, float x, float z, float y_top, float *y, float *n);

/* Push a vertical cylinder (centre x/z, radius r, spanning y0..y1) out of walls.
 * Returns 1 if it touched a wall; nx/nz get the summed push direction. */
int col_walls(const col_world *w, float *x, float *z, float y0, float y1, float r,
              float *nx, float *nz);

#endif
