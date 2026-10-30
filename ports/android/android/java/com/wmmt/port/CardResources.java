package com.wmmt.port;

import android.content.res.AssetManager;
import java.io.*;
import java.security.MessageDigest;
import java.util.*;
import java.util.zip.*;

/** Optional, immutable, hash-pinned resources; never modifies the main data or saves. */
final class CardResources {
  private static final String ASSET="card-resources-v1.zip";
  private static final String ARCHIVE_SHA="89e1092cfd6a4d758bf7eb4987dc9b8895fa61b5d459d3107b160545464faf81";
  private static final long ARCHIVE_SIZE=97444220L;
  private static final String MANIFEST_SHA="763a23c4103f5d4f1692fe17d7f89de6c6e782f5d9f6b6e320894cd06b5ad05f";
  private static final long MANIFEST_SIZE=6295L;
  private static final class Spec {
    final String path, sha; final long size;
    Spec(String path,long size,String sha){this.path=path;this.size=size;this.sha=sha;}
  }
  private static final Spec[] SPECS = {
    new Spec("meters-v2.bin", 17849972L, "b8392eeb206f167099b9a70521e59c64d5fd194241d0e6802ca2c38aa1938954"),
    new Spec("bgm-extra/wm2_01.m4a", 2074790L, "3c6c5321c95a13a643b1e22a085969f5ddd470ae0a99d35d41aa4dddd5bb7ca2"),
    new Spec("bgm-extra/wm2_02.m4a", 2204336L, "56b3a35d383cabd2df52c20481d072a4d18bc05b10a904eb4261b16dc56c0580"),
    new Spec("bgm-extra/wm2_03.m4a", 2077045L, "2af478de40a96abd0e8e776ae35778eddd21ecd8d59b34619a2ab88c630a4b3d"),
    new Spec("bgm-extra/wm2_04.m4a", 1875185L, "fbe95231e1b9aede5e21803efc8db25c3a8fe080cf01dea8b8fb2a9b45545907"),
    new Spec("bgm-extra/wm2_05.m4a", 1790249L, "1eb3b4bc0b050817830059543b4e4f3dfc64120e17a62119bc96ab3b2379cb1f"),
    new Spec("bgm-extra/wm2_06.m4a", 1577294L, "50d9fb6aeb5ae62e7dc5be4400371ebf6684c158047e3f883b9c780fa1a43f1f"),
    new Spec("bgm-extra/wm2_07.m4a", 1287180L, "a303194d5420df80d0c211098e64445b572fcc2c3054cb00ab13cb87472e7447"),
    new Spec("bgm-extra/wm2_08.m4a", 1394071L, "029c9298f8131021b35b30b8daf1176f493fa289fb5627f44def8360016a1afc"),
    new Spec("bgm-extra/wm2_09.m4a", 1354335L, "0dba9b0b0d7df18ac8f55ec7eb78a31b6aba82c908890d4e4a86f48f7353b485"),
    new Spec("bgm-extra/wm2_10.m4a", 2463382L, "13ec067b6feb6b49138b972a114514391cd91b1b14744fd9dc15fe4a77ac7a26"),
    new Spec("bgm-extra/wm2_11.m4a", 3808923L, "9bd3ae14e680ffedcd785818fe8f76793fa972c77420779c98d81a4bfa109b24"),
    new Spec("bgm-extra/wm2_12.m4a", 2729236L, "96736136aade8d6425446b78eb43938fc259b6e7d3e03d1d56bd3b016710e19b"),
    new Spec("bgm-extra/wm2_13.m4a", 2689351L, "e35a389e5a3756ac2cf35f570e711f6c993ae7c00704538ab9bff8fd05a3285a"),
    new Spec("bgm-extra/wm2_14.m4a", 2272640L, "a4db2f1b6e0d598692103029a7fed6350dffe43c77a5653a9f189dd280cd2bc4"),
    new Spec("bgm-extra/wm2_15.m4a", 2032016L, "5cc4a716c57edc2536fb1be126c4251cbc720ccea615c914bf7a4d88dfaea58c"),
    new Spec("bgm-extra/wm2_16.m4a", 2786113L, "cc9ab2821e5b7a0064e07cc281317792e0cff3ab3df1e6fe923abafd1aa2ac7e"),
    new Spec("bgm-extra/wm2_17.m4a", 1328750L, "3286945c44e92b4bb9874a092419b5d0e0126d4d81df7d73ad5a6ab8262cf410"),
    new Spec("bgm-extra/wm2_18.m4a", 1792861L, "3f2d7f66ced46fd03336665ec65b8bedd004bb1e8b2f8c8cd3059e706e6198b1"),
    new Spec("bgm-extra/wm2_19.m4a", 2677447L, "cb889f2428d50a439d1977ec5beee1e6c691b952b7fa7d0b11fac54976848a9d"),
    new Spec("bgm-extra/wm2_20.m4a", 2428883L, "ce9fae9ca4009799afa96a54199b04e14213d6e2714366ea7c86fa24a8637c93"),
    new Spec("bgm-extra/wm2_21.m4a", 3135843L, "1d450854eb9dcc9dcc29d3c58c1f54a8a3a91f0bd146307ef2a88ac983604139"),
    new Spec("bgm-extra/wm2_22.m4a", 2231283L, "86046a554dbd7d35f266fad5c1999495504fae12a2e5cbd686fe701cf1ac7536"),
    new Spec("bgm-extra/wm2_23.m4a", 3638440L, "b5d0bc308ce52265e620fa97b089eab5d3b2ed952ab4ec7820db1eb199d30975"),
    new Spec("bgm-extra/wmr_01.m4a", 1292168L, "4484086f8839458b7269f422ac22c881770c98af7e5fde7817d707340e46308f"),
    new Spec("bgm-extra/wmr_02.m4a", 1878853L, "d1c87112948f6e9c2705e013c02d0fce59ae429751f863d35b5b5b4986a22801"),
    new Spec("bgm-extra/wmr_03.m4a", 2056831L, "41062bc78dff2512c672b50efbc1e3e3dbeded78fb97b9752dfff36df8d55a7e"),
    new Spec("bgm-extra/wmr_04.m4a", 1196870L, "fcce9176f680f8a3fd59d77690ab59334e386ae883067084eaca46c5edc41b47"),
    new Spec("bgm-extra/wmr_05.m4a", 2454639L, "167566e6f641ced6a0a51bd8fc6614144d732fa02a6782c24a87705e17b6ebea"),
    new Spec("bgm-extra/wmr_06.m4a", 946005L, "1877ddcfb0b6b6bc0886fedbdeb082d190c528503ef9e11ff5122eb7af2e2a54"),
    new Spec("bgm-extra/wmr_07.m4a", 2193911L, "957de1099e683dc1b9eeac56746a507cc4f3f65811d63143dd8ee7d17447c3a6"),
    new Spec("bgm-extra/wmr_08.m4a", 2141143L, "dbbd6b6433d8fb5ac75bc652109f76668ee4bef2a49fac469e24a68a630b57d9"),
    new Spec("bgm-extra/wmr_09.m4a", 2077342L, "351aa2193fce627470e6ed27448f89b3bbb8ad282a4e924540f161eaca1e5751"),
    new Spec("bgm-extra/wmr_10.m4a", 1999357L, "5486a793371556b72185124bfacaefa00d85f3aa28dcf5b9912abb3c21db1ebd"),
    new Spec("bgm-extra/wmr_11.m4a", 4172053L, "3fc80934a9250002b693b4705eb041a4188933f1f86da80afeee40e8188f4172"),
    new Spec("bgm-extra/wmr_12.m4a", 5524842L, "50be08d1e2aa28b0b6d7df7f7dac44e42c7365d9654dd8e670ab9d9bd0f8f4e6"),
  };
  private static String hex(byte[] b) { StringBuilder s=new StringBuilder(); for(byte v:b)s.append(String.format(Locale.ROOT,"%02x",v&255));return s.toString(); }
  private static String digest(InputStream in,long exact) throws Exception {
    MessageDigest h=MessageDigest.getInstance("SHA-256");byte[] b=new byte[65536];long count=0;int n;
    while((n=in.read(b))!=-1) { count+=n;if(count>exact)throw new IOException("resource exceeds expected size");h.update(b,0,n); }
    if(count!=exact)throw new IOException("resource truncated");return hex(h.digest());
  }
  private static File child(File root,String name) throws IOException {
    if(name.startsWith("/")||name.indexOf('\\')>=0||name.contains(".."))throw new IOException("unsafe path");
    File p=new File(root,name);String base=root.getCanonicalPath()+File.separator;
    if(!p.getCanonicalPath().equals(base+name.replace('/',File.separatorChar)))throw new IOException("unsafe resource location");return p;
  }
  private static boolean valid(File root) {
    try {
      File m=child(root,"manifest.json");try(InputStream in=new FileInputStream(m)){if(!digest(in,MANIFEST_SIZE).equals(MANIFEST_SHA))return false;}
      for(Spec s:SPECS){File f=child(root,s.path);try(InputStream in=new FileInputStream(f)){if(!digest(in,s.size).equals(s.sha))return false;}}
      return true;
    } catch(Exception e) { return false; }
  }
  /* Only remove the exact files in a staging directory created by this call. */
  private static void discard(File base, File tmp) {
    try {
      if (!tmp.getName().startsWith("staging-") || !tmp.getCanonicalFile().equals(new File(base.getCanonicalFile(),tmp.getName()))) return;
      for (Spec s:SPECS) { File f=child(tmp,s.path); if (f.isFile()) f.delete(); }
      File manifest=child(tmp,"manifest.json");if(manifest.isFile())manifest.delete();
      File sounds=child(tmp,"bgm-extra");if(sounds.isDirectory())sounds.delete();
      tmp.delete();
    } catch (IOException ignored) { /* retain uncertain paths rather than deleting them */ }
  }
  /** Returns the verified immutable directory, or null if not packaged. */
  static File prepare(AssetManager assets, File ext) throws Exception {
    boolean present=false;String[] ls=assets.list(""); if(ls==null)throw new IOException("cannot list assets");for(String n:ls)if(ASSET.equals(n))present=true;
    if(!present)return null;
    try(InputStream in=assets.open(ASSET)){if(!digest(in,ARCHIVE_SIZE).equals(ARCHIVE_SHA))throw new IOException("wrong resource archive hash");}
    File parent=new File(ext,"wmmt-sidecars"); if(!parent.isDirectory()&&!parent.mkdirs())throw new IOException("sidecar parent");
    if(!parent.getCanonicalFile().equals(new File(ext.getCanonicalFile(),"wmmt-sidecars")))throw new IOException("unsafe sidecar parent");
    File base=new File(parent,"card-resources-v1");if(!base.isDirectory()&&!base.mkdirs())throw new IOException("sidecar base");
    if(!base.getCanonicalFile().equals(new File(parent.getCanonicalFile(),"card-resources-v1")))throw new IOException("unsafe sidecar base");
    File[] existing=base.listFiles();if(existing==null)throw new IOException("cannot list sidecars");
    for(File candidate:existing)if(candidate.getName().startsWith("ready-") && candidate.isDirectory() && candidate.getCanonicalFile().equals(new File(base.getCanonicalFile(),candidate.getName())) && valid(candidate))return candidate;
    File tmp=new File(base,"staging-"+UUID.randomUUID());if(!tmp.mkdir())throw new IOException("cannot create staging");
    Map<String,Spec> specs=new HashMap<>();specs.put("manifest.json",new Spec("manifest.json",MANIFEST_SIZE,MANIFEST_SHA));for(Spec s:SPECS)specs.put(s.path,s);
    Set<String> seen=new HashSet<>();long total=0; boolean committed=false;
    try {
    try(InputStream asset=assets.open(ASSET); ZipInputStream zip=new ZipInputStream(asset)) {
      ZipEntry e;byte[] buf=new byte[65536];while((e=zip.getNextEntry())!=null) {
        String name=e.getName();Spec spec=specs.get(name);
        if(spec==null||e.isDirectory()||!seen.add(name))throw new IOException("unexpected zip entry");
        File dest=child(tmp,name);File d=dest.getParentFile();if(!d.isDirectory()&&!d.mkdirs())throw new IOException("cannot create directory");
        if(dest.exists())throw new IOException("duplicate output");MessageDigest h=MessageDigest.getInstance("SHA-256");long count=0;
        try(FileOutputStream out=new FileOutputStream(dest)) { int n;while((n=zip.read(buf))!=-1){count+=n;total+=n;if(count>spec.size||total>110000000L)throw new IOException("resource size limit");h.update(buf,0,n);out.write(buf,0,n);}out.getFD().sync(); }
        if(count!=spec.size||!hex(h.digest()).equals(spec.sha))throw new IOException("resource checksum mismatch");zip.closeEntry();
      }
    }
    if(seen.size()!=specs.size()||!valid(tmp))throw new IOException("incomplete sidecar");
    File ready=new File(base,"ready-"+UUID.randomUUID());if(!tmp.renameTo(ready))throw new IOException("cannot publish sidecar");committed=true;return ready;
    } finally { if(!committed)discard(base,tmp); }
  }
  /** A per-play recheck ensures damage cannot make a missing/corrupt track look available. */
  static File music(File root,String name) {
    if(root==null||name==null)return null;
    for(Spec s:SPECS)if(s.path.equals("bgm-extra/"+name+".m4a")) {
      try {File f=child(root,s.path);try(InputStream in=new FileInputStream(f)){return digest(in,s.size).equals(s.sha)?f:null;}}catch(Exception e){return null;}
    }
    return null;
  }
}
