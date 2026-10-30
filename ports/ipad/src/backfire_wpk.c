#include "backfire_wpk.h"
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static unsigned u16(const unsigned char *p) { return (unsigned)p[0] | (unsigned)p[1] << 8; }
static uint32_t u32(const unsigned char *p) {
  return (uint32_t)p[0] | (uint32_t)p[1] << 8 | (uint32_t)p[2] << 16 | (uint32_t)p[3] << 24;
}
static float f32(const unsigned char *p) { uint32_t n = u32(p); float f; memcpy(&f, &n, 4); return f; }
static int within(size_t off, size_t len, size_t size) { return off <= size && len <= size - off; }
static int finite_bound(float f) { return isfinite(f) && fabsf(f) <= 1e12f; }

int bfx_wpk_validate(const char *path, const bfx_asset *asset) {
  FILE *f = NULL;
  unsigned char *d = NULL;
  unsigned char *seen = NULL;
  size_t size, data;
  uint32_t nt, nc, nb, to, co, bo;
  int result = -1;
  if (!path || !asset || !asset->mesh || !asset->nmesh || asset->nmesh > BFX_MAX_MESH) return -1;
  for (unsigned i = 0; i < asset->nmesh; ++i) {
    if (!asset->mesh[i].group) return -1;
    for (unsigned j = 0; j < i; ++j) if (asset->mesh[i].group == asset->mesh[j].group) return -1;
    for (unsigned k = 0; k < BFX_FRAMES; ++k)
      for (unsigned j = 0; j < 16; ++j) if (!finite_bound(asset->mesh[i].frame[k][j])) return -1;
  }
  f = fopen(path, "rb");
  if (!f || fseek(f, 0, SEEK_END)) goto out;
  long end = ftell(f);
  if (end < 32 || (unsigned long)end > BFX_WPK_MAX_BYTES || fseek(f, 0, SEEK_SET)) goto out;
  size = (size_t)end;
  d = malloc(size);
  if (!d || fread(d, 1, size, f) != size) goto out;
  if (memcmp(d, "WPK2", 4) || !memcmp(d + size - 4, "GLS1", 4)) goto out;
  nt = u32(d+4); nc = u32(d+8); nb = u32(d+12);
  to = u32(d+20); co = u32(d+24); bo = u32(d+28);
  if (!nt || nt > BFX_WPK_MAX_TEXTURES || nc != asset->nmesh || nb != nc || f32(d+16) != 0.0f) goto out;
  /* The backfire packer emits these contiguous tables, one batch per group. */
  if (to != 32 || co != 32u + nt * 64u || bo != co + nc * 36u) goto out;
  data = (size_t)bo + (size_t)nb * 20u;
  if (data > size) goto out;
  for (uint32_t i = 0; i < nt; ++i) {
    const unsigned char *t = d + to + (size_t)i * 64;
    unsigned w = u16(t+48), h = u16(t+50);
    uint32_t fmt = u32(t+52), off = u32(t+56), len = u32(t+60);
    /* Generator uses image_<index>; this also excludes paint-name integer overflow. */
    if (memcmp(t, "image_", 6) || t[6] < '0' || t[6] > '9') goto out;
    unsigned j = 6;
    while (j < 48 && t[j] >= '0' && t[j] <= '9') ++j;
    if (j == 48 || t[j] != 0) goto out;
    if (!w || !h || w > BFX_WPK_MAX_TEXTURE_SIDE || h > BFX_WPK_MAX_TEXTURE_SIDE || fmt > 2 ||
        len != (uint32_t)w * h * 2u || off < data || (off & 3u) || !within(off, len, size)) goto out;
  }
  seen = calloc(nc, 1);
  if (!seen) goto out;
  uint32_t poolverts = 0, poolindices = 0;
  for (uint32_t i = 0; i < nc; ++i) {
    const unsigned char *c = d + co + (size_t)i * 36;
    const unsigned char *b = d + bo + (size_t)i * 20;
    uint32_t group = u32(c+32), match = nc;
    float lo[3], hi[3];
    for (int k = 0; k < 3; ++k) {
      lo[k] = f32(c+4*k); hi[k] = f32(c+12+4*k);
      if (!finite_bound(lo[k]) || !finite_bound(hi[k]) || lo[k] > hi[k]) goto out;
    }
    if (u32(c+24) != i || u32(c+28) != 1) goto out;
    for (uint32_t j = 0; j < nc; ++j) if (asset->mesh[j].group == group) { match = j; break; }
    if (match == nc || seen[match]) goto out;
    seen[match] = 1;
    unsigned tex = u16(b), flags = u16(b+2);
    uint32_t vo = u32(b+4), vn = u32(b+8), io = u32(b+12), in = u32(b+16);
    if (tex == 0xffffu || tex >= nt || flags > 2 || !vn || vn > BFX_WPK_MAX_VERTICES ||
        !in || in > BFX_WPK_MAX_INDICES || in % 3 || vo < data || io < data || (vo & 3u) || (io & 3u) ||
        !within(vo, (size_t)vn * 24u, size) || !within(io, (size_t)in * 2u, size)) goto out;
    if (poolverts + vn > 65536u) { poolverts = 0; poolindices = 0; }
    if (in > (UINT32_MAX / 2u) - poolindices) goto out;
    poolindices += in;
    for (uint32_t v = 0; v < vn; ++v) {
      const unsigned char *p = d + vo + (size_t)v * 24;
      for (int k = 0; k < 5; ++k) {
        float x = f32(p + 4*k);
        if (!finite_bound(x) || (k < 3 && (x < lo[k] || x > hi[k]))) goto out;
      }
    }
    for (uint32_t j = 0; j < in; ++j) {
      unsigned ix = u16(d + io + (size_t)j*2);
      if (ix >= vn || ix + poolverts > 65535u) goto out;
    }
    poolverts += vn;
  }
  result = 0;
out:
  free(seen); free(d); if (f) fclose(f); return result;
}
