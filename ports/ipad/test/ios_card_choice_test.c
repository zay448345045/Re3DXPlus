/* Host fixture: emulate iOS platform macro; no device data. */
#include <TargetConditionals.h>
#undef TARGET_OS_IPHONE
#define TARGET_OS_IPHONE 1
#include "glstub.h"
#define WMMT_GL_H
#include "../src/menu.c"
#include <assert.h>
static int meter_ready = 1, groups = 6, commit_ok = 1;
int hud_meter_available(void) { return meter_ready; }
int ios_bgm_group_available(int g) { return g > 0 && g < 3 && (groups & (1 << g)); }
int app_card_choice_commit(menu_state *m, int row, int choice, long long born) {
  if (!commit_ok) return 0;
  m->card_born[m->maker][m->car] = born;
  if (row) m->sound_car[m->maker][m->car] = choice;
  else m->meter_car[m->maker][m->car] = choice;
  return 1;
}
int main(void) {
  menu_state m = {0};
  m.n_own = 2; m.own_sel = 0; m.maker = 0; m.car = 0;
  m.own[0].maker = 0; m.own[0].car = 0; m.own[0].born = 42;
  m.own[1].maker = 0; m.own[1].car = 1; m.own[1].born = 84;
  assert(menu_card_choice_available(&m,0,0));
  assert(menu_card_choice_available(&m,0,1) && menu_card_choice_available(&m,0,2));
  assert(!menu_card_choice_available(&m,1,1) && !menu_card_choice_available(&m,1,2));
  assert(menu_card_choice_set(&m,0,2) && menu_card_meter(&m)==2);
  assert(m.st_bonus_car[0][0]==0 && !menu_card_choice_available(&m,1,1));
  meter_ready=0; assert(menu_card_meter(&m)==0 && m.meter_car[0][0]==2); meter_ready=1;
  m.st_bonus_car[0][0]=1; assert(menu_card_choice_available(&m,1,1));
  assert(!menu_card_choice_available(&m,1,2)); assert(menu_card_choice_set(&m,1,1));
  m.song=23; assert(menu_bgm(&m,1)==SONG_FILE_MT[23]);
  groups=4; assert(menu_card_bgm_source(&m)==0 && m.sound_car[0][0]==1);
  assert(menu_bgm(&m,1)==SONG_FILE[3]);
  groups=6; assert(menu_card_bgm_source(&m)==1);
  m.st_bonus_car[0][0]=3; assert(menu_card_choice_available(&m,1,2));
  commit_ok=0; assert(!menu_card_choice_set(&m,0,1) && m.card_save_failed && menu_card_meter(&m)==2); commit_ok=1;
  m.own[0].born=43; assert(menu_card_meter(&m)==0 && menu_card_bgm_source(&m)==0);
  assert(!menu_card_choice_available(&m,1,1) && menu_card_choice_available(&m,0,2));
  m.own_sel=1; m.car=1; assert(menu_card_meter(&m)==0 && !menu_card_choice_available(&m,1,1));
  m.car=0; assert(!menu_card_choice_available(&m,0,0));
  m.own_sel=-1; assert(!menu_card_choice_available(&m,0,0));
  m.own_sel=MENU_OWN_MAX; assert(!menu_card_choice_available(&m,0,0));
  m.own_sel=0; m.maker=-1; assert(!menu_card_choice_available(&m,0,0));
  m.maker=MENU_GARAGE_MAKERS; assert(!menu_card_choice_available(&m,0,0));
  m.maker=0; m.car=-1; assert(!menu_card_choice_available(&m,0,0));
  m.car=MENU_GARAGE_CARS; assert(!menu_card_choice_available(&m,0,0));
  m.car=0; assert(!menu_card_choice_available(&m,-1,0) && !menu_card_choice_available(&m,2,0));
  assert(!menu_card_choice_available(&m,0,-1) && !menu_card_choice_available(&m,0,3));
  puts("iOS card choice fixture PASS"); return 0;
}
