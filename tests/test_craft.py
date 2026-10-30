import tempfile
import unittest
from pathlib import Path

try:
    from PIL import Image
    from dc.craft import render_craft_overlay
    from dc.core.config import load_config
except Exception:
    Image = None
    render_craft_overlay = None


@unittest.skipUnless(Image and render_craft_overlay, "Pillow is optional")
class CraftTests(unittest.TestCase):
    def test_transcript_only_chip_overlay(self):
        with tempfile.TemporaryDirectory() as folder:
            path = render_craft_overlay({"craft": {"question_chip": {"text": "What happened here?"}}}, load_config(), Path(folder) / "craft.png")
            image = Image.open(path).convert("RGBA")
            self.assertEqual(image.size, (load_config().regions["feed"]["w"], load_config().regions["feed"]["h"]))
            self.assertGreater(image.getchannel("A").getextrema()[1], 0)
