import tempfile
import unittest
from pathlib import Path

from dc.contracts import validate_artifact, validate_job_spec, validate_render_plan, validate_report
from dc.core.retry import retry_ladder


class ContractTests(unittest.TestCase):
    def test_job_spec_bounds_and_collision_inputs(self):
        spec={"schema_version":5,"job_id":"job_fixture","source":{"path":"input/debate.mp4","url":None},"candidate":{"id":"c_1","start":1,"end":12,"edits":[{"start":3,"end":4}]},"preset":"political_lens","headline":{"text":"A short question?"},"layout":{"mode":"auto"},"output":{"crf":18,"fps":"source_capped"}}
        self.assertIs(validate_job_spec(spec),spec)
        for bad in ({**spec,"candidate":{**spec["candidate"],"end":1}},{**spec,"headline":{"text":"x"*79}},{**spec,"source":{"path":"a","url":"b"}}):
            with self.assertRaises(ValueError):validate_job_spec(bad)

    def test_artifact_render_plan_and_report_contracts(self):
        artifact={"schema_version":5,"cache_key":"k","shots":[]}
        self.assertIs(validate_artifact("shots",artifact),artifact)
        with self.assertRaises(ValueError):validate_artifact("shots",{"schema_version":4,"cache_key":"k","shots":[]})
        plan={"schema_version":5,"source":{"path":"x.mp4","source_id":"s","sha256":"h","width":1920,"height":1080},"trim":{"start":1,"end":3,"duration":2},"framing":{"path":[{"t":0,"x":0,"y":0,"w":100,"h":100}]},"config_hash":"c","plan_hash":"p"}
        self.assertIs(validate_render_plan(plan),plan)
        report={"schema_version":5,"status":"passed","checks":[]}
        self.assertIs(validate_report(report),report)

    def test_retry_records_failure_then_success(self):
        rows=[]
        def op(attempt):
            if attempt==1:raise RuntimeError("transient")
            return "ok"
        self.assertEqual(retry_ladder(op,2,on_attempt=rows.append),"ok")
        self.assertEqual([row["status"] for row in rows],["failed","passed"])
