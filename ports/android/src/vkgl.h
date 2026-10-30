/* vkgl: the part of OpenGL ES the port uses, on Vulkan (Android's renderer, -DWMMT_VK; iOS
 * keeps GLES). gl.h renames the game's gl* calls to these. One device, one queue; the game's
 * thread draws, the loading thread (vkgl_thread_loader) only makes things (its draws warm
 * pipelines). The programs come as SPIR-V made ahead by tools/vkglsl.py (vkgl_spv.c), known
 * by the hash of their source; a desktop build can make missing ones at run time
 * (VKGL_SPV_DIR). A frame is recorded as a list of passes and replayed at its end (or at a
 * glFinish / glReadPixels), when what each attachment needs loaded and stored is known. */
#ifndef WMMT_VKGL_H
#define WMMT_VKGL_H

#include <GLES2/gl2.h>
#include <stdint.h>
#include <vulkan/vulkan.h>

typedef struct {
  const char *refl; /* "key size inputmask name:code:offset ..." (vkglsl.py refl_text) */
  const uint32_t *vs;
  int n_vs;
  const uint32_t *fs;
  int n_fs;
  /* the same with every precision highp, tried when a driver won't make a pipeline of the first */
  const uint32_t *vs2;
  int n_vs2;
  const uint32_t *fs2;
  int n_fs2;
} vkgl_spv;
extern const vkgl_spv VKGL_SPV[];
extern const int VKGL_N_SPV;

/* the instance with these extensions (the surface's), the device, the queue; 0 or -1 */
int vkgl_create(const char *const *inst_ext, int n_ext);
VkInstance vkgl_instance(void);
/* the screen (framebuffer 0): a swapchain on surface, or with VK_NULL_HANDLE an image of
 * w x h of its own (the desktop harness); again for a new surface or size. 0 or -1 */
int vkgl_surface(VkSurfaceKHR surface, int w, int h);
void vkgl_release_surface(void); /* the window going away: the swapchain and surface freed */
void vkgl_screen_size(int *w, int *h);
/* the frame to the GPU and the screen: 0, 1 if the swapchain needs making again, -1 lost */
int vkgl_present(void);
void vkgl_thread_loader(void); /* this thread is the loading one */
void vkgl_pipeline_cache_file(const char *path); /* where the pipelines are kept between runs */
void vkgl_pipeline_cache_save(void);
GLuint vkgl_program(const char *vs, const char *fs, const char **attribs, int n_attribs);
/* Checks shader modules, not eventual pipeline creation. */
int vkgl_program_usable(GLuint id);
/* Single-sample depth/stencil texture capability; not an MSRT2 capability. */
int vkgl_ssao_depth_supported(int w, int h);
void (*vkgl_get_proc(const char *name))(void);

