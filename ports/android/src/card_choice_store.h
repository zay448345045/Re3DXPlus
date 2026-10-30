/* Isolated per-slot card selections. Reject unknown/corrupt sidecars; never rewrite garage. */
#ifndef CARD_CHOICE_STORE_H
#define CARD_CHOICE_STORE_H
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <errno.h>
#include <fcntl.h>
#include <sys/stat.h>
#include "menu.h"
#include "cardb.h"
#define CC_SIZE (16 + MENU_GARAGE_MAKERS * MENU_GARAGE_CARS * 11 + 4)
static uint32_t cc_hash(const unsigned char *p, size_t n) { uint32_t h=2166136261u; while(n--) h=(h^*p++)*16777619u; return h; }
static void cc_put(unsigned char *p,uint32_t n) { for(int i=0;i<4;i++) p[i]=(unsigned char)(n>>(8*i)); }
static uint32_t cc_get(const unsigned char *p) { return (uint32_t)p[0]|(uint32_t)p[1]<<8|(uint32_t)p[2]<<16|(uint32_t)p[3]<<24; }
static uint32_t cc_catalog(void) {
  uint32_t h=2166136261u;
  for(int mk=0;mk<MENU_GARAGE_MAKERS;mk++) {
    h=(h^(unsigned)CARDB_NCARS[mk])*16777619u;
    for(int c=0;c<CARDB_NCARS[mk];c++) { const unsigned char *s=(const unsigned char *)CARDB_CARS[mk][c].label; while(*s) h=(h^*s++)*16777619u; h=(h^0xffu)*16777619u; }
  } return h;
}
static int cc_path(char *p,size_t n,const char *dir,int slot,const char *suffix) {
  int k;if(slot<1||slot>MENU_SAVES)return 0; k=snprintf(p,n,"%s/card-choices-v2-%d%s",dir,slot,suffix);return k>=0&&(size_t)k<n;
}
static uint64_t cc_u64(const unsigned char *p) { uint64_t n=0;for(int i=0;i<8;i++)n|=(uint64_t)p[i]<<(8*i);return n; }
static void cc_put64(unsigned char *p,uint64_t n) { for(int i=0;i<8;i++)p[i]=(unsigned char)(n>>(8*i)); }
static long long cc_owner(const menu_state *m,int mk,int c) {
  int n=m->n_own<0?0:m->n_own>MENU_OWN_MAX?MENU_OWN_MAX:m->n_own;
  for(int i=0;i<n;i++)if(m->own[i].maker==mk && m->own[i].car==c && m->own[i].born>0)return m->own[i].born;
  return 0;
}
static int cc_decode(const unsigned char *b,menu_state *m) {
  if(memcmp(b,"WCS2",4)||cc_get(b+4)!=2||cc_get(b+8)!=cc_catalog()||cc_get(b+12)!=CC_SIZE||cc_get(b+CC_SIZE-4)!=cc_hash(b,CC_SIZE-4))return 0;
  size_t k=16;for(int mk=0;mk<MENU_GARAGE_MAKERS;mk++)for(int c=0;c<MENU_GARAGE_CARS;c++) {
    uint64_t born=cc_u64(b+k+3);if(b[k]>2||b[k+1]>2||b[k+2]>15||born>INT64_MAX || (!born && (b[k]||b[k+1]||b[k+2])))return 0;k+=11;
  }
  k=16;for(int mk=0;mk<MENU_GARAGE_MAKERS;mk++)for(int c=0;c<MENU_GARAGE_CARS;c++) {
    uint64_t born=cc_u64(b+k+3);if(born && born==(uint64_t)cc_owner(m,mk,c)) {
      m->meter_car[mk][c]=(signed char)b[k];m->sound_car[mk][c]=(signed char)b[k+1];m->st_bonus_car[mk][c]=b[k+2];m->card_born[mk][c]=(long long)born;
    } k+=11;
  }
  return 1;
}
/* 1=loaded, 0=absent, -1=invalid or I/O error. Invalid files must not be overwritten. */
static int cc_load(const char *dir,int slot,menu_state *m) {
  char path[1100];unsigned char b[CC_SIZE];if(!cc_path(path,sizeof path,dir,slot,""))return -1;
  int fd=open(path,O_RDONLY|O_NOFOLLOW|O_NONBLOCK);if(fd<0)return errno==ENOENT?0:-1;
  struct stat st;if(fstat(fd,&st)||!S_ISREG(st.st_mode)){close(fd);return -1;}
  FILE *f=fdopen(fd,"rb");if(!f){close(fd);return -1;}
  size_t n=fread(b,1,sizeof b,f);int extra=fgetc(f),err=ferror(f);if(fclose(f))err=1;
  if(n!=sizeof b||extra!=EOF||err)return -1;
  return cc_decode(b,m)?1:-1;
}
static int cc_save(const char *dir,int slot,const menu_state *m) {
  char path[1100],tmp[1100];unsigned char b[CC_SIZE],verify[CC_SIZE];
  menu_state old = {0};
  if(cc_load(dir,slot,&old)<0)return 0;
  if(!cc_path(path,sizeof path,dir,slot,"")||!cc_path(tmp,sizeof tmp,dir,slot,".tmp.XXXXXX"))return 0;
  memcpy(b,"WCS2",4);cc_put(b+4,2);cc_put(b+8,cc_catalog());cc_put(b+12,CC_SIZE);size_t k=16;
  for(int mk=0;mk<MENU_GARAGE_MAKERS;mk++)for(int c=0;c<MENU_GARAGE_CARS;c++) {
    long long born=cc_owner(m,mk,c);if(born!=m->card_born[mk][c])born=0;
    int a=born?m->meter_car[mk][c]:0,s=born?m->sound_car[mk][c]:0,u=born?m->st_bonus_car[mk][c]:0;if(a<0||a>2||s<0||s>2||u>15)return 0;
    b[k++]=(unsigned char)a;b[k++]=(unsigned char)s;b[k++]=(unsigned char)u;cc_put64(b+k,(uint64_t)born);k+=8;
  }
  cc_put(b+CC_SIZE-4,cc_hash(b,CC_SIZE-4));
  int fd=mkstemp(tmp);if(fd<0)return 0;FILE *f=fdopen(fd,"w+b");if(!f){close(fd);unlink(tmp);return 0;}
  int ok=fwrite(b,1,sizeof b,f)==sizeof b && fflush(f)==0 && fsync(fd)==0 && fseek(f,0,SEEK_SET)==0 && fread(verify,1,sizeof verify,f)==sizeof verify && !memcmp(verify,b,sizeof b);
  if(fclose(f))ok=0;if(ok && rename(tmp,path))ok=0;if(!ok)unlink(tmp);return ok;
}
#endif
