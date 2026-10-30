/* The race on the arcade's own code: CSeq::Init and CSeq::Exec, the arcade's race
 * sequence (the player's car, the traffic and what they hit), recompiled to C
 * (src/phys/phys_rc.c). This file sets the race up and reads back what to draw. */
#include "car.h"

#include <math.h>
#include <float.h>
#include <limits.h>
#include <stdarg.h>
#include <stdio.h>
#include <string.h>

#include "phys/rc_runtime.h"

void f_89878c4(void); /* yt::CSeq::Init(SConfigPlay const&) */
void f_8983f64(void); /* yt::CSeq::Exec(std::auto_ptr<clGameInput> const&) */
void f_89a2584(void); /* yt::CElapse::Init */
void f_89a2548(void); /* yt::CElapse::SetByMul */
void f_89825a8(void); /* yt::CSeq::GetInfoOtherCarDisp */
void f_89b45d0(void); /* yt::CMachine::GetInfoCarDisp */
void f_89b410c(void); /* yt::CMachine::GetInfoCarEffect */
#ifdef WMMT_EGL
#include <stdlib.h>
void f_89bcca8(void); /* yt::CMcPilot::Drive, for the desktop harness's WMMT_PILOT */
#endif
void f_89ba620(void); /* yt::CMachine::GetInfoCarCamera */
void f_8982580(void); /* yt::CSeq::GetInfoMirrorCamera */
void f_8982338(void); /* yt::CSeq::GetInfoCarCamera */
void f_89c4000(void); /* yt::CAreaProcessorBase::GetInfoJctBlockDisp */
void f_89c50c0(void); /* yt::CSlit::GetFirstPoint(float, float) const */
void f_89ba05c(void); /* yt::CMachine::SetFirstPos(SFirstPoint const&, float) */
void f_8983950(void); /* yt::CSeq::Get2DInfoRace */
void f_8983874(void); /* yt::CSeq::Get2DInfoMap */
void f_898380c(void); /* yt::CSeq::Get2DInfoSign */
void f_898f518(void); /* yt::CSeq::GetInfoGoalLine */
void f_898f6d4(void); /* yt::CSeq::GetInfoSplitLine */
void f_8983e5c(void); /* yt::CSeq::GetInfoTenRivalLine */
void f_8983488(void); /* yt::CSeq::GetInfoRivalCarDisp */
void f_898287c(void); /* yt::CSeq::Get2DInfoStory */
void f_898317c(void); /* yt::CSeq::GetPlayResult */
void f_898332c(void); /* yt::CSeq::GetPlayLog(youTitle::_TitleRunningLog_ *) */
void f_858d8e8(void); /* youTitle::GetTitleList(_TitleData_ &, _TITLEDATALIST_ &) */
void f_899b378(void); /* yt::CConfigLoader::GetStorySeries(file, int, ESeries), returning SStorySeries */
void f_8982be8(void); /* yt::CSeq::Get2DInfoTenFight(S2DInfoTenFight *) */
void f_89923e4(void); /* yt::GetTenFightRaceField(EStage, level), returning SConfigRaceField */
/* YOURTMOVIE_CPP::clMovieSystem, the realtime movies (clRaceThread::initStory, race) */
void f_89fe784(void); /* clMovieSystem::clMovieSystem(unsigned int) */
void f_89fd9d0(void); /* clMovieSystem::Init(eMovieType, ECarType x4), returning the movie's length in frames */
void f_89fe890(void); /* clMovieSystem::UpDate(float frame) */
void f_89fde9c(void); /* clMovieSystem::GetRTMovieCamera(SInfoCarCamera *) */
void f_89fdfe8(void); /* clMovieSystem::GetRTMovieCarDisp(int, SInfoCarDisp *) */

/* arcade enums and data */
#define TRANS_AT 0u
#define TRANS_MT 1u
#define MODE_STORY 4u            /* EGameMode (GetEGameModeName) */
#define MODE_TIME_ATTACK 6u
/* SConfigPlay, what clRaceThread hands CSeq::Init */
#define CFG_CAR 0x00u
#define CFG_POWER 0x08u
#define CFG_HANDLING 0x0cu
#define CFG_TRANS 0x10u
#define CFG_STAGE 0x1cu
#define CFG_AREA 0x24u
#define CFG_DIST 0x28u
#define CFG_GOAL 0x2cu           /* the goal's odometer reading (SRaceField +0x10) */
#define CFG_MODE 0x34u
#define CFG_CARD 0x19u           /* a byte: the player has a card (clV386CardData::hasCard) */
#define CFG_LEVEL 0x38u          /* the story's loop (initStory: clWorkSpace +0x20, "lap") */
#define CFG_LOSSES 0x3cu         /* the episode's losses (clWorkSpace +0x24), easing the rivals */
#define CFG_RIVALS 0x44u         /* how many rivals (up to 3), then their ECharacter and ECarType */
#define CFG_RIVAL_CHAR 0x48u
#define CFG_RIVAL_CAR 0x54u
#define CFG_SERIES 0x40u         /* the story's ESeries (CSeq::Init: CConfigLoader::GetStorySeries) */
#define STORY_CONFIG 0x9433da8u  /* "data/carconfig/ytConfigStory.txt" */
#define RACE_FIELD 0x1cu         /* SConfigRaceField, 6 words: CFG_STAGE .. the goal and on */
#define CFG_TA_TRAFFIC 0xacu     /* clWorkSpace::isTaOtherCar: time attack with the traffic on */
#define CFG_TEN_LEVEL 0xb8u      /* the 10-in-a-row's level (clRaceThread::initTen: 10 = extend) */
#define MODE_TEN_FIGHT 7u        /* EGameMode of the 10-in-a-row */
/* CSeq's globals */
#define MACHINE_PTR 0x98028e4u   /* CMachine */
#define OTHER_GEN_PTR 0x9802894u /* COtherGen, the traffic */
#define LX_RIVALS 0x980289cu     /* yt::CLxRival *[3]: a versus' link cars (rivals 1..3) */
#define COUNTDOWN 0x9802a68u     /* CState: seconds of countdown left (Prep_CountDown sets 4) */
#define TIME_KEEPER_PTR 0x98028c8u /* CTimeKeeper, the checkpoints (the first is the start, the last the goal) */
#define TK_COUNT 0x00u           /* checkpoints */
#define TK_ODO 0x04u             /* float[]: the odometer reading of each (the last is the goal) */
#define TK_EXTEND 0x08u          /* float[]: seconds each one gives */
#define TK_SPLIT 0x10u           /* float[]: seconds since the start when each was passed */
#define TK_NEXT 0x14u            /* the next one to pass */
#define PLAY_VIEW 0x9802820u     /* CSeq's EPlayView (CSeq::GetInfoCarCamera hands it CMachine's) */
#define STATE 0x9802a78u         /* CState::GetStateName: 2 Run, 4 SlowDown, 5 StopWait, 6 TimeUp, 7 GoalWait, 8 Goal */
/* CSeq::Init gets the STireDimension from the display model here: a hook hands it the spec's */
#define TIRE_HOOK 0x898aa8du
#define TIRE_FRAME 0xd4u         /* the STireDimension at ebp - 0xd4 */
#define TEN_TIRE_HOOK 0x8985a4au   /* CSeq::Exec's next 10-in-a-row rival: CRivalSetting::GetSettingPt's 4th argument */
#define CUTIN_ON 0x9802970u      /* yt::CSeq::GetCutInInfoPt: the info at *CUTIN_INFO while set */
#define CUTIN_INFO 0x9802860u
#define TEN_RIVAL_NO 0x9802accu    /* CTenSeq: the rival on the road now, 0 the first */
#define RIVAL_TIRE_HOOK 0x898e699u /* and CRivalSetting::GetSettingPt the rival's, its 6th argument */
/* CMachine fields */
#define M_ENGINE 0x2c4u          /* CTransmission (engine state at +8: rad/s, AT flag at +0x34, gear at +0x3c) */
#define M_TURBO 0x340u           /* CTurbo (boost at +4) */
#define M_AREA_PROC 0x938u       /* CAreaProcessorBase*, followed by its SAreaProcessorInfo */
#define JCT_BLOCK_NAMES 0x93d9d00u /* const char* by junction block id (clCourseArrow) */
#define TA_LENGTHS 0x9778900u    /* GetTimeAttackRaceField: by EStage from 363, {u32 start, f32 length in mm} */
#define TA_STAGE0 363u

