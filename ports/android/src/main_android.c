/* The Android side of the port (main.m's, for a phone like the Xiaomi Mi 6): MainActivity.java
 * hands over the SurfaceView's surface, touches, the gravity and the lifecycle; the game runs
 * on a thread of its own here with an OpenGL ES 3 context (4x MSAA) on that surface, the
 * loading thread with a context sharing it, and the sound through AAudio. Built with -DWMMT_VK
 * the game's GL goes through vkgl (Vulkan) instead: a swapchain on the surface, the loading
 * thread vkgl's second. */
#ifdef WMMT_VK
#define VK_USE_PLATFORM_ANDROID_KHR
#endif
#include <EGL/egl.h>
#include <EGL/eglext.h>
#include <aaudio/AAudio.h>
#include <android/log.h>
#include <android/native_window_jni.h>
#include <jni.h>
#include <math.h>
#include <pthread.h>
#include <stdint.h>
#include <stdatomic.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <errno.h>
#include "timing60.h"
#include <unistd.h>

#include "app.h"
#include "gl.h"
#include "sound.h"
#include "hud.h"

/* the attract movies (prepare_movie.sh), indexed as app_movie() returns them */
static const char *const MOVIES[3] = { "intro.mp4", "playdemo.mp4", "tutorial.mp4" };

#define TOUCH_MAX 256
typedef struct { int id, phase; float x, y; } touch_ev;

static struct {
  JavaVM *vm;
  jobject activity;
  jmethodID show_movie, play_bgm, set_bgm_volume, fail;
  _Atomic unsigned activity_generation;
  unsigned synced_generation;
  int bgm_level;
  char data_dir[512], save_dir[512], sidecar_dir[512];
  pthread_mutex_t mx;
  pthread_cond_t cv;
  ANativeWindow *window; /* the surface to draw on (NULL while there is none) */
  int window_changed, paused, started;
  touch_ev touches[TOUCH_MAX];
  int n_touch, touch_desync;
  int press_start, movie_done_ev, memory_warning;
  float tilt;
  int tilt_new, wants_tilt;
  /* the game thread's own */
#ifdef WMMT_VK
  int vk_up, have_surface;
  VkSurfaceKHR vk_surface;
#endif
  EGLDisplay dpy;
  EGLConfig config;
  EGLContext ctx, load_ctx;
  EGLSurface surface;
  int fb_w, fb_h;
  float touch_k, touch_edge;
  int movie; /* shown, -1 none */
  const char *bgm;
  AAudioStream *audio;
} A = { .movie = -1, .bgm_level = -1, .mx = PTHREAD_MUTEX_INITIALIZER, .cv = PTHREAD_COND_INITIALIZER };

/* TOUCH_FAILSAFE_BEGIN: queue mutation requires A.mx; active IDs belong solely to
 * the game thread. A poisoned queue rejects every event until its poison is taken.
 * Thereafter unknown IDs are suppressed permanently: a new explicit DOWN alone
 * can enroll an ID, so old fingers cannot reactivate after cancellation. */
static void touch_enqueue(touch_ev ev) {
  if (A.touch_desync) return;
  if (A.n_touch == TOUCH_MAX) {
    A.n_touch = 0;
    A.touch_desync = 1;
    return;
  }
  A.touches[A.n_touch++] = ev;
}

/* Called under A.mx. The returned snapshot predates any later producer overflow. */
static int touch_take(touch_ev *out, int *desync) {
  int n = A.n_touch;
  memcpy(out, A.touches, (size_t)n * sizeof *out);
  *desync = A.touch_desync;
  A.n_touch = A.touch_desync = 0;
  return n;
}

typedef struct touch_active {
  int id;
  float x, y;
  struct touch_active *next;
} touch_active;
static touch_active *touch_active_head;
static int touch_strict;

static void touch_cancel_all(void) {
  while (touch_active_head) {
    touch_active *p = touch_active_head;
    touch_active_head = p->next;
    app_touch((void *)((intptr_t)p->id + 1), 3, p->x * A.touch_k - A.touch_edge, p->y * A.touch_k);
    free(p);
  }
  touch_strict = 1;
}

