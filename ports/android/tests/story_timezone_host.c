/* Compiles the production menu.c directly. Render/audio are host stubs; this is
 * a menu-state test, not an app.c persistence or asset-loading test. */
#include PORT_MENU
#include <assert.h>

void snd_menu(int x) { (void)x; }
int anm_sprite(int x) { return x; }
int anm_sprite_rect(int anim, int frame, int sprite, float r[4]) {
  (void)anim;
  if (sprite == T_ARROW || sprite == T_ARROW2 ||
      sprite != (frame >= 100 ? T_NIGHT : T_MORNING)) return 0;
  r[0] = r[1] = 0; r[2] = r[3] = 100;
  return 1;
}
static void tick(menu_state *m, int n) {
  for (int i = 0; i < n; ++i) menu_update(m, 1.0f / 60.0f);
}
static void enter_story(menu_state *m) {
  memset(m, 0, sizeof *m);
  m->screen = MENU_ST_RIVAL; m->from = -1; m->game = MENU_GAME_STORY;
  m->deciding = 1; m->zones = 2; m->sel = 2;
  tick(m, 1);
  assert(m->screen == MENU_BGM && m->story_day_select && m->from == -1);
}
static void slide_to_night(menu_state *m) {
  m->key = 1; tick(m, 1); assert(m->slide == SLIDE && m->zone == 0);
  tick(m, SLIDE - 1); assert(m->zone == 0 && m->slide == 1);
  tick(m, 1); assert(m->zone == 1 && m->slide == 0);
}
int main(void) {
  menu_state m;
  enter_story(&m); m.ta_zone = 1;
  slide_to_night(&m);
  m.tap = 1; m.tap_x = m.tap_y = 50; tick(&m, 1);
  assert(m.deciding == DECIDE_DAY + FADE && m.story_zone == 1);
  tick(&m, DECIDE_DAY + FADE - 1);
  assert(m.screen == MENU_BGM && m.story_day_select && m.deciding == 1);
  tick(&m, 1);
  assert(m.screen == MENU_PRE && !m.story_day_select && m.zone == 1 && m.ta_zone == 1 && m.zones == 2);
  assert(m.sel == 0 && m.from == -1 && m.deciding == 0);

  enter_story(&m); slide_to_night(&m);
  m.back = 1; tick(&m, 1);
  assert(m.screen == MENU_ST_RIVAL && !m.story_day_select && m.zone == 0 && m.story_zone == 0 && m.ta_zone == 0);
  menu_vs_day_open(&m); assert(m.zone == 0 && m.vs.day);
  m.screen = MENU_COURSE; m.game = MENU_GAME_TA; m.vs.day = 0; m.vs.state = MENU_VS_OFF; m.deciding = 1;
  tick(&m, 1); assert(m.screen == MENU_BGM && m.zone == 0 && !m.story_day_select);
  m.tap = 1; m.tap_x = m.tap_y = 50; tick(&m, 1);
  assert(m.deciding == DECIDE_DAY + FADE); tick(&m, DECIDE_DAY + FADE);
  assert(m.screen == MENU_PRE && m.ta_zone == 0 && !m.story_day_select);
  m.screen = MENU_TEN_LEVEL; m.game = MENU_GAME_TEN; m.deciding = 1; m.ten_course = 0; m.sel = 0;
  tick(&m, 1); assert(m.screen == MENU_PRE && m.ta_zone == 0 && !m.story_day_select);

  memset(&m, 0, sizeof m); m.game = MENU_GAME_STORY; m.story_day_select = 1;
  m.zones = 1; m.tap_x = m.tap_y = 50;
  assert(!day_select_step(&m, 0, 1) && !m.slide && m.zone == 0);
  assert(day_select_step(&m, 1, 0) && m.story_zone == 0);
  puts("production menu Story/TA/VS/TEN state tests passed");
  return 0;
}
