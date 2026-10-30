#include "../src/card_choice_store.h"
#include <assert.h>
int main(void) {
 char dir[]="/private/tmp/wmmt-card-choice-XXXXXX",path[1100];
 assert(mkdtemp(dir)); menu_state a={0},b={0};
 assert(cc_load(dir,1,&b)==0);a.n_own=b.n_own=1; a.own[0].maker=b.own[0].maker=1; a.own[0].car=b.own[0].car=2; a.own[0].born=b.own[0].born=1234; a.card_born[1][2]=1234; a.manual=1;a.meter_car[1][2]=1;a.sound_car[1][2]=2;a.st_bonus_car[1][2]=7;
 assert(cc_save(dir,1,&a));b.manual=1;assert(cc_load(dir,1,&b)==1);
 assert(b.manual==1 && b.meter_car[1][2]==1 && b.sound_car[1][2]==2 && b.st_bonus_car[1][2]==7);
 menu_state replacement={0};replacement.n_own=1;replacement.own[0].maker=1;replacement.own[0].car=2;replacement.own[0].born=9999;assert(cc_load(dir,1,&replacement)==1 && replacement.meter_car[1][2]==0 && replacement.st_bonus_car[1][2]==0);
 assert(cc_path(path,sizeof path,dir,1,""));FILE *f=fopen(path,"r+b");assert(f);assert(fseek(f,4,SEEK_SET)==0);assert(fputc(99,f)!=EOF);assert(fclose(f)==0);
 b.meter_car[1][2]=2;assert(cc_load(dir,1,&b)==-1 && b.meter_car[1][2]==2);assert(!cc_save(dir,1,&a));
 f=fopen(path,"rb");assert(f);assert(fseek(f,4,SEEK_SET)==0);assert(fgetc(f)==99);fclose(f);puts("PASS sidecar missing, roundtrip, preserve unrelated state, corrupt rejection, no overwrite");return 0;
}
