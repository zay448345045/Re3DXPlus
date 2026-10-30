/* iOS audio output and BGM for sound.c. */
#ifndef SOUND_IOS_H
#define SOUND_IOS_H

#import <Foundation/Foundation.h>

void snd_ios_start(NSString *data_dir);
void snd_ios_pause(int paused);
/* Original tracks use data_dir/sound/bgm; extras use bundle/bgm-extra. */
void snd_ios_bgm(const char *name);
/* Group 0 is always available; 1/2 require all bundled files and no playback failure. */
int ios_bgm_group_available(int group);
/* Apply the current app BGM volume to the playing track, on the main thread. */
void snd_ios_bgm_volume(float multiplier);

#endif
