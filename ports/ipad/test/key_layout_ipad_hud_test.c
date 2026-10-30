#include <TargetConditionals.h>
#undef TARGET_OS_IPHONE
#define TARGET_OS_IPHONE 1
#include "glstub.h"
#define WMMT_GL_H
#define GL_ONE_MINUS_DST_COLOR 0x0307
#define GL_ZERO 0
GLuint gl_compile_program(const char *, const char *, const char **, int);
#include "../src/hud.c"
#include <assert.h>
int main(void) {
 hud_state h={0}; h.screen_w=1024; h.screen_h=768; void *a=(void*)1,*b=(void*)2;
 hud_layout_set(HUD_KEYS_LEFT,1.0f,100,-50);
 assert(hud_layout_hit(0,120,570)==HUD_KEYS_LEFT);
 hud_touch(&h,a,TOUCH_BEGAN,130,570); assert(h.left_touch==a);
 hud_touch(&h,b,TOUCH_BEGAN,950,650); assert(h.throttle_touch==b);
 hud_touch(&h,a,TOUCH_CANCELLED,0,0); assert(!h.left_touch && h.throttle_touch==b);
 hud_touch(&h,b,TOUCH_ENDED,0,0); assert(!h.throttle_touch);
 float x=-2000,y=2000; hud_layout_clamp(HUD_KEYS_LEFT,0,1.6f,&x,&y); hud_layout_set(HUD_KEYS_LEFT,1.6f,x,y);
 rect r=key(group_rect(KEY_LEFT,0),KEY_LEFT); assert(r.x>=-0.01f && r.y>=-0.01f && r.x+r.w<=1024.01f && r.y+r.h<=768.01f);
 puts("iPad HUD layout PASS");
}
