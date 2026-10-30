#ifndef STORY_EVIDENCE_H
#define STORY_EVIDENCE_H
/* Pure state machine; state and reward publication require durable commit by
 * the caller. Initialize verified_boundary only for a known clean loop start. */
typedef struct { int expected_div, known_clean; unsigned flags; } story_evidence;
enum { STORY_EVIDENCE_CLEAR = 1, STORY_EVIDENCE_FIRST = 2,
       STORY_EVIDENCE_SECOND = 4, STORY_EVIDENCE_LOST = 8 };
void story_evidence_begin(story_evidence *s, int div, int verified_boundary);
/* div is st_div before outcome; a loss in any race must be reported. Only an
 * episode's final race has final_race=1. Caller must checkpoint per race. */
int story_evidence_result(story_evidence *s, int div, int episode, int won, int final_race);
#endif
