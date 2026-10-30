/* Desktop preview of the HUD: records hud.c's GL calls as triangles for
 * test/hudshot.py to rasterise over a screenshot.
 * cc -O2 -Isrc -Itest test/hudshot.c src/hud.c -lm && ./a.out data > hud.log */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "gl.h"
#include "hud.h"

float car_kmh(const car_state *c) { return c->speed * 3.6f; }

static const float *attr_ptr[2];
static int attr_stride[2], n_prog, n_tex, cur_tex;

GLuint gl_compile_program(const char *vs, const char *fs, const char **a, int n) { return (GLuint)++n_prog; }
void glUseProgram(GLuint p) { printf("P %u\n", p); }
void glUniform4f(GLint l, GLfloat r, GLfloat g, GLfloat b, GLfloat a) { printf("C %g %g %g %g\n", r, g, b, a); }
void glGenTextures(GLsizei n, GLuint *t) { for (int i = 0; i < n; ++i) t[i] = (GLuint)++n_tex; }
void glBindTexture(GLenum t, GLuint id) { cur_tex = (int)id; printf("T %u\n", id); }
void glTexImage2D(GLenum t, GLint l, GLint f, GLsizei w, GLsizei h, GLint b, GLenum fm, GLenum ty, const void *px) {
  char name[64];
  snprintf(name, sizeof name, "tex%d.rgba", cur_tex);
  FILE *o = fopen(name, "wb");
  fwrite(px, 4, (size_t)(w * h), o);
  fclose(o);
  printf("X %d %d %d %s\n", cur_tex, w, h, name);
}
void glVertexAttribPointer(GLuint i, GLint s, GLenum t, GLboolean n, GLsizei st, const void *p) {
  if (i < 2) { attr_ptr[i] = p; attr_stride[i] = st ? st / 4 : 2; }
}
void glDrawArrays(GLenum mode, GLint first, GLsizei count) {
  int idx[512], n = 0;
  for (int i = 2; i < count; ++i) {
    if (mode == GL_TRIANGLES) { if (i % 3 != 2) continue; idx[n++] = i - 2; idx[n++] = i - 1; idx[n++] = i; }
    else if (mode == GL_TRIANGLE_FAN) { idx[n++] = 0; idx[n++] = i - 1; idx[n++] = i; }
    else { idx[n++] = i - 2; idx[n++] = i - 1; idx[n++] = i; }
  }
  printf("D %d\n", n / 3);
  for (int k = 0; k < n; ++k) {
    const float *p = attr_ptr[0] + idx[k] * attr_stride[0];
    const float *u = attr_ptr[1] ? attr_ptr[1] + idx[k] * attr_stride[1] : NULL;
    printf("%g %g %g %g\n", p[0], p[1], u ? u[0] : 0, u ? u[1] : 0);
  }
}
void glEnableVertexAttribArray(GLuint i) {}
void glDisableVertexAttribArray(GLuint i) { if (i == 1) attr_ptr[1] = NULL; }
GLint glGetUniformLocation(GLuint p, const GLchar *n) { return 0; }
void glTexParameteri(GLenum a, GLenum b, GLint c) {}
void glUniform1i(GLint l, GLint v) {}
void glActiveTexture(GLenum t) {}
void glUniformMatrix4fv(GLint l, GLsizei c, GLboolean t, const GLfloat *m) {}
void glEnable(GLenum c) {}
void glDisable(GLenum c) {}
void glBlendFunc(GLenum a, GLenum b) {}
void glBindBuffer(GLenum a, GLuint b) {}

int main(int argc, char **argv) {
  hud_state h;
  hud_init(&h, 1024, 768);
  hud_gl_init();
  hud_load(argc > 1 ? argv[1] : "data");
  car_state c;
  memset(&c, 0, sizeof c);
  c.speed = 156 / 3.6f;
  c.rpm = 7900;
  c.gear = 4;
  c.manual = 1;
  c.steer = 0.4f;
  car_input in = { 0.4f, 1, 0, 0, 0 };
  h.throttle_touch = &h; /* show a held button */
  hud_draw(&h, &c, &in, 60);
  return 0;
}
