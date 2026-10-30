import unittest

from dc.semantic import gate_result, validate_llm_payload


class SemanticTests(unittest.TestCase):
    def test_untrusted_model_output_is_index_validated(self):
        payload = [{"word_ranges": [[0, 2]]}, {"word_ranges": [["not-an-index", 4]]}, {"word_ranges": [[0, 99]]}]
        self.assertEqual(len(validate_llm_payload(payload, 5)), 1)

    def test_gate_stays_off_without_sample(self):
        result = gate_result({"recall_at_10": 0.5}, {"recall_at_10": 0.9}, 0.1, 20)
        self.assertFalse(result["enabled"])
