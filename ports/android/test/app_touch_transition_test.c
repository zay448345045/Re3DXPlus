#include <assert.h>
#include <stdio.h>
#include <string.h>
#include "../src/app.c"
void snd_menu(int x) { (void)x; }
int main(void) {
 memset(&G,0,sizeof G); hud_wide(0,1); hud_init(&G.hud,1024,768);
 void *finger=(void*)1, *other=(void*)2;
 app_touch(finger,TOUCH_BEGAN,950,650); assert(G.hud.throttle_touch==finger);
 G.paused=1; G.menu.pause.open=1;
 app_touch(other,TOUCH_ENDED,950,650); assert(G.hud.throttle_touch==finger);
 app_touch(finger,TOUCH_ENDED,950,650); assert(!G.hud.throttle_touch);
 G.paused=0; G.menu.pause.open=0; car_input in={0}; hud_input(&G.hud,&in); assert(in.throttle==0);
 /* A legitimate menu end is still delivered after the race capture is released. */
 app_touch(finger,TOUCH_BEGAN,950,650); assert(G.hud.throttle_touch==finger);
 G.in_menu=1; G.menu.screen=MENU_CARD; G.menu.card_page=1;
 app_touch(other,TOUCH_BEGAN,760,80); assert(G.menu.card_touch==other);
 app_touch(other,TOUCH_ENDED,760,80); assert(!G.menu.card_touch && G.menu.back==1 && G.hud.throttle_touch==finger);
 app_touch(finger,TOUCH_ENDED,950,650); assert(!G.hud.throttle_touch);
 /* Cancellation remains dual-routed and does not commit a captured button. */
 G.menu.back=0; app_touch(finger,TOUCH_BEGAN,760,80); assert(G.menu.card_touch==finger);
 app_touch(finger,TOUCH_CANCELLED,760,80); assert(!G.menu.card_touch && !G.menu.back);
 puts("app touch transition ok");
}