/* A newer overflow or lifecycle poison invalidates the remaining snapshot.
 * This check is deliberately short; input can arrive again after it returns. */
static void touch_reconcile_snapshot(int *n, int *desync) {
  pthread_mutex_lock(&A.mx);
  if (A.touch_desync) {
    A.n_touch = 0;
    A.touch_desync = 0;
    *n = 0;
    *desync = 1;
  }
  pthread_mutex_unlock(&A.mx);
}

static void touch_deliver(touch_ev *events, int n, int desync) {
  if (desync) touch_cancel_all();
  for (int i = 0; i < n; ++i) {
    int remaining = n - i, poisoned = 0;
    touch_reconcile_snapshot(&remaining, &poisoned);
    if (poisoned) { touch_cancel_all(); return; }
    touch_ev e = events[i];
    touch_active **link = &touch_active_head;
    while (*link && (*link)->id != e.id) link = &(*link)->next;
    touch_active *p = *link;
    if (e.phase == 0 && !p) {
      p = malloc(sizeof *p);
      if (!p) {
        /* Discard both the unprocessed snapshot and anything concurrently queued.
         * The poison prevents new events until the game thread takes it. */
        pthread_mutex_lock(&A.mx);
        A.n_touch = 0;
        A.touch_desync = 1;
        pthread_mutex_unlock(&A.mx);
        touch_cancel_all();
        return;
      }
      *p = (touch_active){ e.id, e.x, e.y, NULL };
      *link = p;
    } else if (touch_strict && !p) {
      continue;
    }
    if (p) { p->x = e.x; p->y = e.y; }
    app_touch((void *)((intptr_t)e.id + 1), e.phase, e.x * A.touch_k - A.touch_edge, e.y * A.touch_k);
    if (p && (e.phase == 2 || e.phase == 3)) {
      *link = p->next;
      free(p);
    }
  }
}
/* TOUCH_FAILSAFE_END */

/* Set only after the immutable sidecar passed CardResources.prepare. Failure events
 * disable a group for this session, without touching its persisted preference. */
static _Atomic unsigned bgm_extra_mask;
int android_bgm_group_available(int group) {
  return group >= 1 && group <= 2 && (atomic_load(&bgm_extra_mask) & (1u << group)) != 0;
}

/* HUD may declare this function locally. Copies a stable snapshot under the activity lock;
 * returns 1 when available, 0 when absent or the caller's buffer is too small. */
int android_card_resources_dir(char *out, size_t capacity) {
  int ok = 0;
  if (!out || capacity == 0) return 0;
  pthread_mutex_lock(&A.mx);
  size_t n = strlen(A.sidecar_dir);
  if (n && n < capacity) { memcpy(out, A.sidecar_dir, n + 1); ok = 1; }
  else out[0] = '\0';
  pthread_mutex_unlock(&A.mx);
  return ok;
}

static double now_s(void) {
  struct timespec t;
  clock_gettime(CLOCK_MONOTONIC, &t);
  return (double)t.tv_sec + t.tv_nsec * 1e-9;
}

/* ---- sound: sound.c's mix, 44.1 kHz stereo int16, low latency ---- */

_Static_assert(ATOMIC_INT_LOCK_FREE == 2, "audio error flag must be lock-free");
static _Atomic unsigned audio_disconnect_generation;
static _Atomic int audio_other_error;
static unsigned audio_generation, audio_handled_generation;
static snd_retry audio_retry;

static aaudio_data_callback_result_t audio_cb(AAudioStream *s, void *user, void *data, int32_t frames) {
  snd_mix((short *)data, frames);
  snd_diag_callback((const short *)data, frames);
  return AAUDIO_CALLBACK_RESULT_CONTINUE;
}

/* The callback only publishes an error. The game thread owns stream lifetime. */
static void audio_error(AAudioStream *s, void *user, aaudio_result_t err) {
  unsigned generation = (unsigned)(uintptr_t)user;
  if (err == AAUDIO_ERROR_DISCONNECTED) {
    snd_diag_disconnect(&audio_disconnect_generation, generation);
  } else atomic_store_explicit(&audio_other_error, err, memory_order_relaxed);
}

