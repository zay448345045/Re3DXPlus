/* Offline fixture: a disposable directory, never a game save. */
#include <TargetConditionals.h>
#undef TARGET_OS_IPHONE
#define TARGET_OS_IPHONE 1
#undef TARGET_OS_MACCATALYST
#define TARGET_OS_MACCATALYST 0
#include <OpenGL/gl3.h>
#define WMMT_GL_H
GLuint gl_compile_program(const char *, const char *, const char **, int);
#include "../src/app.c"
#include <assert.h>
static int seen = -1, ao_calls, hq_calls, ssao_cap, effective_ao = -1, aa_request, aa_samples;
static int msaa_cap, actual_samples, hq_cap = 2;
int render_msaa_capability(void) { return msaa_cap; }
int render_msaa_samples(void) { return actual_samples; }
int render_hq_capability(void) { return hq_cap; }
void render_msaa_request(int on, int samples) { aa_request = on; aa_samples = samples; }
int render_ssao_capability(void) { return ssao_cap; }
void render_enhance(int on) { seen = on; }
void render_ssao(float k) { (void)k; ++ao_calls; }
void render_hq_options(int b, int a, int p, int w) { (void)b; (void)p; (void)w; effective_ao = a; ++hq_calls; }
int main(void) {
  char dir[] = "/tmp/wmmt-ipad-graphics-XXXXXX";
  assert(mkdtemp(dir)); app_save_dir(dir); app_ipad_graphics();
  assert(G.ipad_graphics && !G.console);
  G.fb_w = 1024; G.fb_h = 768; G.menu.enhance_on = 1;
  app_resize(2048, 1536); assert(G.fb_w == 2048 && G.fb_h == 1536);
  app_resize(0, 768); app_resize(640, -1);
  assert(G.fb_w == 2048 && G.fb_h == 1536 && G.menu.enhance_on && G.ipad_graphics && !G.console);
  assert(!strcmp(G.save_dir, dir));
  G.menu.enhance_on = 1; hq_apply(); assert(seen == 1);
  G.menu.enhance_on = 0; hq_apply(); assert(seen == 0);
  assert(enhance_save()); G.menu.enhance_on = 1; enhance_load(); assert(!G.menu.enhance_on);
  char path[1200]; snprintf(path, sizeof path, "%s/enhanced_lighting", dir);
  FILE *f = fopen(path, "w"); assert(f); assert(fputs("enhanced_lighting 1 0 junk\n", f) >= 0); assert(!fclose(f));
  G.menu.enhance_on = 1; enhance_load(); assert(G.menu.enhance_on);
  G.menu.enhance_on = 0; assert(enhance_save());
  G.hq_on = 1; G.hq_bloom = -1; G.menu.ssao_on = 1; hq_apply();
  assert(ao_calls == 1 && hq_calls && !effective_ao && G.menu.ssao_on);
  assert(aa_request && aa_samples == 2); G.menu.aa4 = 1; hq_apply(); assert(aa_samples == 4 && G.menu.aa4);
  ssao_cap = RENDER_SSAO_AVAILABLE; hq_apply(); assert(effective_ao && G.menu.ssao_on);
  ssao_cap = RENDER_SSAO_FAILED; hq_apply(); assert(!effective_ao && G.menu.ssao_on);
  G.menu.ssao_on = 0; hq_apply(); G.menu.ssao_on = 1; hq_apply();
  assert(ao_calls == 1 && !effective_ao);
  msaa_cap = 1; ipad_graphics_sync(); assert(G.menu.hq_rows & 32);
  msaa_cap = 2; actual_samples = 2; ipad_graphics_sync(); assert((G.menu.hq_rows & 256) && G.menu.aa4);
  actual_samples = 4; ipad_graphics_sync(); assert(G.menu.hq_rows & 512);
  msaa_cap = 3; actual_samples = 0; ipad_graphics_sync(); assert(G.menu.hq_rows & 128);
  msaa_cap = -1; ipad_graphics_sync(); assert(G.menu.hq_rows & 64);
  hq_cap = 1; ipad_graphics_sync(); assert(!(G.menu.hq_rows & 1) && (G.menu.hq_rows & 4));
  assert(!unlink(path)); assert(!rmdir(dir));
  puts("iPad graphics persistence/app PASS");
}
