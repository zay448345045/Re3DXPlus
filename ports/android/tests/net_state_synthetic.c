/* Self-contained protocol state regression. Compile from repository root:
 * cc -std=c11 -fsanitize=undefined -fno-sanitize-recover=all ports/android/tests/net_state_synthetic.c -o /tmp/net-state && /tmp/net-state
 * For iPad, add -DNET_IMPL='"../../ipad/src/net.c"'. No device or network. */
#include <assert.h>
#include <stdio.h>
#include <string.h>
#ifndef NET_IMPL
#define NET_IMPL "../src/net.c"
#endif
#include NET_IMPL
static unsigned char sent[2048];
static int sent_len, delivered, last_pcb;
int gk_send(int peer, const void *b, int len) {
  (void)peer; assert(len >= 0 && len <= (int)sizeof sent);
  memcpy(sent, b, (size_t)len); sent_len = len; return 0;
}
int gk_recv(void *b, int max, int *peer) { (void)b; (void)max; (void)peer; return 0; }
void car_link_deliver(int pcb, const unsigned char *packet, int len) {
  assert(packet && len == CAR_LINK_PACKET); delivered++; last_pcb = pcb;
}
static int make_go(unsigned char *b, uint32_t race, int me) {
  head(b, GO); put32(b + 4, race); put32(b + 8, 99);
  b[12] = 128; b[13] = 13; b[14] = 2; b[15] = (unsigned char)me;
  int at = 16;
  for (int i = 0; i < 2; i++) {
    b[at++] = (unsigned char)i; put32(b + at, (uint32_t)(10 + i)); at += 4;
    memset(b + at, 'A' + i, NET_NAME); at += NET_NAME; b[at++] = 0;
  }
  return at; /* old hosts need not send a song */
}
static int make_race(unsigned char *b, uint32_t race, int pcb, uint32_t count) {
  head(b, RACE); put32(b + 4, race); b[8] = (unsigned char)pcb;
  memset(b + 9, 0, CAR_LINK_PACKET); put32(b + 9 + PACKET_COUNT, count);
  return 9 + CAR_LINK_PACKET;
}
int main(void) {
  unsigned char b[2048], packet[CAR_LINK_PACKET] = {0}; net_go go;
  net_open_gk(10); int n = make_go(b, 1, 0);
  for (int k = 0; k < n; k++) { got(b, k, 1.0); assert(!N.go_new); }
  b[14] = 5; got(b, n, 1.0); assert(!N.go_new); b[14] = 2;
  b[15] = 2; got(b, n, 1.0); assert(!N.go_new); b[15] = 0;
  b[16 + 22] = 0; got(b, n, 1.0); assert(!N.go_new); b[16 + 22] = 1;
  got(b, n, 1.0); assert(net_take_go(&go)); assert(go.n == 2 && go.pcb == 0);
  sent_len = 0; net_race_send(packet, -1); assert(!sent_len);
  net_race_send(NULL, 1); assert(!sent_len);
  net_race_send(packet, CAR_LINK_PACKET); assert(sent_len == 9 + CAR_LINK_PACKET && sent[8] == 0);
  n = make_race(b, 1, 1, 0xffffffffu);
  got(b, n - 1, 2.0); assert(!N.rx_new[1]);
  got(b, n, 2.0); net_race_receive(); assert(delivered == 1 && last_pcb == 1);
  put32(b + 9 + PACKET_COUNT, 0); got(b, n, 3.0); net_race_receive(); assert(delivered == 2);
  put32(b + 9 + PACKET_COUNT, 0xffffffffu); got(b, n, 4.0); net_race_receive(); assert(delivered == 2);
  b[8] = 0; got(b, n, 5.0); b[8] = 2; got(b, n, 5.0);
  net_race_receive(); assert(delivered == 2);
  n = make_go(b, 2, 1); got(b, n, 6.0); assert(N.go_new);
  sent_len = 0; net_race_send(packet, CAR_LINK_PACKET);
  assert(sent_len && get32(sent + 4) == 1 && sent[8] == 0);
  n = make_race(b, 1, 1, 1); got(b, n, 7.0);
  net_race_receive(); assert(delivered == 3 && last_pcb == 1);
  assert(net_take_go(&go) && go.pcb == 1);
  n = make_race(b, 2, 0, 0); got(b, n, 8.0);
  net_race_receive(); assert(delivered == 4 && last_pcb == 0);
  head(b, CLOSED); got(b, 4, 9.0); assert(!net_host_closed());
  put32(b + 4, 10); got(b, 8, 9.0); assert(net_host_closed());
  net_found found;
  assert(net_found_list(&found, -1) == 0 && net_found_list(NULL, 1) == 0);
  net_close();
  puts("synthetic net state tests passed"); return 0;
}
