/* Desktop screenshots of the game (menus and race) on Mesa's GLES2, for checking
 * screens without the iPad. Runs a script of frames, taps and shots:
 *   f N        run N frames at 60 Hz
 *   t X Y      tap at (X, Y) on the 1024x768 screen
 *   d X Y      touch down at (X, Y) and hold; u X Y lets go
 *   start      the start button
 *   movie      the attract movie ended
 *   mem        iOS warns of low memory
 *   z MS       sleep MS milliseconds (the loading thread's time to work)
 *   s NAME     save the frame as NAME (binary PPM)
 * With WMMT_THREAD set the loading runs on a thread of its own, as on the iPad (app_loader).
 * build: cc -O1 -DWMMT_EGL -DRC_FPT=double -Isrc -Isrc/phys test/menushot.c src/app.c src/anm.c
 *        src/car.c src/collide.c src/hud.c src/menu.c src/render.c src/sound.c
 *        src/phys/rc_runtime.c src/phys/phys_rc.c -lEGL -lGLESv2 -lm -lpthread
 * run:   EGL_PLATFORM=surfaceless ./a.out <data dir> <script> */
#include <EGL/egl.h>
#include <EGL/eglext.h>
#include <pthread.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

#include "app.h"
#include "gl.h"
#include "hud.h"

#define W 1024
#define H 768

static void shot(const char *name) {
  static unsigned char px[W * H * 4];
  glReadPixels(0, 0, W, H, GL_RGBA, GL_UNSIGNED_BYTE, px);
  FILE *f = fopen(name, "wb");
  if (!f) return;
  fprintf(f, "P6\n%d %d\n255\n", W, H);
  for (int y = H - 1; y >= 0; --y)
    for (int x = 0; x < W; ++x) fwrite(px + 4 * (y * W + x), 1, 3, f);
  fclose(f);
}

static EGLDisplay load_dpy;
static EGLContext load_ctx;

static void *loader(void *arg) {
  (void)arg;
  if (!eglMakeCurrent(load_dpy, EGL_NO_SURFACE, EGL_NO_SURFACE, load_ctx)) {
    fprintf(stderr, "loading thread: no context\n");
    return NULL;
  }
  app_loader();
  return NULL;
}

/* a frame, then what main.m does after its presentRenderbuffer; the BGM as main.m would
 * change it (app_bgm's names are constants) */
static void step_frame(void) {
  static const char *bgm;
  static long frames;
  app_frame(1.0f / 60.0f);
  app_frame_done(0);
  const char *track = app_bgm();
  if (track != bgm) printf("bgm %s at frame %ld\n", track ? track : "(none)", frames);
  bgm = track;
  frames++;
}