static void audio_close(void) {
  if (A.audio) { AAudioStream_close(A.audio); A.audio = NULL; }
}
static int audio_start(void) {
  aaudio_result_t r = AAudioStream_requestStart(A.audio);
  fprintf(stderr, "audio_diag start=%d state=%d\n", r, AAudioStream_getState(A.audio));
  return r == AAUDIO_OK;
}
static int audio_open(void) {
  AAudioStreamBuilder *b = NULL;
  if (audio_generation == UINT32_MAX) { fprintf(stderr, "audio_diag generation exhausted\n"); return 0; }
  ++audio_generation;
  aaudio_result_t r = AAudio_createStreamBuilder(&b);
  if (r != AAUDIO_OK) { fprintf(stderr, "audio_diag create=%d\n", r); return 0; }
  AAudioStreamBuilder_setFormat(b, AAUDIO_FORMAT_PCM_I16);
  AAudioStreamBuilder_setChannelCount(b, 2);
  AAudioStreamBuilder_setSampleRate(b, SND_RATE);
  AAudioStreamBuilder_setPerformanceMode(b, AAUDIO_PERFORMANCE_MODE_LOW_LATENCY);
  AAudioStreamBuilder_setUsage(b, AAUDIO_USAGE_GAME);
  AAudioStreamBuilder_setDataCallback(b, audio_cb, NULL);
  /* Integer token is never dereferenced; late callbacks cannot target a newer generation. */
  AAudioStreamBuilder_setErrorCallback(b, audio_error, (void *)(uintptr_t)audio_generation);
  r = AAudioStreamBuilder_openStream(b, &A.audio);
  AAudioStreamBuilder_delete(b);
  if (r != AAUDIO_OK) { A.audio = NULL; fprintf(stderr, "audio_diag open=%d\n", r); return 0; }
  int format = AAudioStream_getFormat(A.audio), channels = AAudioStream_getChannelCount(A.audio);
  int rate = AAudioStream_getSampleRate(A.audio);
  fprintf(stderr, "audio_diag open=%d format=%d rate=%d channels=%d state=%d\n", r, format, rate, channels, AAudioStream_getState(A.audio));
  /* snd_mix writes stereo int16 and assumes SND_RATE; never start an incompatible stream. */
  if (format != AAUDIO_FORMAT_PCM_I16 || channels != 2 || rate != SND_RATE) {
    fprintf(stderr, "audio_diag incompatible stream; not started\n");
    audio_close(); return 0;
  }
  if (!audio_start()) { audio_close(); return 0; }
  return 1;
}

/* Called only when the game is active. A generation is never reused; old
 * callback notifications therefore cannot clear or supersede newer ones. */
static void audio_service(int resume, double now) {
  int err = atomic_exchange_explicit(&audio_other_error, 0, memory_order_relaxed);
  if (err) fprintf(stderr, "audio_diag callback_error=%d\n", err);
  int interrupted = 0;
  unsigned disconnected = atomic_load_explicit(&audio_disconnect_generation, memory_order_relaxed);
  if (A.audio && disconnected == audio_generation && disconnected != audio_handled_generation) {
    audio_handled_generation = disconnected;
    fprintf(stderr, "audio_diag disconnected generation=%u\n", disconnected);
    audio_close();
    now = now_s(); interrupted = 1;
    snd_retry_interrupt(&audio_retry, now);
    if (!audio_retry.pending) fprintf(stderr, "audio_diag retry_exhausted attempts=3\n");
  }
  if (resume && A.audio) {
    int state = AAudioStream_getState(A.audio);
    if (state != AAUDIO_STREAM_STATE_STARTED && !audio_start()) {
      audio_close();
      now = now_s(); interrupted = 1;
      snd_retry_interrupt(&audio_retry, now);
      if (!audio_retry.pending) fprintf(stderr, "audio_diag retry_exhausted attempts=3\n");
    }
  }
  /* Apply resume after processing a pending disconnect or failed resume start.
   * A newly interrupted stream still observes its full five-second backoff. */
  if (resume && !A.audio && !audio_retry.pending && audio_retry.attempts >= 3)
    snd_retry_begin(&audio_retry, now + (interrupted ? 5.0 : 0.0));
  if (snd_retry_due(&audio_retry, now, 0)) {
    int ok = audio_open();
    now = now_s();
    snd_retry_result(&audio_retry, now, ok);
    if (!ok && !audio_retry.pending) fprintf(stderr, "audio_diag retry_exhausted attempts=3\n");
  }
  if (A.audio) {
    /* A started state, not merely a successful start request, must persist for
     * ten active seconds before the retry budget is reset. */
    snd_retry_stability(&audio_retry, now, AAudioStream_getState(A.audio) == AAUDIO_STREAM_STATE_STARTED);
  }
}

