/* Real menu and app; host resource availability stub, /tmp-only data. */
#include "../src/menu.c"
#include <assert.h>
#include <unistd.h>
#include <sys/wait.h>
menu_state *fixture_menu(void);
void fixture_load(void);
void app_save_dir(const char *);
static int resource = 1;
int hud_meter_available(void) { return resource; }
int android_bgm_group_available(int g) { return g==1 || g==2; }
static void setup(const char *dir) {
 menu_state *m=fixture_menu(); memset(m,0,sizeof *m); app_save_dir(dir);
 m->save_slot=1; m->n_own=2; m->own_sel=0; m->maker=0; m->car=0;
 m->own[0].maker=0; m->own[0].car=0; m->own[0].born=111;
 m->own[1].maker=0; m->own[1].car=1; m->own[1].born=222;
 fixture_load(); assert(!m->card_choice_error);
}
int main(int argc,char **argv) {
 if(argc==3) { setup(argv[2]); menu_state *m=fixture_menu();
  assert(menu_card_meter(m)==2 && m->card_born[0][0]==111);
  assert(!m->st_bonus_car[0][0] && !menu_card_choice_available(m,1,1) && !menu_card_choice_available(m,1,2));
  m->own_sel=1; m->car=1; assert(menu_card_meter(m)==1); puts("real fresh process reload PASS"); return 0; }
 char dir[]="/tmp/wmmt-real-choice-XXXXXX"; assert(mkdtemp(dir)); setup(dir); menu_state *m=fixture_menu();
 assert(menu_card_choice_available(m,0,0) && menu_card_choice_available(m,0,1) && menu_card_choice_available(m,0,2));
 assert(menu_card_choice_set(m,0,2) && menu_card_meter(m)==2 && !m->st_bonus_car[0][0]);
 assert(!menu_card_choice_set(m,1,1) && !menu_card_choice_set(m,1,2));
 resource=0; assert(menu_card_meter(m)==0 && m->meter_car[0][0]==2); resource=1; assert(menu_card_meter(m)==2);
 m->own_sel=1; m->car=1; assert(menu_card_meter(m)==0 && menu_card_choice_set(m,0,1));
 m->own_sel=0; m->car=0; assert(menu_card_meter(m)==2);
 pid_t pid=fork(); assert(pid>=0); if(!pid) { execl(argv[0],argv[0],"reload",dir,(char*)0); _exit(127); }
 int status; assert(waitpid(pid,&status,0)==pid && WIFEXITED(status) && WEXITSTATUS(status)==0);
 m->own[0].born=333; assert(menu_card_meter(m)==0); assert(menu_card_choice_set(m,0,1)); assert(m->card_born[0][0]==333);
 m->own[0].born=111; assert(menu_card_meter(m)==0); m->own[0].born=333;
 char absent[1100]; snprintf(absent,sizeof absent,"%s/missing",dir); app_save_dir(absent);
 assert(!menu_card_choice_set(m,0,2) && m->card_save_failed && m->meter_car[0][0]==1 && m->card_born[0][0]==333);
 app_save_dir(dir); char path[1100]; snprintf(path,sizeof path,"%s/card-choices-v2-1",dir);
 FILE *f=fopen(path,"wb"); assert(f && fwrite("bad",1,3,f)==3 && !fclose(f));
 assert(!menu_card_choice_set(m,0,2) && m->meter_car[0][0]==1 && m->card_born[0][0]==333);
 f=fopen(path,"rb"); char b[4]={0}; assert(f && fread(b,1,3,f)==3 && !memcmp(b,"bad",3) && !fclose(f));
 assert(!unlink(path) && !rmdir(dir)); puts("real menu/app integration PASS"); return 0;
}
