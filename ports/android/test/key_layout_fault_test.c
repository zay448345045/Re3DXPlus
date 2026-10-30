#include <assert.h>
#include <errno.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
static int fault;
static int test_fflush(FILE *f) { if(fault==1) { errno=EIO; return EOF; } return fflush(f); }
static int test_fsync(int fd) { if(fault==2) { errno=EIO; return -1; } return fsync(fd); }
static int test_rename(const char *a,const char *b) { if(fault==3) { errno=EIO; return -1; } return rename(a,b); }
#define fflush test_fflush
#define fsync test_fsync
#define rename test_rename
#include "../src/app.c"
#undef fflush
#undef fsync
#undef rename
static void put(const char *p,const char *s) { FILE *f=fopen(p,"w"); assert(f); assert(fputs(s,f)>=0); assert(!fclose(f)); }
static void is(const char *p,const char *s) { char b[1024]; FILE *f=fopen(p,"r"); assert(f); size_t n=fread(b,1,sizeof(b)-1,f); assert(!ferror(f)); assert(!fclose(f)); b[n]=0; assert(!strcmp(b,s)); }
int main(void) {
 char dir[]="/tmp/wmmt-layout-fault-XXXXXX", opt[1200],side[1200]; assert(mkdtemp(dir));
 snprintf(G.save_dir,sizeof G.save_dir,"%s",dir); snprintf(opt,sizeof opt,"%s/option",dir); snprintf(side,sizeof side,"%s/key_layout",dir);
 const char *original="option 0 5 1 1 0 1 1 1 1 0 1 1 1 0\nkeys 110 -12 5 90 2 -3 160 44 55\n";
 const char *layout="key_layout 1 100 0 0 100 0 0 100 0 0\n";
 put(opt,original); put(side,layout);
 for(int k=0;k<3;k++) G.menu.key_k[k]=100; G.menu.key_k[0]=120; G.menu.key_layout_dirty=1;
 for(fault=1;fault<=3;fault++) { assert(!key_layout_save()); assert(G.menu.key_layout_dirty); is(side,layout); G.options_global=0; G.menu.gyro_sens=7; options_save(); is(opt,original); }
 fault=0; assert(key_layout_save()); is(side,"key_layout 1 120 0 0 100 0 0 100 0 0\n"); G.options_global=0; options_save();
 FILE *f=fopen(opt,"r"); assert(f); char b[1024]; assert(fgets(b,sizeof b,f)); assert(fgets(b,sizeof b,f)); assert(!strcmp(b,"keys 110 -12 5 90 2 -3 160 44 55\n")); assert(!fclose(f));
 assert(!unlink(side)); assert(!unlink(opt)); assert(!rmdir(dir)); puts("layout and option fault injection ok");
}