/* The time attack courses by course card, with the start each one gets from
 * GetConfigRaceField_TimeAttack(EStage): area and distance; and the arcade's course id
 * (nsMenuCheck::taCourseIDFromMenuOrder of the card's place: ids 5, 7 and 11 have no card). */
static const struct { uint32_t stage, area; float dist; int id; } COURSES[CAR_COURSES] = {
  { 363, 28, 1535000.0f, 0 },   /* TA_C1In: TkC1_In */
  { 364, 36, 2930000.0f, 1 },   /* TA_C1Out: TkGinza_Down */
  { 365, 44, 1095000.0f, 2 },   /* TA_RingLeft: TkN9_In */
  { 366, 37, 670000.0f, 3 },    /* TA_RingRight: TkGinza_Up */
  { 367, 45, 7220000.0f, 4 },   /* TA_WanganEast: TkN9_Out */
  { 369, 13, 1185000.0f, 6 },   /* TA_K1_Down: KgK1_Out */
  { 376, 64, 150000.0f, 8 },    /* NAGOYA: NkNagoya */
  { 371, 5, 5000.0f, 9 },       /* OSAKA: OsTonbori */
  { 377, 72, 11870000.0f, 14 }, /* FUKUOKA: FkFukuoka */
  { 372, 59, 390000.0f, 10 },   /* HAKONE_OUTWARD: HkHakone */
  { 374, 55, 3630000.0f, 12 },  /* SYUTOKO_TOKYO: TkTennouzu_Up */
  { 375, 56, 815000.0f, 13 },   /* SYUTOKO_KANAGAWA: TkTokyokou_Down */
};

int car_course_id(int course) { return course >= 0 && course < CAR_COURSES ? COURSES[course].id : 0; }
int car_course_ta_slot(int course) {
  return course >= 0 && course < CAR_COURSES && COURSES[course].stage - TA_STAGE0 < 15u ? (int)(COURSES[course].stage - TA_STAGE0) : -1;
}

/* EAreaId by city (the area names' prefixes): Os 1..9, Hk 58..61, Nk 62..69, Fk 70..73 */
int car_area_city(int area) {
  if (area >= 1 && area <= 9) return CAR_OSAKA;
  if (area >= 58 && area <= 61) return CAR_HAKONE;
  if (area >= 62 && area <= 69) return CAR_NAGOYA;
  if (area >= 70 && area <= 73) return CAR_FUKUOKA;
  return CAR_TOKYO;
}

int car_course_city(int course) { return course >= 0 && course < CAR_COURSES ? car_area_city((int)COURSES[course].area) : CAR_TOKYO; }

const car_spec CAR_SPEC_FD3S = { 5u, 5, { 690.0f, 298.3f, 1285.0f, 684.9f, 298.3f, -1065.2f }, 5, 24, 10 };

int car_tune_hp(int stock_hp, int power) {
  /* the table at 0x9736a60 (gauge_pow_to_Horse's too) */
  static const short HP[CAR_TUNE_MAX + 1] = { 0,   360, 400, 420, 450, 470, 500, 530, 550, 580, 600, 620, 640,
                                              660, 680, 700, 720, 740, 760, 780, 800, 810, 815, 820, 825 };
  if (power <= 0) return stock_hp;
  return HP[power > CAR_TUNE_MAX ? CAR_TUNE_MAX : power];
}

int car_tune_grade(int power, int handling) {
  int d = handling - power;
  return d <= -8 ? CAR_GRADE_DG : d <= -4 ? CAR_GRADE_D : d <= 3 ? CAR_GRADE_B : d <= 7 ? CAR_GRADE_G : CAR_GRADE_HG;
}

/* the traffic's ECarType (42..45) to its model */
static const int TRAFFIC_MODEL[4] = { CAR_TRAFFIC_RC2, CAR_TRAFFIC_NZE121, CAR_TRAFFIC_KZH100G, CAR_TRAFFIC_TRUCK };
#define TRAFFIC_TYPE0 42u
#define TRAFFIC_SLOT0 4 /* COtherGen's cars are 4..15 (0..3 the player and the rivals) */

static struct {
  char image[1024], config[1024];
  int course;
  car_spec spec;
  uint32_t m, gen, gin, gin_ptr, disp, eff, cam, mirror, jct, info_race, info_map, info_sign, lines, ten_line;
  int view;
  int manual, lever, top_lever; /* lever 0..gears-1, -1 = neutral */
  int traffic_model[CAR_TRAFFIC];
  int has_rival, n_rival;
  int ten_stage, ten_level; /* car_set_ten: the 10-in-a-row's EStage (0: not one) and level */
  int n_ten;
  uint32_t info_ten;
  car_rival ten[CAR_TEN_RIVALS];
  car_rival rival[CAR_RIVALS];
  /* car_set_versus: the link race's machines (vs_n others), ramp, km and seed */
  int vs_on, vs_pcb, vs_n, vs_ramp;
  int vs_race; /* the link's cars in the race now (0: not a versus) */
  float vs_km;
  unsigned vs_seed;
  car_link_car vs[CAR_LINK_MACHINES - 1];
  car_link_io vs_io;
  uint32_t info_story, result, first_pt, title_log;
  int ready;
} P = { .view = CAR_VIEW_BEHIND };

static uint32_t fbits(float v) { uint32_t u; memcpy(&u, &v, 4); return u; }

/* cdecl call into recompiled code, with arguments on the emulated stack */
static uint32_t call(void (*fn)(void), int n, ...) {
  uint32_t a[10];
  va_list ap;
  va_start(ap, n);
  for (int i = 0; i < n; i++) a[i] = va_arg(ap, uint32_t);
  va_end(ap);
  esp = RC_STACK_TOP - 0x1000 - 4 * n - 4;
  W32(esp, 0x20200000u);
  for (int i = 0; i < n; i++) W32(esp + 4 + 4 * i, a[i]);
  fn();
  return eax;
}

int car_init(const char *data_dir, char *err, int err_len) {
  snprintf(P.image, sizeof P.image, "%s/phys.img", data_dir);
  /* yt::CConfigLoader's files: data_dir/carconfig (the story's rivals, the 10-in-a-row) */
  snprintf(P.config, sizeof P.config, "%s", data_dir);
  rc_config_dir = P.config;
  FILE *f = fopen(P.image, "rb");
  if (!f) {
    snprintf(err, err_len, "cannot load %s", P.image);
    return -1;
  }
  fclose(f);
  return 0;
}

