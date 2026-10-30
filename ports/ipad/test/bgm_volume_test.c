/* Host regression: compile with function/data sections and dead stripping. */
#include <GLES2/gl2.h>
#include <GLES2/gl2ext.h>
#include <math.h>
#include <fcntl.h>
#include <errno.h>
#include <stdarg.h>
#include <string.h>
#include <stdio.h>
static int deny_open, fail_rename;
static int test_open(const char *path, int flags, ...) {
  if (deny_open && strstr(path, "/bgm_card_")) { errno = EACCES; return -1; }
  if (flags & O_CREAT) { va_list ap; va_start(ap, flags); int mode = va_arg(ap, int); va_end(ap); return open(path, flags, mode); }
  return open(path, flags);
}
static int test_rename(const char *from, const char *to) {
  if (fail_rename && strstr(to, "/bgm_card_")) { errno = EACCES; return -1; }
  return rename(from, to);
}
#define open test_open
#define rename test_rename
#define WMMT_GL_H
GLuint gl_compile_program(const char *, const char *, const char **, int);
#include "../src/app.c"
#include <assert.h>

int main(void) {
  char dir[] = "/private/tmp/wmmt-bgm-test-XXXXXX", path[1100];
  assert(mkdtemp(dir)); app_save_dir(dir);
  G.menu.save_slot = 1; G.menu.n_own = 2; G.menu.own_sel = 0;
  G.menu.own[0] = (menu_own){0, 0, 0, 111, 0};
  G.menu.own[1] = (menu_own){0, 1, 0, 222, 0};
  assert(app_get_bgm_volume() == 3 && app_bgm_volume_multiplier() == 1.0f);
  const float gain[] = {0, 3.0f/7, 5.0f/7, 1};
  for (int i = 0; i < 4; ++i) {
    assert(app_set_bgm_volume(i)); bgm_load();
    assert(app_get_bgm_volume() == i);
    assert(fabsf(app_bgm_volume_multiplier() - gain[i]) < 0.00001f);
  }
  assert(app_set_bgm_volume(1));
  /* Preview car must not change the active card. */
  G.menu.maker = 0; G.menu.car = 1;
  assert(app_get_bgm_volume() == 1);
  G.menu.own_sel = 1; assert(app_get_bgm_volume() == 3); assert(app_set_bgm_volume(2));
  G.menu.save_slot = 2; assert(app_get_bgm_volume() == 3); assert(app_set_bgm_volume(0));
  G.menu.save_slot = 1; assert(app_get_bgm_volume() == 2);
  G.menu.own_sel = 0; assert(app_get_bgm_volume() == 1);
  assert(bgm_path(path, sizeof path));
  FILE *f = fopen(path, "w"); assert(f); assert(fputs("bgm1 1\nBAD", f) >= 0); assert(!fclose(f));
  int before = bgm_level; char previous[1100]; strcpy(previous, bgm_current_path);
  assert(!app_set_bgm_volume(2)); assert(bgm_level == before && !strcmp(previous, bgm_current_path));
  char contents[32] = {0}; f = fopen(path, "r"); assert(f); assert(fread(contents, 1, sizeof contents, f) == 10); assert(!fclose(f)); assert(!memcmp(contents, "bgm1 1\nBAD", 10));
  bgm_load(); assert(app_get_bgm_volume() == 3);
  assert(!unlink(path)); assert(!symlink("/dev/null", path)); bgm_load(); assert(app_get_bgm_volume() == 3);
  assert(!app_set_bgm_volume(2)); struct stat st; assert(!lstat(path, &st) && S_ISLNK(st.st_mode));
  assert(!unlink(path)); assert(!mkdir(path, 0700));
  before = bgm_level; strcpy(previous, bgm_current_path);
  assert(!app_set_bgm_volume(2)); assert(bgm_level == before && !strcmp(previous, bgm_current_path));
  assert(!rmdir(path)); assert(app_set_bgm_volume(1));
  deny_open = 1; before = bgm_level; strcpy(previous, bgm_current_path);
  assert(!app_set_bgm_volume(2)); assert(bgm_level == before && !strcmp(previous, bgm_current_path)); deny_open = 0;
  fail_rename = 1; assert(!app_set_bgm_volume(2)); fail_rename = 0;
  bgm_load(); assert(app_get_bgm_volume() == 1);
  /* Failed setter before getter must not carry the previous car's cache. */
  G.menu.own_sel = 1; assert(app_get_bgm_volume() == 2);
  G.menu.own_sel = 0; deny_open = 1; assert(!app_set_bgm_volume(0)); deny_open = 0;
  assert(app_get_bgm_volume() == 1);
  /* Explicit removal followed by same-second re-registration. */
  bgm_erase_card(1, &G.menu.own[0]); assert(app_get_bgm_volume() == 3);
  assert(app_set_bgm_volume(2));
  assert(bgm_path(path, sizeof path)); assert(!unlink(path)); assert(!mkdir(path, 0700));
  bgm_erase_card(1, &G.menu.own[0]); assert(app_get_bgm_volume() == 3); assert(!app_set_bgm_volume(1));
  assert(!rmdir(path));
  G.menu.own_sel = -1; before = bgm_level; strcpy(previous, bgm_current_path);
  assert(!app_set_bgm_volume(1)); assert(bgm_level == before && !strcmp(previous, bgm_current_path));
  G.menu.own_sel = 1; assert(app_get_bgm_volume() == 2);
  bgm_erase(1); bgm_erase(2); assert(!rmdir(dir));
  return 0;
}
