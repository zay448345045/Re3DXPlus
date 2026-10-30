/* Test-only access to real app state and load. */
#include "../src/app.c"
menu_state *fixture_menu(void) { return &G.menu; }
void fixture_load(void) { card_choice_load(); }
