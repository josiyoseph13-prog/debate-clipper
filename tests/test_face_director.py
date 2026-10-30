import math
import unittest

from dc.core.config import load_config
from dc.framing import framing_quality, rect_at
from dc.vision import directed_framing


class FaceDirectorTests(unittest.TestCase):
    def analysis(self, ambiguous=False, silent=False, switch=False):
        rows=[]
        for index in range(120):
            t=index/15
            for track,x in (("left",300),("right",1300)):
                active=ambiguous or (track==("left" if switch and t>=4 else "right"))
                rows.append({"t":t,"track":track,"mouth":.15+.09*math.sin(index) if active else .001,"speech":not silent,"source_box":[x,230,170,200]})
        return {"engine":"mediapipe_landmarks","landmark_fps":15,"observations":rows}

    def direct(self, analysis):
        return directed_framing(analysis,{"width":1920,"height":1080},8,load_config(),{})

    def test_questioner_selected_over_static_larger_listener(self):
        plan=self.direct(self.analysis())
        self.assertTrue(all(row["mode"]=="SINGLE" and row["track"]=="right" for row in plan["segments"]))
        self.assertGreater(rect_at(plan["path"],0)["x"],900)
        self.assertEqual(plan["debug"]["active_speaker_accuracy"],"Not measured")

    def test_ambiguous_and_silent_faces_do_not_create_a_speaker_crop(self):
        self.assertIsNone(self.direct(self.analysis(ambiguous=True)))
        self.assertIsNone(self.direct(self.analysis(silent=True)))

    def test_speaker_change_cuts_without_panning_across_other_people(self):
        plan=self.direct(self.analysis(switch=True))
        self.assertEqual(plan["segments"][0]["track"],"right")
        self.assertEqual(plan["segments"][-1]["track"],"left")
        quality=framing_quality({"framing":plan})
        self.assertGreaterEqual(quality["clean_cuts"],1)
        self.assertTrue(quality["camera_jump"]["passed"])
        self.assertTrue(quality["zoom_change"]["passed"])

    def test_source_cut_resets_the_track_without_a_hold_on_the_old_person(self):
        analysis=self.analysis(switch=True)
        analysis["scene_cuts"]=[4]
        plan=self.direct(analysis)
        segment=next(row for row in plan["segments"] if row["t0"]==4)
        self.assertEqual(segment["track"],"left")

    def test_unmeasured_geometry_is_not_reported_as_a_face_pass(self):
        quality=framing_quality({"framing":{"segments":[],"path":[]}})
        self.assertIn("Not measured",quality["face_in_safe_area"])
        self.assertEqual(quality["speaker_size"],"Not measured")
