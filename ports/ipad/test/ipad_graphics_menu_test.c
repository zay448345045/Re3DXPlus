#include <TargetConditionals.h>
#undef TARGET_OS_IPHONE
#define TARGET_OS_IPHONE 1
#include "glstub.h"
#define WMMT_GL_H
#include "../src/menu.c"
#include <assert.h>
int anm_sprite(int n) { return n; }
float anm_sprite_width(int n) { (void)n; return 35; }
/* Same 5x7 glyph advance as hud.c; includes no mock shrinkage. */
float hud_ui_text_width(const char *s, float p) { size_t n = strlen(s); return n ? (6 * n - 1) * p : 0; }
void snd_menu(int n) { (void)n; }
static float ao_on_alpha, ao_off_alpha;
void anm_draw_sprite(int s, float x, float y, float a) {
  if (y == OPT_HQ_Y + OPT_HQ_DY - 15 && x >= 500 && s == OPT_TEXT + O_ON) ao_on_alpha = a;
  if (y == OPT_HQ_Y + OPT_HQ_DY - 15 && x >= 500 && s == OPT_TEXT + O_OFF) ao_off_alpha = a;
}
int main(void) {
  menu_state m = {0}; m.res_row=1; m.hq_rows=2; m.enhance_on=1;
  m.tap_x=280; m.tap_y=403; option_step(&m,1,0); assert(!m.enhance_on && m.enhance_changed);
  m.tap_x=301; m.tap_y=376; option_step(&m,1,0); assert(!m.enhance_on && !m.hd_tex);
  m.hq_rows=3; m.tap_x=501; m.tap_y=403; option_step(&m,1,0); assert(m.hd_tex && !m.enhance_on);
  m.tap_x=501; m.tap_y=311; option_step(&m,1,0); assert(m.ssao_on);
  m.hq_rows=3|8; draw_option_hq(&m); assert(ao_on_alpha == 0.3f && ao_off_alpha == 0.3f);
  m.hq_rows=3; draw_option_hq(&m); assert(ao_on_alpha == 1.0f && ao_off_alpha == 0.3f);
  m.hq_rows=3|16; draw_option_hq(&m); assert(ao_on_alpha == 0.3f && ao_off_alpha == 0.3f);
  m.tap_x=570; option_step(&m,1,0); assert(!m.ssao_on);
  m.tap_x=501; option_step(&m,1,0); assert(!m.ssao_on);
  m.tap_x=501; m.tap_y=380; option_step(&m,1,0); assert(!m.aa4);
  m.tap_x=221; m.tap_y=403; option_step(&m,1,0); assert(m.enhance_on && m.hd_tex);
  m.hq_rows=3|256; assert(!strcmp(option_aa_status(&m), "AA ACTUAL 2X"));
  m.tap_x=501; m.tap_y=247; option_step(&m,1,0); assert(m.aa4 && m.hd_tex && m.enhance_on);
  assert(!strcmp(option_aa_status(&m), "AA ACTUAL 2X")); /* preference is not actual */
  m.tap_x=570; option_step(&m,1,0); assert(!m.aa4);
  m.hq_rows=3|512; assert(!strcmp(option_aa_status(&m), "AA ACTUAL 4X"));
  m.hq_rows=3|128; assert(!strcmp(option_aa_status(&m), "AA SSAO PAUSED"));
  m.hq_rows=3|32; assert(!strcmp(option_aa_status(&m), "AA CHECKING"));
  m.hq_rows=3|64; assert(!strcmp(option_aa_status(&m), "AA UNAVAILABLE"));
  m.hq_rows=3; assert(!strcmp(option_aa_status(&m), "AA OFF"));
  assert(332 * 1.6f + hud_ui_text_width("START RACE TO CHECK HQ", 2) + 2 < 1024);
  assert(332 * 1.6f + hud_ui_text_width("AA SSAO PAUSED", 2) + 2 < 1024);
  assert(130 * 1.6f + hud_ui_text_width("SSAO UNAVAILABLE", 2) + 2 < 332 * 1.6f);
  assert(332 * 1.6f + hud_ui_text_width("AA REQUEST", 2) + 2 < 500 * 1.6f);
  assert(247 + OPT_HQ_HALF < OPT_HQ_Y - OPT_HQ_HALF);
  /* Real HUD glyph advance determines resolution bounds, not a guessed width. */
  float rx[2], rw[2]; option_res_chips(rx, rw);
  assert(490 >= rx[1] - SET_CHIP_GAP * .5f && 490 < rx[1] + rw[1] + SET_CHIP_GAP * .5f);
  m.hq_rows=3; m.hires=0; m.paint_on=0; m.tap_x=490; m.tap_y=366;
  option_step(&m,1,0); assert(m.hires == 1 && !m.paint_on);
  option_step(&m,1,0); assert(m.hires == 1 && !m.paint_on); /* selected still consumes */
  m.hires=0; m.paint_on=0; m.tap_y=357; option_step(&m,1,0); assert(!m.hires && m.paint_on);
  m.paint_on=0; m.tap_y=376; option_step(&m,1,0); assert(m.hires == 1 && !m.paint_on);
  puts("iPad graphics menu PASS");
}