/* ---- calls up to MainActivity (the game thread is attached to the VM) ---- */

static JNIEnv *env_here(void) {
  JNIEnv *env = NULL;
  if ((*A.vm)->GetEnv(A.vm, (void **)&env, JNI_VERSION_1_6) != JNI_OK) (*A.vm)->AttachCurrentThread(A.vm, &env, NULL);
  return env;
}

static void call_str(jmethodID m, const char *s) {
  JNIEnv *env = env_here();
  jstring js = s ? (*env)->NewStringUTF(env, s) : NULL;
  pthread_mutex_lock(&A.mx);
  jobject activity = (*env)->NewLocalRef(env, A.activity);
  pthread_mutex_unlock(&A.mx);
  if (activity) { (*env)->CallVoidMethod(env, activity, m, js); (*env)->DeleteLocalRef(env, activity); }
  if (js) (*env)->DeleteLocalRef(env, js);
}

/* the movie the attract loop wants and the BGM (main.m syncMovie) */
static void sync_movie(void) {
  unsigned generation = atomic_load(&A.activity_generation);
  if (generation != A.synced_generation) {
    A.synced_generation = generation;
    A.movie = -2; A.bgm = NULL; A.bgm_level = -1;
  }
  int level = app_get_bgm_volume();
  if (level != A.bgm_level) {
    A.bgm_level = level;
    JNIEnv *env = env_here();
    pthread_mutex_lock(&A.mx);
    jobject activity = (*env)->NewLocalRef(env, A.activity);
    pthread_mutex_unlock(&A.mx);
    if (activity) {
      (*env)->CallVoidMethod(env, activity, A.set_bgm_volume, app_bgm_volume_multiplier());
      (*env)->DeleteLocalRef(env, activity);
    }
  }
  int want = app_movie();
  if (want != A.movie) {
    A.movie = want;
    call_str(A.show_movie, want >= 0 ? MOVIES[want] : NULL);
  }
  const char *track = app_bgm();
  if (track != A.bgm) {
    A.bgm = track;
    call_str(A.play_bgm, track);
  }
}

/* ---- GL ---- */

#ifdef WMMT_VK
/* Vulkan (vkgl): the pipelines it made last time from save_dir; the programs it has no SPIR-V
 * for written there too, for the next build */
static int egl_init(void) {
  static const char *const ext[] = { VK_KHR_SURFACE_EXTENSION_NAME, VK_KHR_ANDROID_SURFACE_EXTENSION_NAME };
  if (vkgl_create(ext, 2) != 0) return -1;
  char path[600];
  snprintf(path, sizeof path, "%s/vk_pipelines.bin", A.save_dir);
  vkgl_pipeline_cache_file(path);
  setenv("VKGL_MISSING_DIR", A.save_dir, 1);
  A.vk_up = 1;
  A.load_ctx = (EGLContext)1; /* (a loading thread: vkgl's second) */
  return 0;
}

static void *loader(void *arg) {
  vkgl_thread_loader();
  app_loader();
  return NULL;
}