/* CSeq::Init: STireDimension, normally from the display model: front (x, radius, z), rear, spokes; mm */
static void on_hook(uint32_t at) {
  if (at == RIVAL_TIRE_HOOK) { /* CSeq::Init's loop over the rivals: edi the rival's number */
    const car_rival *r = &P.rival[edi >= 1 && edi <= (uint32_t)P.n_rival ? edi - 1 : 0];
    uint32_t tire = M32(esp + 0x14);
    for (int i = 0; i < 6; i++) WF(tire + 4 * i, r->tyres[i]);
    W32(tire + 0x18, (uint32_t)r->spokes);
    return;
  }
  if (at == TEN_TIRE_HOOK) {
    uint32_t k = M32(TEN_RIVAL_NO);
    if (k >= (uint32_t)P.n_ten) return;
    uint32_t tire = M32(esp + 0xc);
    for (int i = 0; i < 6; i++) WF(tire + 4 * i, P.ten[k].tyres[i]);
    W32(tire + 0x18, (uint32_t)P.ten[k].spokes);
    return;
  }
  if (at != TIRE_HOOK) return;
  uint32_t tire = ebp - TIRE_FRAME;
  for (int i = 0; i < 6; i++) WF(tire + 4 * i, P.spec.tyres[i]);
  W32(tire + 0x18, (uint32_t)P.spec.spokes);
  /* the cars after it, 0x1c apart (ebp-0xb8, -0x9c, -0x80): yt::GetTireDimension's for cars 1..3
   * (clCarDispManager::getRivalTireParam, the display side's). The realtime movies' ghosts take
   * them (the loop at 0x898bc15: CGhostSetting::GetSettingPt with car i's); unset, their tyres
   * stood nowhere (NaN) */
  for (int k = 0; k < P.n_rival && k < 3; ++k) {
    uint32_t t = tire + 0x1cu * (uint32_t)(k + 1);
    for (int i = 0; i < 6; i++) WF(t + 4 * i, P.rival[k].tyres[i]);
    W32(t + 0x18, (uint32_t)P.rival[k].spokes);
  }
  /* in a versus the link's cars (CSeq::Init's loop at 0x898e800: yt::CLxRivalSetting::GetSettingPt
   * with car k + 1's) */
  for (int k = 0; P.vs_on && k < P.vs_n; ++k) {
    uint32_t t = tire + 0x1cu * (uint32_t)(k + 1);
    for (int i = 0; i < 6; i++) WF(t + 4 * i, P.vs[k].tyres[i]);
    W32(t + 0x18, (uint32_t)P.vs[k].spokes);
  }
}

void car_set_rivals(const car_rival *rivals, int n) {
  P.n_rival = n < 0 ? 0 : n > CAR_RIVALS ? CAR_RIVALS : n;
  P.has_rival = P.n_rival > 0;
  for (int i = 0; i < P.n_rival; ++i) P.rival[i] = rivals[i];
}

void car_set_ten(int stage, int level, const car_rival *rivals, int n) {
  P.ten_stage = stage;
  P.ten_level = level;
  P.n_ten = n < 0 ? 0 : n > CAR_TEN_RIVALS ? CAR_TEN_RIVALS : n;
  for (int i = 0; i < P.n_ten; ++i) P.ten[i] = rivals[i];
}

/* The versus race. clRaceThread::initJoin fills SConfigPlay's link part: +0x60 the join's
 * NoRubberBand, +0x64 this machine's place among the joined (its PCB id's), +0x68 how many others,
 * then per other machine i: +0x6c its PCB id, +0x78 its place, +0x84 its ECarType (from its card),
 * +0x90 / +0x9c its power and handling tune, and +0xa8 the race's random number; the start from
 * GetConfigRaceField_Battle(ERamp of the join ramp: table 0x9739140, +8) and the goal its distance
 * on (clNet::getJoinDist km). CSeq::Init then has CLinx::Init(+0x64, +0x68, +0x6c, +0x78). */
#define MODE_BATTLE 5u
#define CFG_LINK_NO_BAND 0x60u
#define CFG_LINK_PLACE 0x64u
#define CFG_LINK_OTHERS 0x68u
#define CFG_LINK_PCB 0x6cu
#define CFG_LINK_OTHER_PLACE 0x78u
#define CFG_LINK_CAR 0x84u
#define CFG_LINK_POWER 0x90u
#define CFG_LINK_HANDLING 0x9cu
#define CFG_LINK_RANDOM 0xa8u
#define JOIN_RAMPS 0x9739140u /* the join ramps: {name, course, ERamp, ...} */
#define LINK_BUF 0x400u       /* clNet's race packet buffers */
void f_8992604(void); /* yt::GetBattleRaceField(ERamp) */

void car_set_versus(int pcb, const car_link_car *others, int n, int ramp, float km, unsigned seed, const car_link_io *io) {
  P.vs_on = n > 0 && io;
  P.vs_pcb = pcb;
  P.vs_n = n < 0 ? 0 : n > CAR_LINK_MACHINES - 1 ? CAR_LINK_MACHINES - 1 : n;
  for (int i = 0; i < P.vs_n; ++i) P.vs[i] = others[i];
  P.vs_ramp = ramp < 0 || ramp >= CAR_LINK_RAMPS ? 0 : ramp;
  P.vs_km = km;
  P.vs_seed = seed;
  if (io) P.vs_io = *io;
}

const char *car_link_ramp_name(int ramp) {
  if (ramp < 0 || ramp >= CAR_LINK_RAMPS || !P.ready) return "";
  return (const char *)VA(M32(M32(JOIN_RAMPS + 4u * (uint32_t)ramp)));
}

/* clNet::receiveRacePacket / sendRacePacket, the port's */
static void link_receive(void) { if (P.vs_io.receive) P.vs_io.receive(P.vs_io.ctx); }
static void link_send(void) { if (P.vs_io.send) P.vs_io.send(VA(rc_link_tx), CAR_LINK_PACKET, P.vs_io.ctx); }

void car_link_deliver(int pcb, const unsigned char *packet, int len) {
  if (!rc_link_rx || pcb < 0 || pcb >= CAR_LINK_MACHINES || len < CAR_LINK_PACKET) return;
  memcpy(VA(rc_link_rx + LINK_BUF * (uint32_t)pcb), packet, CAR_LINK_PACKET);
}

/* clCarDispManager::setupOtherCar: a traffic car comes on the road; its model */
static int on_other_setup(uint32_t slot, uint32_t type) {
  int i = (int)slot - TRAFFIC_SLOT0;
  if (i >= 0 && i < CAR_TRAFFIC) P.traffic_model[i] = type - TRAFFIC_TYPE0 < 4 ? TRAFFIC_MODEL[type - TRAFFIC_TYPE0] : 0;
  return 1;
}

static void first_frame(car_state *c);

