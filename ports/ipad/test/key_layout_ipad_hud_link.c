#include <TargetConditionals.h>
#undef TARGET_OS_IPHONE
#define TARGET_OS_IPHONE 1
#include "glstub.h"
#define WMMT_GL_H
#define GL_ONE_MINUS_DST_COLOR 0x0307
#define GL_ZERO 0
GLuint gl_compile_program(const char *, const char *, const char **, int);
#include "../src/hud.c"
