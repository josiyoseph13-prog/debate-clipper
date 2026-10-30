"""T-22 actual glyph/drop/manifest acceptance, without mocked fonts."""
import tempfile
import unittest
from pathlib import Path

from dc.chrome import emoji_image, render_chrome
from dc.core.config import ROOT, load_config
from dc.core.io import read_json


class EmojiFallbackTests(unittest.TestCase):
    def test_unavailable_and_notdef_fonts_drop_emoji_and_record_reason(self):
        with tempfile.TemporaryDirectory(dir=ROOT/"work",prefix="job_emoji_test_") as directory:
            work=Path(directory)
            for name,font in (("absent",str(work/"absent.ttf")),("notdef","assets/fonts/Poppins-Regular.ttf")):
                with self.subTest(font=name):
                    cfg=load_config(overrides={"hook":{"emoji_font":font}})
                    if name=="notdef":
                        with self.assertRaisesRegex(ValueError,"missing-glyph"):
                            emoji_image("🎓",60,cfg)
                    output=work/(name+".png")
                    image,manifest=render_chrome(cfg,"Why education matters 🎓",output)
                    plain,_=render_chrome(cfg,"Why education matters")
                    self.assertEqual(image.tobytes(),plain.tobytes())
                    self.assertTrue(manifest["emoji_warning"].startswith("EMOJI_DROPPED: "))
                    saved=read_json(output.with_suffix(".json"))
                    self.assertEqual(saved["emoji_warning"],manifest["emoji_warning"])
                    self.assertTrue(output.is_file())
