#!/usr/bin/env python3
"""Compare actual mixer PCM; pass the root containing sound/ as the sole argument."""
import array, math, os, pathlib, subprocess, sys, tempfile

here = pathlib.Path(__file__).resolve().parent
root = here.parents[2]
source = here / 'audio_volume_compare.c'
versions = [root/'audio-thread-fix-v5/project/src/sound.c', here.parent/'src/sound.c']
if len(sys.argv) != 2:
    raise SystemExit('usage: python3 test/audio_volume_compare.py /path/to/data')
data = pathlib.Path(sys.argv[1]).resolve()
if not (data/'sound/slip.wav').is_file():
    raise SystemExit(f'missing real WAVs: {data}/sound/slip.wav')
labels = [(f'car={c} rpm={r} throttle={t} {m}',m) for c in (0,5,12) for r in (1200,4500,8500,9518.3) for t in (0,1) for m in ('engine','muffler','slip','mixed')]
labels += [(x,'independent') for x in ('cursor','select','cancel','crash1','crash4','valb1','wall')]
labels += [('near-full engine+muffler+slip+wall+crash4','mixed')]
block = 8192*2*2
with tempfile.TemporaryDirectory(prefix='audio-compare-') as tmp:
    outputs=[]
    for n,v in enumerate(versions):
        exe=pathlib.Path(tmp)/str(n)
        cmd=[os.environ.get('CC','clang'),'-std=c11','-O1','-g','-fsanitize=signed-integer-overflow,float-cast-overflow','-fno-sanitize-recover=all',f'-DSOUND_PATH="{v}"',str(source),'-lm','-o',str(exe)]
        subprocess.run(cmd,check=True)
        outputs.append(subprocess.run([str(exe),str(data)],check=True,stdout=subprocess.PIPE).stdout)
    if any(len(p)!=len(labels)*block for p in outputs): raise SystemExit('unexpected PCM length')
    ranges={m:[] for m in ('engine','muffler','slip','mixed')}
    print('scenario | baseline RMS peak | boosted RMS peak | relative dB')
    for i,(name,mode) in enumerate(labels):
        a,b=(p[i*block:(i+1)*block] for p in outputs)
        if mode=='independent' and a!=b: raise AssertionError(f'{name}: PCM differs')
        values=[]
        for p in (a,b):
            samples=array.array('h'); samples.frombytes(p)
            rms=math.sqrt(sum(x*x for x in samples)/len(samples)); peak=max(map(abs,samples))
            values.append((rms,peak))
        ar,ap=values[0]; br,bp=values[1]
        db=20*math.log10(br/ar) if ar and br else float('nan')
        if mode!='independent':
            if not (ar>0 and br>ar): raise AssertionError(f'{name}: missing PCM or not louder: {ar} {br}')
            ranges[mode].append(db)
        print(f'{name} | {ar:.2f} {ap} | {br:.2f} {bp} | {db:+.3f}')
    for mode,vals in ranges.items(): print(f'{mode}: n={len(vals)} relative dB range {min(vals):+.3f}..{max(vals):+.3f}')
    print('PASS: independent PCM byte-identical; 30 sets and RPM edge inputs finite and in range; signed-integer-overflow/float-cast-overflow sanitizers clean')
    print('Note: limiter is nonlinear; mixed sounds may change. No device/music loudness or TSAN claim.')
