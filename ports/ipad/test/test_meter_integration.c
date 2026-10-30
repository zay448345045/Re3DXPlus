/* Host-only isolated HUD resource integration test; never writes supplied fixtures. */
#include <assert.h>
#include <unistd.h>
#include "../src/hud.c"
static int fail_texture, capture_alpha;
typedef struct { unsigned w,h; unsigned char *alpha; } observed_texture;
static observed_texture observed[65536];
static GLint tex=41;
void glGenTextures(GLsizei n, GLuint *p) { static GLuint next=1; while(n--) *p++=fail_texture ? 0 : next++; fail_texture=0; }
void glBindTexture(GLenum a, GLuint b) {(void)a;tex=(GLint)b;}
void glTexParameteri(GLenum a, GLenum b, GLint c) {(void)a;(void)b;(void)c;}
void glTexImage2D(GLenum a, GLint b, GLint c, GLsizei d, GLsizei e, GLint f, GLenum g, GLenum h, const void *p) {
 (void)a;(void)b;(void)c;(void)f;(void)g;(void)h;
 if (capture_alpha && tex>0) { assert(tex<65536); observed_texture *o=&observed[tex];
  free(o->alpha); o->w=d; o->h=e; o->alpha=malloc((size_t)d*e); assert(o->alpha);
  for(size_t i=0;i<(size_t)d*e;i++) o->alpha[i]=((const unsigned char*)p)[i*4+3]; }
}
void glDeleteTextures(GLsizei n, const GLuint *p) { while(n--) { if (*p<65536) {free(observed[*p].alpha); memset(&observed[*p],0,sizeof observed[*p]);} p++; } }
/* State/geometry spies for the preview draw. */
static GLint gp=31, gt=GL_TEXTURE0, gb=17, ena[2]={1,0}, blend, depth=1, cull=1, eq=GL_FUNC_ADD, bs=GL_ONE, bd=GL_ONE_MINUS_SRC_ALPHA;
static const void *ap[2]={(void*)16,(void*)32}; static GLfloat unival[3][16]; static GLint samp=7; static int ndraw, check_projection;
float car_kmh(const car_state *c) { return c->speed*3.6f; }
GLboolean glIsEnabled(GLenum e) { return e==GL_BLEND?blend:e==GL_DEPTH_TEST?depth:cull; }
void glGetIntegerv(GLenum e,GLint *v) { switch(e) { case GL_CURRENT_PROGRAM:*v=gp;break;case GL_ACTIVE_TEXTURE:*v=gt;break;case GL_ARRAY_BUFFER_BINDING:*v=gb;break;case GL_TEXTURE_BINDING_2D:*v=tex;break;case GL_BLEND_EQUATION_RGB:case GL_BLEND_EQUATION_ALPHA:*v=eq;break;case GL_BLEND_SRC_RGB:case GL_BLEND_SRC_ALPHA:*v=bs;break;default:*v=bd; } }
void glGetVertexAttribiv(GLuint i,GLenum e,GLint*v) { switch(e){case GL_VERTEX_ATTRIB_ARRAY_ENABLED:*v=ena[i];break;case GL_VERTEX_ATTRIB_ARRAY_SIZE:*v=2;break;case GL_VERTEX_ATTRIB_ARRAY_TYPE:*v=GL_FLOAT;break;case GL_VERTEX_ATTRIB_ARRAY_NORMALIZED:*v=0;break;case GL_VERTEX_ATTRIB_ARRAY_STRIDE:*v=8;break;default:*v=17;} }
void glGetVertexAttribPointerv(GLuint i,GLenum e,void **v) {(void)e;*v=(void*)ap[i];}
void glGetUniformfv(GLuint p,GLint l,GLfloat *v){(void)p;memcpy(v,unival[l],(l==0?16:4)*sizeof *v);}
void glGetUniformiv(GLuint p,GLint l,GLint *v){(void)p;(void)l;*v=samp;}
void glUseProgram(GLuint p){gp=p;} void glActiveTexture(GLenum t){gt=t;}
void glBindBuffer(GLenum t,GLuint b){(void)t;gb=b;}
void glUniform1i(GLint l,GLint v){(void)l;samp=v;}
void glUniform4f(GLint l,GLfloat a,GLfloat b,GLfloat c,GLfloat d){unival[l][0]=a;unival[l][1]=b;unival[l][2]=c;unival[l][3]=d;}
void glUniform4fv(GLint l,GLsizei n,const GLfloat *v){(void)n;memcpy(unival[l],v,4*sizeof *v);}
void glUniformMatrix4fv(GLint l,GLsizei n,GLboolean t,const GLfloat *v){(void)n;(void)t;if(check_projection && l==0 && v[15]==1.0f) {assert(fabsf(v[0]-2.0f/(1024+2*EDGE))<1e-7f);assert(fabsf(v[5]+2.0f/768)<1e-7f);}memcpy(unival[l],v,16*sizeof *v);}
void glEnableVertexAttribArray(GLuint i){ena[i]=1;} void glDisableVertexAttribArray(GLuint i){ena[i]=0;}
void glVertexAttribPointer(GLuint i,GLint s,GLenum t,GLboolean n,GLsizei stride,const void *p){(void)s;(void)t;(void)n;(void)stride;ap[i]=p;}
void glEnable(GLenum e){if(e==GL_BLEND)blend=1;else if(e==GL_DEPTH_TEST)depth=1;else if(e==GL_CULL_FACE)cull=1;}
void glDisable(GLenum e){if(e==GL_BLEND)blend=0;else if(e==GL_DEPTH_TEST)depth=0;else if(e==GL_CULL_FACE)cull=0;}
void glBlendEquation(GLenum e){eq=e;} void glBlendEquationSeparate(GLenum a,GLenum b){assert(a==b);eq=a;}
void glBlendFunc(GLenum a,GLenum b){bs=a;bd=b;} void glBlendFuncSeparate(GLenum a,GLenum b,GLenum c,GLenum d){assert(a==c&&b==d);bs=a;bd=b;}
static float geom_l,geom_r,geom_t,geom_b, pixel_l,pixel_r,pixel_t,pixel_b;
static void point(const float *v,float u,float w,float *x,float *y) {
 *x=(v[0]+u*(v[4]-v[0])+w*(v[8]-v[0]))/1.6f;
 *y=(v[1]+u*(v[5]-v[1])+w*(v[9]-v[1]))/1.6f;
}
static void limits(float x,float y,float *l,float *r,float *t,float *b) {
 if(x<*l)*l=x;if(x>*r)*r=x;if(y<*t)*t=y;if(y>*b)*b=y;
}
void glDrawArrays(GLenum mode,GLint first,GLsizei count){
 (void)first; assert(mode==GL_TRIANGLE_STRIP&&count==4); const float *v=ap[0];
 assert(tex>0 && tex<65536); observed_texture *o=&observed[tex]; assert(o->alpha);
 unsigned l=o->w,t=o->h,r=0,b=0;
 for(unsigned y=0;y<o->h;y++) for(unsigned x=0;x<o->w;x++) if(o->alpha[(size_t)y*o->w+x]) {
  if(x<l)l=x;if(x+1>r)r=x+1;if(y<t)t=y;if(y+1>b)b=y+1;
  for(int j=0;j<4;j++) {float xx,yy;point(v,(float)(x+(j&1))/o->w,(float)(y+((j>>1)&1))/o->h,&xx,&yy);
   assert(xx>=270-.02f&&xx<=520+.02f&&yy>=238-.02f&&yy<=303+.02f);
   limits(xx,yy,&pixel_l,&pixel_r,&pixel_t,&pixel_b);}
 }
 if(r) for(int j=0;j<4;j++){float xx,yy;point(v,(float)(j&1?r:l)/o->w,(float)(j&2?b:t)/o->h,&xx,&yy);limits(xx,yy,&geom_l,&geom_r,&geom_t,&geom_b);}
 ndraw++;
}
static void copy_file(const char *src, const char *dst) {
 FILE *a=fopen(src,"rb"), *b=fopen(dst,"wb"); assert(a && b); char buf[16384]; size_t n;
 while ((n=fread(buf,1,sizeof buf,a))) assert(fwrite(buf,1,n,b)==n);
 assert(!ferror(a)); fclose(a); fclose(b);
}
int main(int argc, char **argv) {
 assert(argc==3); char dir[]="/tmp/hud-meter-test-XXXXXX"; assert(mkdtemp(dir));
 char legacy[512], extra[512]; snprintf(legacy,sizeof legacy,"%s/meters.bin",dir); snprintf(extra,sizeof extra,"%s/meters-v2.bin",dir);
 copy_file(argv[1],legacy); copy_file(argv[2],extra);
 assert(hud_validate_meter_file(extra)); assert(!hud_validate_meter_file(NULL));
 hud_set_extra_directory(dir); meters_index(dir); assert(meter_legacy.sprites && hud_meter_available());
 for(int style=1;style<=2;style++) {
  hud_set_meter(style);
  for(int c=0;c<MP_CARS;c++) for(int n=0;n<2;n++) {
   int zone=2*style+n;
   hud_set_car(c,n); assert(meter_v2_active && meter_night==zone);
   for(int i=0;i<METERDB_V2[c].n[zone];i++) assert(METER[i].tex);
  }
 }
 hud_set_meter(1); hud_set_car(0,0); assert(meter_v2_active && meter_night==2 && METER[0].tex);
 GLuint race_tex = METER[0].tex; const meterdb_car *race_car = meter_car;
 for (int c=0;c<MP_CARS;c++) for (int s=0;s<3;s++) {
   assert(preview_load(c,s)); GLuint tex=preview_meter[0].tex; assert(tex);
   assert(preview_load(c,s) && preview_meter[0].tex==tex);
   assert(METER[0].tex==race_tex && meter_car==race_car && meter_night==2 && meter_v2_active);
 }
 fail_texture=1; assert(!preview_load(0,1)); assert(!preview_load(0,1));
 assert(meter_extra.sprites && METER[0].tex==race_tex);
 assert(!preview_load(-1,0));
 puts("Preview 55 cars x 3, independent cache and failure: PASS");
 tex_prog=99; u_tproj=0; u_mul=1; u_add=2; u_tex=3;
 for(int i=0;i<16;i++) unival[0][i]=(float)i; for(int i=0;i<4;i++) unival[1][i]=11+i, unival[2][i]=21+i;
 GLfloat saved[3][16]; memcpy(saved,unival,sizeof unival);
 check_projection=1; capture_alpha=1;
 for(int wide=0;wide<2;wide++) { hud_wide(wide?160:0,1); for(int c=0;c<MP_CARS;c++) for(int s=0;s<3;s++) {
   geom_l=pixel_l=1e9f; geom_r=pixel_r=-1e9f; geom_t=pixel_t=1e9f; geom_b=pixel_b=-1e9f;
   int before=ndraw; GLint prevtex=tex; assert(hud_meter_preview(c,s,270,238,250,65,1));
   int count=s?METERDB_V2[c].n[s*2]:METERDB[c].n[0]; assert(ndraw-before==count);
   assert(fabsf((geom_l+geom_r)*.5f-395)<.02f && fabsf((geom_t+geom_b)*.5f-270.5f)<.02f);
   assert(fabsf(geom_r-geom_l-250)<.02f || fabsf(geom_b-geom_t-65)<.02f);
   if(!wide && c==4 && s==1) printf("Racing car 4 visible pixels %.2f x %.2f, x %.2f..%.2f y %.2f..%.2f; fitted bbox %.2f x %.2f\n",pixel_r-pixel_l,pixel_b-pixel_t,pixel_l,pixel_r,pixel_t,pixel_b,geom_r-geom_l,geom_b-geom_t);
   assert(gp==31&&gt==GL_TEXTURE0&&gb==17&&tex==prevtex&&ena[0]&&!ena[1]&&ap[0]==(void*)16&&ap[1]==(void*)32);
   assert(!blend&&depth&&cull&&eq==GL_FUNC_ADD&&bs==GL_ONE&&bd==GL_ONE_MINUS_SRC_ALPHA&&samp==7);
   assert(!memcmp(saved,unival,sizeof unival));
 }}
 puts("Preview real alpha geometry 55x3 and GL state restoration at narrow/wide: PASS");
 hud_set_meter(0); hud_set_car(0,0); assert(!meter_v2_active && meter_night==0 && METER[0].tex);
 hud_set_meter(2); hud_set_car(-1,0); assert(!meter_car && hud_meter_available());
 fail_texture=1; hud_set_car(0,0); assert(!meter_v2_active && !hud_meter_available() && METER[0].tex);
 meters_index(dir); assert(hud_meter_available());
 assert(!truncate(extra, 24)); hud_set_car(0,0); assert(!hud_meter_available() && !meter_v2_active && METER[0].tex);
 copy_file(argv[2],extra); meters_index(dir); assert(hud_meter_available());
 char longdir[1100]; memset(longdir,'x',sizeof longdir-1); longdir[sizeof longdir-1]=0;
 hud_set_extra_directory(longdir); meters_index(dir); assert(!hud_meter_available());
 hud_set_extra_directory(dir); meters_index(dir); assert(hud_meter_available());
 FILE *f=fopen(extra,"r+b"); assert(f); assert(fputc('X',f)!=EOF); fclose(f);
 assert(!hud_validate_meter_file(extra)); meters_index(dir); hud_set_car(0,0); assert(!hud_meter_available() && !meter_v2_active && METER[0].tex);
 assert(!unlink(extra)); meters_index(dir); hud_set_car(1,1); assert(!hud_meter_available() && !meter_v2_active && METER[0].tex);
 assert(!unlink(legacy)); assert(!rmdir(dir)); puts("HUD For Racing and Special 55x2 each, validation and fallback: PASS"); return 0;
}
