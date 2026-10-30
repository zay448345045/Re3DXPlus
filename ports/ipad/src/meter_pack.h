/* Strict, allocation-bounded meter index reader. No globals mutated on failure. */
#ifndef METER_PACK_H
#define METER_PACK_H
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#define MP_CARS 55
#define MP_PARTS 9
#define MP_ZONES 6
#define MP_LIMIT 8192
#define MP_FILE_LIMIT (256L*1024*1024)
typedef struct { uint32_t w,h,offset; } mp_sprite;
typedef struct { int zones; unsigned sprites; uint16_t indices[MP_CARS][MP_ZONES][MP_PARTS]; mp_sprite *table; } meter_pack;
static uint16_t mp_u16(const unsigned char *p) { return (uint16_t)(p[0] | (unsigned)p[1]<<8); }
static uint32_t mp_u32(const unsigned char *p) { return (uint32_t)p[0] | (uint32_t)p[1]<<8 | (uint32_t)p[2]<<16 | (uint32_t)p[3]<<24; }
static void mp_clear(meter_pack *p) { free(p->table); memset(p,0,sizeof *p); }
/* counts indexed [car][zone]. Legacy readers pass counts for the first two zones. */
static int mp_read(const char *path, int extended, const unsigned char counts[MP_CARS][MP_ZONES], meter_pack *out) {
  FILE *f=NULL; meter_pack q; unsigned char h[24], b[12]; long length; size_t head, indexlen, base; unsigned cars,n,zones; uint64_t next;
  memset(&q,0,sizeof q); memset(q.indices,0xff,sizeof q.indices);
  f=fopen(path,"rb"); if (!f) return 0;
  if (fseek(f,0,SEEK_END) || (length=ftell(f)) < 0 || length>MP_FILE_LIMIT || fseek(f,0,SEEK_SET)) goto fail;
  head=extended?24:12; if (fread(h,1,head,f)!=head) goto fail;
  if (extended) { if(memcmp(h,"WMS2",4) || mp_u32(h+4)!=1 || mp_u32(h+12)!=MP_ZONES || mp_u32(h+16)!=MP_PARTS) goto fail; cars=mp_u32(h+8); n=mp_u32(h+20); zones=MP_ZONES; }
  else { if(memcmp(h,"WMT1",4)) goto fail; cars=mp_u32(h+4); n=mp_u32(h+8); zones=2; }
  if(cars!=MP_CARS || !n || n>MP_LIMIT) goto fail;
  indexlen=(size_t)cars*zones*MP_PARTS*2; base=head+indexlen+(size_t)n*12;
  if(base>(size_t)length) goto fail;
  for(unsigned c=0;c<cars;c++) for(unsigned z=0;z<zones;z++) for(unsigned i=0;i<MP_PARTS;i++) {
    if(fread(b,1,2,f)!=2 || counts[c][z]>MP_PARTS) goto fail;
    unsigned v=mp_u16(b); if(i<counts[c][z] ? v>=n : v!=65535) goto fail;
    q.indices[c][z][i]=(uint16_t)v;
  }
  q.table=(mp_sprite*)calloc(n,sizeof *q.table); if(!q.table) goto fail;
  next=base;
  for(unsigned i=0;i<n;i++) {
    if(fread(b,1,12,f)!=12) goto fail;
    uint32_t w=mp_u32(b),hh=mp_u32(b+4),off=mp_u32(b+8);
    if(!w || !hh || w>4096 || hh>4096 || off!=next) goto fail;
    next+=(uint64_t)w*hh*4; if(next>(uint64_t)length) goto fail;
    q.table[i]=(mp_sprite){w,hh,off};
  }
  if(next!=(uint64_t)length) goto fail;
  q.zones=zones; q.sprites=n; fclose(f); *out=q; return 1;
fail:
  free(q.table); fclose(f); return 0;
}
#endif
