#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include "../src/app.c"
static void defaults(void) { for(int i=0;i<3;i++) G.menu.key_k[i]=100,G.menu.key_dx[i]=G.menu.key_dy[i]=0; }
static void put(const char *p,const char *s) { FILE *f=fopen(p,"w"); assert(f); assert(fputs(s,f)>=0); assert(!fclose(f)); }
int main(void) {
 char dir[]="/tmp/wmmt-layout-test-XXXXXX", opt[1200],side[1200]; assert(mkdtemp(dir));
 snprintf(G.save_dir,sizeof G.save_dir,"%s",dir); snprintf(opt,sizeof opt,"%s/option",dir); snprintf(side,sizeof side,"%s/key_layout",dir);
 put(opt,"option 0 5 1 1 0 1 1 1 1 0 1 1 1 0\nkeys 110 -12 5 90 2 -3 160 44 55\n");
 defaults(); key_layout_load(); assert(G.menu.key_k[0]==110 && G.menu.key_dx[0]==-12 && G.menu.key_k[2]==160); assert(access(side,F_OK));
 G.menu.gyro_sens=7; options_save(); defaults(); key_layout_load(); assert(G.menu.key_k[0]==110 && G.menu.key_k[2]==160); assert(access(side,F_OK));
 put(side,"key_layout 1 120 0 0 100 0 0 100 0 0 extra\n"); defaults(); key_layout_load(); assert(G.menu.key_k[0]==100);
 put(side,"key_layout 1 161 0 0 100 0 0 100 0 0\n"); defaults(); key_layout_load(); assert(G.menu.key_k[0]==100);
 const char *extreme="key_layout 1 160 2000 -2000 100 -2000 2000 100 2000 2000\n";
 put(side,extreme); for(int wide=0;wide<2;wide++) { hud_wide(wide ? 200 : 0,wide ? 1.2f : 1.0f); defaults(); assert(key_layout_load()); G.menu.gyro=wide; G.menu.key_layout_dirty=0; key_layout_clamp_visible(); assert(G.menu.key_dx[0]!=2000 && G.menu.key_dx[1]!=-2000 && G.menu.key_dy[2]!=2000 && !G.menu.key_layout_dirty); char buf[256]; FILE *f=fopen(side,"r"); assert(f && fgets(buf,sizeof buf,f)); fclose(f); assert(!strcmp(buf,extreme)); }
 G.menu.key_k[0]=130; G.menu.key_dx[2]=-27; assert(key_layout_save()); defaults(); key_layout_load(); assert(G.menu.key_k[0]==130 && G.menu.key_dx[2]==-27);
 /* Oversized preexisting options are never truncated or rewritten. */
 FILE *big=fopen(opt,"wb"); assert(big); for(int i=0;i<65537;i++) assert(fputc('X',big)!=EOF); assert(!fclose(big)); G.menu.gyro_sens=9; options_save(); struct stat st; assert(!stat(opt,&st) && st.st_size==65537);
 snprintf(G.save_dir,sizeof G.save_dir,"%s/no-dir",dir); assert(!key_layout_save());
 assert(!unlink(side)); assert(!unlink(opt)); assert(!rmdir(dir)); puts("key layout store ok");
}
