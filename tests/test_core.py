import unittest

from dc.captions import ass_color
from dc.core.config import load_config
from dc.core.security import escape_text, validate_id
from dc.layout import validate_layout


class CoreTests(unittest.TestCase):
    def test_config_and_layout(self):
        config = load_config()
        self.assertEqual(config.schema_version, 5)
        self.assertTrue(validate_layout(config).passed)

    def test_ass_colour_order(self):
        self.assertEqual(ass_color("#B4F83D"), "&H003DF8B4&")
        self.assertEqual(ass_color("#FFE600"), "&H0000E6FF&")

    def test_security(self):
        self.assertEqual(escape_text("<script>alert(1)</script>"), "&lt;script&gt;alert(1)&lt;/script&gt;")
        with self.assertRaises(ValueError):
            validate_id("../secret")
