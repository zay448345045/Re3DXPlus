"""Test actual installer methods in an isolated host JVM; no device is accessed.

Run with python3 -m unittest ports/android/test/test_card_pages_upgrade_host.py.
Host renameTo behavior is not proof of Android filesystem rename semantics.
"""
import pathlib
import re
import shutil
import subprocess
import tempfile
import unittest

ANDROID = pathlib.Path(__file__).resolve().parents[1]
SOURCE = ANDROID / 'android/java/com/wmmt/port/MainActivity.java'


def extract(source, signature):
    start = source.index(signature)
    opening = source.index('{', start)
    depth = 0
    for i in range(opening, len(source)):
        if source[i] == '{':
            depth += 1
        elif source[i] == '}':
            depth -= 1
            if depth == 0:
                return source[start:i + 1]
    raise AssertionError('unbalanced method')


HARNESS = r"""
import java.io.*;
import java.nio.file.*;
import java.security.*;
import java.util.*;
public class CardPagesHarness {
  LIMIT_DECL
  private Assets assets;
  private Assets getAssets() { return assets; }
  DIGEST_METHOD
  PREPARE_METHOD
  static class Assets {
    byte[] first, second; boolean failSecond, missing, failList; int opens;
    Assets(byte[] a, byte[] b) { first = a; second = b; }
    String[] list(String p) { return failList ? null : missing ? new String[0] : new String[]{"card-pages.bin"}; }
    InputStream open(String p) throws IOException {
      opens++;
      if (opens == 2 && failSecond) throw new IOException("injected copy failure");
      return new ByteArrayInputStream(opens == 1 ? first : second);
    }
  }
  static byte[] b(String s) { return s.getBytes(java.nio.charset.StandardCharsets.UTF_8); }
  static void check(boolean v, String msg) { if (!v) throw new AssertionError(msg); }
  static void same(Path p, byte[] expected) throws IOException { check(Arrays.equals(Files.readAllBytes(p), expected), "changed: " + p); }
  static void clean(Path dir) throws IOException {
    try (DirectoryStream<Path> ds = Files.newDirectoryStream(dir, ".card-pages-*.tmp")) {
      check(!ds.iterator().hasNext(), "temporary file leaked");
    }
  }
  static void fails(CardPagesHarness h, Path ext) throws Exception {
    try { h.prepareCardPages(ext.toFile()); throw new AssertionError("expected IOException"); }
    catch (IOException expected) { }
  }
  public static void main(String[] args) throws Exception {
    Path root = Paths.get(args[0]);
    Path ext = Files.createDirectory(root.resolve("isolated-external"));
    Path dir = Files.createDirectory(ext.resolve("wmmt-sidecars"));
    Path dest = dir.resolve("card-pages.bin"), save = ext.resolve("save-sentinel.bin");
    byte[] old = b("v1.11 old"), fresh = b("v1.12 new"), saved = b("unchanged save");
    Files.write(dest, old); Files.write(save, saved);
    CardPagesHarness h = new CardPagesHarness();
    h.assets = new Assets(fresh, fresh); h.prepareCardPages(ext.toFile());
    same(dest, fresh); same(save, saved); clean(dir); check(h.assets.opens == 2, "not copied");
    long marker = 946684800000L;
    check(dest.toFile().setLastModified(marker), "cannot set marker");
    h.assets = new Assets(fresh, fresh); h.prepareCardPages(ext.toFile());
    same(dest, fresh); same(save, saved); clean(dir);
    check(dest.toFile().lastModified() == marker && h.assets.opens == 1, "matching target rewritten");
    Files.write(dest, old);
    h.assets = new Assets(fresh, fresh); h.assets.failSecond = true; fails(h, ext);
    same(dest, old); same(save, saved); clean(dir);
    h.assets = new Assets(fresh, b("changed during copy")); fails(h, ext);
    same(dest, old); same(save, saved); clean(dir);
    h.assets = new Assets(new byte[0], new byte[0]); fails(h, ext);
    same(dest, old); same(save, saved); clean(dir);
    h.assets = new Assets(fresh, fresh); h.assets.failList = true; fails(h, ext);
    same(dest, old); same(save, saved); clean(dir);
    h.assets = new Assets(fresh, fresh); h.assets.missing = true; h.prepareCardPages(ext.toFile());
    check(h.assets.opens == 0, "missing asset opened"); same(dest, old); same(save, saved); clean(dir);
    // An invalid sidecar path cannot be published to; a separate existing save is unchanged.
    Path broken = Files.createDirectory(root.resolve("invalid-external"));
    Files.write(broken.resolve("wmmt-sidecars"), b("not a directory"));
    Path otherSave = broken.resolve("save-sentinel.bin"); Files.write(otherSave, saved);
    h.assets = new Assets(fresh, fresh); fails(h, broken);
    same(broken.resolve("wmmt-sidecars"), b("not a directory")); same(otherSave, saved);
  }
}
"""


class CardPagesUpgradeHostTest(unittest.TestCase):
    @unittest.skipUnless(shutil.which('javac') and shutil.which('java'), 'JDK required')
    def test_production_methods(self):
        source = SOURCE.read_text(encoding='utf-8')
        limit = re.search(r'private static final long CUTIN_LIMIT\s*=\s*[^;]+;', source)
        self.assertIsNotNone(limit)
        harness = (HARNESS.replace('LIMIT_DECL', limit.group())
                   .replace('DIGEST_METHOD', extract(source, 'private byte[] cutinDigest('))
                   .replace('PREPARE_METHOD', extract(source, 'private void prepareCardPages(')))
        with tempfile.TemporaryDirectory(prefix='card-pages-host-test-') as temp:
            root = pathlib.Path(temp)
            (root / 'CardPagesHarness.java').write_text(harness, encoding='utf-8')
            log = root / 'android/util/Log.java'
            log.parent.mkdir(parents=True)
            log.write_text('package android.util; public class Log { public static int w(String t, String m) { return 0; } }', encoding='utf-8')
            subprocess.run(['javac', '-d', str(root), str(log), str(root / 'CardPagesHarness.java')], check=True)
            subprocess.run(['java', '-cp', str(root), 'CardPagesHarness', str(root)], check=True)


if __name__ == '__main__':
    unittest.main()
