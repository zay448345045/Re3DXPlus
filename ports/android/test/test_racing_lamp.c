#include <assert.h>
#include "../src/hud.c"
static GLuint next_tex=1, bound, drawn[32]; static int ndraw, fail_next_upload, err;
void glGenTextures(GLsizei n, GLuint *p) { while(n--) *p++=next_tex++; }
void glBindTexture(GLenum a, GLuint b) { (void)a; bound=b; }
void glTexParameteri(GLenum a, GLenum b, GLint c) {(void)a;(void)b;(void)c;}
void glTexImage2D(GLenum a, GLint b, GLint c, GLsizei d, GLsizei e, GLint f, GLenum g, GLenum h, const void *p) {(void)a;(void)b;(void)c;(void)d;(void)e;(void)f;(void)g;(void)h;(void)p; if(fail_next_upload) { err=0x0505; fail_next_upload=0; }}
GLenum glGetError(void) {int e=err; err=0; return e;}
void glDeleteTextures(GLsizei n, const GLuint *p) {(void)n;(void)p;}
void glEnableVertexAttribArray(GLuint a) {(void)a;}
void glDisableVertexAttribArray(GLuint a) {(void)a;}
void glVertexAttribPointer(GLuint a, GLint b, GLenum c, GLboolean d, GLsizei e, const void *f) {(void)a;(void)b;(void)c;(void)d;(void)e;(void)f;}
void glDrawArrays(GLenum a, GLint b, GLsizei c) {(void)a;(void)b;(void)c; assert(ndraw<32); drawn[ndraw++]=bound;}
void glBlendFunc(GLenum a, GLenum b) {(void)a;(void)b;}
float car_kmh(const car_state *c) { return c->speed*3.6f; }
static GLuint run(car_state *c) { ndraw=0; draw_meters(c); assert(ndraw==5); return drawn[4]; }
int main(int argc, char **argv) {
 assert(argc==3); hud_set_extra_directory(argv[2]); meters_index(argv[1]); assert(hud_meter_available());
 car_state c={0}, before; int r32=-1; for(int i=0;i<METER_CARS;i++) if(METERDB[i].car==22) r32=i; assert(r32>=0); hud_set_meter(1);
 for(int n=0;n<2;n++) { hud_set_car(r32,n); assert(racing_lamp_slot==4 && racing_lamp_on.tex); GLuint off=METER[4].tex,on=racing_lamp_on.tex;
 c.rev_rate=.86f; c.rev_lamp_frame=2; before=c; assert(run(&c)==off); assert(!memcmp(&before,&c,sizeof c));
 c.rev_rate=.87f; for(int phase=0;phase<5;phase++) { c.rev_lamp_frame=phase; assert(run(&c)==(phase>1?on:off)); } c.rev_lamp_frame=2; assert(run(&c)==on); assert(run(&c)==on); c.rev_lamp_frame=5; assert(run(&c)==off); }
 hud_set_car(0,0); assert(racing_lamp_slot==4); c.rev_rate=.9f;c.rev_lamp_frame=2; assert(run(&c)==racing_lamp_on.tex);
 { unsigned char raw[64*64*4]; assert(lamp_inflate(raw,lamp_off_m,sizeof lamp_off_m));
   glDeleteTextures(1,&racing_lamp_on.tex); racing_lamp_on.tex=0; racing_lamp_slot=-1;
   raw[0]^=1; lamp_prepare(raw,64,64,2,4); assert(racing_lamp_slot==-1);
   raw[0]^=1; fail_next_upload=1; lamp_prepare(raw,64,64,2,4); assert(racing_lamp_slot==-1 && !racing_lamp_on.tex);
   assert(run(&c)==METER[4].tex); }
 hud_set_meter(2);hud_set_car(r32,0);assert(racing_lamp_slot==-1 && !racing_lamp_on.tex);
 hud_set_meter(0);hud_set_car(r32,0);assert(racing_lamp_slot==-1 && !racing_lamp_on.tex);
 hud_set_meter(1);hud_set_car(-1,0);assert(racing_lamp_slot==-1);
 hud_set_extra_directory("/nonexistent");meters_index(argv[1]);hud_set_car(r32,0);assert(!meter_v2_active && racing_lamp_slot==-1);
 puts("actual draw_meters R32 day/night, threshold, phases, paused, other car, types, missing pack, physics: PASS"); return 0;
}
