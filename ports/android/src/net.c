/* The versus's client: see net.h and tools/vs_server.py (the protocol). */
#include "net.h"

#include <arpa/inet.h>
#include <errno.h>
#include <fcntl.h>
#include <netinet/in.h>
#include <stdio.h>
#include <string.h>
#include <sys/socket.h>
#include <unistd.h>

#include "car.h"
#include "gk.h"

enum { HELLO = 1, LOBBY, START, GO, RACE, BYE, DISCOVER, OFFER, CLOSED };
#define SCAN_EVERY 1.0
#define SCAN_GONE 4.0
#define HELLO_EVERY 0.5
#define PACKET_COUNT 0x34 /* SLxPacket: CLinx's frame count (older packets are dropped) */

static struct {
  int fd, gk; /* the server's UDP socket, or the GameKit session's host */
  uint32_t id;
  double last_hello, last_heard, now;
  int last_status;
  int heard;
  net_lobby lobby;
  net_go go;
  int go_new;
  int closed; /* the host's CLOSED came */
  uint32_t race; /* the race this machine is in (0 none) */
  int race_n, race_pcb; /* active GO snapshot, independent of a pending GO */
  /* the newest race packet from each machine, not yet handed over */
  unsigned char rx[CAR_LINK_MACHINES][CAR_LINK_PACKET];
  int rx_new[CAR_LINK_MACHINES];
  uint32_t rx_count[CAR_LINK_MACHINES];
  int rx_any[CAR_LINK_MACHINES];
} N = { .fd = -1 };

static void put32(unsigned char *p, uint32_t v) {
  p[0] = (unsigned char)v, p[1] = (unsigned char)(v >> 8), p[2] = (unsigned char)(v >> 16), p[3] = (unsigned char)(v >> 24);
}
static uint32_t get32(const unsigned char *p) { return p[0] | (uint32_t)p[1] << 8 | (uint32_t)p[2] << 16 | (uint32_t)p[3] << 24; }

static void head(unsigned char *p, int kind) { p[0] = 'W', p[1] = 'V', p[2] = 1, p[3] = (unsigned char)kind; }

static void tx(const unsigned char *b, int len) {
  if (N.gk) gk_send(-1, b, len);
  else if (N.fd >= 0) send(N.fd, b, (size_t)len, 0);
}

static int rx(unsigned char *b, int max) {
  int peer;
  if (N.gk) return gk_recv(b, max, &peer);
  if (N.fd < 0) return 0;
  ssize_t n = recv(N.fd, b, (size_t)max, 0);
  return n > 0 ? (int)n : 0;
}

int net_open(const char *host, int port, uint32_t id) {
  net_close();
  struct sockaddr_in a;
  memset(&a, 0, sizeof a);
  a.sin_family = AF_INET;
  a.sin_port = htons((uint16_t)port);
  if (inet_pton(AF_INET, host, &a.sin_addr) != 1) return -1;
  int fd = socket(AF_INET, SOCK_DGRAM, 0);
  if (fd < 0) return -1;
  fcntl(fd, F_SETFL, fcntl(fd, F_GETFL, 0) | O_NONBLOCK);
  if (connect(fd, (struct sockaddr *)&a, sizeof a) != 0) {
    close(fd);
    return -1;
  }
  memset(&N, 0, sizeof N);
  N.fd = fd;
  N.id = id;
  N.last_hello = -1e9;
  return 0;
}

int net_open_gk(uint32_t id) {
  net_close();
  memset(&N, 0, sizeof N);
  N.fd = -1;
  N.gk = 1;
  N.id = id;
  N.last_hello = -1e9;
  return 0;
}

void net_close(void) {
  if (!net_is_open()) return;
  unsigned char b[8];
  head(b, BYE);
  put32(b + 4, N.id);
  tx(b, sizeof b);
  if (N.fd >= 0) close(N.fd);
  memset(&N, 0, sizeof N);
  N.fd = -1;
}

int net_is_open(void) { return N.fd >= 0 || N.gk; }

const net_lobby *net_lobby_now(void) { return &N.lobby; }

double net_silence(double now) { return N.heard ? now - N.last_heard : 1e9; }

/* a player record: u32 id, u8 status (lobby only), char name[16], u8 n, profile[n] */
static int read_player(const unsigned char *p, int len, net_player *pl, int with_status) {
  int need = 4 + with_status + NET_NAME + 1;
  if (len < need) return -1;
  memset(pl, 0, sizeof *pl);
  pl->id = get32(p);
  pl->status = with_status ? p[4] : 1;
  memcpy(pl->name, p + 4 + with_status, NET_NAME);
  int n = p[need - 1];
  if (len < need + n) return -1;
  pl->profile_len = n > NET_PROFILE ? NET_PROFILE : n;
  memcpy(pl->profile, p + need, (size_t)pl->profile_len);
  return need + n;
}