int car_start(car_state *c, int course, int manual, const car_spec *spec) {
  /* a fresh arcade memory image per race, like a fresh boot of CSeq::Init */
  P.ready = 0;
  if (course < 0 || course >= CAR_COURSES || rc_load_image(P.image) != 0) return -1;
  P.course = course;
  P.manual = manual != 0;
  P.spec = spec ? *spec : CAR_SPEC_FD3S;
  P.top_lever = P.spec.gears - 1;
  memset(P.traffic_model, 0, sizeof P.traffic_model);
  rc_reset_heap();
  rc_on_hook = on_hook;
  rc_on_other_setup = on_other_setup;
  /* Normal time attack: no traffic; the arcade's hidden traffic-button variant is not selected. */
  uint32_t cfg = rc_alloc(0x200);
  W32(cfg + CFG_CAR, P.spec.type);
  W32(cfg + CFG_POWER, (uint32_t)P.spec.power);
  W32(cfg + CFG_HANDLING, (uint32_t)P.spec.handling);
  W32(cfg + CFG_TRANS, P.manual ? TRANS_MT : TRANS_AT);
  W32(cfg + CFG_STAGE, COURSES[course].stage);
  W32(cfg + CFG_AREA, COURSES[course].area);
  WF(cfg + CFG_DIST, COURSES[course].dist);
  WF(cfg + CFG_GOAL, COURSES[course].dist + MF(TA_LENGTHS + 8 * (COURSES[course].stage - TA_STAGE0) + 4));
#ifdef WMMT_EGL
  if (getenv("WMMT_TA_GOAL")) /* test: the goal this many m from the start */
    WF(cfg + CFG_GOAL, COURSES[course].dist + 1000.0f * (float)atof(getenv("WMMT_TA_GOAL")));
#endif
  W32(cfg + CFG_MODE, MODE_TIME_ATTACK);
  W32(cfg + CFG_TA_TRAFFIC, 0u);
  if (P.has_rival) { /* the story mode's race against its rivals */
    W32(cfg + CFG_MODE, MODE_STORY);
    W32(cfg + CFG_LEVEL, (uint32_t)P.rival[0].level);
    W32(cfg + CFG_LOSSES, (uint32_t)P.rival[0].losses);
    /* the save is the card: with one, a car tuned 1 step or less meets the exhibition
     * characters' easy settings from series 36 on (CSeq::Init) */
    W8(cfg + CFG_CARD, 1u);
    W32(cfg + CFG_RIVALS, (uint32_t)P.n_rival);
    for (int i = 0; i < P.n_rival; ++i) {
      W32(cfg + CFG_RIVAL_CHAR + 4 * (uint32_t)i, (uint32_t)P.rival[i].character);
      W32(cfg + CFG_RIVAL_CAR + 4 * (uint32_t)i, P.rival[i].type);
    }
    W32(cfg + CFG_SERIES, (uint32_t)P.rival[0].series);
    /* the series' own start and goal, as the story's menus set them (GetConfigRaceField_Story:
     * the SConfigRaceField is the first 6 words of the series' config) */
    uint32_t field = rc_alloc(0x40);
    call(f_899b378, 4, field, STORY_CONFIG, 0u, (uint32_t)P.rival[0].series);
    for (int i = 0; i < 6; ++i) W32(cfg + RACE_FIELD + 4 * i, M32(field + 4 * i));
    fprintf(stderr, "story series %d (loop %d, lost %d): stage %u area %u dist %.0f goal %.0f\n", P.rival[0].series,
            P.rival[0].level, P.rival[0].losses, M32(cfg + CFG_STAGE),
            M32(cfg + CFG_AREA), MF(cfg + CFG_DIST), MF(cfg + CFG_GOAL));
  }
  rc_link_tx = rc_link_rx = 0;
  rc_on_link_receive = rc_on_link_send = NULL;
  if (P.vs_on) { /* a versus (clRaceThread::initJoin) */
    W32(cfg + CFG_MODE, MODE_BATTLE);
    W32(cfg + CFG_TA_TRAFFIC, 0u);
    uint32_t field = rc_alloc(0x40), eramp = M32(M32(JOIN_RAMPS + 4u * (uint32_t)P.vs_ramp) + 8);
    call(f_8992604, 2, field, eramp);
    for (int i = 0; i < 6; ++i) W32(cfg + RACE_FIELD + 4 * i, M32(field + 4 * i));
    WF(cfg + CFG_GOAL, MF(cfg + CFG_DIST) + P.vs_km * 1000000.0f);
    W8(cfg + CFG_LINK_NO_BAND, 0u);
    /* the places: PCB ids in order (initJoin's from the join list) */
    int place = 0;
    for (int i = 0; i < P.vs_n; ++i) place += P.vs[i].pcb < P.vs_pcb;
    W32(cfg + CFG_LINK_PLACE, (uint32_t)place);
    W32(cfg + CFG_LINK_OTHERS, (uint32_t)P.vs_n);
    for (int i = 0; i < P.vs_n; ++i) {
      int pl = P.vs[i].pcb > P.vs_pcb;
      for (int j = 0; j < P.vs_n; ++j) pl += P.vs[j].pcb < P.vs[i].pcb;
      W32(cfg + CFG_LINK_PCB + 4u * (uint32_t)i, (uint32_t)P.vs[i].pcb);
      W32(cfg + CFG_LINK_OTHER_PLACE + 4u * (uint32_t)i, (uint32_t)pl);
      W32(cfg + CFG_LINK_CAR + 4u * (uint32_t)i, P.vs[i].type);
      W32(cfg + CFG_LINK_POWER + 4u * (uint32_t)i, (uint32_t)P.vs[i].power);
      W32(cfg + CFG_LINK_HANDLING + 4u * (uint32_t)i, (uint32_t)P.vs[i].handling);
    }
    W32(cfg + CFG_LINK_RANDOM, P.vs_seed);
    rc_link_pcb = (uint32_t)P.vs_pcb;
    rc_link_tx = rc_alloc(LINK_BUF);
    rc_link_rx = rc_alloc(LINK_BUF * CAR_LINK_MACHINES);
    rc_on_link_receive = link_receive;
    rc_on_link_send = link_send;
    fprintf(stderr, "versus pcb %d place %d others %d ramp %d (ERamp %u): stage %u area %u dist %.0f goal %.0f\n", P.vs_pcb, place,
            P.vs_n, P.vs_ramp, eramp, M32(cfg + CFG_STAGE), M32(cfg + CFG_AREA), MF(cfg + CFG_DIST), MF(cfg + CFG_GOAL));
  }
  if (P.ten_stage) { /* the 10-in-a-row (clRaceThread::initTen): its level and course's start */
    W32(cfg + CFG_MODE, MODE_TEN_FIGHT);
    W32(cfg + CFG_TA_TRAFFIC, 0u);
    W32(cfg + CFG_TEN_LEVEL, (uint32_t)P.ten_level);
    uint32_t field = rc_alloc(0x40);
    call(f_89923e4, 3, field, (uint32_t)P.ten_stage, (uint32_t)P.ten_level);
    for (int i = 0; i < 6; ++i) W32(cfg + RACE_FIELD + 4 * i, M32(field + 4 * i));
    fprintf(stderr, "ten stage %d level %d: area %u dist %.0f goal %.0f\n", P.ten_stage, P.ten_level, M32(cfg + CFG_AREA),
            MF(cfg + CFG_DIST), MF(cfg + CFG_GOAL));
  }
  call(f_89878c4, 1, cfg);
  P.vs_race = P.vs_on ? P.vs_n : 0;
  P.vs_on = 0; /* car_set_versus is for this race only */
  call(f_89a2584, 1, fbits(1.0f / 60.0f));
  call(f_89a2548, 1, fbits(1.0f));
  /* the time attack starts rolling (GetSeqStartOfs_Mc): CState's countdown (Prep_CountDown,
   * 4 s) has the pilot drive, then the race runs with the car in the player's hands */
  P.m = M32(MACHINE_PTR);
  P.gen = M32(OTHER_GEN_PTR);
  P.gin = rc_alloc(0x40);
  P.gin_ptr = rc_alloc(4);
  W32(P.gin_ptr, P.gin);
  P.disp = rc_alloc(0x260);
  P.eff = rc_alloc(0x100);
  P.cam = rc_alloc(0x100);
  P.mirror = rc_alloc(0x100);
  P.jct = rc_alloc(8);
  P.info_race = rc_alloc(0x40);
  P.info_map = rc_alloc(0x20);
  P.info_sign = rc_alloc(8);
  P.lines = rc_alloc(48);
  P.ten_line = rc_alloc(24);
  P.title_log = rc_alloc(CAR_TITLE_LOG);
  P.info_story = rc_alloc(0x40);
  P.info_ten = rc_alloc(0xa0);
  P.result = rc_alloc(0x40);
  P.first_pt = rc_alloc(0x20);
  P.ready = 1;
  first_frame(c);
  return 0;
}

/* clCarDisp::update: tyre nodes +0x8c..+0x98 (FL, FR, RL, RR) take SInfoCarDisp +0x188, +0x148,
 * +0x208, +0x1c8; their spin nodes +0x9c..+0xa8 a turn about x by +0x248..+0x254 */
