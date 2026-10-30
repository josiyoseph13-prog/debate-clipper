import csv
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

from dc.learn import import_analytics, propose_taste_update


@unittest.skipUnless(importlib.util.find_spec("numpy"), "NumPy required for learned proposals")
class LearningTests(unittest.TestCase):
    def test_duplicate_votes_cannot_satisfy_training_gate(self):
        with tempfile.TemporaryDirectory() as folder:
            report = propose_taste_update([{"candidate_id": "c_1", "action": "approve", "components": {"hook": .9}}] * 200, Path(folder))
        self.assertEqual(report["labels"], 1)
        self.assertEqual(report["status"], "insufficient_data")
        self.assertFalse(report["enabled"])

    def test_taste_cross_validation_distinguishes_signal_from_constant_features(self):
        with tempfile.TemporaryDirectory() as folder:
            labels = [{"candidate_id": f"c_{i}", "action": "approve" if i % 2 else "reject", "components": {"hook": .9 if i % 2 else .1}} for i in range(150)]
            measured = propose_taste_update(labels, Path(folder))
            self.assertGreater(measured["cv_auc"], .9)
            self.assertTrue(measured["eligible"])
            self.assertFalse(measured["enabled"])
            self.assertFalse(measured["applied"])
            for label in labels:
                label["components"]["hook"] = .5
            constant = propose_taste_update(labels, Path(folder))
            self.assertLess(constant["cv_auc"], .70)
            self.assertEqual(constant["status"], "gate_failed")

    def test_ridge_loo_beats_mean_for_predictive_heldout_outcome(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / "analytics.csv"
            with source.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=["clip_id", "components", "avg_percent_watched"])
                writer.writeheader()
                for i in range(80):
                    feature = i / 79
                    writer.writerow({"clip_id": f"c_{i}", "components": json.dumps({"clarity": feature}), "avg_percent_watched": 30 + 50 * feature})
            report = import_analytics(source, root)
        self.assertLess(report["cv_mse"], report["mean_baseline_mse"])
        self.assertEqual(report["cv"], "leave_one_out")
        self.assertIn("clarity", report["coefficient_ci95"])
        self.assertFalse(report["applied"])
