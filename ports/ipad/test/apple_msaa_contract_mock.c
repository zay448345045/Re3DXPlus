/* Standalone APPLE MSAA contract model, not a GL implementation or device probe.
 * Host: cc -std=c99 -Wall -Wextra -Werror test/apple_msaa_contract_mock.c -o /tmp/apple_msaa_contract_mock && /tmp/apple_msaa_contract_mock
 * iOS: xcrun --sdk iphoneos clang -std=c99 -Wall -Wextra -Werror -c test/apple_msaa_contract_mock.c -o apple_msaa_contract_mock.o
 * Integration adapter must map callbacks to ES2 APPLE entrypoints and preserve GL state.
 */
#include <assert.h>
#include <stdio.h>
#include <string.h>
typedef struct { unsigned fbo,color,depth; int w,h,samples; } Target;
typedef struct Backend Backend;
struct Backend {
 void *ctx; int (*max_samples)(void *); unsigned (*create_fbo)(void *); unsigned (*create_rb)(void *);
 int (*allocate)(void *,unsigned,int,int,int,int); /* 1 RGBA8, 2 DEPTH24_STENCIL8 */
 int (*samples)(void *,unsigned);
 int (*complete)(void *,const Target *); /* attach both, check FBO status AND errors */
 int (*resolve)(void *,unsigned,unsigned); /* bind READ first, DRAW second, resolve, check error */
 void (*delete_fbo)(void *,unsigned); void (*delete_rb)(void *,unsigned);
};
static int has_token(const char *list,const char *token) {
 size_t n=strlen(token); const char *p=list;
 if (!p || !*token || strchr(token,' ')) return 0;
 while (*p) { const char *start; while (*p==' ') ++p; start=p; while (*p && *p!=' ') ++p;
  if ((size_t)(p-start)==n && !memcmp(start,token,n)) return 1; }
 return 0;
}
static void discard(Backend *b,Target *t) {
 if(t->fbo) b->delete_fbo(b->ctx,t->fbo);
 if(t->color) b->delete_rb(b->ctx,t->color);
 if(t->depth) b->delete_rb(b->ctx,t->depth);
 memset(t,0,sizeof(*t));
}
/* Transactional candidate; existing destination remains owned by caller. */
static int make_target(Backend *b,const char *ext,int w,int h,Target *out) {
 int counts[]={4,2}; unsigned i; memset(out,0,sizeof(*out));
 if(w<=0 || h<=0 || !has_token(ext,"GL_APPLE_framebuffer_multisample")) return 0;
 for(i=0;i<2;i++) {
  Target t={0}; int n=counts[i]; if(b->max_samples(b->ctx)<n) continue;
  t.w=w; t.h=h; t.samples=n; t.fbo=b->create_fbo(b->ctx); t.color=b->create_rb(b->ctx); t.depth=b->create_rb(b->ctx);
  if(t.fbo && t.color && t.depth && b->allocate(b->ctx,t.color,1,n,w,h) && b->samples(b->ctx,t.color)==n &&
     b->allocate(b->ctx,t.depth,2,n,w,h) && b->samples(b->ctx,t.depth)==n && b->complete(b->ctx,&t)) { *out=t; return n; }
  discard(b,&t);
 }
 return 0; /* fallback to caller's existing single-sample target */
}
static int resolve_target(Backend *b,const Target *src,const Target *dst) {
 if(!src || !dst || !src->fbo || !dst->fbo || src->samples<2 || dst->samples!=1 ||
 src->w<=0 || src->h<=0 || src->w!=dst->w || src->h!=dst->h || src->fbo==dst->fbo) return 0;
 return b->resolve(b->ctx,src->fbo,dst->fbo);
}
typedef struct { unsigned next,old,read,draw; int max,fail4,fail2,bad_color,bad_depth,fail_complete,resolve_error,calls,allocs,live[256],count; int actual[256]; } Mock;
static int mx(void *v){return ((Mock*)v)->max;}
static unsigned gen(void *v){Mock*m=v; unsigned id=++m->next; assert(id<256); m->live[id]=1; m->count++; return id;}
static int alloc(void *v,unsigned id,int fmt,int n,int w,int h){Mock*m=v; assert(m->live[id] && w>0 && h>0); m->allocs++; if((n==4&&m->fail4)||(n==2&&m->fail2))return 0; m->actual[id]=((fmt==1&&m->bad_color)||(fmt==2&&m->bad_depth))?n-1:n; return 1;}
static int samples(void*v,unsigned id){return ((Mock*)v)->actual[id];}
static int complete(void*v,const Target*t){Mock*m=v; assert(m->live[t->fbo]&&m->live[t->color]&&m->live[t->depth]); return !m->fail_complete;}
static int res(void*v,unsigned r,unsigned d){Mock*m=v; m->calls++; m->read=r; m->draw=d; return !m->resolve_error;}
static void del(void*v,unsigned id){Mock*m=v; assert(id!=m->old && id<256 && m->live[id]); m->live[id]=0; m->count--;}
static Backend backend(Mock*m){Backend b={m,mx,gen,gen,alloc,samples,complete,res,del,del};return b;}
static Mock init(void){Mock m={0};m.max=4;m.next=10;m.old=7;return m;}
int main(void){
 const char *ext="GL_EXT_a GL_APPLE_framebuffer_multisample GL_EXT_b"; Mock m; Backend b; Target t,d={7,0,0,640,480,1};
 assert(has_token(ext,"GL_APPLE_framebuffer_multisample"));
 assert(!has_token("GL_APPLE_framebuffer_multisample_extra","GL_APPLE_framebuffer_multisample"));
 assert(!has_token("xGL_APPLE_framebuffer_multisample","GL_APPLE_framebuffer_multisample"));
 assert(!has_token(NULL,"GL_APPLE_framebuffer_multisample"));
 m=init();b=backend(&m);assert(!make_target(&b,"GL_APPLE_framebuffer_multisample_extra",640,480,&t)&&!m.count&&!m.allocs);
 assert(!make_target(&b,"GL_EXT_other",640,480,&t)&&!m.count);
 m.max=1;assert(!make_target(&b,ext,640,480,&t)&&!m.count);
 m.max=2;assert(make_target(&b,ext,640,480,&t)==2&&m.count==3);discard(&b,&t);assert(!m.count);
 m=init();m.fail4=1;b=backend(&m);assert(make_target(&b,ext,640,480,&t)==2&&m.count==3);discard(&b,&t);assert(!m.count);
 m=init();m.bad_color=1;b=backend(&m);assert(!make_target(&b,ext,640,480,&t)&&!m.count);
 m=init();m.bad_depth=1;b=backend(&m);assert(!make_target(&b,ext,640,480,&t)&&!m.count);
 m=init();m.fail_complete=1;b=backend(&m);assert(!make_target(&b,ext,640,480,&t)&&!m.count);
 m=init();m.fail4=m.fail2=1;b=backend(&m);assert(!make_target(&b,ext,640,480,&t)&&!m.count);
 m=init();b=backend(&m);assert(make_target(&b,ext,640,480,&t)==4);assert(resolve_target(&b,&t,&d));assert(m.read==t.fbo&&m.draw==d.fbo&&m.calls==1);
 d.w++;assert(!resolve_target(&b,&t,&d)&&m.calls==1);d.w--;
 m.resolve_error=1;assert(!resolve_target(&b,&t,&d)&&m.calls==2);assert(m.count==3);discard(&b,&t);assert(!m.count);
 puts("APPLE MSAA mock contract: PASS (device support not tested)");return 0;
}
