#define _DARWIN_C_SOURCE
#define _POSIX_C_SOURCE 200809L
#include "../src/story_evidence_store.h"
#include <assert.h>
#include <stdio.h>
int main(void) {
  char d[]="/tmp/story-evidence-XXXXXX", p[512], q[512], bad[512];
  assert(mkdtemp(d));
  assert(snprintf(p,sizeof p,"%s/car-a",d)>0);
  assert(snprintf(q,sizeof q,"%s/car-b",d)>0);
  assert(snprintf(bad,sizeof bad,"%s/absent/car",d)>0);
  story_evidence a,b,loaded,candidate;
  story_evidence_begin(&a,0,1);story_evidence_begin(&b,0,1);
  assert(se_load(p,&loaded)==0); assert(se_save(p,&a)); assert(se_save(q,&b));
  for(int n=0;n<100;n++) {
    candidate=a; assert(story_evidence_result(&candidate,n/20,n,1,1));
    assert(se_save(p,&candidate)); a=candidate;
    if(n==40) { assert(se_load(p,&loaded)==1);a=loaded; }
  }
  assert(a.flags==7); assert(se_load(p,&loaded)==1 && loaded.flags==7);
  assert(se_load(q,&loaded)==1 && loaded.flags==0);
  candidate=b;assert(story_evidence_result(&candidate,0,0,0,0));
  assert(!se_save(bad,&candidate));assert(b.flags==0); /* caller does not publish */
  int fd=open(q,O_WRONLY);assert(fd>=0);assert(write(fd,"BAD",3)==3);assert(close(fd)==0);
  assert(se_load(q,&loaded)==-1);
  assert(unlink(p)==0 && unlink(q)==0 && rmdir(d)==0);
  puts("story evidence storage test passed");
}
