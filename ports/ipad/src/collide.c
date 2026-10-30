#include "collide.h"

#include <fcntl.h>
#include <math.h>
#include <string.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <unistd.h>

typedef struct {
  char magic[4];
  uint32_t n_tri;
  float cell, x0, z0;
  uint32_t gw, gh, cell_off, tri_off, list_off;
} wcl_header;

int col_load(col_world *w, const char *path) {
  memset(w, 0, sizeof *w);
  int fd = open(path, O_RDONLY);
  if (fd < 0) return -1;
  struct stat st;
  fstat(fd, &st);
  void *p = mmap(NULL, (size_t)st.st_size, PROT_READ, MAP_PRIVATE, fd, 0);
  close(fd);
  if (p == MAP_FAILED) return -1;
  const wcl_header *h = p;
  if (memcmp(h->magic, "WCL1", 4) != 0) {
    munmap(p, (size_t)st.st_size);
    return -1;
  }
  w->map = p;
  w->map_size = (size_t)st.st_size;
  w->cell = h->cell;
  w->x0 = h->x0;
  w->z0 = h->z0;
  w->gw = (int)h->gw;
  w->gh = (int)h->gh;
  w->n_tri = h->n_tri;
  w->cells = (const uint32_t *)((const char *)p + h->cell_off);
  w->tris = (const col_tri *)((const char *)p + h->tri_off);
  w->list = (const uint32_t *)((const char *)p + h->list_off);
  return 0;
}

void col_free(col_world *w) {
  if (w->map) munmap(w->map, w->map_size);
  memset(w, 0, sizeof *w);
}

static int cell_of(const col_world *w, float x, float z, const uint32_t **ids, uint32_t *n) {
  int cx = (int)floorf((x - w->x0) / w->cell);
  int cz = (int)floorf((z - w->z0) / w->cell);
  if (cx < 0 || cz < 0 || cx >= w->gw || cz >= w->gh) return 0;
  const uint32_t *c = w->cells + 2 * (cz * w->gw + cx);
  *ids = w->list + c[0];
  *n = c[1];
  return 1;
}

int col_ground(const col_world *w, float x, float z, float y_top, float *y, float *n) {
  const uint32_t *ids;
  uint32_t cnt;
  if (!cell_of(w, x, z, &ids, &cnt)) return 0;
  int found = 0;
  float best = -1e30f;
  for (uint32_t i = 0; i < cnt; ++i) {
    const col_tri *t = &w->tris[ids[i]];
    if (t->kind != 0) continue;
    const float *a = t->v, *b = t->v + 3, *c = t->v + 6;
    /* barycentric test in XZ */
    float d = (b[2] - c[2]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[2] - c[2]);
    if (fabsf(d) < 1e-6f) continue;
    float l1 = ((b[2] - c[2]) * (x - c[0]) + (c[0] - b[0]) * (z - c[2])) / d;
    float l2 = ((c[2] - a[2]) * (x - c[0]) + (a[0] - c[0]) * (z - c[2])) / d;
    float l3 = 1.0f - l1 - l2;
    if (l1 < -1e-4f || l2 < -1e-4f || l3 < -1e-4f) continue;
    float h = l1 * a[1] + l2 * b[1] + l3 * c[1];
    if (h > y_top || h < best) continue;
    best = h;
    found = 1;
    if (n) {
      float e1[3] = { b[0] - a[0], b[1] - a[1], b[2] - a[2] };
      float e2[3] = { c[0] - a[0], c[1] - a[1], c[2] - a[2] };
      n[0] = e1[1] * e2[2] - e1[2] * e2[1];
      n[1] = e1[2] * e2[0] - e1[0] * e2[2];
      n[2] = e1[0] * e2[1] - e1[1] * e2[0];
      float l = sqrtf(n[0] * n[0] + n[1] * n[1] + n[2] * n[2]);
      if (n[1] < 0) l = -l;
      n[0] /= l; n[1] /= l; n[2] /= l;
    }
  }
  if (found) *y = best;
  return found;
}

/* Closest point on segment p-q (XZ) to point x/z. */
static void closest_on_seg(float px, float pz, float qx, float qz, float x, float z,
                           float *ox, float *oz) {
  float dx = qx - px, dz = qz - pz;
  float l2 = dx * dx + dz * dz;
  float t = l2 > 0 ? ((x - px) * dx + (z - pz) * dz) / l2 : 0;
  if (t < 0) t = 0;
  if (t > 1) t = 1;
  *ox = px + t * dx;
  *oz = pz + t * dz;
}

int col_walls(const col_world *w, float *x, float *z, float y0, float y1, float r,
              float *nx, float *nz) {
  const uint32_t *ids;
  uint32_t cnt;
  *nx = *nz = 0;
  if (!cell_of(w, *x, *z, &ids, &cnt)) return 0;
  int hit = 0;
  for (uint32_t i = 0; i < cnt; ++i) {
    const col_tri *t = &w->tris[ids[i]];
    if (t->kind != 1) continue;
    const float *v = t->v;
    float ymin = fminf(v[1], fminf(v[4], v[7])), ymax = fmaxf(v[1], fmaxf(v[4], v[7]));
    if (ymax < y0 || ymin > y1) continue;
    /* a near-vertical triangle projects to (almost) a segment: test all three edges */
    float best = r, bx = 0, bz = 0;
    for (int e = 0; e < 3; ++e) {
      const float *p = v + 3 * e, *q = v + 3 * ((e + 1) % 3);
      float cx, cz;
      closest_on_seg(p[0], p[2], q[0], q[2], *x, *z, &cx, &cz);
      float dx = *x - cx, dz = *z - cz;
      float d = sqrtf(dx * dx + dz * dz);
      if (d < best && d > 1e-4f) {
        best = d;
        bx = dx / d;
        bz = dz / d;
      }
    }
    if (best < r) {
      *x += bx * (r - best);
      *z += bz * (r - best);
      *nx += bx;
      *nz += bz;
      hit = 1;
    }
  }
  return hit;
}
