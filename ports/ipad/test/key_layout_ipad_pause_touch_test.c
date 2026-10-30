#include <TargetConditionals.h>
#undef TARGET_OS_IPHONE
#define TARGET_OS_IPHONE 1
#include <OpenGL/gl3.h>
#define WMMT_GL_H
GLuint gl_compile_program(const char *, const char *, const char **, int);
#include "../src/app.c"
#include <assert.h>
static int seen, received;
void menu_touch(menu_state *m, void *id, int phase, float x, float y) {
  (void)m; (void)id; (void)x; (void)y; seen++; received=phase;
}
int main(void) {
  void *a=(void*)1, *b=(void*)2;
  hud_wide(0,1); G.in_menu=0; G.paused=0; G.menu.finish=0;
  app_touch(a,TOUCH_BEGAN,950,650); assert(G.hud.throttle_touch==a);
  G.paused=1; app_touch(b,TOUCH_ENDED,0,0); assert(G.hud.throttle_touch==a && received==TOUCH_ENDED);
  app_touch(a,TOUCH_ENDED,0,0); assert(!G.hud.throttle_touch && received==TOUCH_ENDED && seen==2);
  G.paused=0; app_touch(a,TOUCH_BEGAN,950,650); assert(G.hud.throttle_touch==a);
  G.paused=1; app_touch(a,TOUCH_CANCELLED,0,0); assert(!G.hud.throttle_touch && received==TOUCH_CANCELLED);
  G.paused=0; assert(!G.hud.throttle_touch); puts("iPad pause touch release PASS");
}
