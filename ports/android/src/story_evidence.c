#include "story_evidence.h"
#include <string.h>
void story_evidence_begin(story_evidence *s, int div, int verified_boundary) {
  memset(s, 0, sizeof *s);
  s->expected_div = div;
  s->known_clean = !!verified_boundary && div >= 0 && div % 5 == 0;
}
int story_evidence_result(story_evidence *s, int div, int episode, int won, int final_race) {
  if (!s) return 0;
  if (div < 0 || div > 0x1391 || episode < 0 || episode >= 100 ||
      (won != 0 && won != 1) || (final_race != 0 && final_race != 1) ||
      div != s->expected_div || episode / 20 != div % 5) {
    s->known_clean = 0;
    return 0;
  }
  if (!won) { s->flags |= STORY_EVIDENCE_LOST; return 1; }
  if (!final_race) return 1;
  if (episode == 99) {
    s->flags |= STORY_EVIDENCE_CLEAR;
    if (s->known_clean && !(s->flags & STORY_EVIDENCE_LOST))
      s->flags |= STORY_EVIDENCE_FIRST | STORY_EVIDENCE_SECOND;
    s->flags &= ~STORY_EVIDENCE_LOST;
    /* A won ending creates a new observable clean loop, except at the
     * port's wraparound cap, where the successor is not an ordinary loop. */
    s->known_clean = div < 0x1391;
  }
  if (episode % 20 == 19)
    s->expected_div = div == 0x1391 ? div - 9 : div + 1;
  return 1;
}
