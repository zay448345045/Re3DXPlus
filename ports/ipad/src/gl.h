/* GLES2 include shim: the real headers on iOS, Mesa's for the desktop screenshots
 * (test/menushot.c, -DWMMT_EGL), vkgl's calls on Vulkan (Android's, -DWMMT_VK: vkgl.h), a
 * declaration-only stub for syntax checks (test/glstub.h). */
#ifndef WMMT_GL_H
#define WMMT_GL_H

#ifdef __APPLE__
#include <OpenGLES/ES2/gl.h>
#include <OpenGLES/ES2/glext.h>
#elif defined(WMMT_VK)
#include <GLES2/gl2.h>
#include <GLES2/gl2ext.h>
#include <EGL/egl.h>
#include "vkgl.h"
#elif defined(WMMT_EGL)
#include <GLES2/gl2.h>
#include <GLES2/gl2ext.h>
/* iOS has OES_vertex_array_object's functions to link with; Mesa's are looked up (render.c) */
extern PFNGLGENVERTEXARRAYSOESPROC wmmt_glGenVertexArraysOES;
extern PFNGLBINDVERTEXARRAYOESPROC wmmt_glBindVertexArrayOES;
extern PFNGLDELETEVERTEXARRAYSOESPROC wmmt_glDeleteVertexArraysOES;
#define glGenVertexArraysOES wmmt_glGenVertexArraysOES
#define glBindVertexArrayOES wmmt_glBindVertexArrayOES
#define glDeleteVertexArraysOES wmmt_glDeleteVertexArraysOES
#else
#include "glstub.h"
#endif

#include <math.h>

GLuint gl_compile_program(const char *vs, const char *fs, const char **attribs, int n_attribs);

#endif
