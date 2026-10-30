/* Static validation only: prevent changes until the old loader finishes reading.
 * This cannot guarantee memory availability, GL safety, or absence of TOCTOU. */
#ifndef BACKFIRE_WPK_H
#define BACKFIRE_WPK_H
#include "backfire.h"
#define BFX_WPK_MAX_BYTES (128u * 1024u * 1024u)
#define BFX_WPK_MAX_TEXTURES 4096u
#define BFX_WPK_MAX_GROUPS BFX_MAX_MESH
#define BFX_WPK_MAX_VERTICES 65535u
#define BFX_WPK_MAX_INDICES (65535u * 3u)
#define BFX_WPK_MAX_TEXTURE_SIDE 4096u
/* 0 accepted; nonzero rejected/I/O failure. asset and mesh must stay live. */
int bfx_wpk_validate(const char *path, const bfx_asset *asset);
#endif