static void got(const unsigned char *b, int len, double now) {
  if (len < 4 || b[0] != 'W' || b[1] != 'V' || b[2] != 1) return;
  const unsigned char *p = b + 4;
  len -= 4;
  if (b[3] == RACE) {
    if (len < 5 + CAR_LINK_PACKET) return;
    uint32_t race = get32(p);
    int pcb = p[4];
    /* The relay does not authenticate the claimed PCB; at least do not hand
     * our own or a machine outside the active race roster to the game. */
    if (!N.race || race != N.race || pcb >= N.race_n || pcb >= CAR_LINK_MACHINES || pcb == N.race_pcb) return;
    uint32_t count = get32(p + 5 + PACKET_COUNT);
    if (N.rx_any[pcb] && (int32_t)(count - N.rx_count[pcb]) < 0) return; /* came in late */
    memcpy(N.rx[pcb], p + 5, CAR_LINK_PACKET);
    N.rx_count[pcb] = count;
    N.rx_any[pcb] = N.rx_new[pcb] = 1;
    N.last_heard = now, N.heard = 1;
    return;
  }
  if (b[3] == CLOSED) {
    if (len < 4) return; /* host id */
    N.closed = 1;
    return;
  }
  if (b[3] == LOBBY) {
    if (len < 9) return;
    net_lobby l;
    memset(&l, 0, sizeof l);
    l.connected = 1;
    l.n = p[0];
    l.me = p[1];
    l.host = p[2];
    if (l.n < 1 || l.n > NET_PLAYERS || l.me >= l.n || l.host >= l.n) return;
    int at = 9;
    for (int i = 0; i < l.n; ++i) {
      if (at + 1 > len || p[at] != i) return;
      int k = read_player(p + at + 1, len - at - 1, &l.player[i], 1);
      if (k < 0) return;
      at += 1 + k;
    }
    N.lobby = l;
    N.last_heard = now, N.heard = 1;
    return;
  }
  if (b[3] == GO) {
    if (len < 12) return;
    net_go g;
    memset(&g, 0, sizeof g);
    g.race = get32(p);
    g.seed = get32(p + 4);
    g.ramp = p[8];
    g.km = p[9];
    g.n = p[10];
    g.pcb = p[11];
    if (!g.race || g.n < 2 || g.n > NET_PLAYERS || g.n > CAR_LINK_MACHINES || g.pcb >= g.n) return;
    if (g.race == N.go.race || g.race == N.race) return; /* said again */
    unsigned seen = 0;
    int at = 12;
    for (int i = 0; i < g.n; ++i) {
      if (at + 1 > len) return;
      int pcb = p[at];
      net_player pl;
      int k = read_player(p + at + 1, len - at - 1, &pl, 0);
      if (k < 0 || pcb >= g.n || (seen & (1u << pcb))) return;
      seen |= 1u << pcb;
      g.player[pcb] = pl;
      at += 1 + k;
    }
    if (at < len) g.song = p[at]; /* after the machines: a newer host's */
    N.go = g;
    N.go_new = 1;
    N.last_heard = now, N.heard = 1;
  }
}

void net_poll(double now, int status, const char *name, const unsigned char *profile, int profile_len) {
  if (!net_is_open()) return;
  N.now = now;
  unsigned char b[2048];
  for (int n; (n = rx(b, sizeof b)) > 0;) got(b, n, now);
  /* twice a second, and at once on a new status (the area vote's card) */
  if (now - N.last_hello < HELLO_EVERY && status == N.last_status) return;
  N.last_hello = now;
  N.last_status = status;
  int pl = !profile || profile_len < 0 ? 0 : profile_len > NET_PROFILE ? NET_PROFILE : profile_len;
  unsigned char h[4 + 4 + 1 + NET_NAME + 1 + NET_PROFILE];
  head(h, HELLO);
  put32(h + 4, N.id);
  h[8] = (unsigned char)status;
  memset(h + 9, 0, NET_NAME);
  if (name) memcpy(h + 9, name, strlen(name) < NET_NAME ? strlen(name) : NET_NAME);
  h[9 + NET_NAME] = (unsigned char)pl;
  if (pl) memcpy(h + 10 + NET_NAME, profile, (size_t)pl);
  tx(h, 10 + NET_NAME + pl);
}

void net_start(int ramp, int km, int song) {
  if (!net_is_open()) return;
  unsigned char b[7];
  head(b, START);
  b[4] = (unsigned char)ramp;
  b[5] = (unsigned char)km;
  b[6] = (unsigned char)song;
  tx(b, sizeof b);
}

int net_host_closed(void) { return N.closed; }