/* the surface MainActivity has now (under A.mx): its swapchain, or none */
static void take_window(void) {
  A.window_changed = 0;
  if (A.have_surface) {
    vkgl_release_surface(); /* (the surface with it) */
    A.vk_surface = VK_NULL_HANDLE;
    A.have_surface = 0;
  }
  if (!A.window) return;
  VkAndroidSurfaceCreateInfoKHR ci = { VK_STRUCTURE_TYPE_ANDROID_SURFACE_CREATE_INFO_KHR };
  ci.window = A.window;
  if (vkCreateAndroidSurfaceKHR(vkgl_instance(), &ci, NULL, &A.vk_surface) != VK_SUCCESS ||
      vkgl_surface(A.vk_surface, ANativeWindow_getWidth(A.window), ANativeWindow_getHeight(A.window)) != 0) {
    fprintf(stderr, "no Vulkan surface\n");
    return;
  }
  A.have_surface = 1;
  vkgl_screen_size(&A.fb_w, &A.fb_h);
  fprintf(stderr, "surface %dx%d (Vulkan)\n", A.fb_w, A.fb_h);
}
#define SURFACE_UP A.have_surface
#else
#define SURFACE_UP (A.surface != EGL_NO_SURFACE)

static int egl_init(void) {
  A.dpy = eglGetDisplay(EGL_DEFAULT_DISPLAY);
  if (!eglInitialize(A.dpy, NULL, NULL)) return -1;
  /* 8-bit colour, depth 24 + stencil 8 (the cars' shadows), 4x MSAA where there is (an
   * Adreno resolves it on chip, nearly free) */
  for (int samples = 4; samples >= 0; samples -= 4) {
    const EGLint attr[] = { EGL_RENDERABLE_TYPE, EGL_OPENGL_ES3_BIT_KHR, EGL_SURFACE_TYPE, EGL_WINDOW_BIT | EGL_PBUFFER_BIT,
                            EGL_RED_SIZE, 8, EGL_GREEN_SIZE, 8, EGL_BLUE_SIZE, 8, EGL_ALPHA_SIZE, 0,
                            EGL_DEPTH_SIZE, 24, EGL_STENCIL_SIZE, 8,
                            EGL_SAMPLE_BUFFERS, samples ? 1 : 0, EGL_SAMPLES, samples, EGL_NONE };
    EGLint n = 0;
    if (eglChooseConfig(A.dpy, attr, &A.config, 1, &n) && n == 1) {
      fprintf(stderr, "EGL config: %d samples\n", samples);
      break;
    }
    if (!samples) return -1;
  }
  const EGLint ca[] = { EGL_CONTEXT_CLIENT_VERSION, 3, EGL_NONE };
  A.ctx = eglCreateContext(A.dpy, A.config, EGL_NO_CONTEXT, ca);
  if (A.ctx == EGL_NO_CONTEXT) return -1;
  A.load_ctx = eglCreateContext(A.dpy, A.config, A.ctx, ca);
  return 0;
}

static void *loader(void *arg) {
  const EGLint pa[] = { EGL_WIDTH, 1, EGL_HEIGHT, 1, EGL_NONE };
  EGLSurface pb = eglCreatePbufferSurface(A.dpy, A.config, pa);
  if (!eglMakeCurrent(A.dpy, pb, pb, A.load_ctx)) {
    fprintf(stderr, "loading thread: no context\n");
    return NULL;
  }
  app_loader();
  return NULL;
}

/* the surface MainActivity has now (under A.mx): made current, or none */
static void take_window(void) {
  if (A.surface != EGL_NO_SURFACE) {
    eglMakeCurrent(A.dpy, EGL_NO_SURFACE, EGL_NO_SURFACE, EGL_NO_CONTEXT);
    eglDestroySurface(A.dpy, A.surface);
    A.surface = EGL_NO_SURFACE;
  }
  A.window_changed = 0;
  if (!A.window) return;
  A.surface = eglCreateWindowSurface(A.dpy, A.config, A.window, NULL);
  if (A.surface == EGL_NO_SURFACE || !eglMakeCurrent(A.dpy, A.surface, A.surface, A.ctx)) {
    fprintf(stderr, "no window surface: 0x%x\n", eglGetError());
    A.surface = EGL_NO_SURFACE;
    return;
  }
  eglQuerySurface(A.dpy, A.surface, EGL_WIDTH, &A.fb_w);
  eglQuerySurface(A.dpy, A.surface, EGL_HEIGHT, &A.fb_h);
  eglSwapInterval(A.dpy, 1);
  fprintf(stderr, "surface %dx%d\n", A.fb_w, A.fb_h);
}
#endif

