#include "spark.h"
#include "lights.h"
#include "sparkdb.h"

#include <math.h>
#include <string.h>
#ifdef WMMT_EGL
#include <stdio.h>
#include <stdlib.h>
#endif

/* clCarSparkManager: 30 clCarSparkPrimitives a car (getMaxSparkPrimitive). A spark is a
 * ribbon of two quads through six points (A..F, relative to where it started from the car):
 * (A, C) the oldest cross-section, (B, D) the one after, (E, F) its head, F size above E.
 * Each frame (update 0x85f534c) the sections move back one (A, C <- B, D <- E, F), the head
 * goes on by the velocity, gravity takes 0.2 off its y (0x92f8258), and its life (13 at
 * birth) runs down; it is drawn while the life is 0 or more. */
#define SPARK_MAX 30
#define SPARK_LIFE 13
#define SPARK_GRAVITY 0.2f

typedef struct {
  float p[6][3]; /* A B C D E F */
  float v[3], rel[3];
  int life;      /* -1: free */
  int tex;       /* 0 car_spark03.tga (image 0x11a), 1 car_spark04.tga (0x11b) */
} spark;

static struct {
  spark s[SPARK_CARS][SPARK_MAX];
  float pos[SPARK_CARS][3]; /* the car's position (its matrix's translation) */
  int rand_at;              /* createSpark's running index into the tables (0x97fda24) */
  int ready;
  render_vertex v[2][4 * 2 * SPARK_CARS * SPARK_MAX];
} S;

void spark_reset(void) {
  S.ready = 1;
  for (int k = 0; k < SPARK_CARS; ++k)
    for (int i = 0; i < SPARK_MAX; ++i) S.s[k][i].life = -1;
}

/* clCarSparkManager::createSpark (0x85f4eb0), clCarEffectManager::update's (strength * 30 *
 * 0.5) of them: each flies off along the effect's direction (unit length, doubled) plus a
 * random vector (doubled again across, y not), from the contact point; the faster, the wider
 * (((int)|v| / 5 + 10) * 0.1) and that number's odd or even picks its picture. A spark is
 * only made when one of the 30 is free. */
static void create(int k, const car_effect *e) {
  int n = (int)(e->spark * (float)SPARK_MAX * 0.5f);
#ifdef WMMT_EGL
  if (getenv("WMMT_SPARK_LOG"))
    fprintf(stderr, "spark car %d: %.3f at %.1f %.1f %.1f dir %.2f %.2f %.2f (car %.1f %.1f %.1f) n %d\n", k, e->spark, e->at[0], e->at[1],
            e->at[2], e->dir[0], e->dir[1], e->dir[2], S.pos[k][0], S.pos[k][1], S.pos[k][2], n);
#endif
  float len = sqrtf(e->dir[0] * e->dir[0] + e->dir[1] * e->dir[1] + e->dir[2] * e->dir[2]);
  float dn[3] = { 0, 0, 0 };
  if (len > 0)
    for (int j = 0; j < 3; ++j) dn[j] = e->dir[j] / len;
  for (int i = 0; i < n; ++i) {
    const float *r = SPARK_RAND[i % 4][S.rand_at];
    S.rand_at = S.rand_at + 1 > 99 ? 0 : S.rand_at + 1;
    float v[3] = { 2.0f * (2.0f * r[0] + dn[0]), 2.0f * r[1] + dn[1], 2.0f * (2.0f * r[2] + dn[2]) };
    spark *s = NULL;
    for (int j = 0; j < SPARK_MAX && !s; ++j)
      if (S.s[k][j].life == -1) s = &S.s[k][j];
    if (!s) continue;
    int w = (int)sqrtf(v[0] * v[0] + v[1] * v[1] + v[2] * v[2]) / 5 + 10;
    s->tex = w & 1 ? 0 : 1;
    memset(s->p, 0, sizeof s->p);
    s->p[5][1] = (float)w * 0.1f;
    for (int j = 0; j < 3; ++j) {
      s->rel[j] = e->at[j] - S.pos[k][j];
      s->v[j] = v[j];
    }
    s->life = SPARK_LIFE;
  }
}

void spark_step(int k, const float *body, const car_effect *e) {
  if (k < 0 || k >= SPARK_CARS) return;
  if (!S.ready) spark_reset();
  if (!e) {
    for (int i = 0; i < SPARK_MAX; ++i) S.s[k][i].life = -1;
    return;
  }
  memcpy(S.pos[k], body + 12, sizeof S.pos[k]);
  if (e->spark != 0.0f) create(k, e);
  for (int i = 0; i < SPARK_MAX; ++i) {
    spark *s = &S.s[k][i];
    if (s->life == -1) continue;
    memcpy(s->p[0], s->p[1], sizeof s->p[0]);
    memcpy(s->p[2], s->p[3], sizeof s->p[0]);
    memcpy(s->p[1], s->p[4], sizeof s->p[0]);
    memcpy(s->p[3], s->p[5], sizeof s->p[0]);
    for (int j = 0; j < 3; ++j) {
      s->p[4][j] += s->v[j];
      s->p[5][j] += s->v[j];
    }
    s->v[1] -= SPARK_GRAVITY;
    if (--s->life < 0) s->life = -1;
  }
}

/* clCarSparkPrimitive::draw (0x8622d68): the triangles (A B C) (B C D) (B E D) (E D F), as
 * the quads B D C A and D B E F; u across (A B E 0, C D F 1), v along (A C 0, B D 0.5, E F
 * 1); all in clCarSparkPrimitive's colour (240, 212, 0). clCarSparkManager::draw: depth
 * tested, not written, glBlendFunc(GL_SRC_COLOR, GL_ONE). */
void spark_draw(const mat4 *proj, const mat4 *view, render_params *rp) {
  static const int QUAD[2][4] = { { 1, 3, 2, 0 }, { 3, 1, 4, 5 } };
  static const float U[6] = { 0, 0, 1, 1, 0, 1 }, V[6] = { 0, 0.5f, 0, 0.5f, 1, 1 };
  if (!S.ready) return;
  const float *m = view->m;
  int n[2] = { 0, 0 };
  for (int k = 0; k < SPARK_CARS; ++k)
    for (int i = 0; i < SPARK_MAX; ++i) {
      const spark *s = &S.s[k][i];
      if (s->life == -1) continue;
      float q[6][3];
      for (int c = 0; c < 6; ++c) {
        float p[3];
        for (int j = 0; j < 3; ++j) p[j] = S.pos[k][j] + s->rel[j] + s->p[c][j];
        for (int j = 0; j < 3; ++j) q[c][j] = m[j] * p[0] + m[4 + j] * p[1] + m[8 + j] * p[2] + m[12 + j];
      }
      for (int h = 0; h < 2; ++h) {
        render_vertex *v = S.v[s->tex] + 4 * n[s->tex]++;
        for (int c = 0; c < 4; ++c) {
          int at = QUAD[h][c];
          memcpy(v[c].pos, q[at], sizeof v[c].pos);
          v[c].uv[0] = U[at];
          v[c].uv[1] = V[at];
          v[c].rgba[0] = 240;
          v[c].rgba[1] = 212;
          v[c].rgba[2] = 0;
          v[c].rgba[3] = 255;
        }
      }
    }
  for (int t = 0; t < 2; ++t) {
    uint32_t tex = lights_spark_texture(t);
    if (n[t] && tex) render_sprites_by_colour(proj, S.v[t], n[t], tex, rp);
  }
}
