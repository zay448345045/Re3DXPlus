#define GLES_SILENCE_DEPRECATION 1
#define WMMT_IOS_HQ_TEST 1
#include <assert.h>
#include "../src/render.c"
#undef glBindFramebuffer
#undef glCheckFramebufferStatus
#undef glFramebufferTexture2D
static GLuint id=10, fb=7, unit=0, tex[16], color[8192];
static int checks, fail, draws, depth_tex, highp=1, pass_fail, deleted_scene;
static GLuint protected_scene;
static GLuint current_program, depth[8192], stencil[8192];
static int ao_draws, blur_draws, feedback, bad_depth_format, inject_stage, attach_count, ao_images;
static const char *extensions="GL_OES_packed_depth_stencil";
static GLenum injected_error;
static int program_count, fail_program, zero_program, zero_shader, zero_shader_uses, deleted_programs;
int ios_test_missing_msaa;
static int max_samples=4, current_samples, current_w, current_h, current_format, fail_four, fail_two, resolve_fail, resolves;
static GLuint read_fb, draw_fb, rb_binding;
static int delete_bound, viewport_x, viewport_y, viewport_w, viewport_h;
const GLubyte *glGetString(GLenum p){return (const GLubyte *)(p==GL_VERSION?"OpenGL ES 2.0 mock":extensions);}
GLuint glCreateProgram(void){program_count++;if(zero_program){injected_error=GL_OUT_OF_MEMORY;return 0;}return id++;}
GLuint glCreateShader(GLenum x){(void)x;if(zero_shader){injected_error=GL_OUT_OF_MEMORY;return 0;}return id++;}
void glShaderSource(GLuint a,GLsizei b,const GLchar*const*c,const GLint*d){if(!a)zero_shader_uses++;(void)b;(void)c;(void)d;}
void glCompileShader(GLuint s){(void)s;}
void glGetShaderPrecisionFormat(GLenum s,GLenum p,GLint*r,GLint*v){(void)s;(void)p;r[0]=r[1]=127;*v=highp ? 23 : 0;}
void glGetShaderiv(GLuint s,GLenum p,GLint*v){(void)s;(void)p;*v=program_count!=fail_program;}
void glGetShaderInfoLog(GLuint s,GLsizei n,GLsizei*l,GLchar*v){(void)s;(void)n;(void)l;v[0]=0;}
void glAttachShader(GLuint p,GLuint s){(void)p;(void)s;}
void glDeleteShader(GLuint s){(void)s;}
void glBindAttribLocation(GLuint p,GLuint i,const GLchar*n){(void)p;(void)i;(void)n;}
void glLinkProgram(GLuint p){(void)p;}
void glGetProgramiv(GLuint p,GLenum n,GLint*v){(void)p;(void)n;*v=1;}
void glGetProgramInfoLog(GLuint p,GLsizei n,GLsizei*l,GLchar*v){(void)p;(void)n;(void)l;v[0]=0;}
GLint glGetUniformLocation(GLuint p,const GLchar*n){(void)p;(void)n;return 1;}
void glUniform1i(GLint a,GLint b){(void)a;(void)b;}
void glDeleteProgram(GLuint p){if(p)deleted_programs++;}
void glGenTextures(GLsizei n,GLuint*v){while(n--)*v++=id++;}
void glGenFramebuffers(GLsizei n,GLuint*v){while(n--)*v++=id++;}
void glGenRenderbuffers(GLsizei n,GLuint*v){while(n--)*v++=id++;}
void glBindFramebuffer(GLenum t,GLuint v){if(t==IOS_READ_FRAMEBUFFER)read_fb=v;else if(t==IOS_DRAW_FRAMEBUFFER)draw_fb=v;else {fb=v;read_fb=draw_fb=v;}}
void glBindRenderbuffer(GLenum t,GLuint v){(void)t;rb_binding=v;}
void glActiveTexture(GLenum t){unit=t-GL_TEXTURE0;}
void glBindTexture(GLenum t,GLuint v){(void)t;tex[unit]=v;}
void glFramebufferTexture2D(GLenum t,GLenum a,GLenum b,GLuint v,GLint l){(void)t;(void)b;(void)l;if(a==GL_COLOR_ATTACHMENT0)color[fb]=v;else { depth_tex++; attach_count++; if(inject_stage==1+attach_count)injected_error=GL_INVALID_OPERATION; if(a==GL_DEPTH_ATTACHMENT)depth[fb]=v; if(a==GL_STENCIL_ATTACHMENT)stencil[fb]=v; }}
void glFramebufferRenderbuffer(GLenum t,GLenum a,GLenum b,GLuint v){(void)t;(void)b;if(a==GL_DEPTH_ATTACHMENT)depth[fb]=v; if(a==GL_STENCIL_ATTACHMENT)stencil[fb]=v;}
GLenum glCheckFramebufferStatus(GLenum t){(void)t;return ++checks==fail?GL_FRAMEBUFFER_INCOMPLETE_ATTACHMENT:GL_FRAMEBUFFER_COMPLETE;}
GLenum glGetError(void){GLenum e=injected_error;injected_error=GL_NO_ERROR;return e;}
void glGetIntegerv(GLenum p,GLint*v){*v=p==GL_FRAMEBUFFER_BINDING?(GLint)fb:p==GL_RENDERBUFFER_BINDING?(GLint)rb_binding:p==IOS_MAX_SAMPLES?max_samples:GL_ONE;}
void glRenderbufferStorageMultisampleAPPLE(GLenum t,GLsizei n,GLenum f,GLsizei w,GLsizei h){(void)t;current_format=f;current_w=w;current_h=h;current_samples=n;if((n==4&&fail_four)||(n==2&&fail_two))injected_error=GL_INVALID_OPERATION;}
void glGetRenderbufferParameteriv(GLenum t,GLenum p,GLint*v){(void)t;*v=p==GL_RENDERBUFFER_WIDTH?current_w:p==GL_RENDERBUFFER_HEIGHT?current_h:p==GL_RENDERBUFFER_INTERNAL_FORMAT?current_format:current_samples;}
void glResolveMultisampleFramebufferAPPLE(void){assert(read_fb==hq.ms_fbo&&draw_fb==hq.rt_fbo);resolves++;if(resolve_fail)injected_error=GL_INVALID_OPERATION;}
void glGetBooleanv(GLenum p,GLboolean*v){(void)p;*v=GL_TRUE;}
void glDeleteTextures(GLsizei n,const GLuint*v){while(n--) if (*v++==protected_scene && protected_scene) deleted_scene++;}
void glDeleteFramebuffers(GLsizei n,const GLuint*v){while(n--){if (*v && *v==hq.ms_fbo && fb==*v) delete_bound++;v++;}}
void glDeleteRenderbuffers(GLsizei n,const GLuint*v){while(n--){if (*v && (*v==hq.ms_color || *v==hq.ms_depth) && rb_binding==*v) delete_bound++;v++;}}
void glTexImage2D(GLenum a,GLint b,GLint c,GLsizei d,GLsizei e,GLint f,GLenum g,GLenum h,const GLvoid*i){(void)a;(void)b;(void)d;(void)e;(void)f;(void)i; if(c==GL_DEPTH_STENCIL_) { if(g!=GL_DEPTH_STENCIL_ || h!=GL_UNSIGNED_INT_24_8_)bad_depth_format++; if(inject_stage==1)injected_error=GL_INVALID_OPERATION; } else if(hq.z_tex && (d==hq.aw && e==hq.ah)) { ao_images++; if(inject_stage==5+ao_images)injected_error=GL_INVALID_OPERATION; }}
void glTexParameteri(GLenum a,GLenum b,GLint c){(void)a;(void)b;(void)c;}
void glRenderbufferStorage(GLenum a,GLenum b,GLsizei c,GLsizei d){(void)a;(void)b;(void)c;(void)d;}
void glViewport(GLint a,GLint b,GLsizei c,GLsizei d){viewport_x=a;viewport_y=b;viewport_w=c;viewport_h=d;}
void glUseProgram(GLuint a){current_program=a;}
void glUniform1f(GLint a,GLfloat b){(void)a;(void)b;}
void glUniform2f(GLint a,GLfloat b,GLfloat c){(void)a;(void)b;(void)c;}
void glUniform4fv(GLint a,GLsizei b,const GLfloat*c){(void)a;(void)b;(void)c;}
void glBindVertexArrayOES(GLuint a){(void)a;}
void glBindBuffer(GLenum a,GLuint b){(void)a;(void)b;}
void glDisable(GLenum a){(void)a;} void glEnable(GLenum a){(void)a;}
void glEnableVertexAttribArray(GLuint a){(void)a;}
void glVertexAttribPointer(GLuint a,GLint b,GLenum c,GLboolean d,GLsizei e,const GLvoid*f){(void)a;(void)b;(void)c;(void)d;(void)e;(void)f;}
void glDrawArrays(GLenum a,GLint b,GLsizei c){(void)a;(void)b;(void)c;draws++; if(color[fb] && color[fb]==tex[0])feedback++; if(current_program==hq.ao_prog && hq.ao_prog){assert(fb==hq.ao_fbo[0] && tex[0]==hq.z_tex);ao_draws++;if(pass_fail==1)injected_error=GL_INVALID_OPERATION;} if(current_program==hq.ao_blur_prog && hq.ao_blur_prog){assert(fb==hq.ao_fbo[1] && tex[0]==hq.ao_tex[0]);blur_draws++;if(pass_fail==2)injected_error=GL_INVALID_OPERATION;}}
void glDrawElements(GLenum a,GLsizei b,GLenum c,const GLvoid*d){(void)a;(void)b;(void)c;(void)d;draws++;}
void glBlendFunc(GLenum a,GLenum b){(void)a;(void)b;}
void glDepthMask(GLboolean a){(void)a;} void glClear(GLbitfield a){(void)a;}
void glDiscardFramebufferEXT(GLenum a,GLsizei b,const GLenum*c){(void)a;(void)b;(void)c;}
static void setup(void){white_tex=2;memset(&hq,0,sizeof hq);memset(&blur,0,sizeof blur);frame_k=0;frame_wet=0;frame_env=1;ios_blur_active=ios_history=0;hq.on=1;hq.scale=1;hq.samples=hq.samples0=1;hq.bloom=.3f;hq.opt_paint=hq.opt_wet=1;ios_hq_status=1;fb=7;checks=0;fail=0;}
int main(void){setup();
for(int n=1;n<=6;n++){program_count=0;fail_program=n;assert(!render_hq(4,.3f));assert(render_hq_capability()==-1);}
program_count=0;fail_program=0;assert(render_hq(4,.3f));assert(render_hq_capability()==1);assert(hq.samples==1);
setup();render_blur_end();assert(fb==7&&draws==0);
assert(render_blur_begin(0,320,240));assert(ios_hq_status==2&&fb==hq.rt_fbo&&frame_k==0&&tex[FRAME_UNIT]==white_tex);GLuint first=color[fb];assert(first!=blur.tex);assert(!render_blur_begin(0,320,240));render_blur_end();assert(fb==7&&draws>0&&depth_tex==0);
assert(render_blur_begin(0,320,240));assert(color[fb]!=first&&tex[FRAME_UNIT]==first&&frame_k>0);render_blur_end();
hq.opt_paint=hq.opt_wet=0;assert(render_blur_begin(0,320,240));assert(tex[FRAME_UNIT]==white_tex&&tex[FRAME_UNIT]!=color[fb]);render_blur_end();
hq.opt_paint=hq.opt_wet=1;hq.level=7;assert(render_blur_begin(0,320,240));assert(tex[FRAME_UNIT]==white_tex&&tex[FRAME_UNIT]!=color[fb]);render_blur_end();
hq.level=0;assert(render_blur_begin(0,320,240));assert(tex[FRAME_UNIT]==blur.tex&&tex[FRAME_UNIT]!=color[fb]);render_blur_end();
for(int n=1;n<=6;n++){setup();fail=n;assert(!render_blur_begin(0,320,240));assert(fb==7&&ios_hq_status==-1&&!hq.on);}
setup();injected_error=GL_INVALID_OPERATION;assert(!render_blur_begin(0,320,240));assert(fb==7&&ios_hq_status==-1&&!hq.on);
setup();assert(render_blur_begin(0,320,240));injected_error=GL_INVALID_OPERATION;render_blur_end();assert(fb==7&&ios_hq_status==-1&&!hq.on);
setup();assert(render_blur_begin(0,320,240));fail=checks+1;render_blur_end();assert(fb==7&&ios_hq_status==-1&&!hq.on);
setup();assert(render_blur_begin(0,320,240));render_blur_end();fail=checks+1;assert(!render_blur_begin(0,320,240));assert(fb==7&&ios_hq_status==-1&&!hq.on);
setup();assert(render_blur_begin(0,320,240));render_blur_end();assert(render_blur_begin(0,640,480));assert(!ios_history&&frame_k==0&&tex[FRAME_UNIT]==white_tex&&tex[FRAME_UNIT]!=color[fb]);render_blur_end();
 extensions="GL_OES_packed_depth_stencil GL_OES_depth_texture";
 setup();ios_ssao_status=0;hq.opt_ao=1;render_ssao(1);assert(render_ssao_capability()==0);render_hq_view(1,20000,1,1);
 assert(render_blur_begin(0,320,240));assert(render_ssao_capability()==1 && hq.z_tex && depth[blur.fbo]==hq.z_tex && stencil[blur.fbo]==hq.z_tex && depth[hq.rt_fbo]==hq.z_tex && stencil[hq.rt_fbo]==hq.z_tex);assert(!bad_depth_format);
 int oldao=ao_draws, oldblur=blur_draws;render_blur_end();assert(ao_draws==oldao+1 && blur_draws==oldblur+1 && hq.on && hq.ao_on && !feedback);
 render_ssao(0); render_hq_view(1,20000,1,1); oldao=ao_draws; oldblur=blur_draws;
 assert(render_blur_begin(0,320,240));assert(tex[FRAME_UNIT]!=color[fb]);render_blur_end();assert(!feedback && !hq.ao_on && ao_draws==oldao && blur_draws==oldblur);
 ios_hq_status=-1; assert(render_ssao_capability()==RENDER_SSAO_FAILED); ios_hq_status=2;
 render_ssao(1);
 assert(render_blur_begin(0,640,480));assert(render_ssao_capability()==1 && !ios_history);render_blur_end();
 for(int n=7;n<=10;n++){setup();ios_ssao_status=0;ios_ssao_shader_failed=0;hq.opt_ao=1;render_ssao(1);fail=n;assert(render_blur_begin(0,320,240));assert(hq.on && render_ssao_capability()==-1 && !hq.z_tex && depth[blur.fbo]==blur.depth && stencil[hq.rt_fbo]==blur.depth);render_blur_end();assert(hq.on && !hq.ao_on);}
 setup();ios_ssao_status=0;ios_ssao_shader_failed=0;hq.opt_ao=1;render_ssao(1);render_hq_view(1,20000,1,1);assert(render_blur_begin(0,320,240));pass_fail=1;render_blur_end();pass_fail=0;assert(hq.on && render_ssao_capability()==-1 && !hq.ao_on);assert(render_blur_begin(0,320,240));render_blur_end();assert(hq.on && !hq.ao_on);
 for(int n=0;n<2;n++){setup();ios_ssao_status=0;ios_ssao_shader_failed=0;extensions=n?"GL_OES_packed_depth_stencil GL_OES_depth_texture_extra":"GL_OES_packed_depth_stencil";render_ssao(1);assert(render_ssao_capability()==-1 && !hq.ssao);assert(render_blur_begin(0,320,240));render_blur_end();assert(hq.on);}
 extensions="GL_OES_packed_depth_stencil GL_OES_depth_texture";setup();ios_ssao_status=0;ios_ssao_shader_failed=0;highp=0;render_ssao(1);assert(render_ssao_capability()==-1);highp=1;
 for(int n=1;n<=2;n++){setup();ios_ssao_status=0;ios_ssao_shader_failed=0;program_count=0;fail_program=n;render_ssao(1);assert(render_ssao_capability()==-1 && !hq.ao_prog && !hq.ao_blur_prog);fail_program=0;assert(render_blur_begin(0,320,240));render_blur_end();assert(hq.on);}
 for(int n=1;n<=7;n++){setup();ios_ssao_status=0;ios_ssao_shader_failed=0;attach_count=ao_images=0;inject_stage=n;render_ssao(1);assert(render_blur_begin(0,320,240));assert(render_ssao_capability()==-1 && hq.on && !hq.z_tex);inject_stage=0;render_blur_end();assert(hq.on && !hq.ao_on);}
 for(int n=0;n<2;n++){setup();ios_ssao_status=0;ios_ssao_shader_failed=0;zero_program=!n;zero_shader=n;render_ssao(1);zero_program=zero_shader=0;assert(render_ssao_capability()==-1 && !injected_error && !zero_shader_uses);assert(render_blur_begin(0,320,240));render_blur_end();assert(hq.on);}
 setup();ios_ssao_status=0;ios_ssao_shader_failed=0;injected_error=GL_INVALID_OPERATION;render_ssao(1);assert(ios_ssao_status==0 && hq.ssao>0);assert(render_blur_begin(0,320,240));protected_scene=hq.rt_tex;deleted_scene=0;injected_error=GL_INVALID_OPERATION;render_blur_end();assert(!deleted_scene && blur.tex==protected_scene && !hq.rt_tex && !hq.z_tex && !hq.ao_prog && render_ssao_capability()==-1);protected_scene=0;
 setup();extensions="GL_OES_packed_depth_stencil GL_OES_rgb8_rgba8 GL_APPLE_framebuffer_multisample";render_msaa_request(1,4);assert(render_msaa_capability()==1 && !render_msaa_samples());assert(render_blur_begin(0,320,240));assert(fb==hq.ms_fbo && !render_msaa_samples());int r=resolves;render_blur_end();assert(resolves==r+1 && render_msaa_capability()==2 && render_msaa_samples()==4 && fb==7);
 assert(render_blur_begin(0,640,480));assert(ios_msaa_requested && !render_msaa_samples());render_blur_end();assert(render_msaa_samples()==4);
 setup();render_msaa_request(0,4);extensions="GL_OES_packed_depth_stencil";render_msaa_request(1,4);assert(render_blur_begin(0,320,240));assert(fb==hq.rt_fbo && render_msaa_capability()==-1);render_blur_end();assert(hq.on&&ios_msaa_requested);
 extensions="GL_OES_packed_depth_stencil GL_OES_rgb8_rgba8 GL_APPLE_framebuffer_multisample";
 setup();render_msaa_request(0,4);render_msaa_request(1,4);fail_four=1;assert(render_blur_begin(0,320,240));render_blur_end();assert(render_msaa_samples()==2);fail_four=0;
 setup();render_msaa_request(0,4);render_msaa_request(1,4);fail_four=fail_two=1;assert(render_blur_begin(0,320,240));assert(render_msaa_capability()==-1&&fb==hq.rt_fbo);render_blur_end();assert(hq.on);fail_four=fail_two=0;
 setup();render_msaa_request(0,4);render_msaa_request(1,4);assert(render_blur_begin(0,320,240));GLuint saved_prev=blur.tex;int before_draws=draws;resolve_fail=1;render_blur_end();resolve_fail=0;assert(fb==7&&hq.on&&render_msaa_capability()==-1&&ios_msaa_requested&&blur.tex==saved_prev&&draws==before_draws);assert(render_blur_begin(0,320,240));assert(fb==hq.rt_fbo);render_blur_end();assert(hq.on&&!render_msaa_samples());
 setup();extensions="GL_OES_packed_depth_stencil GL_OES_depth_texture GL_OES_rgb8_rgba8 GL_APPLE_framebuffer_multisample";ios_ssao_status=0;ios_ssao_shader_failed=0;render_msaa_request(0,4);render_msaa_request(1,4);hq.opt_ao=1;render_ssao(1);assert(render_blur_begin(0,320,240));assert(render_msaa_capability()==3 && fb==hq.rt_fbo && !render_msaa_samples());render_blur_end();hq.ssao=0;assert(render_blur_begin(0,320,240));render_blur_end();assert(render_msaa_samples()==4);
 setup();render_msaa_request(0,4);render_msaa_request(1,4);max_samples=2;assert(render_blur_begin(0,320,240));render_blur_end();assert(render_msaa_samples()==2);max_samples=4;
 setup();render_msaa_request(0,4);render_msaa_request(1,4);ios_test_missing_msaa=1;assert(render_blur_begin(0,320,240));assert(render_msaa_capability()==-1 && fb==hq.rt_fbo);render_blur_end();ios_test_missing_msaa=0;
 setup();render_msaa_request(0,4);render_msaa_request(1,4);assert(render_blur_begin(0,320,240));render_blur_end();fail=checks+1;assert(render_blur_begin(0,320,240));assert(fb==hq.rt_fbo && render_msaa_capability()==-1);render_blur_end();assert(hq.on);
 /* Failed AA remains failed across enabling/disabling usable SSAO. */
 setup();extensions="GL_OES_packed_depth_stencil GL_OES_depth_texture GL_OES_rgb8_rgba8 GL_APPLE_framebuffer_multisample";ios_ssao_status=0;ios_ssao_shader_failed=0;render_ssao(1);hq.opt_ao=0;render_msaa_request(0,4);render_msaa_request(1,4);ios_test_missing_msaa=1;assert(render_blur_begin(0,320,240));render_blur_end();ios_test_missing_msaa=0;assert(render_msaa_capability()==-1);
 hq.opt_ao=1;assert(render_blur_begin(0,320,240));render_blur_end();assert(render_msaa_capability()==-1);hq.opt_ao=0;assert(render_blur_begin(0,320,240));render_blur_end();assert(render_msaa_capability()==-1 && ios_msaa_requested);
 /* Resolve failure must restore the output viewport despite scaled scene rendering. */
 setup();render_msaa_request(0,4);render_msaa_request(1,4);hq.scale=.5f;assert(render_blur_begin(0,640,480));glViewport(0,0,320,240);resolve_fail=1;render_blur_end();resolve_fail=0;assert(fb==7 && viewport_x==0 && viewport_y==0 && viewport_w==640 && viewport_h==480 && render_msaa_capability()==-1);
 /* HQ allocation failure takes precedence over AA pending when AA requested. */
 setup();render_msaa_request(0,4);render_msaa_request(1,4);fail=1;assert(!render_blur_begin(0,320,240));assert(render_hq_capability()==-1 && render_msaa_capability()==-1);
 assert(!delete_bound);
 puts("ios HQ mock pass");return 0;}
