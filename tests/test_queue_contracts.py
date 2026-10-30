import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from dc.queue import enqueue


class QueueContractTests(unittest.TestCase):
    def test_different_requests_for_same_source_do_not_overwrite(self):
        with tempfile.TemporaryDirectory() as folder:
            source=Path(folder)/"debate.mp4"
            source.write_bytes(b"fixture")
            with patch("dc.queue.ROOT",Path(folder)):
                (Path(folder)/"work").mkdir()
                first=enqueue(source,mode="review")
                second=enqueue(source,mode="auto")
            self.assertNotEqual(first,second)
            self.assertTrue((Path(folder)/"work"/first/"job_request.json").is_file())
            self.assertTrue((Path(folder)/"work"/second/"job_request.json").is_file())
