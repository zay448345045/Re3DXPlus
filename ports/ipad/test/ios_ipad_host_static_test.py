#!/usr/bin/env python3
"""Static iOS host contract checks; these do not simulate EAGL or a device."""
from pathlib import Path
import re

root = Path(__file__).resolve().parents[1]
src = (root / "src/main.m").read_text()
hdr = (root / "src/app.h").read_text()
assert "void app_ipad_graphics(void);" in hdr
start = src[src.index("- (void)startGame {"):src.index("/* the iPad turned")]
assert re.search(r"if\s*\(\[\[UIDevice currentDevice\] userInterfaceIdiom\]\s*==\s*UIUserInterfaceIdiomPad\)\s*\{[^{}]*app_ipad_graphics\(\);\s*\}", start)
assert start.index("app_wide(") < start.index("app_ipad_graphics();") < start.index("app_init(")
assert "initWithAPI:ctx.API sharegroup:ctx.sharegroup" in start
assert "[load_ctx release]" in start
loader = src[src.index("static void *Loader"):src.index("@interface GLView")]
assert re.search(r"if\s*\(\[EAGLContext setCurrentContext:load_ctx\]\)\s*\{\s*app_loader\(\);", loader)
assert "[load_ctx release]" in loader
init = src[src.index("- (id)initWithFrame:(CGRect)f {", src.index("@implementation GLView")):src.index("- (BOOL)makeFramebuffer")]
assert "kEAGLRenderingAPIOpenGLES2" in init
assert "kEAGLRenderingAPIOpenGLES3" not in init
assert "!ctx || ![EAGLContext setCurrentContext:ctx]" in init
assert "[ctx release];" in init and "ctx = nil;" in init
framebuffer = src[src.index("- (BOOL)makeFramebuffer"):src.index("- (BOOL)showMovie:")]
assert "!ctx || ![EAGLContext setCurrentContext:ctx]" in framebuffer
assert "GL_FRAMEBUFFER_COMPLETE" in framebuffer
assert "if (![self makeFramebuffer])" in framebuffer
assert framebuffer.index("failed = YES;") < framebuffer.index("[self startGame]")
assert "link.paused = p || failed;" in src
assert "void app_resize(int w, int h);" in hdr
layout = framebuffer[framebuffer.index("- (void)layoutSubviews {"):]
assert re.search(r"if \(!\[self makeFramebuffer\]\)\s*\{.*?return;\s*\}\s*if \(!started\)\s*\{.*?\[self startGame\];\s*\}\s*else if \(loaded\)\s*\{[^{}]*app_resize\(fb_w, fb_h\);\s*\}", layout, re.S)
assert layout.count("app_resize(") == 1
# Unconditionally forwards the just-read size on each successful later layout,
# including repeated identical sizes and changed sizes; no cached-size guard.
assert "fb_w > 0 && fb_h > 0 && status == GL_FRAMEBUFFER_COMPLETE" in framebuffer
print("iOS host static contracts passed (ES3 intentionally deferred)")