static void read_tyres(float tyre[4][16], float rot[4]) {
  static const uint32_t at[4] = { 0x188, 0x148, 0x208, 0x1c8 };
  for (int k = 0; k < 4; ++k) {
    memcpy(tyre[k], VA(P.disp + at[k]), sizeof tyre[k]);
    rot[k] = MF(P.disp + 0x248 + 4 * (uint32_t)k);
  }
}

static void read_effect(car_effect *e) {
  e->spark = MF(P.eff + 0x68);
  memcpy(e->at, VA(P.eff + 0x6c), sizeof e->at);
  memcpy(e->dir, VA(P.eff + 0x78), sizeof e->dir);
  e->backfire_pulse = (unsigned char)M8(P.eff + 0x84);
  memcpy(e->backfire_vec, VA(P.eff + 0x30), sizeof e->backfire_vec);
  double x = e->backfire_vec[0], y = e->backfire_vec[1], z = e->backfire_vec[2];
  double length = sqrt(x*x + y*y + z*z);
  e->backfire_type = isfinite(length) && length < (double)INT_MAX + 1.0
                       ? (int)length % 2 : -1;
}

static void read_body(car_state *c) {
  call(f_89b45d0, 2, P.m, P.disp);
  /* igMatrix44f is row-major with the translation in the last row: the same
   * memory layout as a GL column-major matrix. Units are already display units. */
  memcpy(c->body, VA(P.disp + 4), sizeof c->body);
  read_tyres(c->tyre, c->tyre_rot);
  c->brake = M8(P.disp + 0x144);
  c->spot = M8(P.disp + 0x146) == 1;
  call(f_89b410c, 2, P.m, P.eff);
  read_effect(&c->effect);
  const float *M = c->body;
  c->pos[0] = M[12];
  c->pos[1] = M[13];
  c->pos[2] = M[14];
  c->yaw = atan2f(M[8], M[10]);
  c->pitch = asinf(fmaxf(-1.0f, fminf(1.0f, M[9])));
  c->roll = atan2f(M[1], M[5]);
}

/* SInfoCarCamera: igMatrix44f view (world -> camera; row-major with the translation
 * last, so GL column-major as it stands), horizontal fov at +0x40, near plane at +0x44,
 * the radial blur at +0x48 (clRaceThread::yield hands it to clGraphicFrame::setBlur).
 * clRaceThread::race takes CSeq::GetInfoCarCamera's: CMachine's with the play view and true
 * (the camera sways with the car, CCamSway, so once per arcade frame), but in the
 * 10-in-a-row while a rival comes on (play state 1) CSeqCamTen's, which shows it arriving,
 * and once a story or 10-in-a-row race reaches its goal (state 8) CSeqCamGoal's. */
static void read_camera(car_state *c) {
  W32(PLAY_VIEW, (uint32_t)P.view);
  call(f_8982338, 1, P.cam);
  memcpy(c->cam_view, VA(P.cam), sizeof c->cam_view);
  const float *V = c->cam_view;
  for (int j = 0; j < 3; j++) c->cam_pos[j] = -(V[12] * V[4 * j] + V[13] * V[4 * j + 1] + V[14] * V[4 * j + 2]);
  c->cam_fov = MF(P.cam + 0x40);
  c->cam_near = MF(P.cam + 0x44);
  c->cam_blur = fminf(1.0f, fmaxf(0.0f, MF(P.cam + 0x48)));
  /* the back mirror's (clRaceThread::yield: CSeq::GetInfoMirrorCamera, CMachine's
   * GetInfoCarMirror: no sway), only for the view from the roof, the one that shows it */
  c->mirror = P.view == CAR_VIEW_ROOF && P.mirror && (call(f_8982580, 1, P.mirror) & 0xff);
  if (c->mirror) {
    memcpy(c->mirror_view, VA(P.mirror), sizeof c->mirror_view);
    c->mirror_fov = MF(P.mirror + 0x40);
    c->mirror_near = MF(P.mirror + 0x44);
  }
}

void car_view(int view) { P.view = view; }

/* SInfoJctBlockDisp, as CSeq::GetInfoJctBlockDisp gets it for clCourseArrow: the two
 * junction blocks (arrow boards closing the branches off the course) to show now. */
static void read_jct_blocks(car_state *c) {
  call(f_89c4000, 3, P.jct, M32(P.m + M_AREA_PROC), P.m + M_AREA_PROC + 4);
  for (int i = 0; i < 2; i++) c->jct_block[i] = (int)M32(P.jct + 4 * i);
}

/* The time attack's consoles: S2DInfoRace (+4 time left, +8 time since the start, +0xc mm
 * to the goal) and S2DInfoMap (+0 area, +4 the next, +8 z, +0xc x in display units, +0x10
 * heading), as CSeq hands them to clStandardConsole and clMiniMap; the sections from the
 * CTimeKeeper the way clWorkSpace gets them for the section times. */
/* Get2DInfoRace uses FLT_MAX as the unavailable sentinel. Check before fmaxf
 * converts a negative or NaN distance to zero for the existing displays. */
static int race_remain_valid(float mm) { return isfinite(mm) && mm >= 0.0f && mm < FLT_MAX; }

