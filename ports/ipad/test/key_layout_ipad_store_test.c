/* Production persistence exercised only in a disposable directory. */
#include <TargetConditionals.h>
#undef TARGET_OS_IPHONE
#define TARGET_OS_IPHONE 1
#include <OpenGL/gl3.h>
#define WMMT_GL_H
GLuint gl_compile_program(const char *, const char *, const char **, int);
#include <unistd.h>
static int fail_sync;
static int test_fsync(int fd) { return fail_sync ? -1 : fsync(fd); }
#define fsync test_fsync
#include "../src/app.c"
#undef fsync
#include <assert.h>
static void put(const char *p, const char *s) { FILE *f=fopen(p,"w"); assert(f); assert(fputs(s,f)>=0); assert(!fclose(f)); }
static void defaults(void) { for(int g=0;g<3;g++) G.menu.key_k[g]=100,G.menu.key_dx[g]=G.menu.key_dy[g]=0; }
int main(void) {
  char dir[]="/tmp/ipad-key-layout-XXXXXX", path[1200], opt[1200], line[512];
  assert(mkdtemp(dir)); app_save_dir(dir); snprintf(path,sizeof path,"%s/key_layout",dir); snprintf(opt,sizeof opt,"%s/option",dir);
  put(opt,"option 0 5 1\nkeys 120 1 -2 90 3 4 160 -5 6\n"); defaults(); key_layout_load();
  assert(G.menu.key_k[0]==120 && G.menu.key_dy[2]==6 && access(path,F_OK)!=0);
  options_save(); defaults(); key_layout_load(); assert(G.menu.key_k[0]==120 && access(path,F_OK)!=0);
  put(path,"key_layout 1 120 1 -2 90 3 4 161 -5 6\n"); defaults(); key_layout_load(); assert(G.menu.key_k[0]==100);
  FILE *f=fopen(path,"r"); assert(f && fgets(line,sizeof line,f)); fclose(f); assert(strstr(line,"161"));
  G.menu.key_k[0]=60; G.menu.key_dx[0]=-11; assert(key_layout_save()); defaults(); key_layout_load(); assert(G.menu.key_k[0]==60 && G.menu.key_dx[0]==-11);
  f=fopen(path,"r"); assert(f && fgets(line,sizeof line,f)); fclose(f); assert(!strcmp(line,"key_layout 1 60 -11 0 100 0 0 100 0 0\n"));
  G.menu.key_layout_dirty=1; G.menu.key_k[0]=80; fail_sync=1; assert(!key_layout_save() && G.menu.key_layout_dirty); fail_sync=0;
  f=fopen(path,"r"); assert(f && fgets(line,sizeof line,f)); fclose(f); assert(!strcmp(line,"key_layout 1 60 -11 0 100 0 0 100 0 0\n"));
  int values[9]; assert(!key_layout_parse("key_layout 1 100  0 0 100 0 0 100 0 0\n","key_layout 1",values));
  assert(!key_layout_parse("key_layout 1 100 0 0 100 0 0 100 0 0 extra\n","key_layout 1",values));
  const char *extreme="key_layout 1 160 -2000 2000 160 2000 -2000 160 -2000 2000\n";
  put(path,extreme); G.menu.key_layout_dirty=0;
  for (int edge=0; edge<=100; edge+=100) {
    hud_wide((float)edge,1); defaults(); key_layout_load(); key_layout_clamp_loaded();
    for(int g=0;g<3;g++) {
      float x=G.menu.key_dx[g], y=G.menu.key_dy[g], ox=x, oy=y;
      hud_layout_clamp(g,G.menu.gyro,G.menu.key_k[g]*0.01f,&x,&y);
      assert(x==ox && y==oy);
    }
    assert(!G.menu.key_layout_dirty);
  }
  f=fopen(path,"r"); assert(f && fgets(line,sizeof line,f)); fclose(f); assert(!strcmp(line,extreme));
  char original[1024]; strcpy(original,G.save_dir); snprintf(G.save_dir,sizeof G.save_dir,"%s/missing",dir); assert(!key_layout_save()); strcpy(G.save_dir,original);
  assert(!unlink(path)); assert(!unlink(opt)); assert(!rmdir(dir)); puts("iPad key layout persistence PASS");
}
