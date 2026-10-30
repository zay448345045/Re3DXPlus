/* Real physics regression: separate process per mode, requires WMMT_PILOT. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "../src/car.h"
int main(int argc,char **argv) {
 char err[256];
 if(argc<3 || !getenv("WMMT_PILOT")) { fprintf(stderr,"usage: WMMT_PILOT=1 %s DATA ta|story|ten [frames] [course]\n",argv[0]); return 2; }
 int frames=argc>3?atoi(argv[3]):6000, course=argc>4?atoi(argv[4]):0;
 if(frames<3000) return 2;
 if(car_init(argv[1],err,sizeof err)) { fprintf(stderr,"car_init: %s\n",err); return 2; }
 car_rival r={0}; r.type=CAR_SPEC_FD3S.type; r.spokes=CAR_SPEC_FD3S.spokes;
 for(int i=0;i<6;i++) r.tyres[i]=CAR_SPEC_FD3S.tyres[i];
 if(!strcmp(argv[2],"story")) { r.type=34; r.character=39; r.series=24; car_set_rival(&r); }
 else if(!strcmp(argv[2],"ten")) { car_rival rivals[CAR_TEN_RIVALS]; for(int i=0;i<CAR_TEN_RIVALS;i++) rivals[i]=r; car_set_ten(333,0,rivals,CAR_TEN_RIVALS); }
 else if(strcmp(argv[2],"ta")) return 2;
 car_state c; if(car_start(&c,course,0,NULL)) return 2;
 int first=c.n_traffic?0:-1, peak=c.n_traffic, with=c.n_traffic>0, over_at=-1;
 car_input in={0}; in.throttle=1;
 for(int i=1;i<=frames;i++) { car_update(&c,&in);
  if(c.n_traffic && first<0) first=i; if(c.n_traffic>peak) peak=c.n_traffic;
  with+=c.n_traffic>0; if(c.race.over && over_at<0) over_at=i;
  if(i%1000==0) printf("%s frame=%d traffic=%d peak=%d first=%d play=%d over=%d race_s=%.1f left=%.1f speed=%.1f pos=%.0f,%.0f\n",argv[2],i,c.n_traffic,peak,first,c.race.play_state,c.race.over,c.race.total,c.race.time_left,car_kmh(&c),c.pos[0],c.pos[2]);
 }
 printf("RESULT mode=%s frames=%d first=%d peak=%d frames_with_traffic=%d over_at=%d\n",argv[2],frames,first,peak,with,over_at);
 return !strcmp(argv[2],"ta")?peak!=0:peak==0;
}
