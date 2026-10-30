import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from dc.core.config import load_config
from dc.core.io import atomic_write_json
from dc.core.jobs import JobStore
from dc.core.locking import ResourceBusy, exclusive_file
from dc.core.process import ProcessCancelled, check_cancelled, job_processes
from dc.distribute.adapters import _upload_request, publish_tiktok_inbox
from dc.semantic import validate_llm_payload
from dc.timeline import runtime_plan


class OpsHardeningTests(unittest.TestCase):
    def test_busy_run_does_not_overwrite_the_active_job_state(self):
        from dc.cli import main
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            store=JobStore(root/"work"/"jobs.sqlite")
            store.upsert("job_live","rendering","{}")
            with patch("dc.cli.ROOT",root),patch("dc.cli.command_run",side_effect=ResourceBusy("Already running")):
                self.assertEqual(main(["run","--source","fixture.mp4","--job","job_live"]),75)
            self.assertEqual(store.get("job_live")["state"],"rendering")

    def test_retention_preserves_active_and_unreviewed_jobs(self):
        import os
        from dc.ops import cleanup_work
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            store=JobStore(root/"work"/"jobs.sqlite")
            for job,state in (("job_active","rendering"),("job_review","awaiting_review"),("job_old","passed")):
                path=root/"work"/job
                path.mkdir()
                store.upsert(job,state,"{}")
                os.utime(path,(1,1))
            self.assertEqual(cleanup_work(root),["job_old"])

    @unittest.skipUnless(importlib.util.find_spec("psutil"),"Process recovery requires psutil")
    def test_recovery_terminates_only_identity_verified_orphan(self):
        import os
        import psutil
        from dc.core.hashing import content_hash
        from dc.core.recovery import recover_children
        from dc.core.process import terminate_tree
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            child=subprocess.Popen([sys.executable,"-c","import time;time.sleep(30)"],start_new_session=os.name!="nt",creationflags=getattr(subprocess,"CREATE_NEW_PROCESS_GROUP",0) if os.name=="nt" else 0)
            try:
                process=psutil.Process(child.pid)
                proof={"pid":child.pid,"started":process.create_time(),"command_hash":content_hash(process.cmdline()),"owner_pid":999999999,"owner_started":0}
                atomic_write_json(root/f"child_{child.pid}.json",{**proof,"started":proof["started"]-10})
                self.assertEqual(recover_children(root),[])
                self.assertIsNone(child.poll())
                atomic_write_json(root/f"child_{child.pid}.json",proof)
                self.assertEqual(recover_children(root),[child.pid])
                child.wait(timeout=5)
            finally:terminate_tree(child)

    def test_process_lock_rejects_second_owner_and_is_released(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/"execution.lock"
            with exclusive_file(path):
                with self.assertRaises(ResourceBusy):
                    with exclusive_file(path):pass
            with exclusive_file(path):pass

    def test_job_cancellation_is_persisted_before_cpu_stage_runs(self):
        from dc.cli import _execute_job
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            job=root/"work"/"job_cancel"
            job.mkdir(parents=True)
            (job/"cancel.request").write_text("cancel")
            with patch("dc.cli.ROOT",root):
                code=_execute_job("job_cancel",lambda: self.fail("Cancelled stage executed"))
            self.assertEqual(code,130)
            self.assertEqual(JobStore(root/"work"/"jobs.sqlite").get("job_cancel")["state"],"cancelled")

    def test_qa_does_not_swallow_child_cancellation(self):
        from dc.qa import validate_output
        with tempfile.TemporaryDirectory() as folder:
            output=Path(folder)/"clip.mp4"
            output.write_bytes(b"fixture")
            with patch("dc.qa.run_process",side_effect=ProcessCancelled("cancelled")),patch("dc.qa.require_tool",return_value="ffprobe"):
                with self.assertRaises(ProcessCancelled):validate_output(output,{},load_config())

    def test_mapped_craft_and_nameplate_timings_follow_silence_edits(self):
        plan={"source":{"path":"source"},"trim":{"start":10,"end":20,"duration":6},"original_trim":{"start":10,"end":20,"duration":10},"transcript":{"words":[]},"source_spans":[{"start":10,"end":12,"output_start":0},{"start":16,"end":20,"output_start":2}],"craft":{"evidence_card":{"text":"90%","start":7,"end":8}},"polish":{"nameplates":[{"start":6,"end":7}]}}
        result=runtime_plan(plan,Path("edited"))
        self.assertEqual(result["craft"]["evidence_card"]["start"],3)
        self.assertEqual(result["polish"]["nameplates"][0]["start"],2)

    def test_receipt_disclosure_edits_are_not_replaced_by_tight_cut(self):
        from dc.polish import apply_polish
        cuts=[{"start":2,"end":70,"kind":"receipt_gap"}]
        plan={"trim":{"start":0,"end":75,"duration":75},"framing":{"segments":[{"mode":"WIDE"}]},"receipt":{},"edited":True,"edits":cuts}
        # A nonempty receipt is how CLI represents a proposed pair.
        plan["receipt"]={"gap":68}
        apply_polish(plan,{"words":[]},load_config(overrides={"polish":{"tight_cut":{"enabled":True}}}))
        self.assertEqual(plan["edits"],cuts)

    def test_llm_ranges_reject_floats_empty_lists_and_booleans(self):
        self.assertEqual(validate_llm_payload([{"ranges":[]},{"ranges":[[.4,1]]},{"ranges":[[False,1]]}],5),[])
        self.assertEqual(len(validate_llm_payload([{"ranges":[[0,1]]}],5)),1)

    def test_preview_and_receipts_commands_have_real_parser_entries(self):
        from dc.cli import build_parser
        self.assertEqual(build_parser().parse_args(["receipts","--job","job_test"]).command,"receipts")
        self.assertEqual(build_parser().parse_args(["preview","--job","job_test","--candidate","c_test"]).command,"preview")

    def test_source_caption_band_is_not_expanded_like_a_face(self):
        from dc.vision import source_text_exclusions
        from dc.framing import framing_plan
        config=load_config()
        source={"width":1920,"height":1080}
        shots={"shots":[{"start":0,"end":10,"source_has_captions":True,"text_band":[0,.7,1,.25]}]}
        boxes=source_text_exclusions(shots,source,config,framing_plan(1920,1080,10,config),0,10)
        self.assertEqual(boxes[0][2],config.regions["feed"]["w"])
        self.assertAlmostEqual(boxes[0][3],151.875)

    def test_upload_urls_cannot_send_tokens_to_arbitrary_hosts(self):
        import urllib.request
        for url in ("http://www.googleapis.com/upload","https://attacker.invalid/upload","https://googleapis.com.attacker.invalid/upload","https://user@www.googleapis.com/upload"):
            with self.assertRaises(ValueError):_upload_request(urllib.request.Request(url),"youtube")

    def test_tiktok_upload_uses_bounded_chunks_and_exact_byte_ranges(self):
        from io import BytesIO
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/"clip.mp4"
            size=17*1024*1024
            with path.open("wb") as handle:handle.truncate(size)
            requests=[]
            def upload(request,platform):
                requests.append((len(request.data),request.get_header("Content-range")))
                return BytesIO(b"ok")
            with patch("dc.distribute.adapters.credential",return_value="test-token"),patch("dc.distribute.adapters.request_json",return_value=({"error":{"code":"ok"},"data":{"upload_url":"https://open.tiktokapis.com/upload","publish_id":"fixture"}},{})),patch("dc.distribute.adapters._upload_request",side_effect=upload):
                result=publish_tiktok_inbox(path)
            self.assertEqual(result["privacy"],"private")
            self.assertEqual([length for length,_ in requests],[8*1024*1024,9*1024*1024])
            self.assertEqual(requests[-1][1],f"bytes {8*1024*1024}-{size-1}/{size}")


@unittest.skipUnless(importlib.util.find_spec("fastapi") and importlib.util.find_spec("httpx"),"Studio dependencies unavailable")
class LanHardeningTests(unittest.TestCase):
    def test_token_bootstrap_cookie_protects_lan_reads_and_editing(self):
        from fastapi.testclient import TestClient
        from dc.studio.server import create_app
        app,token=create_app(lan=True)
        client=TestClient(app,base_url="http://192.168.1.20:8765")
        self.assertEqual(client.get("/api/jobs").status_code,403)
        self.assertEqual(client.get("/?token="+token).status_code,200)
        response=client.get("/api/system")
        self.assertEqual(response.status_code,200)
        self.assertEqual(client.post("/api/render",json={},headers={"Origin":"http://192.168.1.20:8765","X-DC-Token":token}).status_code,403)
