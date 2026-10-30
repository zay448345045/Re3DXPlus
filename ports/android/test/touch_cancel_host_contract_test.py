from pathlib import Path
import subprocess, tempfile
r = Path(__file__).resolve().parents[3]
j = (r / "android/project/android/java/com/wmmt/port/MainActivity.java").read_text()
i = (r / "ipad/project/src/main.m").read_text()
for event, phase in [("Moved",1),("Ended",2),("Cancelled",3)]:
    assert f"touches{event}:(NSSet *)t withEvent:(UIEvent *)e {{ [self forward:t phase:{phase}]; }}" in i
assert "app_touch(t, phase, (float)p.x * touch_k - touch_edge, (float)p.y * touch_k);" in i
m = j[j.index("  private void touch(MotionEvent e) {"):j.index("\n  @Override public void surfaceCreated")]
s = """import java.util.*;
class MotionEvent {
 static final int ACTION_DOWN=0,ACTION_UP=1,ACTION_MOVE=2,ACTION_CANCEL=3,ACTION_POINTER_DOWN=5,ACTION_POINTER_UP=6;
 int action,index; int[] ids; float[] xs,ys;
 MotionEvent(int a,int ix,int[] id,float[] x,float[] y){action=a;index=ix;ids=id;xs=x;ys=y;}
 int getActionMasked(){return action;} int getActionIndex(){return index;} int getPointerCount(){return ids.length;}
 int getPointerId(int i){return ids[i];} float getX(int i){return xs[i];} float getY(int i){return ys[i];}
}
public class TouchContract {
 boolean started=true; List<String> events=new ArrayList<>();
 void nativeTouch(int id,int phase,float x,float y){events.add(id+":"+phase+":"+x+":"+y);}
""" + m + """
 void check(MotionEvent e,String... expected){events.clear();touch(e);if(!events.equals(Arrays.asList(expected)))throw new AssertionError(events+" != "+Arrays.toString(expected));}
 public static void main(String[] args){
  TouchContract c=new TouchContract(); int[] ids={7,4,23}; float[] x={11,22,33},y={44,55,66};
  c.check(new MotionEvent(3,1,ids,x,y),"7:3:11.0:44.0","4:3:22.0:55.0","23:3:33.0:66.0");
  c.check(new MotionEvent(2,0,ids,x,y),"7:1:11.0:44.0","4:1:22.0:55.0","23:1:33.0:66.0");
  c.check(new MotionEvent(5,1,ids,x,y),"4:0:22.0:55.0"); c.check(new MotionEvent(6,2,ids,x,y),"23:2:33.0:66.0");
  c.check(new MotionEvent(0,0,ids,x,y),"7:0:11.0:44.0"); c.check(new MotionEvent(1,0,ids,x,y),"7:2:11.0:44.0");
  c.check(new MotionEvent(9,0,ids,x,y)); c.started=false; c.check(new MotionEvent(3,0,ids,x,y));
 }
}"""
with tempfile.TemporaryDirectory(prefix="touch-contract-") as t:
    p=Path(t)/"TouchContract.java"; p.write_text(s)
    subprocess.run(["javac","-d",t,str(p)],check=True)
    subprocess.run(["java","-cp",t,"TouchContract"],check=True)
print("touch source and Java behavior contracts passed")
