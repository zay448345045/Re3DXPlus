#!/usr/bin/env python3
"""Compile both ports' verbatim HUD map code against a mock GLES.

Run: python3 tools/navi_mock_dynamic_test.py
Set NAVI_TEST_INPUT to a directory with android/ and ipad/ WNV1 files.
Inputs are never modified; symlinks and a minimal HUD pack live in a temp root.
This verifies call/resource behavior, not real GPU output or rendering visibility.
"""
import pathlib,tempfile,subprocess,os,struct
root=pathlib.Path(__file__).resolve().parents[1]/'ports'; inp=pathlib.Path(os.environ['NAVI_TEST_INPUT']) if os.environ.get('NAVI_TEST_INPUT') else None
prefix=r'''
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <math.h>
#include <assert.h>
#include "mathx.h"
typedef unsigned GLuint; typedef int GLint,GLsizei, GLenum,GLboolean; typedef long GLsizeiptr;
#define GL_TEXTURE_2D 1
#define GL_TEXTURE_MIN_FILTER 2
#define GL_TEXTURE_MAG_FILTER 3
#define GL_LINEAR 4
#define GL_TEXTURE_WRAP_S 5
#define GL_TEXTURE_WRAP_T 6
#define GL_CLAMP_TO_EDGE 7
#define GL_RGBA 8
#define GL_UNSIGNED_BYTE 9
#define GL_ARRAY_BUFFER 10
#define GL_ELEMENT_ARRAY_BUFFER 11
#define GL_STATIC_DRAW 12
#define GL_VIEWPORT 13
#define GL_SCISSOR_TEST 14
#define GL_TRUE 1
#define GL_FALSE 0
#define GL_DEPTH_BUFFER_BIT 16
#define GL_DEPTH_TEST 17
#define GL_LEQUAL 18
#define GL_FLOAT 19
#define GL_TRIANGLES 20
#define GL_UNSIGNED_SHORT 21
#define GL_TRIANGLE_STRIP 22
#define CAR_CITIES 5
#define SPR_COUNT 400
typedef struct {GLuint tex; float w,h;} hud_sprite; static hud_sprite SPR[SPR_COUNT];
static float EDGE,MAP_UP; static const float HUD_K=1.1f; static float tx(float x){return x*HUD_K;} static float ty(float y){return 26+y*HUD_K;}
typedef struct {float screen_w,screen_h;} hud_state; typedef struct {int area,next_area; float map_angle,map_x,map_z;} car_race;
static void meters_index(const char*p){(void)p;} static char navi_dir[1024]; static unsigned char navi_warm[2];
static int fail_alloc,alloc_count; static void *tmalloc(size_t n){if(fail_alloc && ++alloc_count==fail_alloc)return NULL;return malloc(n);} static void *tcalloc(size_t n,size_t s){if(fail_alloc && ++alloc_count==fail_alloc)return NULL;return calloc(n,s);}
#define malloc tmalloc
#define calloc tcalloc
static int mock_error,inject_upload_error;
static unsigned nextid=1,ab,ib,tex; static size_t sizes[2048]; static unsigned char tex_live[2048],buf_live[2048]; static int roads,arrows,invalid,scissor,depth,mask=1,at[3],vp[4]={0,0,1024,768};
static void glGenTextures(int n,GLuint*p){while(n--){assert(nextid<2048);tex_live[nextid]=1;*p++=nextid++;}} static void glBindTexture(int t,GLuint v){(void)t;if(v&&!tex_live[v])invalid++;tex=v;}
static void glTexParameteri(int a,int b,int c){(void)a;(void)b;(void)c;} static void glTexImage2D(int a,int b,int c,int w,int h,int d,int e,int f,const void*p){(void)a;(void)b;(void)c;(void)w;(void)h;(void)d;(void)e;(void)f;(void)p;}
static void glDeleteTextures(int n,const GLuint*p){while(n--){unsigned x=*p++;if(x){assert(x<2048&&tex_live[x]);tex_live[x]=0;if(tex==x)tex=0;}}} static void glGenBuffers(int n,GLuint*p){while(n--){assert(nextid<2048);buf_live[nextid]=1;*p++=nextid++;}} static void glDeleteBuffers(int n,const GLuint*p){while(n--){unsigned x=*p++;if(x){assert(x<2048&&buf_live[x]);buf_live[x]=0;sizes[x]=0;if(ab==x)ab=0;if(ib==x)ib=0;}}}
static void glBindBuffer(int t,GLuint b){if(b&&!buf_live[b])invalid++;if(t==GL_ARRAY_BUFFER)ab=b;else ib=b;} static void glBufferData(int t,GLsizeiptr n,const void*p,int u){(void)p;(void)u;unsigned b=t==GL_ARRAY_BUFFER?ab:ib;assert(b && b<2048);sizes[b]=n;if(inject_upload_error)mock_error=1;}
static GLuint gl_compile_program(const char*a,const char*b,const char**c,int d){(void)a;(void)b;(void)c;(void)d;return nextid++;} static GLint glGetUniformLocation(GLuint p,const char*n){(void)p;(void)n;return 1;}
static void glGetIntegerv(int a,GLint*v){(void)a;memcpy(v,vp,sizeof vp);} static void glViewport(int x,int y,int w,int h){vp[0]=x;vp[1]=y;vp[2]=w;vp[3]=h;}
static void glEnable(int v){if(v==GL_SCISSOR_TEST)scissor=1;if(v==GL_DEPTH_TEST)depth=1;} static void glDisable(int v){if(v==GL_SCISSOR_TEST)scissor=0;if(v==GL_DEPTH_TEST)depth=0;}
static void glScissor(int x,int y,int w,int h){(void)x;(void)y;(void)w;(void)h;} static void glDepthMask(int b){mask=b;} static void glClear(int x){(void)x;} static void glDepthFunc(int x){(void)x;}
static void glUseProgram(GLuint v){(void)v;} static void glUniformMatrix4fv(int a,int b,int c,const float*d){(void)a;(void)b;(void)c;(void)d;} static void glUniform1i(int a,int b){(void)a;(void)b;}
static void glEnableVertexAttribArray(int i){at[i]=1;} static void glDisableVertexAttribArray(int i){at[i]=0;} static void glVertexAttrib4f(int i,float a,float b,float c,float d){(void)i;(void)a;(void)b;(void)c;(void)d;}
static void glVertexAttribPointer(int i,int n,int t,int norm,int stride,const void*p){(void)i;(void)n;(void)t;(void)norm;(void)stride;if(ab&&(uintptr_t)p>=sizes[ab])invalid++;}
static void glDrawElements(int mode,int n,int t,const void*p){(void)mode;(void)t;roads++;if(!ab||!ib||!tex||(size_t)(uintptr_t)p+(size_t)n*2>sizes[ib]||!at[0]||!at[1]||!at[2])invalid++;}
static void glDrawArrays(int mode,int start,int n){(void)mode;(void)start;arrows++;if(n!=4||ab||ib||!tex||!at[0]||!at[1]||at[2])invalid++;}
#define GL_NO_ERROR 0
static int glGetError(void){int e=mock_error;mock_error=0;return e;}
static int navi_load(const char*); static void navi_clear(void); static void navi_select(int,int); void hud_set_city(int); static int navi_city=-1, navi_requested=-1;
'''
suffix=r'''
static void report(const char*label){hud_state h={1024,768};car_race r={0,1,0,0,0};roads=arrows=invalid=0;at[0]=1;draw_navi(&h,&r);printf("%s n=%d roads=%d arrow=%d invalid=%d vb=%lu ib=%lu scissor=%d depth=%d mask=%d vp=%d,%d,%d,%d\n",label,NAVI.n,roads,arrows,invalid,(unsigned long)sizes[NAVI.vbo],(unsigned long)sizes[NAVI.ibo],scissor,depth,mask,vp[0],vp[1],vp[2],vp[3]);if(NAVI.n&&navi_city>=0&&navi_city==navi_requested)assert(roads>0&&arrows==1&&!invalid);else assert(!roads&&!arrows&&!invalid);}
static int live(const unsigned char*a){int n=0;for(int i=1;i<2048;i++)n+=a[i]!=0;return n;}
int main(int argc,char**argv){assert(argc==2);assert(!navi_gl_init());assert(!hud_load(argv[1]));report("tokyo");assert(NAVI.n==98);hud_set_city(1);report("osaka");assert(NAVI.n==17);hud_set_city(3);report("nagoya");assert(NAVI.n==2);hud_set_city(0);report("tokyo2");assert(NAVI.n==98);hud_set_city(2);report("hakone");assert(NAVI.n==2);hud_set_city(4);report("fukuoka");assert(NAVI.n==2);hud_set_city(0);
char p[1200],q[1200];snprintf(p,sizeof p,"%s/navi_oosaka.bin",argv[1]);snprintf(q,sizeof q,"%s/hidden",argv[1]);unsigned old_vb=NAVI.vbo,old_tex=NAVI.tex[0];assert(!rename(p,q));hud_set_city(1);report("missing");assert(roads==0 && arrows==0 && NAVI.n==98);int preservation_failure=!(buf_live[old_vb]&&tex_live[old_tex]);if(preservation_failure)puts("FAIL: missing target destroyed previous valid resources");assert(!preservation_failure);assert(!rename(q,p));hud_set_city(1);report("repeat-restored");assert(NAVI.n==17);assert(live(buf_live)==2&&live(tex_live)==2);
assert(!hud_load(argv[1]));report("reload-hud");assert(NAVI.n==98);hud_set_city(1);report("same-city-after-reload");assert(NAVI.n==17);
for(int k=1;k<=4;k++){hud_set_city(0);alloc_count=0;fail_alloc=k;hud_set_city(3);fail_alloc=0;report("failed-alloc");assert(NAVI.n==98&&!roads&&!arrows);assert(live(buf_live)==2&&live(tex_live)==2);hud_set_city(3);report("alloc-retry");assert(NAVI.n==2&&live(buf_live)==2&&live(tex_live)==2);}
hud_set_city(0);inject_upload_error=1;hud_set_city(3);inject_upload_error=0;report("failed-gl");assert(NAVI.n==98&&!roads&&!arrows&&live(buf_live)==2&&live(tex_live)==2);hud_set_city(3);report("gl-retry");assert(NAVI.n==2);
snprintf(p,sizeof p,"%s/navi.bin",argv[1]);assert(!rename(p,q));assert(!hud_load(argv[1]));report("hud-reload-missing");assert(NAVI.n==2&&!roads&&!arrows&&live(buf_live)==2&&live(tex_live)==2);assert(!rename(q,p));hud_set_city(0);report("hud-reload-retry");assert(NAVI.n==98);navi_clear();assert(live(buf_live)==0&&live(tex_live)==0);return preservation_failure?2:0;}
'''
def part(s,a,b):
 assert s.count(a)==1,(a,s.count(a));return s[s.index(a):s.index(b,s.index(a))]
