#ifndef STORY_EVIDENCE_STORE_H
#define STORY_EVIDENCE_STORE_H
/* Independent per-car story-evidence sidecar. The app supplies an
 * identity-bearing filename and applies a candidate only after se_save succeeds. */
#include "story_evidence.h"
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <errno.h>
#include <unistd.h>
#include <fcntl.h>
#include <sys/stat.h>
static uint32_t se_hash(const unsigned char *b, size_t n) {
  uint32_t h=2166136261u; while(n--) h=(h^*b++)*16777619u; return h;
}
static void se_put(unsigned char *b,uint32_t x) {
  for(int i=0;i<4;i++) b[i]=(unsigned char)(x>>(8*i));
}
static uint32_t se_get(const unsigned char *b) {
  return (uint32_t)b[0]|(uint32_t)b[1]<<8|(uint32_t)b[2]<<16|(uint32_t)b[3]<<24;
}
/* Missing=0, loaded=1, invalid or inaccessible=-1. Path is supplied by the
 * caller, which must bind it unambiguously to slot, car and card incarnation. */
static int se_load(const char *path, story_evidence *s) {
  unsigned char b[20];
  int fd=open(path,O_RDONLY|O_NOFOLLOW|O_NONBLOCK);
  if(fd<0) return errno==ENOENT?0:-1;
  struct stat st;
  if(fstat(fd,&st)||!S_ISREG(st.st_mode)) { close(fd); return -1; }
  FILE *f=fdopen(fd,"rb"); if(!f) {close(fd);return -1;}
  size_t n=fread(b,1,sizeof b,f); int extra=fgetc(f), err=ferror(f);
  if(fclose(f))err=1;
  if(n!=sizeof b||extra!=EOF||err||memcmp(b,"SE01",4)||
     se_get(b+16)!=se_hash(b,16)||se_get(b+4)>0x1391||
     se_get(b+8)>1||se_get(b+12)>15)return -1;
  s->expected_div=(int)se_get(b+4);s->known_clean=(int)se_get(b+8);
  s->flags=se_get(b+12);return 1;
}
static int se_save(const char *path,const story_evidence *s) {
  unsigned char b[20]; char tmp[1200];
  if(!path||!s||s->expected_div<0||s->expected_div>0x1391||
     s->known_clean<0||s->known_clean>1||s->flags>15)return 0;
  story_evidence previous; if(se_load(path,&previous)<0)return 0;
  int len=snprintf(tmp,sizeof tmp,"%s.tmp.XXXXXX",path);
  if(len<0||(size_t)len>=sizeof tmp)return 0;
  memcpy(b,"SE01",4);se_put(b+4,(uint32_t)s->expected_div);
  se_put(b+8,(uint32_t)s->known_clean);se_put(b+12,s->flags);se_put(b+16,se_hash(b,16));
  int fd=mkstemp(tmp);if(fd<0)return 0;
  FILE *f=fdopen(fd,"wb");if(!f){close(fd);unlink(tmp);return 0;}
  int ok=fwrite(b,1,sizeof b,f)==sizeof b && fflush(f)==0 && fsync(fd)==0;
  if(fclose(f))ok=0;
  if(ok && rename(tmp,path))ok=0;
  if(!ok)unlink(tmp);
  return ok;
}
#endif
