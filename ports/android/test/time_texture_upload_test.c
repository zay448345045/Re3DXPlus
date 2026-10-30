/* Exercises actual texture() upload with GL replaced by a byte capture. */
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#define GL_FUNC_ADD 0x8006
#define GL_FUNC_REVERSE_SUBTRACT 0x800B
void glBlendEquation(unsigned int);
#include "../src/anm.c"
static unsigned char uploaded[8192];
static int calls;
void glGenTextures(GLsizei n, GLuint *p) { (void)n; *p = 1; }
void glBindTexture(GLenum a, GLuint b) { (void)a; (void)b; }
void glTexParameteri(GLenum a, GLenum b, GLint c) { (void)a;(void)b;(void)c; }
void glTexImage2D(GLenum a, GLint b, GLint c, GLsizei w, GLsizei h, GLint d, GLenum e, GLenum f, const void *p) {
  (void)a;(void)b;(void)c;(void)d;(void)e;(void)f;
  assert(w == 64 && h == 32); memcpy(uploaded, p, sizeof uploaded); calls++;
}
int main(int argc, char **argv) {
  assert(argc == 3); unsigned char expected[8192], packed[8192];
  FILE *source = fopen(argv[1], "rb"), *data = fopen(argv[2], "rb");
  assert(source && data && fread(expected, 1, sizeof expected, source) == sizeof expected);
  assert(fread(packed, 1, sizeof packed, data) == sizeof packed);
  fclose(source); rewind(data);
  GLuint tex[1]={0}; long offset[1]={0}; uint32_t zsize[1]={0}, used[1]={0};
  float size[1][2]={{64,32}}; int ids[1]={1573}; uint16_t cols[1][2]={{0,0}};
  A.tex=tex; A.offset=offset; A.zsize=zsize; A.used=used; A.size=size; A.ids=ids; A.cols=cols;
  A.base_sprites=1; A.file=data; A.nsprites=1;
  assert(texture(0)==1 && calls==1 && !memcmp(uploaded,expected,sizeof expected));
  tex[0]=0; ids[0]=1574; assert(texture(0)==1 && calls==2 && !memcmp(uploaded,packed,sizeof packed));
  tex[0]=0; ids[0]=1573; A.base_sprites=0; A.extra_file=data;
  assert(texture(0)==1 && calls==3 && !memcmp(uploaded,packed,sizeof packed));
  tex[0]=0; A.base_sprites=1; A.file=NULL; assert(texture(0)==0 && calls==3);
  tex[0]=0; A.file=data; offset[0]=99999; assert(texture(0)==0 && calls==3);
  fclose(data); puts("texture upload RGBA, other ID, sidecar, missing/truncated data: OK");
}
