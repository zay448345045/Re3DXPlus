/* Local UDP loopback regression. Compile from repository root with:
 * cc -std=c11 -fsanitize=undefined -fno-sanitize-recover=all ports/android/tests/net_udp_loopback.c -o /tmp/net-udp && /tmp/net-udp
 * For iPad add -DNET_IMPL='"../../ipad/src/net.c"'. Uses no external network. */
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include <sys/time.h>
#include <sys/select.h>
#ifndef NET_IMPL
#define NET_IMPL "../src/net.c"
#endif
#include NET_IMPL
static int delivered, last_pcb;
int gk_send(int peer, const void *b, int len) { (void)peer; (void)b; (void)len; return 0; }
int gk_recv(void *b, int max, int *peer) { (void)b; (void)max; (void)peer; return 0; }
void car_link_deliver(int pcb, const unsigned char *b, int len) {
  assert(b && len == CAR_LINK_PACKET); delivered++; last_pcb = pcb;
}
static int go_packet(unsigned char *b, uint32_t race, int local) {
  head(b, GO); put32(b+4, race); put32(b+8, 0x12345678);
  b[12]=134; b[13]=13; b[14]=2; b[15]=(unsigned char)local;
  int at=16;
  for(int k=0;k<2;k++) {
    b[at++]=(unsigned char)k; put32(b+at, 10u+(uint32_t)k); at+=4;
    memset(b+at, 'A'+k, NET_NAME); at+=NET_NAME; b[at++]=0;
  }
  return at;
}
static int race_packet(unsigned char *b, uint32_t race, int pcb, uint32_t count) {
  head(b,RACE); put32(b+4,race); b[8]=(unsigned char)pcb;
  memset(b+9,0,CAR_LINK_PACKET); put32(b+9+PACKET_COUNT,count);
  return 9+CAR_LINK_PACKET;
}
static void send_packet(int fd,const struct sockaddr_in *dst,const unsigned char *b,int n) {
  assert(sendto(fd,b,(size_t)n,0,(const struct sockaddr *)dst,sizeof *dst)==n);
  fd_set ready; FD_ZERO(&ready); FD_SET(N.fd, &ready);
  struct timeval timeout = {2, 0};
  assert(select(N.fd + 1, &ready, NULL, NULL, &timeout) == 1);
}
int main(void) {
  int fd=socket(AF_INET,SOCK_DGRAM,0); assert(fd>=0);
  struct timeval timeout={2,0}; assert(!setsockopt(fd,SOL_SOCKET,SO_RCVTIMEO,&timeout,sizeof timeout));
  struct sockaddr_in addr={0},peer={0}; addr.sin_family=AF_INET;
  addr.sin_addr.s_addr=htonl(INADDR_LOOPBACK); assert(!bind(fd,(const struct sockaddr *)&addr,sizeof addr));
  socklen_t sz=sizeof addr; assert(!getsockname(fd,(struct sockaddr *)&addr,&sz));
  assert(!net_open("127.0.0.1",ntohs(addr.sin_port),10));
  net_poll(1,0,"LOCAL",NULL,0);
  unsigned char b[2048]; sz=sizeof peer;
  int n=(int)recvfrom(fd,b,sizeof b,0,(struct sockaddr *)&peer,&sz);
  assert(n==26 && b[3]==HELLO);
  /* Two-player legacy GO has no optional song. Truncated packet changes no state. */
  n=go_packet(b,1,0); send_packet(fd,&peer,b,n-1); net_poll(1.1,0,"LOCAL",NULL,0);
  net_go g; assert(!net_take_go(&g));
  send_packet(fd,&peer,b,n); net_poll(1.2,0,"LOCAL",NULL,0); assert(net_take_go(&g));
  assert(g.ramp==134 && g.km==13 && g.song==0 && g.n==2 && g.pcb==0);
  n=race_packet(b,1,1,8); send_packet(fd,&peer,b,n); net_race_receive();
  assert(delivered==1 && last_pcb==1);
  n=race_packet(b,1,1,7); send_packet(fd,&peer,b,n); net_race_receive(); assert(delivered==1);
  n=race_packet(b,1,1,8); send_packet(fd,&peer,b,n); net_race_receive(); assert(delivered==2); /* original duplicate behavior */
  b[8]=0; send_packet(fd,&peer,b,n); net_race_receive();
  b[8]=2; send_packet(fd,&peer,b,n); net_race_receive(); assert(delivered==2);
  /* A queued next GO cannot alter the active PCB or roster until taken. */
  n=go_packet(b,2,1); send_packet(fd,&peer,b,n); net_poll(1.3,0,"LOCAL",NULL,0);
  unsigned char data[CAR_LINK_PACKET]={0}; net_race_send(data,CAR_LINK_PACKET);
  n=(int)recv(fd,b,sizeof b,0); assert(n==9+CAR_LINK_PACKET && b[3]==RACE && get32(b+4)==1 && b[8]==0);
  assert(net_take_go(&g) && g.pcb==1);
  n=race_packet(b,2,0,1); send_packet(fd,&peer,b,n); net_race_receive();
  assert(delivered==3 && last_pcb==0);
  net_close(); close(fd); puts("UDP loopback net tests passed"); return 0;
}