static int start_game(void) {
  app_save_dir(A.save_dir);
  /* the game's 1024x768 layout, 768 high on screen; a phone's 16:9 is wider (main.m) */
  A.touch_k = 768.0f / (float)A.fb_h;
  A.touch_edge = ((float)A.fb_w * A.touch_k - 1024.0f) * 0.5f;
  if (A.touch_edge < 1.0f) A.touch_edge = 0;
  app_console();
  /* the keys a little smaller than the iPhone's 1.3, under the meters' plate and the shift gate */
  app_wide(A.touch_edge, A.touch_edge > 0 ? 1.2f : 1.0f);
  /* HUD loads once on this game thread; later Activity recreation does not reload it. */
  char sidecar[sizeof A.sidecar_dir];
  hud_set_extra_directory(android_card_resources_dir(sidecar, sizeof sidecar) ? sidecar : NULL);
  if (app_init(A.data_dir, A.fb_w, A.fb_h, 1024, 768) != 0) {
    fprintf(stderr, "%s\n", app_error());
    call_str(A.fail, app_error());
    return -1;
  }
  snd_retry_begin(&audio_retry, now_s());
  pthread_t t;
  if (A.load_ctx != EGL_NO_CONTEXT && pthread_create(&t, NULL, loader, NULL) == 0) pthread_detach(t);
  else fprintf(stderr, "no loading thread: the menu frames load\n");
  return 0;
}

static void *game(void *arg) {
  env_here();
  if (egl_init() != 0) {
    call_str(A.fail, "no OpenGL ES 3 on this phone");
    return NULL;
  }
  double last = 0;
  timing60_pacer pacer = {0};
  int failed = 0, away = 0;
  for (;;) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    int64_t ns = (int64_t)ts.tv_sec * 1000000000LL + ts.tv_nsec;
    int64_t deadline = timing60_deadline(&pacer, ns);
    ts.tv_sec = deadline / 1000000000LL;
    ts.tv_nsec = deadline % 1000000000LL;
    int sleep_result;
    do { sleep_result = clock_nanosleep(CLOCK_MONOTONIC, TIMER_ABSTIME, &ts, NULL); }
    while (sleep_result == EINTR);
    if (sleep_result) { fprintf(stderr, "clock_nanosleep failed: %d\n", sleep_result); return NULL; }
    touch_ev tv[TOUCH_MAX];
    int nt, touch_desync, press, done, warn, tilt_new;
    float tilt;
    pthread_mutex_lock(&A.mx);
    while (A.paused || (!A.window && !A.window_changed)) {
      if (A.started && !away && !failed) {
        /* The lifecycle callback poisoned the queue. Release captures on the
         * game thread even if no further surface/frame ever arrives. */
        pthread_mutex_unlock(&A.mx);
        touch_cancel_all();
        pthread_mutex_lock(&A.mx);
        app_suspend(1); /* the loading thread stops too */
#ifdef WMMT_VK
        vkgl_pipeline_cache_save();
#endif
        snd_retry_stability(&audio_retry, now_s(), 0);
        if (A.audio) {
          aaudio_result_t pause_result = AAudioStream_requestPause(A.audio);
          fprintf(stderr, "audio_diag pause=%d state=%d\n", pause_result, AAudioStream_getState(A.audio));
        }
        away = 1;
      }
      last = 0;
      timing60_pacer_reset(&pacer);
      if (A.paused || (!A.window && !A.window_changed))
        pthread_cond_wait(&A.cv, &A.mx);
    }
    if (A.window_changed) take_window();
    /* Keep queued input while the surface is unavailable; overflow poisons it. */
    nt = 0; touch_desync = 0;
    if (SURFACE_UP) nt = touch_take(tv, &touch_desync);
    press = A.press_start, done = A.movie_done_ev, warn = A.memory_warning;
    A.press_start = A.movie_done_ev = A.memory_warning = 0;
    tilt = A.tilt, tilt_new = A.tilt_new;
    A.tilt_new = 0;
    pthread_mutex_unlock(&A.mx);
    if (!SURFACE_UP) { snd_retry_stability(&audio_retry, now_s(), 0); last = 0; timing60_pacer_reset(&pacer); continue; }
    if (!A.started) {
      A.started = 1;
      failed = start_game() != 0;
    }
    if (failed) {
      usleep(100000);
      continue;
    }
    audio_service(away, now_s());
    if (away) {
      app_suspend(0);
      away = 0;
    }
    if (warn) app_memory_warning();
    if (done) {
      A.movie = -1;
      app_movie_done();
    }
    if (press) app_press_start();
    touch_reconcile_snapshot(&nt, &touch_desync);
    touch_deliver(tv, nt, touch_desync);
    A.wants_tilt = app_wants_tilt();
    if (tilt_new) app_tilt(tilt);
    double now = now_s();
    timing60_started(&pacer, (int64_t)(now * 1000000000.0));
    float dt = last > 0 ? (float)(now - last) : 0.0f;
    last = now;
    glBindFramebuffer(GL_FRAMEBUFFER, 0);
    /* Recheck just before the frame; later arrivals are handled next frame. */
    int empty = 0, poisoned = 0;
    touch_reconcile_snapshot(&empty, &poisoned);
    if (poisoned) touch_cancel_all();
    app_frame(dt);
    sync_movie();
    /* depth and stencil need not go out to memory */
    static PFNGLDISCARDFRAMEBUFFEREXTPROC discard_fb;
    if (!discard_fb) discard_fb = (PFNGLDISCARDFRAMEBUFFEREXTPROC)eglGetProcAddress("glDiscardFramebufferEXT");
    const GLenum discard[] = { GL_DEPTH_EXT, GL_STENCIL_EXT };
    if (discard_fb) discard_fb(GL_FRAMEBUFFER, 2, discard);
    double p0 = now_s();
#ifdef WMMT_VK
    /* (the swapchain made again for a new size or rotation) */
    if (vkgl_present() != 0 && A.window) {
      pthread_mutex_lock(&A.mx);
      A.window_changed = 1;
      pthread_mutex_unlock(&A.mx);
    }
#else
    eglSwapBuffers(A.dpy, A.surface);
#endif
    app_frame_done((now_s() - p0) * 1000.0);
  }
  return NULL;
}

