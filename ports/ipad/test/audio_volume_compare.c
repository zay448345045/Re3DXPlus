/* Compile twice against the selected, unmodified sound.c. */
#include SOUND_PATH
#include <assert.h>
float car_kmh(const car_state *c) { return c->speed * 3.6f; }
static void reset(void) {
  memset(SHOTS,0,sizeof SHOTS); memset(&BAR,0,sizeof BAR); shot_next=0;
  memset(&E,0,sizeof E); E.rpm=1000; E.accel=1000; E.accel_target=1000;
  for(int i=0;i<N_LOOP;i++) { LOOPS[i].pos=0; LOOPS[i].cur_vol=0; LOOP_STORE(LOOPS[i].vol,0); }
}
static void emit(void) {
  short pcm[16384]; snd_mix(pcm,8192);
  for(int i=0;i<8192;i++) assert(pcm[2*i]==pcm[2*i+1]);
  assert(fwrite(pcm,sizeof pcm,1,stdout)==1);
}
static void validate(void) {
  for(int i=0;i<N_LOOP;i++) { assert(isfinite(LOOP_LOAD(LOOPS[i].vol))); assert(isfinite(LOOP_LOAD(LOOPS[i].pitch))); assert(LOOP_LOAD(LOOPS[i].vol)>=0); }
}
int main(int argc,char **argv) {
  if(argc!=2 || snd_init(argv[1])) { fprintf(stderr,"WAV load failed\n"); return 2; }
  const unsigned cars[]={0,5,12}; const float rpms[]={1200,4500,8500,9518.3f};
  for(int c=0;c<3;c++) for(int r=0;r<4;r++) for(int t=0;t<2;t++) for(int mode=0;mode<4;mode++) {
    reset(); snd_set_car(cars[c],24);
    car_state car={0}; car_input in={0}; car.rpm=rpms[r]; car.slip=1; car.speed=180/3.6f; in.throttle=(float)t;
    for(int j=0;j<40;j++) snd_update(&car,&in,1.0f/60); validate();
    for(int i=0;i<N_LOOP;i++) if ((mode==0 && i>=4) || (mode==1 && (i<4 || i>=8)) || (mode==2 && i!=S_SLIP) || (mode==3 && i==S_WALL)) LOOP_STORE(LOOPS[i].vol,0);
    short warm[2048]; snd_mix(warm,1024); emit();
  }
  for(int effect=0;effect<7;effect++) {
    reset(); snd_set_car(5,24);
    if(effect<3) snd_menu(effect);
    else if(effect<6) { const char *names[]={"crash1","crash4","valb1"}; snd_effect(names[effect-3],1); }
    else { car_state car={0}; car_input in={0}; car.rpm=4500; car.speed=180/3.6f; car.wall_hit=1; snd_update(&car,&in,1.0f/60); for(int i=0;i<S_WALL;i++) LOOP_STORE(LOOPS[i].vol,0); }
    emit();
  }
  /* Near-full mix also contains wall and collision, not only car loops. */
  reset(); snd_set_car(0,24);
  car_state loud={0}; car_input gas={0}; loud.rpm=4500; loud.slip=1; loud.speed=180/3.6f; loud.wall_hit=1; gas.throttle=1;
  for(int j=0;j<40;j++) snd_update(&loud,&gas,1.0f/60);
  short warm[2048]; snd_mix(warm,1024); snd_effect("crash4",1); emit();
  const float bounds[]={0,1000,8999,9000,9001,10000,1000000,INFINITY,-INFINITY,NAN};
  for(int k=0;k<SOUNDDB_NSETS;k++) for(unsigned j=0;j<sizeof bounds/sizeof bounds[0];j++) {
    reset(); engine_set=&SOUNDDB_SETS[k];
    for(int i=0;i<8;i++) LOOP_STORE(LOOPS[i].s,&ENGINE_SAMPLES[k][i]);
    car_state car={0}; car_input in={0}; car.rpm=bounds[j]; car.slip=1; car.speed=250/3.6f; car.wall_hit=1; in.throttle=1;
    for(int q=0;q<10;q++) snd_update(&car,&in,0.05f); validate();
    float acc[1024]={0}; for(int i=0;i<N_LOOP;i++) mix_loop(&LOOPS[i],acc,1024);
    for(int i=0;i<1024;i++) { assert(isfinite(acc[i])); float y=32767.0f*tanhf(acc[i]/32767.0f); assert(isfinite(y) && y>=-32767 && y<=32767); }
    short out[2048]; snd_mix(out,1024);
  }
  return ferror(stdout)?1:0;
}
