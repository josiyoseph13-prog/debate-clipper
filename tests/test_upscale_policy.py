import unittest

from dc.core.config import load_config
from dc.layout import upscale_policy
from dc.framing import framing_plan


class UpscalePolicyTests(unittest.TestCase):
    def test_reference_low_resolution_policy_and_punch_zoom(self):
        cfg=load_config()
        self.assertEqual(upscale_policy(1280,720,cfg)["action"],"soft_upscale")
        self.assertEqual(upscale_policy(854,480,cfg)["action"],"prefer_wide_or_dual")
        punched=upscale_policy(1280,720,cfg,1.2)
        self.assertGreater(punched["upscale_factor"],upscale_policy(1280,720,cfg)["upscale_factor"])
        plan=framing_plan(854,480,10,cfg)
        self.assertIn("UPSCALE_BUDGET",plan["segments"][0]["reasons"])