/* ---- JNI ---- */

#define JFN(name) Java_com_wmmt_port_MainActivity_##name

JNIEXPORT void JNICALL JFN(nativeBgmFailure)(JNIEnv *env, jclass cls, jobject owner, jint group) {
  (void)cls;
  /* A late callback from a destroyed/replaced Activity must not disable the
   * resource group selected by its successor. */
  pthread_mutex_lock(&A.mx);
  int current = owner && A.activity && (*env)->IsSameObject(env, owner, A.activity);
  if (current && group >= 1 && group <= 2) atomic_fetch_and(&bgm_extra_mask, ~(1u << group));
  pthread_mutex_unlock(&A.mx);
}

JNIEXPORT void JNICALL JFN(nativeStart)(JNIEnv *env, jclass cls, jobject activity, jstring data, jstring save, jstring sidecar) {
  const char *resource_path = sidecar ? (*env)->GetStringUTFChars(env, sidecar, NULL) : NULL;
  pthread_mutex_lock(&A.mx);
  A.sidecar_dir[0] = '\0';
  if (resource_path && strlen(resource_path) < sizeof A.sidecar_dir)
    memcpy(A.sidecar_dir, resource_path, strlen(resource_path) + 1);
  if (resource_path) (*env)->ReleaseStringUTFChars(env, sidecar, resource_path);
  atomic_store(&bgm_extra_mask, A.sidecar_dir[0] ? 6u : 0u);
  if (A.activity) {
    jobject replacement = (*env)->NewGlobalRef(env, activity);
    if (replacement) {
      (*env)->DeleteGlobalRef(env, A.activity);
      A.activity = replacement;
      atomic_fetch_add(&A.activity_generation, 1);
    }
    pthread_mutex_unlock(&A.mx);
    return;
  }
  (*env)->GetJavaVM(env, &A.vm);
  A.activity = (*env)->NewGlobalRef(env, activity);
  atomic_fetch_add(&A.activity_generation, 1);
  pthread_mutex_unlock(&A.mx);
  A.show_movie = (*env)->GetMethodID(env, cls, "showMovie", "(Ljava/lang/String;)V");
  A.play_bgm = (*env)->GetMethodID(env, cls, "playBgm", "(Ljava/lang/String;)V");
  A.set_bgm_volume = (*env)->GetMethodID(env, cls, "setBgmVolume", "(F)V");
  A.fail = (*env)->GetMethodID(env, cls, "fail", "(Ljava/lang/String;)V");
  const char *d = (*env)->GetStringUTFChars(env, data, NULL), *s = (*env)->GetStringUTFChars(env, save, NULL);
  snprintf(A.data_dir, sizeof A.data_dir, "%s", d);
  snprintf(A.save_dir, sizeof A.save_dir, "%s", s);
  (*env)->ReleaseStringUTFChars(env, data, d);
  (*env)->ReleaseStringUTFChars(env, save, s);
  char log[600];
  snprintf(log, sizeof log, "%s/log.txt", A.save_dir);
  freopen(log, "w", stderr);
  setvbuf(stderr, NULL, _IONBF, 0);
  fprintf(stderr, "start (android)\n");
  pthread_t t;
  pthread_attr_t at;
  pthread_attr_init(&at);
  pthread_attr_setstacksize(&at, 8 << 20); /* the recompiled physics has deep frames */
  pthread_create(&t, &at, game, NULL);
  pthread_detach(t);
}

