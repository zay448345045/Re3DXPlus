#include <assert.h>
#include <stdio.h>
#include <string.h>
#include "../src/menu.c"
void snd_menu(int x) { (void)x; }
int anm_sprite(int id) { return id; }
float anm_sprite_width(int id) { (void)id; return 50; }
static void press(menu_state *m, int id, float x, float y) { menu_touch(m,(void*)(long)id,TOUCH_BEGAN,x,y); menu_touch(m,(void*)(long)id,TOUCH_ENDED,x,y); layout_step(m,0); }
int main(void) {
 menu_state m; memset(&m,0,sizeof m); m.screen=MENU_LAYOUT; m.lay_sel=HUD_KEYS_RIGHT; for(int i=0;i<3;i++)m.key_k[i]=100; hud_wide(0,1);
 const float xs[3]={130,40,950},ys[3]={30,650,650};
 for(int g=0;g<3;g++) { layout_apply(&m); int old=m.key_dx[g]; menu_touch(&m,(void*)1,TOUCH_BEGAN,xs[g],ys[g]); assert(m.lay_drag && m.lay_sel==g); menu_touch(&m,(void*)2,TOUCH_MOVED,xs[g]+50,ys[g]); menu_touch(&m,(void*)2,TOUCH_CANCELLED,xs[g],ys[g]); assert(m.lay_drag && m.key_dx[g]==old); menu_touch(&m,(void*)1,TOUCH_MOVED,xs[g]+20,ys[g]-20); menu_touch(&m,(void*)1,TOUCH_CANCELLED,0,0); assert(!m.lay_drag && m.key_dx[g]==old); }
 menu_touch(&m,(void*)1,TOUCH_BEGAN,40,650); menu_touch(&m,(void*)1,TOUCH_MOVED,100,600); menu_touch(&m,(void*)1,TOUCH_ENDED,100,600); assert(m.key_dx[1]!=0 && m.key_layout_dirty);
 press(&m,1,650,380); assert(m.key_k[1]==110); for(int i=0;i<10;i++) press(&m,1,650,380); assert(m.key_k[1]==160); for(int i=0;i<20;i++) press(&m,1,330,380); assert(m.key_k[1]==60);
 /* Button release/cancel is captured and may not be hijacked by a second finger. */
 menu_touch(&m,(void*)1,TOUCH_BEGAN,330,450); menu_touch(&m,(void*)2,TOUCH_ENDED,330,450); layout_step(&m,0); assert(m.key_k[1]==60);
 menu_touch(&m,(void*)1,TOUCH_CANCELLED,330,450); layout_step(&m,0); assert(m.key_k[1]==60);
 press(&m,1,330,450); for(int i=0;i<3;i++) assert(m.key_k[i]==100 && !m.key_dx[i] && !m.key_dy[i]);
 /* Even when keys overlap RESET ALL, panel hit testing wins. */
 m.key_dx[0]=250; m.key_dy[0]=420; press(&m,1,330,450); assert(m.key_dx[0]==0);
 press(&m,1,600,450); assert(m.screen==MENU_OPTION);
 /* Entry sits wholly above the steering band; graphics rows retain their hit logic. */
 memset(&m,0,sizeof m); m.screen=MENU_OPTION; m.hq_rows=1; m.tap_x=460; m.tap_y=120; option_step(&m,1,0); assert(m.screen==MENU_LAYOUT);
 memset(&m,0,sizeof m); m.screen=MENU_OPTION; m.hq_rows=1; m.over_on=0; m.tap_x=195; m.tap_y=288; option_step(&m,1,0); assert(m.over_on==1 && m.screen==MENU_OPTION);
 /* OPTION -> editor while a different finger still owns the old back button. */
 for (int phase=TOUCH_ENDED; phase<=TOUCH_CANCELLED; ++phase) {
   memset(&m,0,sizeof m); m.screen=MENU_OPTION; m.lay_sel=HUD_KEYS_RIGHT; for(int i=0;i<3;i++) m.key_k[i]=100;
   menu_touch(&m,(void*)1,TOUCH_BEGAN,760,80); assert(m.back_touch==(void*)1);
   menu_touch(&m,(void*)2,TOUCH_BEGAN,736,192); assert(m.tap); option_step(&m,m.tap,0); assert(m.screen==MENU_LAYOUT); m.tap=0;
   menu_touch(&m,(void*)3,TOUCH_BEGAN,40,650); assert(m.lay_touch==(void*)3 && m.lay_drag);
   menu_touch(&m,(void*)1,phase,760,80); assert(!m.back_touch && !m.back && m.lay_touch==(void*)3 && m.lay_drag);
   menu_touch(&m,(void*)3,TOUCH_CANCELLED,0,0); assert(!m.lay_touch);
 }
 /* Ordinary left/right capture remains owned until its own cancel or end. */
 memset(&m,0,sizeof m); m.screen=MENU_OPTION;
 menu_touch(&m,(void*)1,TOUCH_BEGAN,50,680); assert(m.key_touch==(void*)1 && m.key==-1 && m.key_held==-1);
 menu_touch(&m,(void*)2,TOUCH_CANCELLED,50,680); assert(m.key_touch==(void*)1 && m.key_held==-1);
 menu_touch(&m,(void*)2,TOUCH_ENDED,50,680); assert(m.key_touch==(void*)1 && m.key_held==-1);
 menu_touch(&m,(void*)1,TOUCH_CANCELLED,50,680); assert(!m.key_touch && !m.key_held && !m.key);
 /* Card cancel retains another finger and never commits. */
 memset(&m,0,sizeof m); m.screen=MENU_CARD; m.card_page=1; menu_touch(&m,(void*)1,TOUCH_BEGAN,760,80); assert(m.card_touch); menu_touch(&m,(void*)2,TOUCH_CANCELLED,760,80); assert(m.card_touch==(void*)1); menu_touch(&m,(void*)1,TOUCH_CANCELLED,760,80); assert(!m.card_touch && !m.back && !m.key && !m.tap);
 /* Actual race HUD uses the same scale/offset and releases only the owner. */
 hud_wide(100, 1.2f); hud_layout_set(HUD_KEYS_LEFT,1.5f,40,-20);
 hud_state h; hud_init(&h,1024,768);
 float x=-100+40+16*1.8f+10, y=768-20+(604-768)*1.8f+20;
 assert(hud_layout_hit(0,x,y)==HUD_KEYS_LEFT);
 hud_touch(&h,(void*)1,TOUCH_BEGAN,x,y); assert(h.left_touch==(void*)1);
 hud_touch(&h,(void*)2,TOUCH_CANCELLED,x,y); assert(h.left_touch==(void*)1);
 hud_touch(&h,(void*)1,TOUCH_CANCELLED,x,y); assert(!h.left_touch);
 h.gyro=1; hud_touch(&h,(void*)1,TOUCH_BEGAN,x,y); assert(h.brake_touch==(void*)1);
 hud_touch(&h,(void*)1,TOUCH_CANCELLED,x,y); assert(!h.brake_touch);
 puts("key layout editor ok");
}
