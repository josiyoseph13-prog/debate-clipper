import tempfile
import unittest
from pathlib import Path

from dc.captions import build_captions, group_words, solve_caption_slot
from dc.core.config import load_config


class CaptionTests(unittest.TestCase):
    def test_source_trust_suppression_preserves_words_and_requires_review(self):
        with tempfile.TemporaryDirectory() as folder:
            output=Path(folder)/"captions.ass"
            plan=build_captions({"words":[{"text":"Hello","start":.1,"end":.7}]},0,1,load_config(),output,suppress=True)
            self.assertTrue(plan["suppressed"])
            self.assertEqual([word["text"] for word in plan["words"]],["Hello"])
            self.assertNotIn("Dialogue:",output.read_text())
            self.assertIn("SOURCE_CAPTIONS_TRUST_REVIEW",plan["warnings"])

    def test_group_and_slot(self):
        config = load_config()
        words = [{"i": i, "text": text, "start": i * 0.5, "end": i * 0.5 + 0.4} for i, text in enumerate(("One", "two", "three", "four"))]
        self.assertEqual(len(group_words(words, config)), 2)
        slot = solve_caption_slot(config)
        self.assertFalse(slot["review"])

    def test_ass_is_feed_local_and_versioned_plan_is_written(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "captions.ass"
            plan = build_captions({"segments": [{"start": 0, "end": 2, "words": [{"start": 0.1, "end": 0.7, "text": "hello"}, {"start": 0.8, "end": 1.4, "text": "world"}]}]}, 0, 2, load_config(), output)
            self.assertIn("PlayResY: 1216", output.read_text(encoding="utf-8"))
            self.assertEqual(plan["schema_version"], 5)

    def test_protected_phrases_keep_individual_highlights_and_numeric_text(self):
        text=["Donald","Trump","paid","$1.2","million","to","the","school."]
        words=[{"i":i,"text":word,"start":.1+i*.4,"end":.45+i*.4} for i,word in enumerate(text)]
        groups=group_words(words,load_config())
        self.assertTrue(any([word["text"] for word in group][:2]==["Donald","Trump"] for group in groups))
        self.assertTrue(any("$1.2" in [word["text"] for word in group] and "million" in [word["text"] for word in group] for group in groups))
        self.assertEqual([word["i"] for group in groups for word in group],list(range(len(text))))
        with tempfile.TemporaryDirectory() as folder:
            output=Path(folder)/"captions.ass"
            plan=build_captions({"words":words},0,4,load_config(),output)
            self.assertEqual([event["active_word"] for event in plan["events"]],list(range(len(text))))
            self.assertIn("$1.2",output.read_text(encoding="utf-8"))
