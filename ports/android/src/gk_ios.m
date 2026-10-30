// gk.h on iOS: a GKSession (GameKit, iOS 3..6; deprecated from 7 but there through 9) in server
// mode for the host, client mode for the others, its peers numbered as they connect; the
// datagrams queued as they come (the session calls back on the main run loop).
#import <GameKit/GameKit.h>
#pragma clang diagnostic ignored "-Wdeprecated-declarations"

#include <string.h>

#include "gk.h"

#define GK_QUEUE 64
#define GK_DATAGRAM 2048

@interface GkLink : NSObject <GKSessionDelegate> {
@public
  GKSession *session;
  int host;
  NSMutableArray *found;  /* hosts available (browsing), peer ids */
  NSMutableArray *peers;  /* connected peers by number (host), or the host (client) at 0 */
  int joined;
  unsigned char queue[GK_QUEUE][GK_DATAGRAM];
  int queue_len[GK_QUEUE], queue_peer[GK_QUEUE], head, count;
}
@end

@implementation GkLink
- (void)session:(GKSession *)s peer:(NSString *)peer didChangeState:(GKPeerConnectionState)state {
  fprintf(stderr, "bluetooth: %s %s is %d\n", host ? "host" : "client", [[s displayNameForPeer:peer] UTF8String] ?: "?", (int)state);
  switch (state) {
  case GKPeerStateAvailable:
    if (!host && ![found containsObject:peer]) [found addObject:peer];
    break;
  case GKPeerStateUnavailable:
    [found removeObject:peer];
    break;
  case GKPeerStateConnected:
    if (![peers containsObject:peer]) [peers addObject:peer];
    if (!host) joined = 1;
    break;
  case GKPeerStateDisconnected:
    /* (a host keeps the number: the lobby drops the player when it goes quiet) */
    if (!host && peers.count && [peers[0] isEqualToString:peer]) joined = -1;
    break;
  default:
    break;
  }
}
- (void)session:(GKSession *)s didReceiveConnectionRequestFromPeer:(NSString *)peer {
  if (host) [s acceptConnectionFromPeer:peer error:nil];
  else [s denyConnectionFromPeer:peer];
}
- (void)session:(GKSession *)s connectionWithPeerFailed:(NSString *)peer withError:(NSError *)error {
  fprintf(stderr, "bluetooth: connection failed: %s\n", [[error description] UTF8String] ?: "?");
  if (!host) joined = -1;
}
- (void)session:(GKSession *)s didFailWithError:(NSError *)error {
  fprintf(stderr, "bluetooth: the session failed: %s\n", [[error description] UTF8String] ?: "?");
  joined = -1;
}
- (void)receiveData:(NSData *)data fromPeer:(NSString *)peer inSession:(GKSession *)s context:(void *)context {
  if (count >= GK_QUEUE || data.length > GK_DATAGRAM) return;
  int k = (head + count) % GK_QUEUE;
  NSUInteger n = [peers indexOfObject:peer];
  if (n == NSNotFound) {
    [peers addObject:peer];
    n = peers.count - 1;
  }
  memcpy(queue[k], data.bytes, data.length);
  queue_len[k] = (int)data.length;
  queue_peer[k] = host ? (int)n : -1;
  count++;
}
@end

static GkLink *L;

static int start(const char *name, int host) {
  gk_stop();
  L = [[GkLink alloc] init];
  L->host = host;
  L->found = [[NSMutableArray alloc] init];
  L->peers = [[NSMutableArray alloc] init];
  NSString *shown = [NSString stringWithUTF8String:name && *name ? name : "WMMT3DX"];
  L->session = [[GKSession alloc] initWithSessionID:@"wmmt3dx-versus" displayName:shown
                                        sessionMode:host ? GKSessionModeServer : GKSessionModeClient];
  if (!L->session) {
    gk_stop();
    return -1;
  }
  L->session.delegate = L;
  [L->session setDataReceiveHandler:L withContext:NULL];
  L->session.available = YES;
  fprintf(stderr, "bluetooth: %s as %s (peer %s)\n", host ? "hosting" : "searching", [shown UTF8String], [L->session.peerID UTF8String] ?: "?");
  return 0;
}

int gk_host(const char *name) { return start(name, 1); }
int gk_browse(const char *name) { return start(name, 0); }

void gk_stop(void) {
  if (!L) return;
  if (L->session) {
    L->session.available = NO;
    [L->session disconnectFromAllPeers];
    L->session.delegate = nil;
    [L->session setDataReceiveHandler:nil withContext:NULL];
    [L->session release];
  }
  [L->found release];
  [L->peers release];
  [L release];
  L = nil;
}

int gk_found(char names[][GK_NAME], int max) {
  if (!L || L->host) return 0;
  int n = 0;
  for (NSString *peer in L->found) {
    if (n >= max) break;
    const char *s = [[L->session displayNameForPeer:peer] UTF8String];
    strncpy(names[n], s ? s : "?", GK_NAME - 1);
    names[n][GK_NAME - 1] = 0;
    n++;
  }
  return n;
}

int gk_join(int k) {
  if (!L || L->host || k < 0 || k >= (int)L->found.count) return -1;
  L->joined = 0;
  [L->peers removeAllObjects];
  [L->session connectToPeer:L->found[k] withTimeout:10];
  return 0;
}

int gk_joined(void) { return L ? L->joined : -1; }

int gk_send(int peer, const void *b, int len) {
  if (!L || !L->session) return -1;
  NSString *to = nil;
  if (peer < 0) to = !L->host && L->peers.count ? L->peers[0] : nil;
  else if (peer < (int)L->peers.count) to = L->peers[peer];
  if (!to) return -1;
  NSData *d = [NSData dataWithBytes:b length:(NSUInteger)len];
  return [L->session sendData:d toPeers:@[ to ] withDataMode:GKSendDataUnreliable error:nil] ? 0 : -1;
}

int gk_recv(void *b, int max, int *peer) {
  if (!L || !L->count) return 0;
  int k = L->head, n = L->queue_len[k];
  if (n > max) n = max;
  memcpy(b, L->queue[k], (size_t)n);
  *peer = L->queue_peer[k];
  L->head = (L->head + 1) % GK_QUEUE;
  L->count--;
  return n;
}
