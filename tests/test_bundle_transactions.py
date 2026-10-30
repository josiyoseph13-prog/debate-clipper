import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch
from dc.core.bundles import write_complete_bundle,recover_export_bundles
from dc.core.io import read_json


class BundleTransactionTests(unittest.TestCase):
    def test_hard_qa_failure_cannot_be_overridden_by_review_acceptance(self):
        from dc.exports import export_bundle
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            for status in ("failed",None,"unknown","needs_review"):
                accepted="yes" if status=="needs_review" else True
                with self.assertRaises(ValueError):
                    export_bundle(root/"exports"/"c_test",root/"clip.mp4",{}, {}, {}, {}, {"status":status,"review_accepted":accepted})
            self.assertFalse((root/"exports").exists())

    def test_interrupted_build_keeps_previous_export_intact(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            job=root/"work"/"job_test"
            target=root/"exports"/"c_test"
            write_complete_bundle(job,target,lambda stage:(stage/"clip.mp4").write_bytes(b"old complete clip"))
            def incomplete(stage):
                (stage/"clip.mp4").write_bytes(b"new but incomplete bundle")
                raise RuntimeError("power loss while writing metadata")
            with self.assertRaises(RuntimeError):write_complete_bundle(job,target,incomplete)
            self.assertEqual((target/"clip.mp4").read_bytes(),b"old complete clip")
            self.assertTrue(read_json(target/"bundle_manifest.json")["complete"])
            self.assertFalse(any(path.name.endswith(".part") for path in target.iterdir()))

    def test_crash_after_previous_move_recovers_hash_checked_bundle(self):
        import os
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            job=root/"work"/"job_test"
            target=root/"exports"/"c_test"
            write_complete_bundle(job,target,lambda stage:(stage/"clip.mp4").write_bytes(b"old clip"))
            real_replace=os.replace
            def crash(source,destination):
                if Path(source).is_dir() and Path(source).name.startswith("bundle_stage_") and Path(destination)==target:
                    raise RuntimeError("killed before new directory promotion")
                return real_replace(source,destination)
            with patch("dc.core.bundles.os.replace",side_effect=crash):
                with self.assertRaises(RuntimeError):write_complete_bundle(job,target,lambda stage:(stage/"clip.mp4").write_bytes(b"new complete clip"))
            self.assertEqual((target/"clip.mp4").read_bytes(),b"old clip")
            recovered=recover_export_bundles(job,root/"exports")
            self.assertEqual(recovered[0]["action"],"promoted_complete_bundle")
            self.assertEqual((target/"clip.mp4").read_bytes(),b"new complete clip")
            self.assertTrue(any(path.is_dir() for path in job.glob("bundle_previous_*")))