JNIEXPORT void JNICALL JFN(nativeSurface)(JNIEnv *env, jclass cls, jobject surface, jint w, jint h) {
  ANativeWindow *win = surface ? ANativeWindow_fromSurface(env, surface) : NULL;
  pthread_mutex_lock(&A.mx);
  if (!surface) { A.n_touch = 0; A.touch_desync = 1; }
  if (A.window) ANativeWindow_release(A.window);
  A.window = win;
  A.window_changed = 1;
  pthread_cond_broadcast(&A.cv);
  pthread_mutex_unlock(&A.mx);
  /* the old surface must be let go of before surfaceDestroyed returns */
  if (!surface) {
    for (int i = 0; i < 200; ++i) {
      pthread_mutex_lock(&A.mx);
      int pending = A.window_changed && A.started;
      pthread_mutex_unlock(&A.mx);
      if (!pending) break;
      usleep(5000);
    }
  }
}

JNIEXPORT void JNICALL JFN(nativeTouch)(JNIEnv *env, jclass cls, jint id, jint phase, jfloat x, jfloat y) {
  pthread_mutex_lock(&A.mx);
  touch_enqueue((touch_ev){ id, phase, x, y });
  pthread_mutex_unlock(&A.mx);
}

JNIEXPORT void JNICALL JFN(nativePause)(JNIEnv *env, jclass cls, jboolean p) {
  pthread_mutex_lock(&A.mx);
  if (p) { A.n_touch = 0; A.touch_desync = 1; }
  A.paused = p;
  pthread_cond_broadcast(&A.cv);
  pthread_mutex_unlock(&A.mx);
}

JNIEXPORT void JNICALL JFN(nativeTilt)(JNIEnv *env, jclass cls, jfloat r) {
  pthread_mutex_lock(&A.mx);
  A.tilt = r;
  A.tilt_new = 1;
  pthread_mutex_unlock(&A.mx);
}

JNIEXPORT jboolean JNICALL JFN(nativeWantsTilt)(JNIEnv *env, jclass cls) { return A.wants_tilt ? JNI_TRUE : JNI_FALSE; }

JNIEXPORT void JNICALL JFN(nativeMovieDone)(JNIEnv *env, jclass cls) {
  pthread_mutex_lock(&A.mx);
  A.movie_done_ev = 1;
  pthread_mutex_unlock(&A.mx);
}

JNIEXPORT void JNICALL JFN(nativePressStart)(JNIEnv *env, jclass cls) {
  pthread_mutex_lock(&A.mx);
  A.press_start = 1;
  pthread_mutex_unlock(&A.mx);
}

JNIEXPORT void JNICALL JFN(nativeMemoryWarning)(JNIEnv *env, jclass cls) {
  pthread_mutex_lock(&A.mx);
  A.memory_warning = 1;
  pthread_mutex_unlock(&A.mx);
}
