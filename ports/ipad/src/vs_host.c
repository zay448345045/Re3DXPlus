/* The versus host in the app (Bluetooth and LAN versus): tools/vs_server.py's lobby and race
 * relay, the same protocol, on UDP NET_PORT on every interface (the host's own client comes in
 * through the loopback; the LAN's devices from the Wi-Fi, which find it by a DISCOVER
 * broadcast) and on GameKit's peers (gk.h, Bluetooth). */
#include "vs_host.h"

#include <arpa/inet.h>
#include <fcntl.h>
#include <netinet/in.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <unistd.h>

#include "gk.h"
#include "net.h"

enum { HELLO = 1, LOBBY, START, GO, RACE, BYE, DISCOVER, OFFER, CLOSED };
#define TIMEOUT 6.0
#define TIMEOUT_RACING 20.0 /* a player loading or racing (status 1): its device may stall a while at the start */
#define RACES 4

typedef struct {
  int gk, peer; /* a GameKit peer's number, or a UDP address */
  struct sockaddr_in a;
} addr;

typedef struct {
  uint32_t id;
  addr from;
  int status;
  unsigned char name[NET_NAME];
  unsigned char profile[NET_PROFILE];
  int profile_len;
  double seen;
} player;

static struct {
  int fd, gk, open;
  uint32_t owner;
  player p[NET_PLAYERS];
  int n;
  int ramp, km, song;
  uint32_t race_id;
  /* the races' machines (by PCB) as the players' ids, the newest RACES */
  uint32_t race[RACES], machine[RACES][NET_PLAYERS];
  int machines[RACES];
} H = { .fd = -1 };

static void put32(unsigned char *p, uint32_t v) {
  p[0] = (unsigned char)v, p[1] = (unsigned char)(v >> 8), p[2] = (unsigned char)(v >> 16), p[3] = (unsigned char)(v >> 24);
}
static uint32_t get32(const unsigned char *p) { return p[0] | (uint32_t)p[1] << 8 | (uint32_t)p[2] << 16 | (uint32_t)p[3] << 24; }
static void head(unsigned char *p, int kind) { p[0] = 'W', p[1] = 'V', p[2] = 1, p[3] = (unsigned char)kind; }

static int same(const addr *x, const addr *y) {
  if (x->gk != y->gk) return 0;
  if (x->gk) return x->peer == y->peer;
  return x->a.sin_addr.s_addr == y->a.sin_addr.s_addr && x->a.sin_port == y->a.sin_port;
}

static void send_to(const addr *to, const unsigned char *b, int len) {
  if (to->gk) gk_send(to->peer, b, len);
  else if (H.fd >= 0) sendto(H.fd, b, (size_t)len, 0, (const struct sockaddr *)&to->a, sizeof to->a);
}

static int find(const addr *from) {
  for (int i = 0; i < H.n; ++i)
    if (same(&H.p[i].from, from)) return i;
  return -1;
}

static void lobby_to(int i) {
  unsigned char b[1024];
  head(b, LOBBY);
  b[4] = (unsigned char)H.n, b[5] = (unsigned char)i, b[6] = 0, b[7] = (unsigned char)H.ramp, b[8] = (unsigned char)H.km;
  put32(b + 9, H.race_id);
  int at = 13;
  for (int k = 0; k < H.n; ++k) {
    const player *q = &H.p[k];
    b[at] = (unsigned char)k;
    put32(b + at + 1, q->id);
    b[at + 5] = (unsigned char)q->status;
    memcpy(b + at + 6, q->name, NET_NAME);
    b[at + 6 + NET_NAME] = (unsigned char)q->profile_len;
    memcpy(b + at + 7 + NET_NAME, q->profile, (size_t)q->profile_len);
    at += 7 + NET_NAME + q->profile_len;
  }
  send_to(&H.p[i].from, b, at);
}

static void lobby_all(void) {
  for (int i = 0; i < H.n; ++i) lobby_to(i);
}

