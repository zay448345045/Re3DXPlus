"""Check the actual startup guard for Android, iPad and other hosts."""
from pathlib import Path
import re

source = (Path(__file__).resolve().parents[1] / "src/app.c").read_text()
match = re.search(r"if\s*\(([^\n]+)\)\s*render_aniso\(16\);", source)
assert match, "anisotropy initialization missing"
assert re.sub(r"\s+", "", match.group(1)) == "G.console||G.ipad_graphics"
print("iPad and Android anisotropy guard PASS")
