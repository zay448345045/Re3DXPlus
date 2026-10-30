#!/usr/bin/env python3
"""Extract and execute production C functions with offline stubs; no device or GPU."""
import os, pathlib, re, subprocess, tempfile, unittest
ROOT=pathlib.Path(__file__).resolve().parents[1]
APP=(ROOT/'src/app.c').read_text(); MENU=(ROOT/'src/menu.c').read_text(); RENDER=(ROOT/'src/render.c').read_text()
def func(s,n):
 m=re.search(r'(?m)^(?:static\s+)?(?:void|int|float)(?:\s*\*\s*|\s+)'+n+r'\s*\([^;]*?\)\s*\{',s)
 if not m: raise RuntimeError(n)
 i=m.end(); d=1
 while d:
  if s[i]=='{': d+=1
  elif s[i]=='}': d-=1
  i+=1
 return s[m.start():i]
PRE=r"""
#define _POSIX_C_SOURCE 200809L
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <math.h>
#include <assert.h>
static char key_layout_legacy[512];
static int fail_rename;
static int test_rename(const char *a,const char *b){return fail_rename ? -1 : rename(a,b);}
#define rename test_rename
typedef struct {float tap_x,tap_y; int enhance_on,enhance_changed,garage_changed,gyro,gyro_sens,over_on,sharp_on,pedal_slide,ao_on,bm_on,hd_tex,bloom_on,ssao_on,wet_on,paint_on,aa4,hires,hq_rows,res_row;} menu_state;
static struct { char save_dir[1100]; menu_state menu; int options_global,console,ipad_graphics,hq_on,hq_ssao_made,hq_bloom,hq_ssao,hq_env,hd_maps,hd_reload,extras_city; } G;
/* Compile the production Apple branch while G.ipad_graphics distinguishes Android. */
#ifndef __APPLE__
#define __APPLE__ 1
#endif
#undef TARGET_OS_IPHONE
#define TARGET_OS_IPHONE 1
#undef TARGET_OS_MACCATALYST
#define TARGET_OS_MACCATALYST 0
enum { RENDER_SSAO_FAILED=-1, RENDER_SSAO_PENDING=0, RENDER_SSAO_AVAILABLE=1 };
static int ssao_capability=RENDER_SSAO_PENDING;
int render_ssao_capability(void){return ssao_capability;}
static int current,rb,rs,rp,rw,ssao_calls,sounds,msaa_calls,msaa_enabled,msaa_samples;
void render_msaa_request(int enabled,int samples){msaa_calls++;msaa_enabled=enabled;msaa_samples=samples;}
void render_enhance(int x){current=x;}
void render_ssao(float x){(void)x;ssao_calls++;}
void render_hq_options(int b,int s,int p,int w){rb=b;rs=s;rp=p;rw=w;}
#define SND_CURSOR 1
void snd_menu(int x){(void)x;sounds++;}
#define O_REFLECTION 1
#define O_SHARP 2
#define O_AO 3
#define O_BM 4
#define O_HD 5
#define O_BLOOM 6
#define O_SSAO 7
#define O_WET 8
#define O_PAINT 9
#define O_AA 10
#define O_ON 20
#define O_4X 22
#define OPT_TEXT 100
#define SET_CHIP_GAP 10.0f
int anm_sprite(int n){return n;}
float anm_sprite_width(int n){(void)n;return 40.0f;}
typedef struct {float fog_color[3],grade[3]; int night;} render_params;
"""
BODY=r"""
static void readfile(const char*n,char*s,size_t z){char p[1200];snprintf(p,sizeof p,"%s/%s",G.save_dir,n);FILE*f=fopen(p,"r");assert(f);size_t k=fread(s,1,z-1,f);s[k]=0;fclose(f);}
static void putfile(const char*n,const char*s){char p[1200];snprintf(p,sizeof p,"%s/%s",G.save_dir,n);FILE*f=fopen(p,"w");assert(f);assert(fputs(s,f)>=0);assert(!fclose(f));}
static void tap(float x,float y){G.menu.tap_x=x;G.menu.tap_y=y;option_hq_step(&G.menu);option_enhance_step(&G.menu);}
int main(int argc,char**argv){
 assert(argc==2);snprintf(G.save_dir,sizeof G.save_dir,"%s",argv[1]);
 const char*legacy="option 1 7 1 0 1 1 0 1 0 0 1 0 1 1\n";char a[512],b[512];
 putfile("option",legacy);assert(options_load());G.options_global=1;
 assert(!G.menu.bloom_on&&!G.menu.ssao_on&&G.menu.wet_on&&!G.menu.paint_on);
 G.menu.enhance_on=1;enhance_load();assert(G.menu.enhance_on);readfile("option",a,sizeof a);assert(!strcmp(a,legacy));
 G.console=1;G.hq_on=1;G.hq_bloom=G.hq_ssao=G.hq_env=-1;G.hd_maps=G.menu.hd_tex;
 hq_apply();assert(current&&!rb&&!rs&&!rp&&rw&&ssao_calls==0);assert(!G.menu.bloom_on&&!G.menu.ssao_on&&!G.menu.paint_on&&G.menu.wet_on);
 /* Exhaust every bloom/SSAO/paint/wet combination with enhancement both ways. */
 for(int e=0;e<2;e++) for(int mask=0;mask<16;mask++) {
  G.menu.enhance_on=e;G.menu.bloom_on=!!(mask&1);G.menu.ssao_on=!!(mask&2);G.menu.paint_on=!!(mask&4);G.menu.wet_on=!!(mask&8);
  G.hq_bloom=G.hq_ssao=G.hq_env=-1;hq_apply();
  assert(current==e&&rb==!!(mask&1)&&rs==!!(mask&2)&&rp==!!(mask&4)&&rw==!!(mask&8));
  assert(G.menu.bloom_on==rb&&G.menu.ssao_on==rs&&G.menu.paint_on==rp&&G.menu.wet_on==rw);
 }
 G.menu.enhance_on=1;G.menu.bloom_on=G.menu.ssao_on=G.menu.paint_on=0;G.menu.wet_on=1;hq_apply();
 tap(274.9f,403);assert(G.menu.enhance_on&&!G.menu.enhance_changed);
 tap(275,403);assert(!G.menu.enhance_on&&G.menu.enhance_changed&&!G.menu.garage_changed&&sounds==1);
 tap(275,403);assert(sounds==1);hq_apply();assert(!current&&!rb&&!rs&&!rp&&rw);
 assert(enhance_save());G.menu.enhance_on=1;enhance_load();assert(!G.menu.enhance_on);
 readfile("option",b,sizeof b);assert(!strcmp(a,b));readfile("enhanced_lighting",b,sizeof b);assert(!strcmp(b,"enhanced_lighting 1 0\n"));
 G.menu.enhance_changed=0;tap(220,403);assert(G.menu.enhance_on&&G.menu.enhance_changed);assert(enhance_save());
 G.menu.enhance_on=0;enhance_load();assert(G.menu.enhance_on);readfile("option",b,sizeof b);assert(!strcmp(a,b));
 tap(275,392);assert(!G.menu.enhance_on);tap(220,414);assert(!G.menu.enhance_on);
 putfile("enhanced_lighting","enhanced_lighting 1 0 junk\n");G.menu.enhance_on=1;enhance_load();assert(G.menu.enhance_on);
 putfile("enhanced_lighting","enhanced_lighting 2 0\n");enhance_load();assert(G.menu.enhance_on);
 G.menu.bloom_on=1;G.menu.ssao_on=1;G.menu.paint_on=1;G.menu.ao_on=0;options_save();G.menu.bloom_on=G.menu.ssao_on=G.menu.paint_on=0;G.menu.ao_on=1;
 assert(options_load());assert(G.menu.bloom_on&&G.menu.ssao_on&&G.menu.paint_on&&G.menu.wet_on&&!G.menu.ao_on);
 G.menu.enhance_on=0;hq_apply();assert(!current&&rb&&rs&&rp&&rw&&!G.menu.ao_on);
 G.menu.enhance_on=1;hq_apply();assert(current&&rb&&rs&&rp&&rw&&!G.menu.ao_on);
 assert(msaa_calls==0); /* Android combinations did not issue iPad requests. */
 render_params p={{0.05f,0.05f,0.05f},{1.0f,0.9f,0.8f},1};float x[3],y[3],road[3];
 enhance_grade(&p,0,x);enhance_grade(&p,0,y);enhance_grade(&p,1,road);for(int i=0;i<3;i++){assert(x[i]==y[i]);assert(road[i]>x[i]);}
 assert(enhance_night(&p)==1);p.fog_color[0]=p.fog_color[1]=p.fog_color[2]=1;assert(enhance_night(&p)==1);p.night=0;assert(enhance_night(&p)==0);
 /* iPad standalone works without HQ. Pending kicks off SSAO once without applying it. */
 G.console=0;G.ipad_graphics=1;G.hq_on=0;G.menu.enhance_on=1;current=-1;hq_apply();assert(current==1);
 G.menu.enhance_on=0;hq_apply();assert(current==0&&msaa_calls==0);
 G.hq_on=1;G.menu.aa4=0;hq_apply();assert(msaa_calls==1&&msaa_enabled==1&&msaa_samples==2);
 G.menu.aa4=1;hq_apply();assert(msaa_calls==2&&msaa_enabled==1&&msaa_samples==4);
 G.menu.aa4=0;hq_apply();assert(msaa_calls==3&&msaa_enabled==1&&msaa_samples==2);
 G.menu.enhance_on=1;G.menu.ssao_on=1;G.hq_ssao_made=0;G.hq_ssao=-1;ssao_calls=0;
 ssao_capability=RENDER_SSAO_PENDING;hq_apply();assert(current==1&&rs==0&&ssao_calls==1&&G.menu.ssao_on==1);
 hq_apply();assert(rs==0&&ssao_calls==1&&G.menu.ssao_on==1);
 /* Becoming available applies it without recreating; failure disables only the renderer. */
 ssao_capability=RENDER_SSAO_AVAILABLE;hq_apply();assert(rs==1&&ssao_calls==1&&G.menu.ssao_on==1);
 ssao_capability=RENDER_SSAO_FAILED;hq_apply();assert(rs==0&&ssao_calls==1&&G.menu.ssao_on==1);
 ssao_capability=RENDER_SSAO_AVAILABLE;hq_apply();assert(rs==1&&ssao_calls==1&&G.menu.ssao_on==1);
 G.menu.ssao_on=0;hq_apply();assert(rs==0&&ssao_calls==1&&G.menu.ssao_on==0);
 /* A failed rename leaves the old file intact and a later retry succeeds. */
 putfile("enhanced_lighting","enhanced_lighting 1 0\n");G.menu.enhance_on=1;fail_rename=1;assert(!enhance_save());
 readfile("enhanced_lighting",b,sizeof b);assert(!strcmp(b,"enhanced_lighting 1 0\n"));fail_rename=0;assert(enhance_save());
 readfile("enhanced_lighting",b,sizeof b);assert(!strcmp(b,"enhanced_lighting 1 1\n"));
 /* iPad HD shares the row but not the enhancement chips. */
 G.menu.hq_rows=2;G.menu.hd_tex=1;G.menu.enhance_on=1;G.menu.enhance_changed=G.menu.garage_changed=0;
 tap(275,403);assert(!G.menu.enhance_on&&G.menu.hd_tex==1&&G.menu.enhance_changed&&!G.menu.garage_changed);
 tap(550,403);assert(!G.menu.hd_tex&&!G.menu.enhance_on&&G.menu.garage_changed);
 puts("PASS: upgrade, atomic failure, Android/iPad, HQ options, tap boundaries, scene grade");return 0;
}
"""
class Regression(unittest.TestCase):
 def test_native_extracted_functions(self):
  constants=MENU[MENU.index('#define OPT_HQ_Y'):MENU.index('/* the switch a row sets')]
  code=PRE+'\n'+'\n'.join(func(APP,n) for n in ['hq_apply','enhance_load','enhance_save','options_load','options_save'])+'\n'+constants+'\n'+'\n'.join(func(MENU,n) for n in ['option_set','option_hq_value','option_hq_chips','option_enhance_step','option_hq_step'])+'\n'+'\n'.join(func(RENDER,n) for n in ['enhance_night','enhance_grade'])+BODY
  with tempfile.TemporaryDirectory(prefix='enhanced-test-') as t:
   c=pathlib.Path(t)/'h.c';exe=pathlib.Path(t)/'h';saves=pathlib.Path(t)/'saves';saves.mkdir();c.write_text(code)
   subprocess.run([os.environ.get('CC','cc'),'-std=c11','-Wall','-Wextra','-Werror',str(c),'-lm','-o',str(exe)],check=True)
   subprocess.run([str(exe),str(saves)],check=True)
 def test_integration_sites_source(self):
  self.assertRegex(MENU,r'm->enhance_on\s*=\s*1\s*;')
  self.assertRegex(APP,r'if\s*\(G\.console\s*\|\|\s*G\.ipad_graphics\)\s*enhance_load\(\)')
  self.assertRegex(APP,r'if\s*\(G\.menu\.enhance_changed\)\s*\{\s*hq_apply\(\);\s*if\s*\(enhance_save\(\)\)\s*G\.menu\.enhance_changed\s*=\s*0')
  self.assertIn('if (m->hq_rows) draw_option_enhance',MENU)
  self.assertIn('if (enhance_on) { enhance_grade(p, 0, adjusted); grade = adjusted; }',RENDER)
  self.assertIn('glUniform3fv(pr->grade, 1, grade)',RENDER)
  # AO selection is source-checked only, not executed in the harness.
  self.assertIn('wpk_ao(G.ao_test >= 0 ? G.ao_test : G.menu.ao_on)',APP)
if __name__=='__main__': unittest.main(verbosity=2)
