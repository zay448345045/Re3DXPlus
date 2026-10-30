/* iOS audio output and BGM for sound.c. */
#ifndef SOUND_IOS_H
#define SOUND_IOS_H

#import <Foundation/Foundation.h>

void snd_ios_start(NSString *data_dir);
void snd_ios_pause(int paused);
/* Play data_dir/sound/bgm/<name>.m4a over and over, or nothing for NULL. */
void snd_ios_bgm(const char *name);

#endif