int net_take_go(net_go *go) {
  if (!go || !N.go_new) return 0;
  N.go_new = 0;
  *go = N.go;
  /* the race's packets from now on */
  N.race = N.go.race;
  N.race_n = N.go.n;
  N.race_pcb = N.go.pcb;
  memset(N.rx_new, 0, sizeof N.rx_new);
  memset(N.rx_any, 0, sizeof N.rx_any);
  return 1;
}

void net_race_send(const unsigned char *packet, int len) {
  if (!net_is_open() || !N.race || len < 0 || len > CAR_LINK_PACKET || (len && !packet)) return;
  unsigned char b[4 + 5 + CAR_LINK_PACKET];
  head(b, RACE);
  put32(b + 4, N.race);
  b[8] = (unsigned char)N.race_pcb;
  if (len) memcpy(b + 9, packet, (size_t)len);
  tx(b, 9 + len);
}

void net_race_receive(void) {
  if (!net_is_open()) return;
  unsigned char b[2048];
  for (int n; (n = rx(b, sizeof b)) > 0;) got(b, n, N.now);
  for (int k = 0; k < CAR_LINK_MACHINES; ++k)
    if (N.rx_new[k]) {
      car_link_deliver(k, N.rx[k], CAR_LINK_PACKET);
      N.rx_new[k] = 0;
    }
}

/* ---- the LAN's games: a DISCOVER to the Wi-Fi's broadcast address (and the loopback, for a
 * host on this machine: the harness) every SCAN_EVERY s, each host's OFFER kept till it has
 * been quiet SCAN_GONE s */
static struct {
  int fd;
  double last;
  net_found found[NET_FOUND];
  int n;
} S = { .fd = -1 };

void net_scan(double now, int on) {
  if (!on) {
    if (S.fd >= 0) close(S.fd);
    memset(&S, 0, sizeof S);
    S.fd = -1;
    return;
  }
  if (S.fd < 0) {
    S.fd = socket(AF_INET, SOCK_DGRAM, 0);
    if (S.fd < 0) return;
    int one = 1;
    setsockopt(S.fd, SOL_SOCKET, SO_BROADCAST, &one, sizeof one);
    fcntl(S.fd, F_SETFL, fcntl(S.fd, F_GETFL, 0) | O_NONBLOCK);
    S.last = -1e9;
  }
  unsigned char b[256];
  for (;;) {
    struct sockaddr_in from;
    socklen_t al = sizeof from;
    ssize_t n = recvfrom(S.fd, b, sizeof b, 0, (struct sockaddr *)&from, &al);
    if (n <= 0) break;
    if (n < 9 + NET_NAME || b[0] != 'W' || b[1] != 'V' || b[2] != 1 || b[3] != OFFER) continue;
    char ip[16] = { 0 };
    if (!inet_ntop(AF_INET, &from.sin_addr, ip, sizeof ip)) continue;
    uint32_t id = get32(b + 5 + NET_NAME);
    int k = 0;
    while (k < S.n && S.found[k].id != id) k++;
    if (k == S.n) {
      if (S.n >= NET_FOUND) continue;
      S.n++;
      memset(&S.found[k], 0, sizeof S.found[k]);
    }
    net_found *f = &S.found[k];
    /* (the loopback's answer only till the Wi-Fi's comes) */
    int loop = from.sin_addr.s_addr == htonl(INADDR_LOOPBACK);
    if (!f->ip[0] || !loop) memcpy(f->ip, ip, sizeof f->ip);
    f->id = id;
    memcpy(f->name, b + 5, NET_NAME);
    f->name[NET_NAME] = 0;
    f->n = b[4];
    f->seen = now;
  }
  for (int k = S.n - 1; k >= 0; --k)
    if (now - S.found[k].seen > SCAN_GONE) memmove(&S.found[k], &S.found[k + 1], sizeof S.found[0] * (size_t)(--S.n - k));
  if (now - S.last < SCAN_EVERY) return;
  S.last = now;
  unsigned char d[4];
  head(d, DISCOVER);
  struct sockaddr_in to;
  memset(&to, 0, sizeof to);
  to.sin_family = AF_INET;
  to.sin_port = htons(NET_PORT);
  to.sin_addr.s_addr = htonl(INADDR_BROADCAST);
  sendto(S.fd, d, sizeof d, 0, (struct sockaddr *)&to, sizeof to);
  to.sin_addr.s_addr = htonl(INADDR_LOOPBACK);
  sendto(S.fd, d, sizeof d, 0, (struct sockaddr *)&to, sizeof to);
}

int net_found_list(net_found *out, int max) {
  if (!out || max <= 0) return 0;
  int n = S.n < max ? S.n : max;
  if (n) memcpy(out, S.found, sizeof out[0] * (size_t)n);
  return n;
}
