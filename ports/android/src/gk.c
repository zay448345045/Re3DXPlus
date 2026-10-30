/* gk.h off iOS (the harness): no Bluetooth, nothing found. */
#ifndef __APPLE__
#include "gk.h"

int gk_host(const char *name) { return (void)name, -1; }
int gk_browse(const char *name) { return (void)name, -1; }
void gk_stop(void) {}
int gk_found(char names[][GK_NAME], int max) { return (void)names, (void)max, 0; }
int gk_join(int k) { return (void)k, -1; }
int gk_joined(void) { return -1; }
int gk_send(int peer, const void *b, int len) { return (void)peer, (void)b, (void)len, -1; }
int gk_recv(void *b, int max, int *peer) { return (void)b, (void)max, (void)peer, 0; }
#endif
