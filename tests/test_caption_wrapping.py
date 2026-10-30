import tempfile
import unittest
from pathlib import Path

from dc.captions import build_captions
from dc.core.config import load_config


class CaptionWrappingTests(unittest.TestCase):
    def test_long_group_records_lines_and_preserves_all_tokens(self):
        with tempfile.TemporaryDirectory() as folder:
            output=Path(folder)/"captions.ass"
            words=[{"text":text,"start":.2+index*.3,"end":.45+index*.3} for index,text in enumerate(("Department","of","Education","policy","needs","a","careful","answer"))]
            plan=build_captions({"words":words},0,3,load_config(overrides={"captions":{"max_w":180}}),output)
            self.assertEqual([row["text"] for row in plan["words"]],[row["text"] for row in words])
            self.assertTrue(any(group.get("line_count",1)>1 for group in plan["groups"]) or "\\N" in output.read_text(encoding="utf-8"))
