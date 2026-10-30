"""No game assets, device, or saves are needed."""
import importlib.util
import math
import pathlib
import re
import struct
import subprocess
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('finish_pack', ROOT/'tools/finish_pack.py')
pack = importlib.util.module_from_spec(spec); spec.loader.exec_module(pack)

class FinishTest(unittest.TestCase):
    def test_c_runtime_boundaries(self):
        text = (ROOT/'src/hud.c').read_text()
        fn = re.search(r'int hud_finish_metres\(int play_state, float remain\) \{.*?\n\}', text, re.S).group()
        program = '''#include <math.h>\n#include <assert.h>\n'''+fn+'''\nint main(void) {
          assert(hud_finish_metres(2,0)==0); assert(hud_finish_metres(2,600)==600);
          assert(hud_finish_metres(2,700)==700); assert(hud_finish_metres(2,701)==-1);
          assert(hud_finish_metres(2,699.99f)==699); assert(hud_finish_metres(2,-1)==-1);
          assert(hud_finish_metres(2,NAN)==-1); assert(hud_finish_metres(2,INFINITY)==-1);
          for(int i=0;i<10;i++) if(i!=2) assert(hud_finish_metres(i,100)==-1);
          assert(hud_finish_metres(2,100)==100); assert(hud_finish_metres(0,100)==-1);
          assert(hud_finish_metres(2,701)==-1); assert(hud_finish_metres(2,600)==600);
          return 0; }'''
        with tempfile.TemporaryDirectory() as d:
            src=pathlib.Path(d)/'test.c'; exe=pathlib.Path(d)/'test';src.write_text(program)
            subprocess.run(['cc','-std=c99',str(src),'-o',str(exe)],check=True)
            subprocess.run([str(exe)],check=True)

    def test_wcp_validation_and_collision(self):
        sprite=struct.pack('<iHHI',123,1,1,0)+bytes(4)
        rec=pack.RECORD.pack(123,0,1,0,0,1,0,0,*([256]*4),*([0]*4))
        anim=struct.pack('<48sII',b'test',1,1)+struct.pack('<II',0,1)+rec
        data=struct.pack('<4sIII',b'WCP1',1,1,1)+sprite+anim
        ids,names,sprites,anims=pack.bank(data,True)
        self.assertEqual(ids,{123});self.assertEqual(names,{'test'})
        self.assertEqual(sprites,[sprite]);self.assertEqual(anims,[anim])
        with self.assertRaises(ValueError): pack.bank(data,True,{123})
        with self.assertRaises(ValueError): pack.bank(data[:-1],True)
        with self.assertRaises(ValueError): pack.bank(data,True,set(),{'test'})
        with self.assertRaises(ValueError): pack.bank(data+b'x',True)

    def test_mock_draw_validity_and_missing_resources(self):
        text = (ROOT/'src/hud.c').read_text()
        metres = re.search(r'int hud_finish_metres\(int play_state, float remain\) \{.*?\n\}', text, re.S).group()
        draw = re.search(r'static void draw_finish_remaining\(const car_race \*r\) \{.*?\n\}', text, re.S).group()
        prefix = r"""#include <math.h>
#include <assert.h>
#include <string.h>
typedef struct { int play_state, remain_valid; float remain; } car_race;
typedef struct { int from, to; } anm_swap;
static int available=1, calls=0;
int anm_find(const char *s) { return available ? (strstr(s,"000m") ? 1 : 2) : -1; }
int anm_frames(int a) { return a==1 ? 300 : 60; }
int anm_sprite(int id) { return available ? id : -1; }
void anm_draw(int a,int f,float alpha) { assert(a==2 && f==30); calls++; }
void anm_draw_ex(int a,int f,float alpha,float x,float y,const anm_swap *sw,int n) {
 assert(a==1 && f==150 && n==4); assert(sw[0].from==0x10fc && sw[0].to==0x26f);
 assert(sw[1].to==0x268 && sw[2].to==0x268 && sw[3].to==0x272); calls++;
}
"""
        main = r"""int main(void) { car_race r={2,1,700};
 draw_finish_remaining(&r); assert(calls==2);
 r.remain_valid=0; draw_finish_remaining(&r); assert(calls==2);
 r.remain_valid=1; r.play_state=1; draw_finish_remaining(&r); assert(calls==2);
 r.play_state=2; r.remain=701; draw_finish_remaining(&r); assert(calls==2);
 r.remain=700; available=0; draw_finish_remaining(&r); assert(calls==2);
 available=1; draw_finish_remaining(&r); assert(calls==4); return 0; }
"""
        with tempfile.TemporaryDirectory() as d:
            src=pathlib.Path(d)/'test.c'; exe=pathlib.Path(d)/'test'; src.write_text(prefix+metres+'\n'+draw+'\n'+main)
            subprocess.run(['cc','-std=c99',str(src),'-o',str(exe)],check=True)
            subprocess.run([str(exe)],check=True)

    def test_fallback_and_authored_frames(self):
        s=(ROOT/'src/hud.c').read_text()
        self.assertIn('anm_frames(number) <= 150',s)
        self.assertIn('anm_frames(label) <= 30',s)
        self.assertIn('if (t[i] < 0 || digits[i] < 0) return;',s)
        self.assertIn('if (!r->remain_valid) return;',s)
        self.assertIn('draw_finish_remaining(&car->race)',s)

if __name__ == '__main__': unittest.main()
