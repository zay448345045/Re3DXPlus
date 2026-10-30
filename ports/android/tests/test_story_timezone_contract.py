"""Asset-free source guards; not a substitute for interactive testing."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[3]

class StoryTimezoneContract(unittest.TestCase):
    def test_both_ports(self):
        for port in ("android", "ipad"):
            with self.subTest(port=port):
                src = ROOT / "ports" / port / "src"
                menu = (src / "menu.c").read_text()
                app = (src / "app.c").read_text()
                for token in ("m->story_day_select = 1;", "m->story_zone = m->zone;",
                              "m->sel = m->story_n % 5;", "m->story_zones_saved = m->zones;",
                              "m->zones = m->story_zones_saved;",
                              "!m->story_day_select && (!m->vs.day",
                              "m->story_day_select || (m->vs.day",
                              "m->song = 1 + rand() % (card_bgm_lines(m) - 2);"):
                    self.assertIn(token, menu)
                for token in ("%s/story_timezone", "story_tz ? fgetc(story_tz) == '1' : 0",
                              "story_was_selecting && G.menu.story_day_select && G.menu.deciding",
                              "G.menu.game == MENU_GAME_TA ? fopen(path, \"w\") : NULL",
                              "G.menu.story_day_select ? 0 : G.story_race",
                              "G.menu.zone >= G.menu.zones"):
                    self.assertIn(token, app)

if __name__ == "__main__":
    unittest.main()
