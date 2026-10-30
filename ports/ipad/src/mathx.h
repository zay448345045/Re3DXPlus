/* Small column-major 4x4 matrix helpers (OpenGL convention). */
#ifndef MATHX_H
#define MATHX_H

#include <math.h>
#include <string.h>

typedef struct { float m[16]; } mat4;

static inline mat4 mat4_identity(void) {
  mat4 r;
  memset(&r, 0, sizeof r);
  r.m[0] = r.m[5] = r.m[10] = r.m[15] = 1.0f;
  return r;
}

static inline mat4 mat4_mul(mat4 a, mat4 b) {
  mat4 r;
  for (int c = 0; c < 4; ++c)
    for (int row = 0; row < 4; ++row) {
      float s = 0;
      for (int k = 0; k < 4; ++k) s += a.m[k * 4 + row] * b.m[c * 4 + k];
      r.m[c * 4 + row] = s;
    }
  return r;
}

static inline mat4 mat4_perspective(float fovy, float aspect, float n, float f) {
  mat4 r;
  float t = 1.0f / tanf(fovy * 0.5f);
  memset(&r, 0, sizeof r);
  r.m[0] = t / aspect;
  r.m[5] = t;
  r.m[10] = (f + n) / (n - f);
  r.m[11] = -1.0f;
  r.m[14] = 2.0f * f * n / (n - f);
  return r;
}

static inline mat4 mat4_ortho(float l, float r_, float b, float t, float n, float f) {
  mat4 r = mat4_identity();
  r.m[0] = 2.0f / (r_ - l);
  r.m[5] = 2.0f / (t - b);
  r.m[10] = -2.0f / (f - n);
  r.m[12] = -(r_ + l) / (r_ - l);
  r.m[13] = -(t + b) / (t - b);
  r.m[14] = -(f + n) / (f - n);
  return r;
}

/* glFrustum's */
static inline mat4 mat4_frustum(float l, float r_, float b, float t, float n, float f) {
  mat4 m = { { 0 } };
  m.m[0] = 2.0f * n / (r_ - l);
  m.m[5] = 2.0f * n / (t - b);
  m.m[8] = (r_ + l) / (r_ - l);
  m.m[9] = (t + b) / (t - b);
  m.m[10] = -(f + n) / (f - n);
  m.m[11] = -1.0f;
  m.m[14] = -2.0f * f * n / (f - n);
  return m;
}

static inline void v3_sub(const float *a, const float *b, float *o) {
  o[0] = a[0] - b[0]; o[1] = a[1] - b[1]; o[2] = a[2] - b[2];
}
static inline float v3_dot(const float *a, const float *b) {
  return a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
}
static inline void v3_cross(const float *a, const float *b, float *o) {
  o[0] = a[1] * b[2] - a[2] * b[1];
  o[1] = a[2] * b[0] - a[0] * b[2];
  o[2] = a[0] * b[1] - a[1] * b[0];
}
static inline void v3_norm(float *a) {
  float l = sqrtf(v3_dot(a, a));
  if (l > 0) { a[0] /= l; a[1] /= l; a[2] /= l; }
}

static inline mat4 mat4_look_at(const float *eye, const float *at, const float *up) {
  float x[3], y[3], z[3];
  v3_sub(eye, at, z); v3_norm(z);
  v3_cross(up, z, x); v3_norm(x);
  v3_cross(z, x, y);
  mat4 r = mat4_identity();
  r.m[0] = x[0]; r.m[4] = x[1]; r.m[8] = x[2];
  r.m[1] = y[0]; r.m[5] = y[1]; r.m[9] = y[2];
  r.m[2] = z[0]; r.m[6] = z[1]; r.m[10] = z[2];
  r.m[12] = -v3_dot(x, eye);
  r.m[13] = -v3_dot(y, eye);
  r.m[14] = -v3_dot(z, eye);
  return r;
}

/* Model matrix for a body at pos with heading yaw (0 = +z), nose-up pitch and roll (radians).
 * Body axes: +x right, +y up, +z forward. */
static inline mat4 mat4_body(const float *pos, float yaw, float pitch, float roll) {
  float cy = cosf(yaw), sy = sinf(yaw), cp = cosf(pitch), sp = sinf(pitch);
  float fwd[3] = { sy * cp, sp, cy * cp };
  float right0[3] = { cy, 0, -sy };
  float up0[3], right[3], up[3];
  v3_cross(fwd, right0, up0);
  for (int i = 0; i < 3; ++i) right[i] = right0[i] * cosf(roll) + up0[i] * sinf(roll);
  v3_cross(fwd, right, up);
  mat4 r = mat4_identity();
  r.m[0] = right[0]; r.m[1] = right[1]; r.m[2] = right[2];
  r.m[4] = up[0];    r.m[5] = up[1];    r.m[6] = up[2];
  r.m[8] = fwd[0];   r.m[9] = fwd[1];   r.m[10] = fwd[2];
  r.m[12] = pos[0];  r.m[13] = pos[1];  r.m[14] = pos[2];
  return r;
}

#endif
