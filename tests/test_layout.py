import unittest

from dc.core.config import load_config
from dc.layout import crop_rect, fit_headline


class LayoutTests(unittest.TestCase):
    def test_actual_hook_ink_and_descenders_stay_inside_the_band(self):
        from dc.chrome import render_chrome
        cfg=load_config()
        for text in ("Why We Need to Abolish the Department of Education 🎓","Why policy matters?","A short headline"):
            image,manifest=render_chrome(cfg,text)
            box=manifest["headline"]["ink_box"]
            self.assertGreaterEqual(box[0],cfg.regions["hook"]["x"])
            self.assertLessEqual(box[2],cfg.regions["hook"]["x"]+cfg.get("hook","max_w"))
            self.assertGreaterEqual(box[1],cfg.regions["hook"]["top_limit"])
            self.assertLessEqual(box[3],cfg.regions["hook"]["bottom"])
            self.assertEqual(manifest["headline"]["effective_baseline"],cfg.regions["hook"]["last_baseline"]+manifest["headline"]["baseline_shift_px"])
        with self.assertRaises(ValueError):render_chrome(cfg,"unreasonablylongword"*100)

    def test_headline_fits_or_flags_without_truncation(self):
        result = fit_headline("Should the Department of Education Be Abolished?", load_config())
        self.assertLessEqual(len(result["lines"]), 3)
        self.assertIn("Education", result["text"])

    def test_crop_is_inside_source(self):
        result = crop_rect(1920, 1080, load_config())
        self.assertGreaterEqual(result["x"], 0)
        self.assertLessEqual(result["x"] + result["w"], 1920 + 1e-6)
        self.assertLessEqual(result["y"] + result["h"], 1080 + 1e-6)
