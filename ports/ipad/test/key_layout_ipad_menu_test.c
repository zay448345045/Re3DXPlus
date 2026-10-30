#include <TargetConditionals.h>
#undef TARGET_OS_IPHONE
#define TARGET_OS_IPHONE 1
#include "glstub.h"
#define WMMT_GL_H
#include "../src/menu.c"
#include <assert.h>
void snd_menu(int n) { (void)n; }
int hud_meter_available(void) { return 0; }
int ios_bgm_group_available(int n) { (void)n; return 0; }
void hud_layout_set(int g,float k,float x,float y) { (void)g; (void)k; (void)x; (void)y; }
void hud_layout_clamp(int g,int gyro,float k,float *x,float *y) { (void)g;(void)gyro;(void)k; if(*x>500)*x=500;if(*y>500)*y=500; }
int hud_layout_hit(int gyro,float x,float y) { (void)gyro;(void)y; return x<270?1:2; }
int hud_menu_key(float x,float y) { if (x>720 && x<800 && y<100) return HUD_MENU_BACK; if (x<200 && y>640) return -1; return 0; }
int anm_sprite(int n) { return n; }
float anm_sprite_width(int n) { (void)n; return 35; }
float hud_ui_text_width(const char *s,float p) { return (float)strlen(s)*6*p; }
int main(void) {
 menu_state m={0}; for(int i=0;i<3;i++)m.key_k[i]=100;
 m.screen=MENU_OPTION; m.tap_x=446; m.tap_y=110; option_step(&m,1,0); assert(m.screen==MENU_LAYOUT);
 m.screen=MENU_OPTION; m.tap_x=622; m.tap_y=110; option_step(&m,1,0); assert(m.screen==MENU_OPTION);
 m.tap_x=446; m.tap_y=136; option_step(&m,1,0); assert(m.screen==MENU_OPTION);
 m.tap_x=300; m.tap_y=212; option_step(&m,1,0); assert(m.screen==MENU_OPTION && m.pedal_slide);
 layout_enter(&m); assert(m.screen==MENU_LAYOUT);
 void *a=(void*)1,*b=(void*)2;
 layout_touch(&m,a,TOUCH_BEGAN,100,600); layout_touch(&m,b,TOUCH_MOVED,400,400); assert(m.key_dx[1]==0);
 layout_touch(&m,a,TOUCH_MOVED,140,640); assert(m.key_dx[1]==40 && m.key_dy[1]==40);
 layout_touch(&m,a,TOUCH_CANCELLED,140,640); assert(!m.key_dx[1] && !m.key_layout_dirty);
 layout_touch(&m,a,TOUCH_BEGAN,100,600); layout_touch(&m,a,TOUCH_ENDED,140,640); assert(m.key_dx[1]==40 && m.key_layout_dirty);
 layout_touch(&m,a,TOUCH_BEGAN,650,380); layout_touch(&m,a,TOUCH_CANCELLED,650,380); layout_step(&m,0); assert(m.key_k[1]==100);
 layout_touch(&m,a,TOUCH_BEGAN,650,380); layout_touch(&m,a,TOUCH_ENDED,650,380); layout_step(&m,0); assert(m.key_k[1]==110);
 for(int i=0;i<20;i++){m.lay_tap=LAY_BIGGER+1; layout_step(&m,0);} assert(m.key_k[1]==160);
 m.lay_tap=LAY_RESET+1; layout_step(&m,0); assert(m.key_k[1]==100 && !m.key_dx[1]);
 m.lay_tap=LAY_DONE+1; layout_step(&m,0); assert(m.screen==MENU_OPTION);
 m.screen=MENU_GAME; menu_touch(&m,a,TOUCH_BEGAN,100,680); assert(m.key == -1 && m.key_held == -1);
 menu_touch(&m,b,TOUCH_CANCELLED,100,680); assert(m.key == -1 && m.key_held == -1);
 menu_touch(&m,a,TOUCH_CANCELLED,100,680); assert(!m.key && !m.key_held);
 menu_touch(&m,a,TOUCH_ENDED,100,680); assert(!m.key && !m.key_held);
 for (int phase=TOUCH_ENDED; phase<=TOUCH_CANCELLED; ++phase) {
   m.screen=MENU_GAME; menu_touch(&m,a,TOUCH_BEGAN,100,680); assert(m.key_touch==a);
   layout_enter(&m); menu_touch(&m,b,TOUCH_BEGAN,100,600); assert(m.lay_touch==b);
   menu_touch(&m,a,phase,100,680); assert(!m.key_touch && !m.key_held && m.lay_touch==b);
   menu_touch(&m,b,TOUCH_CANCELLED,100,600); assert(!m.lay_touch);
 }
 puts("iPad key layout editor PASS");
}