static void read_race(car_race *r) {
  call(f_8983950, 1, P.info_race);
  call(f_8983874, 1, P.info_map);
  call(f_898380c, 1, P.info_sign);
  { /* CSeq::Exec 0x8984ff7: do not use elapsed time or the absolute odometer. */
    uint32_t m = M32(MACHINE_PTR);
    r->story_distance_valid = m != 0 && !P.ten_stage;
    r->story_distance = r->story_distance_valid ? (MF(m + 0x970u) - MF(0x9802908u)) * 0.001f : 0.0f;
  }
  r->countdown = MF(P.info_race);
  r->time_left = MF(P.info_race + 4);
  float remain_mm = MF(P.info_race + 0xc);
  r->remain_valid = race_remain_valid(remain_mm);
  r->remain = fmaxf(0.0f, remain_mm * 0.001f);
  uint32_t st = M32(STATE);
  int was = r->state;
  r->play_state = (int)st;
  r->state = st >= 7 && st <= 8 ? CAR_RACE_GOAL : st >= 4 && st <= 6 ? CAR_RACE_TIME_UP : CAR_RACE_RUN;
  /* clRaceThread::race returns on clWorkSpace::getPlayState 8 (setGoal) or 6 (setTimeUp);
   * in the time attack GoalWait (7) gives way to Goal the next frame (Ck_GoalWait_2_Goal).
   * A story race also ends on 3 (Defeat) and 10 (Suspend: Ck_X_2_Suspend, the odometer past
   * the episode's distance at 0x9802a7c; clRaceThread::race fades out and returns). */
  r->over = st == 8 || st == 6 || st == 3 || st == 10;
  /* the arcade's total runs on after the time is up; the console's stops there */
  if (r->state != CAR_RACE_TIME_UP || was != CAR_RACE_TIME_UP) r->total = MF(P.info_race + 8);
  uint32_t tk = M32(TIME_KEEPER_PTR);
  int n = tk ? (int)M32(tk + TK_COUNT) : 0, next = tk ? (int)M32(tk + TK_NEXT) : 0;
  int section = next - 1;
  if (n > 1 && section > r->section && section < n - 1) /* a checkpoint passed (not the goal) */
    r->extended = MF(M32(tk + TK_EXTEND) + 4 * (uint32_t)(next - 1));
  r->sections = n - 1 < CAR_SECTIONS ? n - 1 : CAR_SECTIONS;
  r->section = section < 0 ? 0 : section;
  for (int k = 0; k < next && k <= CAR_SECTIONS; k++) r->split[k] = MF(M32(tk + TK_SPLIT) + 4 * (uint32_t)k);
  r->area = (int)M32(P.info_map);
  { /* CSeq::GetInfoMyCarPlace */
    uint32_t m = M32(MACHINE_PTR);
    r->place = m ? (int)M32(M32(m + 0x93cu)) : 0;
    r->place_at = m ? MF(m + 0x7b4u + 0x1bcu) - MF(m + 0x7b4u + 0x180u) : 0.0f;
  }
  r->next_area = (int)M32(P.info_map + 4);
  r->map_z = MF(P.info_map + 8);
  r->map_x = MF(P.info_map + 0xc);
  r->map_angle = MF(P.info_map + 0x10);
  r->sign = (int)M32(P.info_sign + 4);
  { /* GetMapText(EAreaId, float) 0x899f4d0 (a stub in the recompile): table 0x9778980 of
     * {area, text below, threshold, text at or above}, keyed by the CSlit's 0x1bc - 0x180 */
    uint32_t slit = M32(0x98028e4u) + 0x7b4u, row = 0x9778980u + 16u * (uint32_t)r->area;
    float at = MF(slit + 0x1bc) - MF(slit + 0x180);
    r->map_text = r->area >= 0 && r->area < 75 ? (int)M32(MF(row + 8) > at ? row + 4 : row + 0xc) : 0;
  }
  /* clGoalLine::clLine::update: the goal's row while the race info has the goal ahead, the
   * checkpoint's whenever CSeq gives one */
  r->lines = 0;
  if (MF(P.info_race + 0xc) > 0.0f && (call(f_898f518, 2, P.lines, P.lines + 12) & 0xffu)) r->lines |= 1;
  if (call(f_898f6d4, 2, P.lines + 24, P.lines + 36) & 0xffu) r->lines |= 2;
  memcpy(r->line, VA(P.lines), sizeof r->line);
  if (P.ten_stage) {
    /* S2DInfoTenFight: +0 rivals beaten, +4.. the s each took, +0x84 s on the one now, +0x88
     * the rolling start's gear, +0x8c mm behind it (float), +0x90/+0x91 SwName, SwGear */
    memset(VA(P.info_ten), 0, 0xa0);
    call(f_8982be8, 1, P.info_ten);
    r->ten_beaten = (int)M32(P.info_ten);
    r->ten_rival = (int)M32(TEN_RIVAL_NO);
    for (int k = 0; k < 32; ++k) r->ten_time[k] = MF(P.info_ten + 4 + 4 * (uint32_t)k);
    r->ten_now = MF(P.info_ten + 0x84);
    r->ten_gear = (int)M32(P.info_ten + 0x88);
    r->ten_gap = MF(P.info_ten + 0x8c) * 0.001f;
    r->ten_sw_name = M8(P.info_ten + 0x90);
    r->ten_sw_gear = M8(P.info_ten + 0x91);
    uint32_t ci = M8(CUTIN_ON) ? M32(CUTIN_INFO) : 0;
    r->cut_char = ci ? (int)M32(ci + 0x4c) : -1;
    r->cut_start = ci && M8(ci + 0x50);
    r->cut_lose = ci && M8(ci + 0x51);
    r->ten_line_on = (call(f_8983e5c, 2, P.ten_line, P.ten_line + 12) & 0xffu) && st == 2;
    memcpy(r->ten_line, VA(P.ten_line), sizeof r->ten_line);
    /* all ten beaten (Goal): SPlayResult +0x14, CState::GetTenFightResult -> CTenSeq::GetResult
     * of the time left: 3 gold, 2 silver, 1 bronze (the workspace's TenResult, the card's) */
    if (st == 8 && !r->ten_medal) {
      call(f_898317c, 1, P.result);
      r->ten_medal = (int)M32(P.result + 0x14);
    }
  }
  if (P.vs_race) {
    /* yt::CSeq::Get2DInfoBattle (clJoinConsole's getInfoJoinRank / getInfoJoinAdvantage): the
     * player's odometer (CMachine +0x970) less each link rival's (CLxRival: +8 on the road,
     * +0x240 its packet, +0x30 there the odometer; 0 while it is not on), mm; the rank counts
     * those ahead */
    uint32_t m = M32(MACHINE_PTR);
    float odo = m ? MF(m + 0x970u) : 0.0f;
    r->vs_rank = 0;
    for (int i = 0; i < CAR_RIVALS; ++i) {
      uint32_t lx = M32(LX_RIVALS + 4u * (uint32_t)i);
      r->vs_on[i] = lx && i < P.vs_race;
      if (!r->vs_on[i]) continue;
      float d = odo - (M8(lx + 8u) ? MF(M32(lx + 0x240u) + 0x30u) : 0.0f);
      r->vs_gap[i] = d * 0.001f;
      if (d < 0.0f) r->vs_rank++;
    }
  }
  if (P.vs_race && (st == 3 || st == 6 || st == 8) && !r->vs_place) {
    /* a versus: SPlayResult +0 the place by the odometers (CState::Prep_Goal's ranking, 0 first;
     * the link's machines' from their finish packets), +0x10 whether the goal was reached */
    call(f_898317c, 1, P.result);
    r->vs_place = (int)M32(P.result) + 1;
    r->won = M32(P.result) == 0;
  }
  if ((st == 3 || st == 6 || st == 8 || st == 10) && !r->title_log_on) {
    /* the run's log for the titles (yt::CTitle's, CSeq::GetPlayLog) once it is over: the
     * _TitleRunningLog_ judgeTitle hands youTitle::GetTitleList at _TitleData_ +0x384 */
    memset(VA(P.title_log), 0, CAR_TITLE_LOG);
    call(f_898332c, 1, P.title_log);
    memcpy(r->title_log, VA(P.title_log), CAR_TITLE_LOG);
    r->title_log_on = 1;
  }
  if (P.has_rival) {
    /* S2DInfoStory +0: mm (a float) the rival is behind (negative: ahead). At the end (states 3
     * Defeat, 6 TimeUp, 8 Goal) SPlayResult has the player's place by the odometers
     * (CState::Prep_Goal's ranking, 0 first) at +0 and whether the goal was reached at +0x10. */
    call(f_898287c, 1, P.info_story);
    r->gap = MF(P.info_story) * 0.001f;
    /* +4 a rival i's, +0xc + i whether it is there (CSeq: its car on the road and not out) */
    for (int i = 0; i < 3; ++i) {
      r->story_gap[i] = MF(P.info_story + 4 * i) * 0.001f;
      r->story_on[i] = M8(P.info_story + 0xc + i);
    }
    /* clRaceThread::finiStory: won = rank 0 && !TimeUp && !Retire. GetPlayResult only fills
     * the result for 3/6/8 (mask 0x148); on 10 (Suspend: the episode's distance run without a
     * Defeat) the workspace keeps initRace's rank 0, so surviving the distance is a win. */
    if (st == 10) r->won = 1;
    else if (st == 3 || st == 6) r->won = 0;
    else if (st == 8) {
      call(f_898317c, 1, P.result);
      r->won = M32(P.result) == 0;
    }
  }
}

int car_title_list(const unsigned char *data, int n, int out[3]) {
  /* the image holds youTitle's tables; it is in once any race has been */
  if (!rc_mem && rc_load_image(P.image) != 0) return 0;
  /* above the stack call() starts at: _TitleData_ there, then the 3 slots */
  uint32_t td = RC_STACK_TOP - 0x800, list = RC_STACK_TOP - 0x40;
  memset(VA(td), 0, 0x7c0);
  memcpy(VA(td), data, (size_t)(n < 0x7c0 ? n : 0x7c0));
  call(f_858d8e8, 2, td, list);
  int got = 0;
  for (int i = 0; i < 3; ++i) {
    out[i] = (int)M32(list + 4 * (uint32_t)i);
    got += out[i] != 0;
  }
  return got;
}

