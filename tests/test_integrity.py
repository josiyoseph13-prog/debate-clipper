import unittest

from dc.core.config import load_config
from dc.integrity import publish_gate, verify_claims


class IntegrityTests(unittest.TestCase):
    def test_claim_gate_blocks_unchecked_claim(self):
        candidate = {"claims": [{"word_i": 1, "text": "90%", "claim_checked": False}], "integrity_flags": []}
        result = verify_claims(candidate)
        self.assertFalse(result["claim_checked"])
        allowed, reasons = publish_gate(result, {"rights_class": "unknown"}, load_config())
        self.assertFalse(allowed)
        self.assertIn("rights_class_unknown", reasons)
