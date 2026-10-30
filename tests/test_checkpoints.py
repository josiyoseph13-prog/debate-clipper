import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch
from dc.core.checkpoints import StageCheckpoints
from dc.core.config import load_config
from dc.core.io import atomic_write_json
from dc.pipeline import write_analysis_artifacts
from dc.cli import _selection_key


class CheckpointTests(unittest.TestCase):
    def test_corrupt_or_incomplete_stage_is_not_reused(self):
        with tempfile.TemporaryDirectory() as folder:
            job=Path(folder)
            cache=StageCheckpoints(job)
            atomic_write_json(job/"graph.json",{"words":["original"]})
            atomic_write_json(job/"candidates.json",{"candidates":[1]})
            self.assertFalse(cache.valid("selection","key",["graph.json","candidates.json"]))
            cache.commit("selection","key",["graph.json","candidates.json"])
            self.assertTrue(cache.valid("selection","key",["graph.json","candidates.json"]))
            self.assertFalse(cache.valid("selection","changed",["graph.json","candidates.json"]))
            atomic_write_json(job/"graph.json",{"words":["tampered"]})
            self.assertFalse(cache.valid("selection","key",["graph.json","candidates.json"]))
            atomic_write_json(job/"checkpoint_selection.json",["not a checkpoint object"])
            self.assertFalse(cache.valid("selection","key",["graph.json","candidates.json"]))
            with self.assertRaises(ValueError):cache.commit("selection","key",["../outside.json"])

    def test_analysis_reuses_valid_stages_but_detects_metadata_and_file_changes(self):
        with tempfile.TemporaryDirectory() as folder:
            job=Path(folder)
            source={"path":str(job/"source.mp4"),"duration":10,"has_audio":False,"fingerprint":{"sha256":"source"},"meta":{"heatmap":[{"start_time":0,"end_time":10,"value":.2}]}}
            cfg=load_config()
            graph={"turns":[]}
            transcript={"segments":[]}
            with patch("dc.pipeline._scene_shots",return_value=[{"start":0,"end":10}]) as scan,patch("dc.vision.classify_shots",side_effect=lambda source,shots:shots):
                first=write_analysis_artifacts(job,source,transcript,graph,cfg)
                second=write_analysis_artifacts(job,source,transcript,graph,cfg)
                self.assertEqual(scan.call_count,1)
                self.assertEqual(first,second)
                source["meta"]["heatmap"][0]["value"]=.8
                changed=write_analysis_artifacts(job,source,transcript,graph,cfg)
                self.assertNotEqual(first["signals"]["cache_key"],changed["signals"]["cache_key"])
                self.assertEqual(scan.call_count,1)
                atomic_write_json(job/"shots.json",{"schema_version":5,"cache_key":first["shots"]["cache_key"],"shots":[]})
                write_analysis_artifacts(job,source,transcript,graph,cfg)
                self.assertEqual(scan.call_count,2)

    def test_palette_reuses_discovery_but_words_rights_and_negative_memory_do_not(self):
        cfg=load_config()
        source={"fingerprint":{"sha256":"source"},"rights_class":"unknown"}
        transcript={"segments":[{"text":"Original words"}]}
        key=_selection_key(source,transcript,cfg,8,[],{})
        palette=load_config(overrides={"captions":{"active":"#FFE600"},"craft":{"caption_mode":"karaoke_lite"},"output":{"crf":23}})
        self.assertEqual(key,_selection_key(source,transcript,palette,8,[],{}))
        self.assertNotEqual(key,_selection_key(source,{"segments":[]},cfg,8,[],{}))
        self.assertNotEqual(key,_selection_key({**source,"rights_class":"permission"},transcript,cfg,8,[],{}))
        self.assertNotEqual(key,_selection_key(source,transcript,cfg,8,["rejected words"],{}))
