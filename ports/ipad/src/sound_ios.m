// Audio output for sound.c (RemoteIO, 44.1 kHz stereo int16) plus the menu and race BGM
// through AVAudioPlayer, which decodes the AAC in hardware.
#import <AVFoundation/AVFoundation.h>
#import <AudioToolbox/AudioToolbox.h>

#include "sound.h"
#include "sound_ios.h"
#include <math.h>
#include <string.h>
#include <dispatch/dispatch.h>

static AudioComponentInstance unit;
static NSString *dir;
static AVAudioPlayer *bgm; /* the track main.m asked for (nil: none) */
static int paused;
static float bgm_volume = 1.0f;
static int failed_groups;
static int playing_group;
static NSString *last_original;
static void interruption(void *ref, UInt32 state);

/* The signed bundle is immutable: cache each conservative complete-group scan once. */
static int scan_bgm_group(int group) {
  NSString *base = [[[NSBundle mainBundle] resourcePath] stringByAppendingPathComponent:@"bgm-extra"];
  if (!base) return 0;
  NSString *prefix = group == 1 ? @"wm2" : @"wmr";
  int count = group == 1 ? 23 : 12;
  for (int i = 1; i <= count; ++i) {
    NSString *path = [base stringByAppendingPathComponent:[NSString stringWithFormat:@"%@_%02d.m4a", prefix, i]];
    BOOL isDirectory = NO;
    if (![[NSFileManager defaultManager] fileExistsAtPath:path isDirectory:&isDirectory] || isDirectory) return 0;
  }
  return 1;
}

int ios_bgm_group_available(int group) {
  if (group == 0) return 1;
  if (group < 1 || group > 2 || (__atomic_load_n(&failed_groups, __ATOMIC_SEQ_CST) & (1 << group))) return 0;
  static dispatch_once_t once[2];
  static int present[2];
  int index = group - 1;
  dispatch_once(&once[index], ^{ present[index] = scan_bgm_group(group); });
  /* Recheck after the scan: a playback failure overrides even a positive cache. */
  return present[index] && !(__atomic_load_n(&failed_groups, __ATOMIC_SEQ_CST) & (1 << group));
}

static int track_group(const char *name) {
  if (!name || strlen(name) != 6 || name[4] < '0' || name[4] > '9' || name[5] < '0' || name[5] > '9') return 0;
  int n = (name[4] - '0') * 10 + name[5] - '0';
  if (!strncmp(name, "wm2_", 4) && n >= 1 && n <= 23) return 1;
  if (!strncmp(name, "wmr_", 4) && n >= 1 && n <= 12) return 2;
  return 0;
}

@interface BgmErrors : NSObject <AVAudioPlayerDelegate>
@end
@implementation BgmErrors
- (void)audioPlayerDecodeErrorDidOccur:(AVAudioPlayer *)player error:(NSError *)error {
  /* AVFoundation may deliver delegate events off-main; retain the callback's player. */
  [player retain];
  dispatch_async(dispatch_get_main_queue(), ^{
    if (player == bgm && playing_group) {
      __atomic_fetch_or(&failed_groups, 1 << playing_group, __ATOMIC_SEQ_CST);
      fprintf(stderr, "BGM decode failed: %s\n", [[error description] UTF8String]);
      snd_ios_bgm(last_original ? [last_original UTF8String] : NULL);
    }
    [player release];
  });
}
@end
static BgmErrors *bgm_errors;

static void bgm_apply(void) {
  if (!paused) {
    if (bgm && ![bgm play] && playing_group) {
      __atomic_fetch_or(&failed_groups, 1 << playing_group, __ATOMIC_SEQ_CST);
      snd_ios_bgm(last_original ? [last_original UTF8String] : NULL);
    }
  } else [bgm pause];
}

static OSStatus render(void *ref, AudioUnitRenderActionFlags *flags, const AudioTimeStamp *ts, UInt32 bus,
                       UInt32 frames, AudioBufferList *io) {
  snd_mix((short *)io->mBuffers[0].mData, (int)frames);
  return noErr;
}