#define VKGL_FN(ret, name, args) ret vkgl_##name args;
#define VKGL_FUNCS                                                                                              \
  VKGL_FN(void, glActiveTexture, (GLenum))                                                                       \
  VKGL_FN(void, glBindBuffer, (GLenum, GLuint))                                                                  \
  VKGL_FN(void, glBindFramebuffer, (GLenum, GLuint))                                                             \
  VKGL_FN(void, glBindRenderbuffer, (GLenum, GLuint))                                                            \
  VKGL_FN(void, glBindTexture, (GLenum, GLuint))                                                                 \
  VKGL_FN(void, glBlendEquation, (GLenum))                                                                       \
  VKGL_FN(void, glBlendFunc, (GLenum, GLenum))                                                                   \
  VKGL_FN(void, glBufferData, (GLenum, GLsizeiptr, const void *, GLenum))                                        \
  VKGL_FN(void, glBufferSubData, (GLenum, GLintptr, GLsizeiptr, const void *))                                   \
  VKGL_FN(GLenum, glCheckFramebufferStatus, (GLenum))                                                            \
  VKGL_FN(void, glClear, (GLbitfield))                                                                           \
  VKGL_FN(void, glClearColor, (GLfloat, GLfloat, GLfloat, GLfloat))                                              \
  VKGL_FN(void, glColorMask, (GLboolean, GLboolean, GLboolean, GLboolean))                                       \
  VKGL_FN(void, glCompressedTexImage2D, (GLenum, GLint, GLenum, GLsizei, GLsizei, GLint, GLsizei, const void *)) \
  VKGL_FN(void, glCullFace, (GLenum))                                                                            \
  VKGL_FN(void, glDeleteBuffers, (GLsizei, const GLuint *))                                                      \
  VKGL_FN(void, glDeleteFramebuffers, (GLsizei, const GLuint *))                                                 \
  VKGL_FN(void, glDeleteProgram, (GLuint))                                                                       \
  VKGL_FN(void, glDeleteRenderbuffers, (GLsizei, const GLuint *))                                                \
  VKGL_FN(void, glDeleteTextures, (GLsizei, const GLuint *))                                                     \
  VKGL_FN(void, glDepthFunc, (GLenum))                                                                           \
  VKGL_FN(void, glDepthMask, (GLboolean))                                                                        \
  VKGL_FN(void, glDisable, (GLenum))                                                                             \
  VKGL_FN(void, glDisableVertexAttribArray, (GLuint))                                                            \
  VKGL_FN(void, glDiscardFramebufferEXT, (GLenum, GLsizei, const GLenum *))                                      \
  VKGL_FN(void, glDrawArrays, (GLenum, GLint, GLsizei))                                                          \
  VKGL_FN(void, glDrawElements, (GLenum, GLsizei, GLenum, const void *))                                         \
  VKGL_FN(void, glEnable, (GLenum))                                                                              \
  VKGL_FN(void, glEnableVertexAttribArray, (GLuint))                                                             \
  VKGL_FN(void, glFinish, (void))                                                                                \
  VKGL_FN(void, glFlush, (void))                                                                                 \
  VKGL_FN(void, glFramebufferRenderbuffer, (GLenum, GLenum, GLenum, GLuint))                                     \
  VKGL_FN(void, glFramebufferTexture2D, (GLenum, GLenum, GLenum, GLuint, GLint))                                 \
  VKGL_FN(void, glFrontFace, (GLenum))                                                                           \
  VKGL_FN(void, glGenBuffers, (GLsizei, GLuint *))                                                               \
  VKGL_FN(void, glGenFramebuffers, (GLsizei, GLuint *))                                                          \
  VKGL_FN(void, glGenRenderbuffers, (GLsizei, GLuint *))                                                         \
  VKGL_FN(void, glGenTextures, (GLsizei, GLuint *))                                                              \
  VKGL_FN(void, glGenerateMipmap, (GLenum))                                                                      \
  VKGL_FN(void, glGetBooleanv, (GLenum, GLboolean *))                                                            \
  VKGL_FN(GLenum, glGetError, (void))                                                                            \
  VKGL_FN(void, glGetFloatv, (GLenum, GLfloat *))                                                                \
  VKGL_FN(void, glGetIntegerv, (GLenum, GLint *))                                                                \
  VKGL_FN(const GLubyte *, glGetString, (GLenum))                                                                \
  VKGL_FN(GLint, glGetUniformLocation, (GLuint, const GLchar *))                                                 \
  VKGL_FN(void, glPixelStorei, (GLenum, GLint))                                                                  \
  VKGL_FN(void, glReadPixels, (GLint, GLint, GLsizei, GLsizei, GLenum, GLenum, void *))                          \
  VKGL_FN(void, glRenderbufferStorage, (GLenum, GLenum, GLsizei, GLsizei))                                       \
  VKGL_FN(void, glScissor, (GLint, GLint, GLsizei, GLsizei))                                                     \
  VKGL_FN(void, glStencilFunc, (GLenum, GLint, GLuint))                                                          \
  VKGL_FN(void, glStencilMask, (GLuint))                                                                         \
  VKGL_FN(void, glStencilOp, (GLenum, GLenum, GLenum))                                                           \
  VKGL_FN(void, glTexImage2D, (GLenum, GLint, GLint, GLsizei, GLsizei, GLint, GLenum, GLenum, const void *))     \
  VKGL_FN(void, glTexParameterf, (GLenum, GLenum, GLfloat))                                                      \
  VKGL_FN(void, glTexParameteri, (GLenum, GLenum, GLint))                                                        \
  VKGL_FN(void, glUniform1f, (GLint, GLfloat))                                                                   \
  VKGL_FN(void, glUniform1i, (GLint, GLint))                                                                     \
  VKGL_FN(void, glUniform2f, (GLint, GLfloat, GLfloat))                                                          \
  VKGL_FN(void, glUniform3f, (GLint, GLfloat, GLfloat, GLfloat))                                                 \
  VKGL_FN(void, glUniform3fv, (GLint, GLsizei, const GLfloat *))                                                 \
  VKGL_FN(void, glUniform4f, (GLint, GLfloat, GLfloat, GLfloat, GLfloat))                                        \
  VKGL_FN(void, glUniform4fv, (GLint, GLsizei, const GLfloat *))                                                 \
  VKGL_FN(void, glUniformMatrix4fv, (GLint, GLsizei, GLboolean, const GLfloat *))                                \
  VKGL_FN(void, glUseProgram, (GLuint))                                                                          \
  VKGL_FN(void, glVertexAttrib4f, (GLuint, GLfloat, GLfloat, GLfloat, GLfloat))                                  \
  VKGL_FN(void, glVertexAttribPointer, (GLuint, GLint, GLenum, GLboolean, GLsizei, const void *))                \
  VKGL_FN(void, glViewport, (GLint, GLint, GLsizei, GLsizei))                                                    \
  VKGL_FN(void, glGenVertexArraysOES, (GLsizei, GLuint *))                                                       \
  VKGL_FN(void, glBindVertexArrayOES, (GLuint))                                                                  \
  VKGL_FN(void, glDeleteVertexArraysOES, (GLsizei, const GLuint *))                                              \
  VKGL_FN(void, glBlitFramebuffer, (GLint, GLint, GLint, GLint, GLint, GLint, GLint, GLint, GLbitfield, GLenum)) \
  VKGL_FN(void, glRenderbufferStorageMultisample, (GLenum, GLsizei, GLenum, GLsizei, GLsizei))                   \
  VKGL_FN(void, glInvalidateFramebuffer, (GLenum, GLsizei, const GLenum *))                                      \
  VKGL_FN(void, glFramebufferTexture2DMultisampleEXT, (GLenum, GLenum, GLenum, GLuint, GLint, GLsizei))
