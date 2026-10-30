/* Exercise actual app hooks, exclusively against a new temporary directory. */
#include "../src/app.c"
#include <assert.h>
void fixture_own_register(menu_state *m);
static void restart_process(void) {
  memset(story_live,0,sizeof story_live); memset(story_live_born,0,sizeof story_live_born);
  memset(story_poison,0,sizeof story_poison); story_load_all();
}
static void garage_fixture(void) {
  char p[1100]; snprintf(p,sizeof p,"%s/garage%d",G.save_dir,G.menu.save_slot);
  FILE *f=fopen(p,"w"); assert(f);
  for(int i=0;i<G.menu.n_own;i++) {
    menu_own *o=&G.menu.own[i]; const char *label=CARDB_CARS[o->maker][o->car].label;
    fprintf(f,"own %d %lld 0 %s\ncstory %d %d %s\n",o->color,o->born,label,
      G.menu.st_div_car[o->maker][o->car],G.menu.st_bits_car[o->maker][o->car],label);
  }
  assert(!fclose(f));
}
static void lap(int car,int start) {
  G.menu.car=car;
  for(int n=0;n<100;n++) {
    G.menu.st_div=start+n/20; G.menu.story_n=n; story_race_commit(1,1);
    if(n==20) { G.menu.st_div_car[0][car]=start+1; story_load_all(); }
  }
  G.menu.st_div=start+5; G.menu.st_bits=0; G.menu.st_div_car[0][car]=start+5;
}
int main(void) {
  char dir[]="/tmp/story-app-XXXXXX"; assert(mkdtemp(dir));
  memset(&G,0,sizeof G);snprintf(G.save_dir,sizeof G.save_dir,"%s",dir);
  G.menu.save_slot=1; G.menu.own_sel=-1; G.menu.maker=0; G.menu.car=0;
  fixture_own_register(&G.menu); story_new_card_commit(); assert(story_ev[0][0].known_clean);
  G.menu.car=1; fixture_own_register(&G.menu); story_new_card_commit(); assert(story_ev[0][1].known_clean);
  assert(G.menu.n_own==2);
  /* Existing WCS2 bonus is not evidence of a confirmed story reward. */
  G.menu.st_bonus_car[0][1]=7; assert(cc_save(dir,1,&G.menu));
  char oldpath[1100]; assert(cc_path(oldpath,sizeof oldpath,dir,1,""));
  unsigned char before[CC_SIZE],after[CC_SIZE];
  FILE *old=fopen(oldpath,"rb"); assert(old && fread(before,1,sizeof before,old)==sizeof before); assert(!fclose(old));
  card_choice_load(); assert(G.menu.st_bonus_car[0][1]==0);
  lap(0,0); assert(G.menu.st_bonus_car[0][0]==0); /* pending is not a reward */
  garage_fixture(); story_verify_garage(); assert(G.menu.st_bonus_car[0][0]==7);
  /* Simulate a later division mismatch; old independent confirmation survives. */
  G.menu.st_div_car[0][0]=4; story_load_all();
  assert(G.menu.st_bonus_car[0][0]==7 && story_poison[1][0][0]);
  restart_process(); assert(G.menu.st_bonus_car[0][0]==7 && !story_ev[0][0].known_clean);
  G.menu.car=0; G.menu.st_div=4; G.menu.st_bits=0; story_verify_garage();
  assert(story_poison[1][0][0] && G.menu.st_bonus_car[0][0]==7);
  restart_process(); assert(G.menu.st_bonus_car[0][0]==7);
  /* The second car's pending ending must not leak across restart or cars. */
  lap(1,0); assert(G.menu.st_bonus_car[0][1]==0 && G.menu.st_bonus_car[0][0]==7);
  restart_process(); assert(G.menu.st_bonus_car[0][1]==0 && !story_ev[0][1].known_clean);
  /* Failure to persist a loss leaves an older clean SE01 on disk. */
  G.menu.car=1; G.menu.st_div=5; G.menu.story_n=0;
  char p[1100],backup[1200]; assert(story_path(p,sizeof p,0,1,cc_owner(&G.menu,0,1)));
  snprintf(backup,sizeof backup,"%s.old",p); assert(rename(p,backup)==0); assert(mkdir(p,0700)==0);
  story_race_commit(0,0); assert(story_poison[1][0][1]);
  assert(rmdir(p)==0); assert(rename(backup,p)==0);
  restart_process(); assert(!story_ev[0][1].known_clean);
  lap(1,5); garage_fixture(); story_verify_garage();
  assert(G.menu.st_bonus_car[0][1]==STORY_EVIDENCE_CLEAR);
  assert(G.menu.st_bonus_car[0][0]==7);
  /* A real, garage-verified ending creates a clean origin for the next loop. */
  lap(1,10); assert(G.menu.st_bonus_car[0][1]==STORY_EVIDENCE_CLEAR);
  garage_fixture(); story_verify_garage(); assert(G.menu.st_bonus_car[0][1]==7);
  restart_process(); assert(G.menu.st_bonus_car[0][0]==7 && G.menu.st_bonus_car[0][1]==7);
  old=fopen(oldpath,"rb"); assert(old && fread(after,1,sizeof after,old)==sizeof after);
  assert(fgetc(old)==EOF && !fclose(old) && !memcmp(before,after,sizeof before));
  puts("story app hooks passed"); return 0;
}
