import os,sys,struct,zlib,tempfile,hashlib,unittest
from pathlib import Path
from PIL import Image
P=Path(__file__).resolve().parents[1];sys.path.insert(0,str(P/'tools'))
import card_pages_pack as pack
import menupack as m
ROOT=Path(os.environ['ORIG_ROOT']); MENU=Path(os.environ['BASE_MENU']); STORY=Path(os.environ['STORY']); SIDECAR=Path(os.environ['SIDECAR']); OLD=Path(os.environ['BASELINE'])
def parse(path):
 d=path.read_bytes(); magic,v,n,na=struct.unpack_from('<4sIII',d); assert (magic,v)==(b'WCP1',1); pos=16; entries={}
 for _ in range(n):
  start=pos; sid,w,h,z=struct.unpack_from('<iHHI',d,pos);pos+=12; raw=zlib.decompress(d[pos:pos+z]);pos+=z
  assert sid not in entries and len(raw)==w*h*4;entries[sid]=(w,h,raw,d[start:pos])
 return entries,na,d[pos:]
class TestPack(unittest.TestCase):
 def test_pack(self):
  old,na,anim=parse(OLD);new,nb,anim2=parse(P/'data/card-pages.bin');self.assertEqual((na,anim),(nb,anim2))
  for sid in old:self.assertEqual(old[sid],new[sid])
  added=set(new)-set(old);self.assertEqual(added,set(range(101030,101055))|set(range(101060,101074))|{0x1641,0x19ce})
  base,_=pack.inventory(MENU);story,_=pack.inventory(STORY);self.assertFalse(added&(base|story|set(old)));self.assertIn(0x1643,base)
  with tempfile.TemporaryDirectory(dir='/private/tmp') as tmp:
   paths=[Path(tmp)/'a',Path(tmp)/'b']
   for path in paths:pack.augment_bgm(ROOT,MENU,STORY,OLD,SIDECAR,path)
   self.assertEqual(paths[0].read_bytes(),paths[1].read_bytes());self.assertEqual(paths[0].read_bytes(),(P/'data/card-pages.bin').read_bytes())
  self.assertEqual(hashlib.sha256((P/'data/card-pages.bin').read_bytes()).hexdigest(),'a030da34fd7a367a0b3a0e5dc9831af13435faeb82f74c426174c985bc2f38ec')
 def test_samples(self):
  entries,_,_=parse(P/'data/card-pages.bin');e=m.Elf(str(ROOT/'main'));names=m.sprite_names(e)
  ng,half,full,cell,cols,_,cells,pages,gm=struct.unpack_from('<9I',e.d,e.off(m.FONT_TABLE))
  for s,k in ((1,0),(1,1),(1,23),(1,24),(2,1),(2,12),(2,13)):
   song=struct.unpack_from('<i',e.d,e.off(m.BGM_SET+4*(25*s+k)))[0];title='RANDOM' if song==110 else 'NO BGM' if song<0 else e.wstr(e.u32(m.BGM_MUSIC+12*song+8));ch=ord(title[0]);page=e.i16s(gm+2*(ch>>5),1)[0];g=e.i16s(gm+0x1000+64*page+2*(ch&31),1)[0];sid=e.u32(pages+4*(g//cells));i=g%cells
   with Image.open(ROOT/names[sid]) as sheet: glyph=sheet.convert('RGBA').crop(((i%cols)*cell,(i//cols)*cell,(i%cols+1)*cell,(i//cols+1)*cell))
   expected=Image.new('RGBA',(cell,cell));expected.alpha_composite(glyph);w,h,raw,_=entries[m.BGM_TEXT_BASE+30*s+k];actual=Image.frombytes('RGBA',(w,h),raw).crop((0,0,half,cell));self.assertEqual(actual.tobytes(),expected.crop((0,0,half,cell)).tobytes(),(s,k,title))
if __name__=='__main__':unittest.main()
