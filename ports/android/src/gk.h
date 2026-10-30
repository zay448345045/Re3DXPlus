/* Bluetooth versus over GameKit's GKSession (iOS 6: Bluetooth or Wi-Fi peer to peer, whichever
 * the devices share): the host advertises its game, the others find and join it, and the
 * versus protocol's datagrams (net.c, vs_host.c) go through the session. Off iOS, stubs that
 * find nothing. Everything on the main thread. */
#ifndef GK_H
#define GK_H

#define GK_FOUND 4
#define GK_NAME 24

/* advertise a game as `name` (host) / look for games (join); 0 on success */
int gk_host(const char *name);
int gk_browse(const char *name);
void gk_stop(void);
/* the games found while browsing, their names into names[k] (at most max); their count */
int gk_found(char names[][GK_NAME], int max);
/* connect to found game k; gk_joined: 1 connected, -1 failed or lost, 0 still on its way */
int gk_join(int k);
int gk_joined(void);
/* a datagram to a peer (the host's numbers for its peers; -1 from a client: to its host) */
int gk_send(int peer, const void *b, int len);
/* the next datagram arrived: its length (0 none), *peer its sender's number (-1 the host) */
int gk_recv(void *b, int max, int *peer);

#endif
