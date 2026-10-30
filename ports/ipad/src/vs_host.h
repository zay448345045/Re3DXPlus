/* The versus host in the app (Bluetooth and LAN versus): tools/vs_server.py's lobby and the
 * race packets' relay on UDP NET_PORT (every interface) and on GameKit's peers. Everything
 * runs on the caller's thread: vs_host_poll reads what has arrived, never blocking. */
#ifndef VS_HOST_H
#define VS_HOST_H

#include <stdint.h>

/* open the host (gk: also GameKit's peers, gk_host already advertising); owner: the host's
 * own player's id, the lobby's host whenever it is in; 0 on success */
int vs_host_open(int gk, uint32_t owner);
void vs_host_close(void);
int vs_host_is_open(void);
/* serve what has arrived; `name`: the game's name in the LAN's answers */
void vs_host_poll(double now, const char *name);

#endif