static void drop(int i) {
  fprintf(stderr, "versus host: %.16s left\n", (const char *)H.p[i].name);
  memmove(&H.p[i], &H.p[i + 1], sizeof H.p[0] * (size_t)(H.n - i - 1));
  H.n--;
  lobby_all();
}

static void got(const unsigned char *b, int len, const addr *from, double now, const char *name) {
  if (len < 4 || b[0] != 'W' || b[1] != 'V' || b[2] != 1) return;
  const unsigned char *p = b + 4;
  len -= 4;
  int i = find(from);
  switch (b[3]) {
  case DISCOVER: {
    /* OFFER: u8 players, char name[16], u32 the host's own id (one host by two ways in, once) */
    unsigned char o[4 + 1 + NET_NAME + 4];
    head(o, OFFER);
    o[4] = (unsigned char)H.n;
    memset(o + 5, 0, NET_NAME);
    memcpy(o + 5, name, strlen(name) < NET_NAME ? strlen(name) : NET_NAME);
    put32(o + 5 + NET_NAME, H.owner);
    send_to(from, o, sizeof o);
    return;
  }
  case RACE: {
    if (len < 5 || i < 0) return;
    uint32_t race = get32(p);
    H.p[i].seen = now;
    for (int r = 0; r < RACES; ++r) {
      if (H.race[r] != race || !race) continue;
      for (int k = 0; k < H.machines[r]; ++k)
        for (int j = 0; j < H.n; ++j)
          if (j != i && H.p[j].id == H.machine[r][k]) send_to(&H.p[j].from, b, len + 4);
    }
    return;
  }
  case HELLO: {
    if (len < 22) return;
    uint32_t id = get32(p);
    int n = p[5 + NET_NAME];
    if (len < 6 + NET_NAME + n) return;
    if (n > NET_PROFILE) n = NET_PROFILE;
    int k = -1;
    for (int j = 0; j < H.n; ++j)
      if (H.p[j].id == id) k = j;
    int changed = 0;
    if (k < 0) {
      if (H.n >= NET_PLAYERS) return;
      /* the host's own player first: it is the lobby's host (slot 0) */
      k = id == H.owner ? 0 : H.n;
      memmove(&H.p[k + 1], &H.p[k], sizeof H.p[0] * (size_t)(H.n - k));
      memset(&H.p[k], 0, sizeof H.p[k]);
      H.p[k].id = id;
      H.n++;
      changed = 1;
      fprintf(stderr, "versus host: %.16s joined (%d players)\n", (const char *)p + 5, H.n);
    }
    player *q = &H.p[k];
    changed |= !same(&q->from, from) || q->status != p[4] || memcmp(q->name, p + 5, NET_NAME) || q->profile_len != n ||
               memcmp(q->profile, p + 6 + NET_NAME, (size_t)n);
    q->from = *from;
    q->status = p[4];
    memcpy(q->name, p + 5, NET_NAME);
    q->profile_len = n;
    memcpy(q->profile, p + 6 + NET_NAME, (size_t)n);
    q->seen = now;
    if (changed) lobby_all();
    else lobby_to(k);
    return;
  }
  case START: {
    if (i != 0 || len < 2 || H.n < 2) return;
    H.ramp = p[0], H.km = p[1];
    H.song = len >= 3 ? p[2] : 0;
    H.race_id = H.race_id + 1 ? H.race_id + 1 : 1;
    uint32_t seed = (uint32_t)rand() & 0x7fffffff;
    int r = (int)(H.race_id % RACES);
    H.race[r] = H.race_id;
    H.machines[r] = H.n;
    for (int k = 0; k < H.n; ++k) H.machine[r][k] = H.p[k].id, H.p[k].status = 1;
    fprintf(stderr, "versus host: race %u, ramp %d, %d km, %d players\n", H.race_id, H.ramp, H.km, H.n);
    for (int k = 0; k < H.n; ++k) {
      unsigned char g[1024];
      head(g, GO);
      put32(g + 4, H.race_id);
      put32(g + 8, seed);
      g[12] = (unsigned char)H.ramp, g[13] = (unsigned char)H.km, g[14] = (unsigned char)H.n, g[15] = (unsigned char)k;
      int at = 16;
      for (int j = 0; j < H.n; ++j) {
        const player *q = &H.p[j];
        g[at] = (unsigned char)j;
        put32(g + at + 1, q->id);
        memcpy(g + at + 5, q->name, NET_NAME);
        g[at + 5 + NET_NAME] = (unsigned char)q->profile_len;
        memcpy(g + at + 6 + NET_NAME, q->profile, (size_t)q->profile_len);
        at += 6 + NET_NAME + q->profile_len;
      }
      g[at++] = (unsigned char)H.song; /* everyone's BGM (an older client stops at the machines) */
      for (int t = 0; t < 3; ++t) send_to(&H.p[k].from, g, at); /* said more than once: the first counts */
    }
    return;
  }
  case BYE:
    if (i >= 0) drop(i);
    return;
  }
}

