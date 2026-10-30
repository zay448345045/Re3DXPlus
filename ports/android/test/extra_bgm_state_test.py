from pathlib import Path
import tempfile, subprocess
root=Path(tempfile.mkdtemp(prefix="wmmt-bgm-test-"))
project=Path(__file__).resolve().parents[1]
p=(project / 'android/java/com/wmmt/port/MainActivity.java').read_text()
a=p.index('  void setBgmVolume('); b=p.index('  void fail(',a)
lifecycle=p[p.index('  @Override protected void onPause()'):p.index('  @Override public void onTrimMemory(')]
methods=p[a:b].replace('Executors.newSingleThreadExecutor()', 'new FakeExecutor()')
(root / 'android/util').mkdir(parents=True,exist_ok=True)
(root / 'android/util/Log.java').write_text('package android.util; public class Log { public static int w(String a,String b){return 0;} public static int w(String a,String b,Throwable c){return 0;} }')
t='''import java.io.*; import java.util.*; import java.util.concurrent.*;
class Activity { protected void onPause(){} protected void onResume(){} protected void onDestroy(){} }
class Sensors { void unregisterListener(Object o){} void registerListener(Object o,Object g,int rate){} }
class SensorManager { static final int SENSOR_DELAY_GAME=1; }
class Movie { void pause(){} void start(){} void stopPlayback(){} }
class CardResources { static File music(File f,String n) { return f; } }
class MediaPlayer {
 interface Error { boolean call(MediaPlayer p,int w,int e); } interface Prepared { void call(MediaPlayer p); }
 static ArrayList<MediaPlayer> all=new ArrayList<>(); Error error; Prepared prepared; boolean released,playing,preparing; float volume;
 MediaPlayer(){all.add(this);} void setOnErrorListener(Error e){error=e;} void setOnPreparedListener(Prepared p){prepared=p;}
 void setDataSource(String p){} void setLooping(boolean b){} void prepare(){} void prepareAsync(){preparing=true;} void setVolume(float a,float b){if(preparing)throw new AssertionError("volume during prepare");volume=a;} void start(){if(released||preparing)throw new AssertionError("invalid start"); playing=true;} void pause(){if(preparing)throw new AssertionError("invalid pause");playing=false;} void firePrepared(){preparing=false;prepared.call(this);} void release(){if(released)throw new RuntimeException("double release");released=true;playing=false;}
}
class FakeExecutor extends AbstractExecutorService { ArrayList<Runnable> q=new ArrayList<>(); boolean closed; public void execute(Runnable r){q.add(r);} public void shutdown(){closed=true;} public java.util.List<Runnable> shutdownNow(){closed=true;return q;} public boolean isShutdown(){return closed;} public boolean isTerminated(){return closed;} public boolean awaitTermination(long n,TimeUnit u){return true;} void run(){q.remove(0).run();} }
public class AsyncStateTest extends Activity {
 volatile boolean started=true,destroyed=false; boolean resumed=true,bgmPreparing; volatile long bgmGeneration; ExecutorService bgmExecutor; MediaPlayer bgm; float bgmVolume=1; File cardResources,dataDir; int failures; ArrayList<Runnable> ui=new ArrayList<>();
 Sensors sensors; Object gravity; Movie movie; void nativePause(boolean p){} void hideBars(){}
 boolean isFinishing(){return false;} void nativeBgmFailure(AsyncStateTest a,int g){failures++;} void runOnUiThread(Runnable r){ui.add(r);} void drain(){while(!ui.isEmpty())ui.remove(0).run();} void worker(){((FakeExecutor)bgmExecutor).run();}
'''+lifecycle+methods+'''
 static void check(boolean b){if(!b)throw new AssertionError();}
 public static void main(String[] x)throws Exception {
  AsyncStateTest a=new AsyncStateTest(); a.cardResources=File.createTempFile("music",".m4a",new File(x[0])); a.dataDir=new File(x[0],"fixture"); a.dataDir.mkdirs();
  a.playBgm("wm2_01");a.drain(); a.playBgm("wmr_01");a.drain(); a.worker();check(a.ui.isEmpty());a.worker();a.drain();MediaPlayer old=a.bgm;check(a.bgmPreparing);
  a.onPause();a.onResume();check(a.bgmPreparing&&!old.playing);a.onPause();a.setBgmVolume(.25f);a.drain();old.firePrepared();check(!old.playing&&old.volume==.25f);a.onResume();check(old.playing);
  a.playBgm("wm2_01");a.drain();check(old.released);a.worker();a.drain();MediaPlayer current=a.bgm;old.error.call(old,1,1);old.prepared.call(old);check(a.bgm==current&&a.failures==0);
  a.playBgm(null);a.drain();check(current.released);current.error.call(current,1,1);check(a.failures==0);
  a.playBgm("wm2_01");a.drain();a.worker();a.drain();MediaPlayer error=a.bgm;error.error.call(error,1,1);check(error.released&&a.failures==1&&a.bgm==null);
  a.playBgm("wm2_01");a.drain();a.worker();a.playBgm(null);a.drain();check(a.bgm==null&&a.failures==1);
  File dir=new File(a.dataDir,"sound/bgm");dir.mkdirs();new File(dir,"legacy.m4a").createNewFile();
  a.playBgm("wm2_01");a.drain();a.worker();a.playBgm("legacy");a.drain();MediaPlayer legacy=a.bgm;check(legacy!=null&&legacy.playing&&!a.bgmPreparing&&a.failures==1);
  a.playBgm("wm2_01");a.drain();a.worker();a.drain();MediaPlayer dead=a.bgm;a.onDestroy();dead.error.call(dead,1,1);dead.prepared.call(dead);check(dead.released&&a.failures==1);
  System.out.println("fake executor/player state tests passed");
 }
}
'''
(root / 'AsyncStateTest.java').write_text(t)
(root / 'classes').mkdir()
subprocess.run(['javac','-d',str(root / 'classes'),str(root / 'android/util/Log.java'),str(root / 'AsyncStateTest.java')],check=True)
subprocess.run(['java','-cp',str(root / 'classes'),'AsyncStateTest',str(root)],check=True)
print('Temporary test artifacts:', root)