void snd_ios_start(NSString *data_dir) {
  AudioSessionInitialize(NULL, NULL, interruption, NULL);
  AVAudioSession *session = [AVAudioSession sharedInstance];
  /* Playback: sound even with the side switch on mute, like a handheld console */
  [session setCategory:AVAudioSessionCategoryPlayback error:nil];
  [session setActive:YES error:nil];

  AudioComponentDescription desc = { kAudioUnitType_Output, kAudioUnitSubType_RemoteIO,
                                     kAudioUnitManufacturer_Apple, 0, 0 };
  AudioComponent comp = AudioComponentFindNext(NULL, &desc);
  if (comp && AudioComponentInstanceNew(comp, &unit) == noErr) {
    AudioStreamBasicDescription fmt = { 0 };
    fmt.mSampleRate = SND_RATE;
    fmt.mFormatID = kAudioFormatLinearPCM;
    fmt.mFormatFlags = kAudioFormatFlagIsSignedInteger | kAudioFormatFlagIsPacked;
    fmt.mChannelsPerFrame = 2;
    fmt.mBitsPerChannel = 16;
    fmt.mBytesPerFrame = fmt.mBytesPerPacket = 4;
    fmt.mFramesPerPacket = 1;
    AudioUnitSetProperty(unit, kAudioUnitProperty_StreamFormat, kAudioUnitScope_Input, 0, &fmt, sizeof fmt);
    AURenderCallbackStruct cb = { render, NULL };
    AudioUnitSetProperty(unit, kAudioUnitProperty_SetRenderCallback, kAudioUnitScope_Input, 0, &cb, sizeof cb);
    if (AudioUnitInitialize(unit) == noErr) AudioOutputUnitStart(unit);
    else fprintf(stderr, "audio unit init failed\n");
  } else {
    fprintf(stderr, "no RemoteIO\n");
  }

  dir = [data_dir retain];
}

void snd_ios_bgm_volume(float multiplier) {
  if (![NSThread isMainThread]) {
    dispatch_async(dispatch_get_main_queue(), ^{ snd_ios_bgm_volume(multiplier); });
    return;
  }
  if (!isfinite(multiplier) || multiplier < 0 || multiplier > 1) return;
  bgm_volume = multiplier;
  bgm.volume = 0.5f * bgm_volume;
}

void snd_ios_bgm(const char *name) {
  if (![NSThread isMainThread]) {
    NSString *copy = name ? [[NSString alloc] initWithUTF8String:name] : nil;
    dispatch_async(dispatch_get_main_queue(), ^{ snd_ios_bgm(copy ? [copy UTF8String] : NULL); [copy release]; });
    return;
  }
  if (!name) {
    [bgm stop]; [bgm release]; bgm = nil; playing_group = 0;
    return;
  }
  int group = track_group(name);
  NSString *track = [NSString stringWithUTF8String:name];
  NSString *file = group ? [@"bgm-extra" stringByAppendingPathComponent:[track stringByAppendingPathExtension:@"m4a"]]
                         : [@"sound/bgm" stringByAppendingPathComponent:[track stringByAppendingPathExtension:@"m4a"]];
  NSString *root = group ? [[NSBundle mainBundle] resourcePath] : dir;
  NSError *err = nil;
  AVAudioPlayer *next = nil;
  if (root && (!group || ios_bgm_group_available(group)))
    next = [[AVAudioPlayer alloc] initWithContentsOfURL:[NSURL fileURLWithPath:[root stringByAppendingPathComponent:file]] error:&err];
  if (next) {
    if (!bgm_errors) bgm_errors = [[BgmErrors alloc] init];
    next.delegate = bgm_errors;
    next.numberOfLoops = -1;
    next.volume = 0.5f * bgm_volume;
    if (![next prepareToPlay] || (!paused && ![next play])) { [next release]; next = nil; }
  }
  if (!next) {
    fprintf(stderr, "BGM unavailable %s: %s\n", name, err ? [[err description] UTF8String] : "prepare/play failed");
    if (group) {
      __atomic_fetch_or(&failed_groups, 1 << group, __ATOMIC_SEQ_CST);
      /* Keep the existing player if it is an original; otherwise restore the last original. */
      if (playing_group && last_original) snd_ios_bgm([last_original UTF8String]);
    }
    return;
  }
  if (!group) {
    NSString *original = [track copy];
    [last_original release]; last_original = original;
  }
  [bgm stop]; [bgm release]; bgm = next; playing_group = group;
}

void snd_ios_pause(int p) {
  if (![NSThread isMainThread]) {
    dispatch_async(dispatch_get_main_queue(), ^{ snd_ios_pause(p); });
    return;
  }
  /* the lock screen and the home screen can take the audio session from the app (an
   * interruption), and then RemoteIO and the BGM player came back silent: the session is
   * made active again first, and the BGM player prepared anew */
  if (!p) {
    NSError *err = nil;
    if (![[AVAudioSession sharedInstance] setActive:YES error:&err])
      fprintf(stderr, "audio session not active again: %s\n", [[err description] UTF8String]);
  }
  if (unit) {
    if (p) AudioOutputUnitStop(unit);
    else if (AudioOutputUnitStart(unit) != noErr) {
      AudioOutputUnitStop(unit);
      AudioUnitUninitialize(unit);
      if (AudioUnitInitialize(unit) != noErr || AudioOutputUnitStart(unit) != noErr) fprintf(stderr, "audio unit restart failed\n");
    }
  }
  paused = p;
  if (!p) [bgm prepareToPlay];
  bgm_apply();
}

/* an interruption (a call, an alarm, the lock screen): the end of one restarts the output */
static void interruption(void *ref, UInt32 state) {
  if (state == kAudioSessionEndInterruption && !paused) snd_ios_pause(0);
}
