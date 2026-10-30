import importlib.util
import json
import random
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import xml.etree.ElementTree as ET

from dc.core.config import load_config,load_preset,ROOT
from dc.core.hashing import content_hash,file_hash
from dc.core.io import atomic_write_json
from dc.core.logging import redact
from dc.core.security import validate_id
from dc.craft import receipt_pair,question_chip
from dc.evaluation import wilson,bootstrap_difference,kappa,diarization_error
from dc.exports import write_interop,write_sidecars
from dc.integrity import publish_gate
from dc.layout import crop_rect,validate_framing_rect
from dc.polish import tight_cut_edits,split_series
from dc.selection import can_auto_approve,headline_fidelity,generate_headlines
from dc.signals import timestamp_mentions,replay_feature
from dc.timeline import kept_spans,map_transcript


class ExtendedRequirementsTests(unittest.TestCase):
    @unittest.skipUnless(importlib.util.find_spec("PIL"),"Measured headline fitting requires Pillow")
    def test_thirty_short_long_and_emoji_headlines_fit_without_overflow(self):
        from dc.layout import fit_headline
        from dc.chrome import render_chrome
        config=load_config()
        topics=("Education","Healthcare","Student loans","Public records","Climate policy","Housing costs")
        forms=("The {topic} question","Should {topic} actually work?","Why the debate over {topic} matters","The full case for {topic}","What does the record show about {topic}? 🎓")
        headlines=[form.format(topic=topic) for topic in topics for form in forms]
        self.assertEqual(len(headlines),30)
        for headline in headlines:
            fit=fit_headline(headline,config)
            self.assertTrue(fit["fit"],headline)
            self.assertLessEqual(len(fit["lines"]),3)
            self.assertGreaterEqual(fit["font_px"],40)
            self.assertLessEqual(fit["width"],config.get("hook","max_w"))
            _,manifest=render_chrome(config,headline)
            self.assertIsNone(manifest["emoji_warning"],headline)

    def test_randomized_crop_containment_1000_cases(self):
        rng=random.Random(7)
        config=load_config()
        for _ in range(1000):
            width,height=rng.randrange(240,4096),rng.randrange(240,2161)
            rect=crop_rect(width,height,config,rng.uniform(-width,width*2),rng.uniform(-height,height*2),rng.uniform(1,2))
            self.assertTrue(validate_framing_rect(rect,width,height))
            self.assertAlmostEqual(rect["w"]/rect["h"],config.regions["feed"]["w"]/config.regions["feed"]["h"])

    def test_tight_cut_only_removes_word_free_same_speaker_silence(self):
        words=[{"start":0,"end":1,"text":"Hello","speaker":"a"},{"start":3,"end":15,"text":"Answer","speaker":"a"}]
        edits=tight_cut_edits(words)
        self.assertEqual(len(edits),1)
        self.assertGreater(edits[0]["start"],words[0]["end"])
        self.assertLess(edits[0]["end"],words[1]["start"])
        self.assertLessEqual(edits[0]["removed_s"]/15,.15)
        words[1]["speaker"]="b"
        self.assertEqual(tight_cut_edits(words),[])
        words[1]["speaker"]=words[0]["speaker"]="unknown"
        self.assertEqual(tight_cut_edits(words),[])

    def test_timeline_preserves_words_and_order_across_a_disclosed_gap(self):
        transcript={"segments":[{"start":1,"end":2,"text":"One.","words":[{"start":1,"end":2,"text":"One."}]},{"start":10,"end":11,"text":"Two.","words":[{"start":10,"end":11,"text":"Two."}]}]}
        spans=kept_spans(0,12,[{"start":3,"end":9}])
        mapped=map_transcript(transcript,spans)
        self.assertEqual([word["text"] for word in mapped["words"]],["One.","Two."])
        self.assertEqual(mapped["words"][1]["start"],4)
        self.assertEqual(sum(span["end"]-span["start"] for span in spans),6)

    def test_receipts_require_verified_same_speaker_and_block_qualifiers(self):
        config=load_config()
        transcript={"verified_speakers":["a"],"segments":[{"start":0,"end":5,"speaker":"a","text":"I will always support this policy."},{"start":70,"end":75,"speaker":"a","text":"I will never support this policy."}]}
        proposal=receipt_pair(transcript,config)
        self.assertIsNotNone(proposal)
        self.assertFalse(proposal["auto_allowed"])
        transcript["segments"][1]["speaker"]="b"
        self.assertIsNone(receipt_pair(transcript,config))
        transcript["segments"][1]["speaker"]="a"
        transcript["segments"].insert(1,{"start":6,"end":8,"speaker":"a","text":"What I meant was support with conditions."})
        self.assertIsNone(receipt_pair(transcript,config))
        transcript["segments"].pop(1)
        transcript["verified_speakers"]=[]
        self.assertIsNone(receipt_pair(transcript,config))

    def test_question_chip_uses_nearest_other_speaker_and_exact_text(self):
        transcript={"segments":[{"start":0,"end":2,"speaker":"a","text":"What is the policy?","words":[{"start":0,"end":2,"text":"What is the policy?"}]},{"start":3,"end":5,"speaker":"b","text":"It helps families.","words":[{"start":3,"end":5,"text":"It helps families."}]}]}
        chip=question_chip(transcript,3,5,load_config())
        self.assertEqual(chip["text"],"What is the policy?")
        transcript["segments"][1]["speaker"]="a"
        self.assertIsNone(question_chip(transcript,3,5,load_config()))

    def test_neutral_election_headlines_pass_fidelity(self):
        text="The election ballot count is disputed. The record shows the count."
        options=generate_headlines(text,load_config())
        self.assertTrue(options)
        self.assertTrue(all(option.endswith("?") and headline_fidelity(option,text) for option in options))

    def test_auto_rejects_missing_layout_evidence_or_unchecked_claims(self):
        candidate={"score":99,"boundary":{"confidence":1},"integrity_flags":[],"archetype":"A3"}
        self.assertFalse(can_auto_approve(candidate))
        candidate["layout_confidence"]=1
        self.assertTrue(can_auto_approve(candidate))
        candidate["claims"]=[{"claim_checked":False}]
        self.assertFalse(can_auto_approve(candidate))

    def test_null_safe_crowd_and_count_only_mentions(self):
        self.assertIsNone(replay_feature(None,0,10))
        self.assertEqual(timestamp_mentions(["User A said 1:05 and 01:02:03","same moment 1:05"]),{"60":2,"3720":1})
        feature=replay_feature([{"start_time":0,"end_time":10,"value":.1},{"start_time":10,"end_time":20,"value":.9}],10,20)
        self.assertEqual(feature,1)

    def test_srt_vtt_have_standard_millisecond_timecodes(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            write_sidecars(root,{"words":[{"text":"Hello","start":2.125,"end":2.875}]},2,3)
            self.assertIn("00:00:00,125 --> 00:00:00,875",(root/"captions.srt").read_text())
            self.assertIn("00:00:00.125 --> 00:00:00.875",(root/"captions.vtt").read_text())

    def test_nle_timeline_preserves_two_source_spans_at_25fps(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            plan={"source":{"path":str(root/"a video.mp4"),"width":1280,"height":720},"trim":{"start":2,"end":10,"duration":4},"candidate_id":"c_test","frame_rate":{"target_cfr":25},"source_spans":[{"start":2,"end":4,"output_start":0},{"start":8,"end":10,"output_start":2}]}
            write_interop(root,plan)
            timeline=json.loads((root/"timeline.otio").read_text())
            clips=timeline["tracks"]["children"][0]["children"]
            self.assertEqual([clip["source_range"]["start_time"]["value"] for clip in clips],[50,200])
            self.assertEqual(sum(clip["source_range"]["duration"]["value"] for clip in clips),100)
            self.assertEqual(len(ET.parse(root/"timeline.fcpxml").findall(".//asset-clip")),2)
            edl=(root/"timeline.edl").read_text()
            self.assertIn("00:00:02:00",edl)
            self.assertIn("002  AX",edl)

    def test_statistical_protocol_does_not_invent_confidence_or_labels(self):
        interval=wilson(70,100)
        self.assertLess(interval[0],.7)
        self.assertGreater(interval[1],.7)
        self.assertIsNone(wilson(0,0))
        paired=bootstrap_difference([0,0,0],[1,1,1],200)
        self.assertEqual(paired["ci95"],[1,1])
        self.assertEqual(kappa([1,0],[1,0]),1)

    def test_diarization_metric_is_label_permutation_invariant(self):
        reference=[{"start":0,"end":2,"speaker":"Alice"},{"start":2,"end":4,"speaker":"Bob"}]
        hypothesis=[{"start":0,"end":2,"speaker":"cluster_1"},{"start":2,"end":4,"speaker":"cluster_0"}]
        self.assertEqual(diarization_error(reference,hypothesis,4)["der"],0)

    def test_font_assets_have_recorded_licenses_and_path_hashes_stream(self):
        for name in ("Poppins-ExtraBold.ttf","Poppins-Regular.ttf","Poppins-SemiBold.ttf","Anton-Regular.ttf","NotoColorEmoji.ttf"):
            self.assertTrue((ROOT/"assets"/"fonts"/name).is_file())
        self.assertIn("SIL OPEN FONT LICENSE",(ROOT/"assets"/"fonts"/"Poppins-OFL.txt").read_text())
        self.assertEqual(content_hash(ROOT/"assets"/"fonts"/"Poppins-Regular.ttf"),file_hash(ROOT/"assets"/"fonts"/"Poppins-Regular.ttf"))

    def test_security_redacts_every_url_query_and_reserved_windows_extension(self):
        self.assertNotIn("sensitive",redact("https://example.org/video?anything=sensitive"))
        for value in ("CON.mp4","NUL.json","a..b","LPT1.log","file."):
            with self.assertRaises(ValueError): validate_id(value)

    def test_preset_unknown_is_not_silently_replaced(self):
        with self.assertRaises(ValueError):load_preset("missing_brand")
        self.assertFalse(load_preset("faithful").get("polish","tight_cut","enabled"))

    def test_unregistered_models_cannot_run_or_download(self):
        from dc.models import model_spec
        with self.assertRaises(RuntimeError):model_spec("unknown_model")