int main(int argc, char **argv) {
  if (argc < 3) return 1;
  EGLDisplay d = eglGetDisplay(EGL_DEFAULT_DISPLAY);
  if (!eglInitialize(d, NULL, NULL)) { fprintf(stderr, "no EGL\n"); return 1; }
  const EGLint cfg_attr[] = { EGL_SURFACE_TYPE, EGL_PBUFFER_BIT, EGL_RENDERABLE_TYPE, EGL_OPENGL_ES2_BIT,
                              EGL_RED_SIZE, 8, EGL_GREEN_SIZE, 8, EGL_BLUE_SIZE, 8, EGL_DEPTH_SIZE, 24, EGL_STENCIL_SIZE, 8, EGL_NONE };
  EGLConfig cfg;
  EGLint n = 0;
  eglChooseConfig(d, cfg_attr, &cfg, 1, &n);
  eglBindAPI(EGL_OPENGL_ES_API);
  const EGLint ctx_attr[] = { EGL_CONTEXT_CLIENT_VERSION, 2, EGL_NONE };
  EGLContext ctx = eglCreateContext(d, n ? cfg : EGL_NO_CONFIG_KHR, EGL_NO_CONTEXT, ctx_attr);
  EGLSurface surf = EGL_NO_SURFACE;
  if (n) {
    const EGLint pb[] = { EGL_WIDTH, W, EGL_HEIGHT, H, EGL_NONE };
    surf = eglCreatePbufferSurface(d, cfg, pb);
  }
  if (!eglMakeCurrent(d, surf, surf, ctx)) { fprintf(stderr, "no context\n"); return 1; }
  GLuint fbo = 0, rb[2];
  if (surf == EGL_NO_SURFACE) { /* surfaceless: draw into a framebuffer of our own */
    glGenFramebuffers(1, &fbo);
    glBindFramebuffer(GL_FRAMEBUFFER, fbo);
    glGenRenderbuffers(2, rb);
    glBindRenderbuffer(GL_RENDERBUFFER, rb[0]);
    glRenderbufferStorage(GL_RENDERBUFFER, GL_RGB565, W, H);
    glFramebufferRenderbuffer(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, GL_RENDERBUFFER, rb[0]);
    glBindRenderbuffer(GL_RENDERBUFFER, rb[1]);
    glRenderbufferStorage(GL_RENDERBUFFER, GL_DEPTH24_STENCIL8_OES, W, H);
    glFramebufferRenderbuffer(GL_FRAMEBUFFER, GL_DEPTH_ATTACHMENT, GL_RENDERBUFFER, rb[1]);
    glFramebufferRenderbuffer(GL_FRAMEBUFFER, GL_STENCIL_ATTACHMENT, GL_RENDERBUFFER, rb[1]);
  }
  GLint depth_bits = 0;
  glGetIntegerv(GL_DEPTH_BITS, &depth_bits);
  fprintf(stderr, "EGL configs %d, depth bits %d\n", n, depth_bits);
  if (app_init(argv[1], W, H, W, H) != 0) { fprintf(stderr, "init: %s\n", app_error()); return 1; }
  if (getenv("WMMT_THREAD")) {
    load_dpy = d;
    load_ctx = eglCreateContext(d, n ? cfg : EGL_NO_CONFIG_KHR, ctx, ctx_attr);
    pthread_t t;
    if (load_ctx != EGL_NO_CONTEXT && pthread_create(&t, NULL, loader, NULL) == 0) fprintf(stderr, "loading thread up\n");
  }
  FILE *s = fopen(argv[2], "r");
  char line[256];
  while (s && fgets(line, sizeof line, s)) {
    char cmd[32], arg[200];
    float x, y;
    int k;
    if (sscanf(line, "%31s", cmd) != 1 || cmd[0] == '#') continue;
    if (!strcmp(cmd, "f") && sscanf(line, "f %d", &k) == 1) {
      for (int i = 0; i < k; ++i) step_frame();
    } else if (!strcmp(cmd, "t") && sscanf(line, "t %f %f", &x, &y) == 2) {
      app_touch((void *)1, TOUCH_BEGAN, x, y);
      step_frame();
      app_touch((void *)1, TOUCH_ENDED, x, y);
    } else if (!strcmp(cmd, "d") && sscanf(line, "d %f %f", &x, &y) == 2) {
      app_touch((void *)2, TOUCH_BEGAN, x, y);
    } else if (!strcmp(cmd, "u") && sscanf(line, "u %f %f", &x, &y) == 2) {
      app_touch((void *)2, TOUCH_ENDED, x, y);
    } else if (!strcmp(cmd, "start")) {
      app_press_start();
    } else if (!strcmp(cmd, "z") && sscanf(line, "z %d", &k) == 1) {
      usleep((useconds_t)k * 1000);
    } else if (!strcmp(cmd, "mem")) {
      app_memory_warning();
    } else if (!strcmp(cmd, "movie")) {
      app_movie_done();
    } else if (!strcmp(cmd, "s") && sscanf(line, "s %199s", arg) == 1) {
      shot(arg);
      fprintf(stderr, "shot %s\n", arg);
    }
  }
  return 0;
}
