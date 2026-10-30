#include <assert.h>
#include "../src/vkgl.c"
int main(void) {
  GLuint id=prog_gen(), va=vao_gen(); vprog *p=prog_get(id); assert(p);
  p->block=16; p->shadow=malloc(16); assert(p->shadow); memset(p->shadow,0x39,16); p->samp_unit[0]=5;
  ctx()->prog=7; ctx()->vao=va; ctx()->array_buf=18; ctx()->unit=3; ctx()->tex2d[0]=19;
  ctx()->blend=1; ctx()->depth_test=1; ctx()->bsrc=GL_ONE; ctx()->bdst=GL_ZERO;
  cur_vao(ctx())->a[0].enabled=1; cur_vao(ctx())->a[0].ptr=(void*)24;
  void *s=vkgl_preview_save(id); assert(s);
  ctx()->prog=id; ctx()->array_buf=55; ctx()->unit=0; ctx()->tex2d[0]=44; ctx()->blend=0;
  cur_vao(ctx())->a[0].enabled=0; cur_vao(ctx())->a[0].ptr=(void*)32;
  memset(p->shadow,0x82,16); p->samp_unit[0]=1; vkgl_preview_restore(s);
  assert(ctx()->prog==7 && ctx()->vao==va && ctx()->array_buf==18 && ctx()->unit==3);
  assert(ctx()->tex2d[0]==19 && ctx()->blend==1 && ctx()->depth_test==1);
  assert(cur_vao(ctx())->a[0].enabled==1 && cur_vao(ctx())->a[0].ptr==(void*)24);
  assert(p->shadow[0]==0x39 && p->samp_unit[0]==5 && p->dirty);
  assert(!vkgl_preview_save(0));
  ctx()->vao=0; ctx()->vao0.a[1].enabled=1; ctx()->vao0.a[1].ptr=(void*)48;
  s=vkgl_preview_save(id); assert(s); ctx()->vao0.a[1].enabled=0; ctx()->vao0.a[1].ptr=0;
  vkgl_preview_restore(s); assert(ctx()->vao0.a[1].enabled && ctx()->vao0.a[1].ptr==(void*)48);
  free(p->shadow); puts("vkgl preview snapshot state, VAO and uniforms: PASS"); return 0;
}
