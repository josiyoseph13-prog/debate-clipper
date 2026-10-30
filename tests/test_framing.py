import unittest

from dc.core.config import load_config
from dc.framing import framing_plan, path_is_static, rect_at


class FramingTests(unittest.TestCase):
    def test_conservative_plan_and_interpolation(self):
        plan = framing_plan(1920, 1080, 30, load_config())
        self.assertEqual(plan["schema_version"], 5)
        self.assertTrue(path_is_static(plan["path"]))
        self.assertEqual(rect_at(plan["path"], 12)["w"], plan["path"][0]["w"])
