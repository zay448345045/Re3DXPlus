#include <GLES2/gl2.h>
#include <GLES2/gl2ext.h>
#define WMMT_GL_H
GLuint gl_compile_program(const char *, const char *, const char **, int);
#include "../src/app.c"
#include <assert.h>
int menu_card_choice_available(const menu_state *m, int row, int choice) {
  return m && row == 0 && choice >= 0 && choice <= 1;
}
int main(void) {
  char dir[] = "/private/tmp/wmmt-card-commit-XXXXXX";
  assert(mkdtemp(dir)); app_save_dir(dir);
  G.menu.save_slot = 1; G.menu.n_own = 2; G.menu.own_sel = 0;
  G.menu.own[0] = (menu_own){0, 0, 0, 111, 0};
  G.menu.own[1] = (menu_own){0, 1, 0, 222, 0};
  G.menu.maker = 0; G.menu.car = 0;
  card_choice_load(); assert(!G.menu.card_choice_error);
  assert(app_card_choice_commit(&G.menu, 0, 1, 111));
  assert(G.menu.meter_car[0][0] == 1 && G.menu.card_born[0][0] == 111);
  G.menu.maker = 0; G.menu.car = 1; G.menu.own_sel = 1;
  assert(app_card_choice_commit(&G.menu, 0, 1, 222));
  card_choice_clear(); card_choice_load();
  assert(G.menu.meter_car[0][0] == 1 && G.menu.meter_car[0][1] == 1);
  char path[1100]; assert(cc_path(path, sizeof path, dir, 1, ""));
  FILE *f = fopen(path, "wb"); assert(f); assert(fwrite("bad", 1, 3, f) == 3); assert(!fclose(f));
  G.menu.meter_car[0][1] = 0; G.menu.card_born[0][1] = 222;
  assert(!app_card_choice_commit(&G.menu, 0, 1, 222));
  assert(G.menu.meter_car[0][1] == 0 && G.menu.card_born[0][1] == 222);
  f = fopen(path, "rb"); assert(f); char b[4] = {0}; assert(fread(b, 1, 3, f) == 3 && !memcmp(b, "bad", 3)); assert(!fclose(f));
  G.n_car_best = 3;
  G.car_best[0].course = 0; G.car_best[0].pack = 7; G.car_best[0].ms = 123456;
  G.car_best[1].course = 0; G.car_best[1].pack = 7; G.car_best[1].ms = 125000;
  G.car_best[2].course = 0; G.car_best[2].pack = 8; G.car_best[2].ms = 110000;
  assert(app_model_ta_best_ms(7, 0) == 123456);
  assert(app_model_ta_best_ms(8, 0) == 110000 && app_model_ta_best_ms(7, 1) == 0);
  G.menu.save_slot = 0; assert(app_model_ta_best_ms(7, 0) == 0);
  puts("card commit and per-model TA record checks passed");
  return 0;
}
