/* Standalone synthetic WPK2 test: cc -std=c11 backfire_wpk.c backfire_wpk_test.c -lm */
#define _POSIX_C_SOURCE 200809L
#include "backfire_wpk.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include <unistd.h>
static void put32(unsigned char *p, unsigned x) { for(int i=0;i<4;i++) p[i]=(unsigned char)(x>>(8*i)); }
static int write_bytes(const char *path, const unsigned char *p, size_t n) { FILE *f=fopen(path,"wb"); if(!f)return -1; int ok=fwrite(p,1,n,f)==n; return fclose(f) || !ok ? -1:0; }
static int check(const char *path, unsigned char *p, size_t n, bfx_asset *a, int want) { return write_bytes(path,p,n) || ((bfx_wpk_validate(path,a)==0) != want); }
int main(void) {
  char path[]="/tmp/bfx_wpk_test_XXXXXX";
  int fd=mkstemp(path); if(fd < 0) return 1; close(fd);
  unsigned char d[256]={0}, orig[256];
  bfx_mesh mesh={0}; bfx_asset a={0}; a.nmesh=1; a.mesh=&mesh; mesh.group=7;
  memcpy(d,"WPK2",4); put32(d+4,1); put32(d+8,1); put32(d+12,1); put32(d+20,32); put32(d+24,96); put32(d+28,132);
  memcpy(d+32,"image_1",7); d[80]=1; d[82]=1; put32(d+88,152); put32(d+92,2);
  put32(d+120,0); put32(d+124,1); put32(d+128,7);
  d[132]=0; put32(d+136,156); put32(d+140,3); put32(d+144,228); put32(d+148,3);
  d[230]=1; d[232]=2; memcpy(orig,d,sizeof d);
  if(check(path,d,234,&a,1)) return 1;
#define BAD(expr) do { memcpy(d,orig,sizeof d); expr; if(check(path,d,234,&a,0)) return __LINE__; } while(0)
  BAD(d[0]='X'); BAD(put32(d+4,0xffffffffu)); BAD(put32(d+24,0xffffffffu));
  BAD(put32(d+88,0xffffffffu)); BAD(put32(d+92,1)); BAD(d[80]=0); BAD(put32(d+84,3));
  BAD(memset(d+38,'9',42)); BAD(put32(d+124,2)); BAD(put32(d+128,8));
  BAD(d[132]=255;d[133]=255); BAD(put32(d+136,232)); BAD(put32(d+140,65536));
  BAD(put32(d+144,233)); BAD(put32(d+148,4)); BAD(d[232]=3);
  BAD(put32(d+156,0x7fc00000)); BAD(memcpy(d+230,"GLS1",4));
  mesh.frame[0][0]=NAN; if(check(path,orig,234,&a,0)) return __LINE__;
  mesh.frame[0][0]=0; mesh.group=9; if(check(path,orig,234,&a,0)) return __LINE__;
  unlink(path); puts("synthetic validator tests passed"); return 0;
}
