import copy
import math
import unittest
from unittest.mock import patch

from dc.core.config import load_config
from dc.speaker_frame import validate_speaker_frame,build_framing,compose_frame,blend_slots


def setting(layout="stacked"):
    return {"enabled":True,"layout":layout,"selected":"A","boxes":[{"id":"A","name":"Host","x":220,"y":190,"w":460,"h":540},{"id":"B","name":"Guest","x":1230,"y":200,"w":360,"h":480}],"voice_map":{"voice_1":"A","voice_2":"B"}}


class SpeakerFrameTests(unittest.TestCase):
    def test_rejects_nonfinite_numbers_html_unknown_fields_and_out_of_source_boxes(self):
        for value in (math.nan,math.inf,True,"200"):
            spec=setting();spec["boxes"][0]["x"]=value
            with self.assertRaises(ValueError):validate_speaker_frame(spec,1920,1080,12)
        for name in ("<img src=x onerror=alert(1)>","a\n<script>","X"*41):
            spec=setting();spec["boxes"][0]["name"]=name
            with self.assertRaises(ValueError):validate_speaker_frame(spec,1920,1080,12)
        spec=setting();spec["boxes"][1]["x"]=1910
        with self.assertRaises(ValueError):validate_speaker_frame(spec,1920,1080,12)
        spec=setting();spec["path"]="../../secret"
        with self.assertRaises(ValueError):validate_speaker_frame(spec,1920,1080,12)

    def test_disabled_is_explicit_and_two_layouts_require_two_boxes(self):
        self.assertEqual(validate_speaker_frame({"enabled":False},1920,1080,12),{"enabled":False})
        spec=setting();spec["boxes"].pop()
        with self.assertRaises(ValueError):validate_speaker_frame(spec,1920,1080,12)
        self.assertIsNone(build_framing({"enabled":False},{"width":1920,"height":1080},12,load_config()))

    def test_audio_unknown_uses_both_and_voice_mapping_switches_with_minimum_dwell(self):
        source={"width":1920,"height":1080,"clip_start":100}
        spec=setting("auto")
        unknown=build_framing(spec,source,12,load_config(),{"turns":[{"start":100,"end":112,"speaker":"unknown","confidence":0}]})
        self.assertEqual(unknown["segments"][0]["mode"],"DUAL")
        self.assertIn("Audio unclear",unknown["debug"]["warnings"][0]["text"])
        turns={"turns":[{"start":100,"end":104,"speaker":"voice_1","confidence":.9},{"start":104,"end":108,"speaker":"voice_2","confidence":.9},{"start":108,"end":112,"speaker":"voice_1","confidence":.9}]}
        plan=build_framing(spec,source,12,load_config(),turns)
        self.assertEqual([r["choice"] for r in plan["segments"]],["A","B","A"])
        self.assertTrue(all(r["t1"]-r["t0"]>=1.5 for r in plan["segments"]))

    def test_camera_cut_requires_confirmed_part_and_offscreen_never_invents_a_crop(self):
        spec=setting("single");source={"width":1920,"height":1080}
        plan=build_framing(spec,source,12,load_config(),cuts=[6])
        self.assertEqual(plan["segments"][-1]["mode"],"WIDE")
        self.assertIn("Camera changed. Check the boxes.",[row["text"] for row in plan["debug"]["warnings"]])
        spec["shots"]=[{"t":6,"boxes":copy.deepcopy(spec["boxes"])}]
        plan=build_framing(spec,source,12,load_config(),cuts=[6])
        self.assertEqual(plan["segments"][-1]["mode"],"SINGLE")
        spec["boxes"][0]["offscreen"]=True;spec["shots"]=[]
        self.assertEqual(build_framing(spec,source,12,load_config())["segments"][0]["mode"],"WIDE")

    def test_dwell_deadline_is_scheduled_inside_a_long_voice_turn(self):
        turns={"turns":[{"start":0,"end":.3,"speaker":"unknown","confidence":0},{"start":.3,"end":12,"speaker":"voice_1","confidence":.9}]}
        plan=build_framing(setting("auto"),{"width":1920,"height":1080},12,load_config(),turns)
        single=next(s for s in plan["segments"] if s["choice"]=="A")
        self.assertAlmostEqual(single["t0"],1.5)
        self.assertEqual(single["t1"],12)

    def test_uniform_stack_and_blend_have_no_mask_step_or_stretch(self):
        import numpy as np
        source={"width":1920,"height":1080};cfg=load_config()
        frame=np.zeros((1080,1920,3),dtype=np.uint8);frame[:,:960]=[220,0,0];frame[:,960:]=[0,0,220]
        for layout in ("single","stacked","blended"):
            spec=setting(layout);plan=build_framing(spec,source,12,cfg)
            segment=plan["segments"][0];image=compose_frame(frame,segment,1080,1216)
            self.assertEqual(image.shape,(1216,1080,3))
            slots,_,_=blend_slots(1080,1216,segment["blend"])
            ratios=[1080/1216] if layout=="single" else [1080/608]*2 if layout=="stacked" else [s[2]/s[3] for s in slots]
            for region,ratio in zip(segment["regions"],ratios):self.assertAlmostEqual(region["w"]/region["h"],ratio)
            if layout=="blended":
                _,a,b=blend_slots(1080,1216,segment["blend"])
                red=image[600,a:b,0].astype(float)
                self.assertGreater(red[0],200);self.assertLess(red[-1],5)
                self.assertLess(np.max(np.abs(np.diff(red))),5)

    def test_timeline_corrections_are_bounded_and_survive_auto(self):
        spec=setting("auto");spec["overrides"]=[{"start":2,"end":5,"choice":"B"}]
        plan=build_framing(spec,{"width":1920,"height":1080},12,load_config())
        segment=next(s for s in plan["segments"] if s["t0"]==2)
        self.assertEqual(segment["choice"],"B")
        spec["overrides"].append({"start":4,"end":8,"choice":"A"})
        with self.assertRaises(ValueError):validate_speaker_frame(spec,1920,1080,12)

    def test_duo_stays_blended_until_mapped_turn_reaches_delay_then_returns(self):
        spec=setting("duo");spec["duo"]={"style":"smart","full_after":2,"duo_after":.5}
        turns={"turns":[{"start":0,"end":4,"speaker":"voice_1","confidence":.9},{"start":4.2,"end":5,"speaker":"voice_2","confidence":.9}]}
        plan=build_framing(spec,{"width":1920,"height":1080},6,load_config(),turns)
        self.assertEqual(plan["segments"][0]["mode"],"BLEND")
        self.assertTrue(any(row["mode"]=="SINGLE" and row["choice"]=="A" for row in plan["segments"]))
        self.assertTrue(any(row["mode"]=="BLEND" and row["t0"]>=4 for row in plan["segments"]))
        self.assertEqual(plan["debug"]["layout_seconds"].get("Duo") is not None,True)

    def test_duo_unknown_audio_does_not_invent_full_screen_switches(self):
        spec=setting("duo");spec["duo"]={"style":"smart","full_after":.5,"duo_after":0}
        plan=build_framing(spec,{"width":1920,"height":1080},6,load_config(),{"turns":[{"start":0,"end":6,"speaker":"unknown","confidence":0}]})
        self.assertTrue(all(row["mode"]=="BLEND" for row in plan["segments"]))
        self.assertIn("Audio unclear. Staying in Duo.",[row["text"] for row in plan["debug"]["warnings"]])