with tempfile.TemporaryDirectory(prefix='navi-dynamic-') as d:
 print('temporary root',d,flush=True)
 for port in ('android','ipad'):
  src=(root/port/'src/hud.c').read_text();chunks=[part(src,'static GLuint upload(','\n/* ---- each car'),part(src,'int hud_load(','\n/* Sprite centred'),part(src,'#define NAVI_VERT','\n/* PowerVR leaves'),part(src,'static int navi_area(','\n/* a story race')]
  temp=pathlib.Path(d)/port;temp.mkdir()
  names=('tokyo','oosaka','hakone','nagoya','fukuoka'); counts=(98,17,2,2,2)
  source=inp/port if inp is not None else None
  have_real=source is not None and all((source/f'navi_{n}.bin').is_file() for n in names)
  print('input:', 'real read-only WNV1' if have_real else 'synthetic WNV1 (real files unavailable)', flush=True)
  for n,count in zip(names,counts):
   dest=temp/('navi.bin' if n=='tokyo' else f'navi_{n}.bin')
   if have_real: dest.symlink_to(source/f'navi_{n}.bin')
   else:
    vertex=struct.pack('<5f4B',0,0,0,0,0,255,255,255,255)
    mesh=struct.pack('<hBBII',-1,0,0,3,3)+vertex*3+struct.pack('<3H',0,1,2)
    dest.write_bytes(b'WNV1'+struct.pack('<5I',1,1,1,1,count)+bytes([255]*8)+mesh*count)
  (temp/'hud.bin').write_bytes(b'WHD1\0\0\0\0')
  c=temp/'test.c';c.write_text(prefix+'\n'.join(chunks)+suffix);exe=temp/'test'
  subprocess.run(['cc','-std=c11','-O0','-I',str(root/port/'src'),str(c),'-lm','-o',str(exe)],check=True)
  print('\n===',port,'===',flush=True);subprocess.run([str(exe),str(temp)],check=True)