const char *car_jct_block_name(int id) {
  if (id <= 0 || id >= CAR_JCT_BLOCKS) return NULL;
  const char *name = (const char *)VA(M32(JCT_BLOCK_NAMES + 4 * (uint32_t)id));
  /* a few carry the scene file's prefix ("yazirushi_all:..."); no strchr in the patched SDK */
  for (const char *p = name; *p; ++p)
    if (*p == ':') return p + 1;
  return name;
}

/* What the traffic shows this frame: each car COtherGen has on the road and, in a versus, the
 * other machines' share (CLxOtherGen: they drive it, it comes in their packets, this machine
 * hits it), as CSeq::GetInfoOtherCarDisp asks one then the other. */
static void read_traffic(car_state *c) {
  c->n_traffic = 0;
  for (int i = 0; P.gen && i < CAR_TRAFFIC; i++) {
    if (!(call(f_89825a8, 3, (uint32_t)(TRAFFIC_SLOT0 + i), P.disp, 0u) & 0xff)) continue;
    car_traffic *t = &c->traffic[c->n_traffic++];
    t->model = P.traffic_model[i];
    memcpy(t->body, VA(P.disp + 4), sizeof t->body);
  }
}

/* The rivals (CSeq::GetInfoRivalCarDisp, rivals 1..): off the road (out of reach) it says so. */
static void read_rival(car_state *c) {
  for (int i = 0; i < CAR_RIVALS; ++i) {
    c->rival_shown[i] = (i < P.n_rival || i < P.vs_race || (P.ten_stage && i == 0)) && (call(f_8983488, 3, (uint32_t)i + 1u, P.disp, P.eff) & 0xff);
    c->rival_effect[i].spark = 0;
    c->rival_effect[i].backfire_pulse = 0;
    memset(c->rival_effect[i].backfire_vec, 0, sizeof c->rival_effect[i].backfire_vec);
    c->rival_effect[i].backfire_type = -1;
    if (c->rival_shown[i]) {
      read_effect(&c->rival_effect[i]);
      memcpy(c->rival_body[i], VA(P.disp + 4), sizeof c->rival_body[i]);
      read_tyres(c->rival_tyre[i], c->rival_tyre_rot[i]);
      c->rival_brake[i] = M8(P.disp + 0x144);
      c->rival_spot[i] = M8(P.disp + 0x146) == 1;
    }
  }
}

/* The realtime movies: clRaceThread::initStory makes a clMovieSystem (0x1c1fc bytes) and Inits
 * it with the movie, the player's car and the rivals'; its CMovieEditWraps runs CSeq in its
 * movie mode, each car a yt::CGhost driven along its recorded trail (data/rtmovie/trail). Each
 * frame clRaceThread::race runs CSeq::Exec, then UpDate(frame), GetRTMovieCamera and
 * GetRTMovieCarDisp for cars 0..3; the frame goes on by 1 up to the length Init gave. */
#define MOVIE_SYSTEM_SIZE 0x1c1fcu
static uint32_t movie;

float car_movie_start(car_state *c, int id, const car_spec *player, const car_rival *rivals, int n) {
  P.ready = 0;
  movie = 0;
  if (rc_load_image(P.image) != 0) return 0;
  rc_reset_heap();
  P.spec = player ? *player : CAR_SPEC_FD3S;
  car_set_rivals(rivals, n);
  rc_on_hook = on_hook;
  rc_on_other_setup = on_other_setup;
  P.ten_stage = 0;
  uint32_t rival_type[CAR_RIVALS] = { 0 };
  for (int i = 0; i < P.n_rival; ++i) rival_type[i] = P.rival[i].type;
  uint32_t ms = rc_alloc(MOVIE_SYSTEM_SIZE);
  call(f_89fe784, 2, ms, 1u);
  call(f_89fd9d0, 6, ms, (uint32_t)id, P.spec.type, rival_type[0], rival_type[1], rival_type[2]);
  float len = (float)ST(0);
  fpop();
  call(f_89a2584, 1, fbits(1.0f / 60.0f));
  call(f_89a2548, 1, fbits(1.0f));
  P.m = M32(MACHINE_PTR);
  P.gen = M32(OTHER_GEN_PTR);
  P.gin = rc_alloc(0x40);
  P.gin_ptr = rc_alloc(4);
  W32(P.gin_ptr, P.gin);
  W32(P.gin + 0x14, 0xffffffffu);
  P.disp = rc_alloc(0x260);
  P.cam = rc_alloc(0x100);
  P.mirror = 0;
  movie = ms;
  memset(c, 0, sizeof *c);
  return len;
}

int car_movie_update(car_state *c, float frame) {
  if (!movie) return 0;
  call(f_8983f64, 1, P.gin_ptr);
  call(f_89fe890, 2, movie, fbits(frame));
  if (call(f_89fde9c, 2, movie, P.cam) & 0xff) {
    memcpy(c->cam_view, VA(P.cam), sizeof c->cam_view);
    const float *V = c->cam_view;
    for (int j = 0; j < 3; j++) c->cam_pos[j] = -(V[12] * V[4 * j] + V[13] * V[4 * j + 1] + V[14] * V[4 * j + 2]);
    c->cam_fov = MF(P.cam + 0x40);
    c->cam_near = MF(P.cam + 0x44);
    c->cam_blur = 0;
  }
  int shown = 0;
  for (int i = 0; i <= CAR_RIVALS; ++i) {
    int on = call(f_89fdfe8, 3, movie, (uint32_t)i, P.disp) & 0xff;
    shown |= on << i;
    if (!i) {
      if (!on) continue;
      memcpy(c->body, VA(P.disp + 4), sizeof c->body);
      read_tyres(c->tyre, c->tyre_rot);
      c->brake = M8(P.disp + 0x144);
      c->spot = M8(P.disp + 0x146) == 1;
      for (int j = 0; j < 3; j++) c->pos[j] = c->body[12 + j];
      continue;
    }
    c->rival_shown[i - 1] = on;
    if (on) {
      memcpy(c->rival_body[i - 1], VA(P.disp + 4), sizeof c->rival_body[i - 1]);
      read_tyres(c->rival_tyre[i - 1], c->rival_tyre_rot[i - 1]);
      c->rival_brake[i - 1] = M8(P.disp + 0x144);
      c->rival_spot[i - 1] = M8(P.disp + 0x146) == 1;
    }
  }
  c->n_traffic = 0;
  return shown;
}

void car_movie_end(void) { movie = 0; }

/* The top bar's reset key (a port extra: the arcade has no such key): the car put back on the
 * road where it is, facing the course in the start's lane, the way CSeq::Exec's 10-in-a-row
 * warp places it (0x898644c: yt::CSlit::GetFirstPoint at an odometer reading and a lateral
 * offset, CSeq::StartOfsAry[1] the start's; yt::CMachine::SetFirstPos, which sets the body,
 * the tyres, the gear for the speed, the hit and the camera effects, its speed the warp's
 * 120 km/h at most here, the car's own forward speed below that). */
#define START_OFS 0x9802920u     /* yt::CSeq::StartOfsAry: [1] the start's lateral offset */
#define WARP_SPEED 33333.333f    /* SetFirstPos's speed for the warp (mm/s: 120 km/h) */
static int hits; /* car_hits */
#define SPARK_CLEAR 30 /* frames without the scrape before its next start is a hit */
void car_hits(int on) { hits = on != 0; }

void car_reset(car_state *c) {
  if (!P.ready) return;
  c->vel_ok = 0; /* (the warp is no hit) */
  uint32_t slit = P.m + 0x7b4u;
  float odo = MF(slit + 0x1bc), speed = fminf(fmaxf(c->speed * 1000.0f, 0.0f), WARP_SPEED);
  call(f_89c50c0, 4, P.first_pt, slit, fbits(odo), M32(START_OFS + 4));
  call(f_89ba05c, 3, P.m, P.first_pt, fbits(speed));
  if (P.manual) { /* the lever to the gear SetFirstPos chose (CTransmission::SetFirst) */
    int g = (int)M32(P.m + M_ENGINE + 0x3c);
    P.lever = g < 1 ? 0 : g - 1 > P.top_lever ? P.top_lever : g - 1;
  }
  read_body(c); /* car_update's displacement from here */
  c->steer = 0;
}