int vs_host_open(int gk, uint32_t owner) {
  vs_host_close();
  int fd = socket(AF_INET, SOCK_DGRAM, 0);
  if (fd < 0) return -1;
  int one = 1;
  setsockopt(fd, SOL_SOCKET, SO_REUSEADDR, &one, sizeof one);
  struct sockaddr_in a;
  memset(&a, 0, sizeof a);
  a.sin_family = AF_INET;
  a.sin_port = htons(NET_PORT);
  a.sin_addr.s_addr = htonl(INADDR_ANY);
  if (bind(fd, (struct sockaddr *)&a, sizeof a) != 0) {
    close(fd);
    return -1;
  }
  fcntl(fd, F_SETFL, fcntl(fd, F_GETFL, 0) | O_NONBLOCK);
  memset(&H, 0, sizeof H);
  H.fd = fd;
  H.gk = gk;
  H.owner = owner;
  H.km = 13;
  H.open = 1;
  return 0;
}

void vs_host_close(void) {
  /* the others told the game is closed (a race of theirs ends with it), said more than once */
  unsigned char b[8];
  head(b, CLOSED);
  put32(b + 4, H.owner);
  for (int i = 0; H.open && i < H.n; ++i)
    for (int t = 0; H.p[i].id != H.owner && t < 3; ++t) send_to(&H.p[i].from, b, sizeof b);
  if (H.fd >= 0) close(H.fd);
  memset(&H, 0, sizeof H);
  H.fd = -1;
}

int vs_host_is_open(void) { return H.open; }

void vs_host_poll(double now, const char *name) {
  if (!H.open) return;
  unsigned char b[2048];
  for (;;) {
    addr from;
    memset(&from, 0, sizeof from);
    socklen_t al = sizeof from.a;
    ssize_t n = recvfrom(H.fd, b, sizeof b, 0, (struct sockaddr *)&from.a, &al);
    if (n <= 0) break;
    got(b, (int)n, &from, now, name);
  }
  for (int n, peer; H.gk && (n = gk_recv(b, sizeof b, &peer)) > 0;) {
    addr from;
    memset(&from, 0, sizeof from);
    from.gk = 1, from.peer = peer;
    got(b, n, &from, now, name);
  }
  int dropped = 0;
  for (int i = H.n - 1; i >= 0; --i)
    if (now - H.p[i].seen > (H.p[i].status == 1 ? TIMEOUT_RACING : TIMEOUT)) {
      fprintf(stderr, "versus host: %.16s timed out\n", (const char *)H.p[i].name);
      memmove(&H.p[i], &H.p[i + 1], sizeof H.p[0] * (size_t)(H.n - i - 1));
      H.n--;
      dropped = 1;
    }
  if (dropped) lobby_all();
}
