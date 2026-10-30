/* Mock state transitions; shared production retry/generation helpers, no AAudio. */
#include "sound.h"
#include <assert.h>
#include <stdio.h>
static _Atomic unsigned mark;
static snd_retry retry;
static unsigned generation, handled;
static int stream, starts, opens, closes, fail;
static void service(double now, int paused, int resume) {
  if (paused) { snd_retry_stability(&retry, now, 0); return; }
  int interrupted = 0;
  unsigned d = atomic_load_explicit(&mark, memory_order_relaxed);
  if (stream && d == generation && d != handled) {
    handled = d; stream = 0; ++closes; interrupted = 1; snd_retry_interrupt(&retry, now);
  }
  if (resume && stream) ++starts;
  if (resume && !stream && !retry.pending && retry.attempts >= 3) snd_retry_begin(&retry, now + (interrupted ? 5 : 0));
  if (snd_retry_due(&retry, now, 0)) {
    ++generation; ++opens;
    if (!fail) { stream = 1; ++starts; }
    snd_retry_result(&retry, now, !fail);
  }
  if (stream) snd_retry_stability(&retry, now, 1);
}
int main(void) {
  snd_retry_begin(&retry, 0); service(0, 0, 0);
  assert(stream && starts == 1 && retry.attempts == 1);
  snd_diag_disconnect(&mark, generation);
  service(1, 1, 1); assert(stream && starts == 1);
  service(2, 0, 1); assert(!stream && closes == 1 && starts == 1);
  service(6.9, 0, 0); assert(opens == 1);
  service(7, 0, 0); assert(stream && starts == 2 && opens == 2);
  snd_diag_disconnect(&mark, 1); service(8, 0, 0); assert(closes == 1);
  snd_diag_disconnect(&mark, generation); service(8.1, 0, 0);
  service(13.1, 0, 0); assert(stream && opens == 3 && retry.attempts == 3);
  snd_diag_disconnect(&mark, generation); service(14, 0, 0);
  service(100, 0, 0); assert(!stream && !retry.pending && opens == 3);
  service(101, 1, 0); assert(opens == 3);
  fail = 1; service(102, 0, 1); assert(opens == 4 && retry.attempts == 1);
  service(106.9, 0, 0); assert(opens == 4);
  service(107, 0, 0); service(112, 0, 0); service(200, 0, 0);
  assert(opens == 6 && !retry.pending && retry.attempts == 3);
  fail = 0; service(201, 0, 1); assert(stream && retry.attempts == 1);
  service(210.9, 0, 0); assert(retry.attempts == 1);
  service(211, 0, 0); assert(retry.attempts == 0);
  snd_diag_disconnect(&mark, generation); service(212, 0, 0);
  service(217, 0, 0); assert(stream && retry.attempts == 2);
  /* Regression: third-attempt live stream disconnects while backgrounded. */
  retry.attempts = 3; snd_diag_disconnect(&mark, generation);
  service(218, 1, 0); service(219, 0, 1);
  assert(!stream && retry.pending && retry.attempts == 0 && retry.next == 224);
  service(223.9, 0, 0); assert(!stream);
  service(224, 0, 0); assert(stream && retry.attempts == 1);
  snd_diag_disconnect(&mark, generation); snd_diag_disconnect(&mark, 2);
  assert(atomic_load(&mark) == generation);
  puts("retry simulation passed: fast disconnect, backoff, exhaustion, resume, stable reset, old callback");
}