static void first_frame(car_state *c) {
  memset(c, 0, sizeof *c);
  /* the rolling start is at about 120 km/h: second gear */
  P.lever = 1;
  read_body(c);
  read_camera(c);
  read_jct_blocks(c);
  read_traffic(c);
  read_rival(c);
#ifdef WMMT_EGL
  if (getenv("WMMT_TA_GOAL")) { /* test: the checkpoints and the goal (car_start) within this many m */
    uint32_t tk = M32(TIME_KEEPER_PTR);
    int n = tk ? (int)M32(tk + TK_COUNT) : 0;
    float len = 1000.0f * (float)atof(getenv("WMMT_TA_GOAL"));
    for (int k = 1; k < n; ++k) WF(M32(tk + TK_ODO) + 4u * (uint32_t)k, COURSES[P.course].dist + len * (float)k / (float)(n - 1));
  }
  if (getenv("WMMT_TA_TIME")) WF(0x9802a6cu, (float)atof(getenv("WMMT_TA_TIME"))); /* test: the time to start with */
#endif
  read_race(&c->race);
  c->manual = P.manual;
  c->gear = P.manual ? 2 : 1;
  c->on_ground = 1;
}

void car_set_manual(car_state *c, int manual) {
  P.manual = manual != 0;
  c->manual = P.manual;
  if (!P.ready) return;
  /* the flag CTransmission::TransOn reads every frame (a reset starts with P.manual's) */
  W32(P.m + M_ENGINE + 0x34, P.manual ? 0u : 1u);
  /* the lever takes over from the gear the automatic was in */
  if (P.manual) {
    int g = (int)M32(P.m + M_ENGINE + 0x3c);
    P.lever = g < 1 ? 0 : g - 1 > P.top_lever ? P.top_lever : g - 1;
  }
}

float car_kmh(const car_state *c) { return fabsf(c->speed) * 3.6f; }

void car_update(car_state *c, const car_input *in) {
  if (!P.ready) return;
  /* digital buttons: the arcade expects a wheel, so stand in for the driver's hands.
   * Turn in at a steady rate and centre faster, to full lock at any speed as the cabinet's
   * wheel goes; the tilt is a wheel already, followed closely */
  float target = in->steer;
  float rate = in->analog ? 12.0f : fabsf(target) > fabsf(c->steer) && target * c->steer >= 0 ? 3.0f : 8.0f;
  float ds = target - c->steer;
  if (ds > rate / 60.0f) ds = rate / 60.0f;
  if (ds < -rate / 60.0f) ds = -rate / 60.0f;
  c->steer += ds;

  /* clGameInput for CIO::Drive: wheel, pedals and the shift lever (gear - 1, -1 = neutral).
   * With AT the arcade ignores the lever. */
  if (P.manual) {
    if (in->shift_up && P.lever < P.top_lever) P.lever++;
    if (in->shift_down && P.lever > -1) P.lever--;
  }
  WF(P.gin, c->steer);
#ifdef WMMT_EGL
  if (getenv("WMMT_PILOT")) { /* test: the arcade's own pilot (CMcPilot) steers, flat out */
    uint32_t pilot = M32(0x98028dcu);
    W32(pilot, M32(0x9802924u));
    W32(pilot + 4, M32(0x9802928u));
    call(f_89bcca8, 2, pilot, P.m);
    WF(P.gin, -MF(pilot + 0x14));
  }
#endif
  WF(P.gin + 4, in->throttle);
  WF(P.gin + 8, in->brake);
  W32(P.gin + 0x14, P.manual ? (uint32_t)P.lever : 0xffffffffu);
  /* the arcade frame: the traffic's AI and life, the car, what everything hit, the
   * checkpoints and the time, the sounds' cues */
  call(f_8983f64, 1, P.gin_ptr);
  c->rev_lamp_frame = (int32_t)M32(0x9802828u); /* CSeq::nCnt, observation only */

  float prev[3] = { c->pos[0], c->pos[1], c->pos[2] };
  float prev_speed = c->speed;
  read_body(c);
  read_camera(c);
  read_jct_blocks(c);
  read_traffic(c);
  read_rival(c);
  read_race(&c->race);
  /* velocity from the frame's displacement (display units per frame -> m/s) */
  float v[3] = { (c->pos[0] - prev[0]) * 6.0f, (c->pos[1] - prev[1]) * 6.0f, (c->pos[2] - prev[2]) * 6.0f };
  const float *M = c->body;
  c->speed = v[0] * M[8] + v[1] * M[9] + v[2] * M[10];
  float lateral = v[0] * M[0] + v[1] * M[1] + v[2] * M[2];

  c->rpm = MF(P.m + M_ENGINE + 8) * (60.0f / 6.2831853f);
  /* CEngine::GetRevRate: rpm over the engine's rev limit (its parameters' +0x8c) */
  float limit = MF(M32(P.m + M_ENGINE) + 0x8c);
  c->rev_rate = limit > 0 ? fminf(1.0f, fmaxf(0.0f, c->rpm / limit)) : 0;
  c->boost = MF(P.m + M_TURBO + 4);
  int gear = (int)M32(P.m + M_ENGINE + 0x3c);
  if (gear != c->gear && c->gear) c->shift_event = gear > c->gear ? 1 : -1;
  c->gear = gear;

  /* effect cues: squeal from sideways speed, impact from a sudden loss of speed */
  float squeal = fminf(1.0f, fmaxf(0.0f, (fabsf(lateral) - 1.5f) / 5.0f));
  if (in->brake > 0.5f && fabsf(c->speed) > 15.0f) squeal = fmaxf(squeal, 0.7f * in->brake);
  c->slip += (squeal - c->slip) * 0.15f;
  float lost = fabsf(prev_speed) - fabsf(c->speed);
  c->wall_hit = fmaxf(0.0f, c->wall_hit - 1.0f / 60.0f);
  if (hits) {
    /* the frame's change of velocity across the ground, past what the tyres do (about 1.5 g,
     * 0.25 m/s a frame; a hard corner flat out comes to 0.4 on the Mi 6's log). Sliding along
     * a wall at 120 km/h bounces 0.5..0.7 m/s a frame: the wall's loop; a crash (snd_update's
     * from impact 6) from 0.8 m/s, a car's or a wall's hit */
    float dx = v[0] - c->vel[0], dz = v[2] - c->vel[2], dv = sqrtf(dx * dx + dz * dz);
    if (c->vel_ok && dv > 0.5f) c->wall_hit = 0.3f;
    if (c->vel_ok && dv > 0.8f) c->impact = fmaxf(c->impact, dv * 12.0f);
    /* the arcade's scrape: the wall's loop while it lasts, a light crash as it starts after
     * half a second clear (it flickers on and off along a wall) */
    if (c->effect.spark > 0.0f) {
      c->wall_hit = fmaxf(c->wall_hit, 0.2f);
      if (!c->sparked) c->impact = fmaxf(c->impact, 7.0f);
    }
    c->sparked = c->effect.spark > 0.0f ? SPARK_CLEAR : c->sparked > 0 ? c->sparked - 1 : 0;
    memcpy(c->vel, v, sizeof c->vel);
    c->vel_ok = 1;
  } else if (lost > 0.4f) { /* beyond what the brakes do (about 1.5 g = 0.25 m/s per frame) */
    c->impact = fmaxf(c->impact, lost * 4.0f);
    c->wall_hit = 0.3f;
  }
}
