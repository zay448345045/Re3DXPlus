// Audio output for sound.c (RemoteIO, 44.1 kHz stereo int16) plus the menu and race BGM
// through AVAudioPlayer, which decodes the AAC in hardware.
#import <AVFoundation/AVFoundation.h>
#import <AudioToolbox/AudioToolbox.h>

#include "sound.h"
#include "sound_ios.h"

static AudioComponentInstance unit;
static NSString *dir;
static AVAudioPlayer *bgm; /* the track main.m asked for (nil: none) */
static int paused;
static void interruption(void *ref, UInt32 state);

static void bgm_apply(void) {
  if (!paused) [bgm play];
  else [bgm pause];
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

void snd_ios_bgm(const char *name) {
  [bgm stop];
  [bgm release];
  bgm = nil;
  if (name) {
    NSString *file = [NSString stringWithFormat:@"sound/bgm/%s.m4a", name];
    NSError *err = nil;
    bgm = [[AVAudioPlayer alloc] initWithContentsOfURL:[NSURL fileURLWithPath:[dir stringByAppendingPathComponent:file]]
                                                 error:&err];
    if (!bgm) fprintf(stderr, "no BGM %s: %s\n", name, [[err description] UTF8String]);
    bgm.numberOfLoops = -1;
    bgm.volume = 0.5f; /* BGM_VOLUME_TYPE_MIDDLE from audio.lua */
  }
  bgm_apply();
}

void snd_ios_pause(int p) {
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
