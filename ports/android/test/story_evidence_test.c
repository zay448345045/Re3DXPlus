#include "../src/story_evidence.h"
#include <assert.h>
#include <stdio.h>
static void lap(story_evidence *s, int loop, int fail_at) {
  for (int n=0; n<100; ++n) {
    int div=loop*5+n/20;
    if (n==fail_at) assert(story_evidence_result(s,div,n,0,0));
    assert(story_evidence_result(s,div,n,1,0));
    assert(story_evidence_result(s,div,n,1,1));
  }
}
int main(void) {
  story_evidence a,b, restart;
  story_evidence_begin(&a,0,1); story_evidence_begin(&b,0,1);
  lap(&a,0,-1); assert(a.flags==7);
  restart=a; /* state copy, not a real persistence test */
  lap(&restart,1,-1); assert(restart.flags==7);
  assert(b.flags==0); lap(&b,0,21); assert(b.flags==1);
  lap(&b,1,-1); assert(b.flags==7);
  lap(&b,2,9); assert(b.flags==7);
  story_evidence_begin(&a,0,0); lap(&a,0,-1); assert(a.flags==1);
  lap(&a,1,-1); assert(a.flags==7);
  story_evidence_begin(&a,0,1);
  /* Upstream permits advancing each division via its last episode; do not
   * manufacture a requirement for 100 different wins. */
  for (int d=0; d<5; d++) assert(story_evidence_result(&a,d,d*20+19,1,1));
  assert(a.flags==7);
  story_evidence_begin(&a,0,1);
  assert(!story_evidence_result(&a,0,20,1,1)); assert(!a.known_clean);
  puts("story evidence simulation passed");
}
