#!/usr/bin/env python3
"""CGL desktop GL synthetic postprocessing diagnostic; not iOS or GLES."""
import ast,pathlib,re,subprocess,tempfile
source=(pathlib.Path(__file__).resolve().parents[1]/'src/render.c').read_text()
def extract(name):
 m=re.search(r'static const char \*'+name+r'\s*=\s*(.*?);\s*$',source,re.M|re.S)
 return ''.join(ast.literal_eval(x) for x in re.findall(r'"(?:\\.|[^"\\])*"',m.group(1)))
def quote(s):
 s=re.sub(r'precision\s+(?:lowp|mediump|highp)\s+float\s*;', '',s)
 return '"'+s.replace('\\','\\\\').replace('"','\\"').replace('\n','\\n')+'"'
c=r"""
#include <OpenGL/OpenGL.h>
#include <OpenGL/gl.h>
#include <OpenGL/glext.h>
#include <stdio.h>
#include <stdlib.h>
#define C(x) do {if(!(x)){fprintf(stderr,"FAIL line %d GL %x\n",__LINE__,glGetError());exit(1);}}while(0)
static const char *vs=VS_CODE,*fs=FS_CODE,*fs_plain=PLAIN_CODE,*up=UP_CODE;
static GLuint prog(const char *f){GLuint v=glCreateShader(GL_VERTEX_SHADER),s=glCreateShader(GL_FRAGMENT_SHADER),p=glCreateProgram(); GLint ok;
 glShaderSource(v,1,&vs,0);glCompileShader(v);glGetShaderiv(v,GL_COMPILE_STATUS,&ok);C(ok);
 glShaderSource(s,1,&f,0);glCompileShader(s);glGetShaderiv(s,GL_COMPILE_STATUS,&ok);if(!ok){char b[2048];glGetShaderInfoLog(s,2048,0,b);fprintf(stderr,"%s\n",b);}C(ok);
 glAttachShader(p,v);glAttachShader(p,s);glBindAttribLocation(p,0,"aPos");glLinkProgram(p);glGetProgramiv(p,GL_LINK_STATUS,&ok);C(ok);return p;}
static void target(GLuint *t,GLuint *f,int n,const unsigned char *data){glGenTextures(1,t);glBindTexture(GL_TEXTURE_2D,*t);glTexParameteri(GL_TEXTURE_2D,GL_TEXTURE_MIN_FILTER,GL_LINEAR);glTexParameteri(GL_TEXTURE_2D,GL_TEXTURE_MAG_FILTER,GL_LINEAR);glTexParameteri(GL_TEXTURE_2D,GL_TEXTURE_WRAP_S,GL_CLAMP_TO_EDGE);glTexParameteri(GL_TEXTURE_2D,GL_TEXTURE_WRAP_T,GL_CLAMP_TO_EDGE);glTexImage2D(GL_TEXTURE_2D,0,GL_RGBA8,n,n,0,GL_RGBA,GL_UNSIGNED_BYTE,data);glGenFramebuffersEXT(1,f);glBindFramebufferEXT(GL_FRAMEBUFFER_EXT,*f);glFramebufferTexture2DEXT(GL_FRAMEBUFFER_EXT,GL_COLOR_ATTACHMENT0_EXT,GL_TEXTURE_2D,*t,0);C(glCheckFramebufferStatusEXT(GL_FRAMEBUFFER_EXT)==GL_FRAMEBUFFER_COMPLETE_EXT);}
static void draw(GLuint p,GLuint f,GLuint t,int n,float texel){float q[]={-1,-1,1,-1,-1,1,1,1};glBindFramebufferEXT(GL_FRAMEBUFFER_EXT,f);glViewport(0,0,n,n);glUseProgram(p);glActiveTexture(GL_TEXTURE0);glBindTexture(GL_TEXTURE_2D,t);glUniform1i(glGetUniformLocation(p,"uTex"),0);glUniform2f(glGetUniformLocation(p,"uTexel"),texel,texel);glUniform1f(glGetUniformLocation(p,"uThresh"),.75);glEnableVertexAttribArray(0);glVertexAttribPointer(0,2,GL_FLOAT,0,0,q);glDrawArrays(GL_TRIANGLE_STRIP,0,4);glDisableVertexAttribArray(0);C(glGetError()==0);}
static int pixel(GLuint f,int n){unsigned char p[4];glBindFramebufferEXT(GL_FRAMEBUFFER_EXT,f);glReadPixels(n/2,n/2,1,1,GL_RGBA,GL_UNSIGNED_BYTE,p);C(glGetError()==0);return p[0];}
int main(void){CGLPixelFormatAttribute a[]={kCGLPFAAccelerated,kCGLPFAColorSize,(CGLPixelFormatAttribute)24,0};CGLPixelFormatObj f;CGLContextObj c;GLint n;C(CGLChoosePixelFormat(a,&f,&n)==0&&n);C(CGLCreateContext(f,0,&c)==0);C(CGLSetCurrentContext(c)==0);printf("Desktop renderer %s; %s\n",glGetString(GL_RENDERER),glGetString(GL_VERSION));GLuint d=prog(fs),plain=prog(fs_plain),u=prog(up),t[3],fb[3];unsigned char data[16*16*4];for(int i=0;i<sizeof(data);i++)data[i]=255;target(t,fb,16,data);target(t+1,fb+1,8,0);target(t+2,fb+2,4,0);glDisable(GL_BLEND);draw(d,fb[1],t[0],8,1.f/16);int bright=pixel(fb[1],8);C(bright>20);draw(plain,fb[2],t[1],4,1.f/8);glEnable(GL_BLEND);glBlendFunc(GL_ONE,GL_ONE);draw(u,fb[1],t[2],8,1.f/4);glDisable(GL_BLEND);int add=pixel(fb[1],8);C(add>bright);C(pixel(fb[0],16)==255);for(int i=0;i<sizeof(data);i++)data[i]=0;glBindTexture(GL_TEXTURE_2D,t[0]);glTexSubImage2D(GL_TEXTURE_2D,0,0,0,16,16,GL_RGBA,GL_UNSIGNED_BYTE,data);draw(d,fb[1],t[0],8,1.f/16);int dark=pixel(fb[1],8);C(dark<=1&&bright>dark+20);printf("PASS scene preserved; bloom bright=%d dark=%d up=%d\n",bright,dark,add);CGLSetCurrentContext(0);CGLDestroyContext(c);CGLDestroyPixelFormat(f);return 0;}
"""
c=c.replace('VS_CODE',quote(extract('VS_POST'))).replace('FS_CODE',quote('#define BRIGHT 1\n'+extract('FS_DOWN'))).replace('PLAIN_CODE',quote('#define BRIGHT 0\n'+extract('FS_DOWN'))).replace('UP_CODE',quote(extract('FS_UP')))
with tempfile.TemporaryDirectory(prefix='cgl-bloom-') as t:
 p=pathlib.Path(t);(p/'test.c').write_text(c);subprocess.run(['cc','-Wno-deprecated-declarations',str(p/'test.c'),'-framework','OpenGL','-o',str(p/'test')],check=True);subprocess.run([str(p/'test')],check=True)
