/* Test-only wrapper around the actual static registration function. */
#include "../src/menu.c"
void fixture_own_register(menu_state *m) { own_register(m); }
