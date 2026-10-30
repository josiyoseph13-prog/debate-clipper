from pathlib import Path
import tempfile
import unittest
from PIL import Image,ImageChops,ImageDraw
from dc.chrome import render_chrome
from dc.core.config import ROOT,load_config
from dc.core.hashing import file_hash


class SuppliedBrandTests(unittest.TestCase):
    def test_real_logo_artwork_is_used_without_redrawing(self):
        config=load_config()
        logo=config.get("header","logo")
        path=ROOT/logo["file"]
        with Image.open(path) as image:original=image.convert("RGBA")
        original.thumbnail((logo["d"],logo["d"]),Image.Resampling.LANCZOS)
        mask=Image.new("L",original.size,0)
        ImageDraw.Draw(mask).ellipse((0,0,original.width-1,original.height-1),fill=255)
        expected=Image.new("RGBA",original.size,"white")
        expected.paste(original,(0,0),mask)
        chrome,manifest=render_chrome(config,"Logo check")
        actual=chrome.crop((logo["x"],logo["y"],logo["x"]+logo["d"],logo["y"]+logo["d"]))
        self.assertIsNone(ImageChops.difference(actual,expected).getbbox())
        self.assertFalse(manifest["placeholder_logo"])
        self.assertTrue(manifest["logo"]["user_supplied"])
        self.assertEqual(manifest["logo"]["sha256"],file_hash(path))