VKGL_FUNCS
#undef VKGL_FN

#ifndef VKGL_IMPL
#define glActiveTexture vkgl_glActiveTexture
#define glBindBuffer vkgl_glBindBuffer
#define glBindFramebuffer vkgl_glBindFramebuffer
#define glBindRenderbuffer vkgl_glBindRenderbuffer
#define glBindTexture vkgl_glBindTexture
#define glBlendEquation vkgl_glBlendEquation
#define glBlendFunc vkgl_glBlendFunc
#define glBufferData vkgl_glBufferData
#define glBufferSubData vkgl_glBufferSubData
#define glCheckFramebufferStatus vkgl_glCheckFramebufferStatus
#define glClear vkgl_glClear
#define glClearColor vkgl_glClearColor
#define glColorMask vkgl_glColorMask
#define glCompressedTexImage2D vkgl_glCompressedTexImage2D
#define glCullFace vkgl_glCullFace
#define glDeleteBuffers vkgl_glDeleteBuffers
#define glDeleteFramebuffers vkgl_glDeleteFramebuffers
#define glDeleteProgram vkgl_glDeleteProgram
#define glDeleteRenderbuffers vkgl_glDeleteRenderbuffers
#define glDeleteTextures vkgl_glDeleteTextures
#define glDepthFunc vkgl_glDepthFunc
#define glDepthMask vkgl_glDepthMask
#define glDisable vkgl_glDisable
#define glDisableVertexAttribArray vkgl_glDisableVertexAttribArray
#define glDiscardFramebufferEXT vkgl_glDiscardFramebufferEXT
#define glDrawArrays vkgl_glDrawArrays
#define glDrawElements vkgl_glDrawElements
#define glEnable vkgl_glEnable
#define glEnableVertexAttribArray vkgl_glEnableVertexAttribArray
#define glFinish vkgl_glFinish
#define glFlush vkgl_glFlush
#define glFramebufferRenderbuffer vkgl_glFramebufferRenderbuffer
#define glFramebufferTexture2D vkgl_glFramebufferTexture2D
#define glFrontFace vkgl_glFrontFace
#define glGenBuffers vkgl_glGenBuffers
#define glGenFramebuffers vkgl_glGenFramebuffers
#define glGenRenderbuffers vkgl_glGenRenderbuffers
#define glGenTextures vkgl_glGenTextures
#define glGenerateMipmap vkgl_glGenerateMipmap
#define glGetBooleanv vkgl_glGetBooleanv
#define glGetError vkgl_glGetError
#define glGetFloatv vkgl_glGetFloatv
#define glGetIntegerv vkgl_glGetIntegerv
#define glGetString vkgl_glGetString
#define glGetUniformLocation vkgl_glGetUniformLocation
#define glPixelStorei vkgl_glPixelStorei
#define glReadPixels vkgl_glReadPixels
#define glRenderbufferStorage vkgl_glRenderbufferStorage
#define glScissor vkgl_glScissor
#define glStencilFunc vkgl_glStencilFunc
#define glStencilMask vkgl_glStencilMask
#define glStencilOp vkgl_glStencilOp
#define glTexImage2D vkgl_glTexImage2D
#define glTexParameterf vkgl_glTexParameterf
#define glTexParameteri vkgl_glTexParameteri
#define glUniform1f vkgl_glUniform1f
#define glUniform1i vkgl_glUniform1i
#define glUniform2f vkgl_glUniform2f
#define glUniform3f vkgl_glUniform3f
#define glUniform3fv vkgl_glUniform3fv
#define glUniform4f vkgl_glUniform4f
#define glUniform4fv vkgl_glUniform4fv
#define glUniformMatrix4fv vkgl_glUniformMatrix4fv
#define glUseProgram vkgl_glUseProgram
#define glVertexAttrib4f vkgl_glVertexAttrib4f
#define glVertexAttribPointer vkgl_glVertexAttribPointer
#define glViewport vkgl_glViewport
#define glGenVertexArraysOES vkgl_glGenVertexArraysOES
#define glBindVertexArrayOES vkgl_glBindVertexArrayOES
#define glDeleteVertexArraysOES vkgl_glDeleteVertexArraysOES
#define eglGetProcAddress(name) vkgl_get_proc(name)
#endif

#endif