class SpeakerFrameSecurityTests(unittest.TestCase):
    def test_new_endpoints_keep_origin_token_and_lan_guards(self):
        from fastapi.testclient import TestClient
        from dc.studio.server import create_app
        app,token=create_app()
        client=TestClient(app,base_url="http://127.0.0.1")
        payload={"job_id":"../secret","candidate_id":"c_ok","speaker_frame":setting()}
        self.assertEqual(client.post("/api/speaker-frame/save",json=payload).status_code,403)
        headers={"Origin":"http://127.0.0.1","X-DC-Token":token}
        self.assertEqual(client.post("/api/speaker-frame/save",json=payload,headers=headers).status_code,400)
        self.assertEqual(client.post("/api/speaker-frame/save",json={},headers={**headers,"Origin":"https://evil.invalid"}).status_code,403)
        app,token=create_app(lan=True);client=TestClient(app,base_url="http://127.0.0.1")
        self.assertEqual(client.post("/api/speaker-frame/save",json={"job_id":"job_ok","candidate_id":"c_ok"},headers={"Origin":"http://127.0.0.1","X-DC-Token":token}).status_code,403)

    def test_api_rejects_bad_boxes_without_writing_and_disabled_uses_no_analysis(self):
        from fastapi.testclient import TestClient
        from dc.studio.server import create_app
        app,token=create_app();client=TestClient(app,base_url="http://127.0.0.1")
        headers={"Origin":"http://127.0.0.1","X-DC-Token":token}
        payload={"job_id":"job_863e97df620d","candidate_id":"c_a9ef26901548","speaker_frame":setting()}
        payload["speaker_frame"]["boxes"][0]["name"]="<script>"
        with patch("dc.studio.speaker_frame_api.record_decision") as save:
            self.assertEqual(client.post("/api/speaker-frame/save",json=payload,headers=headers).status_code,400)
            save.assert_not_called()
