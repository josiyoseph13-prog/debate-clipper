import unittest

from dc.core.config import load_config
from dc.selection import build_graph, prompt_search, select_candidates


TRANSCRIPT = {
    "segments": [
        {"start": 0, "end": 5, "text": "Why did you vote for this policy?", "words": [{"start": 0, "end": 5, "text": "Why did you vote for this policy?"}], "speaker": "a"},
        {"start": 5.5, "end": 18, "text": "Because the data shows it helps families, and that is the record.", "words": [{"start": 5.5, "end": 18, "text": "Because the data shows it helps families, and that is the record."}], "speaker": "b"},
        {"start": 18.5, "end": 27, "text": "That's not true, you are wrong, and you did not answer the question.", "words": [{"start": 18.5, "end": 27, "text": "That's not true, you are wrong, and you did not answer the question."}], "speaker": "a"},
    ]
}


class SelectionTests(unittest.TestCase):
    def test_one_sided_clip_flags_identifiable_response_cut_from_full_source(self):
        from dc.selection import fairness_meter,can_auto_approve
        words=[{"text":"A clear position must include the full opposing response.","start":.2,"end":27,"speaker":"a"},{"text":"That is not true and I need to explain why.","start":30,"end":35,"speaker":"b"}]
        transcript={"segments":[{**word,"words":[word]} for word in words]}
        graph,candidates=select_candidates(transcript,{"source_id":"fixture","duration":40,"rights_class":"own","meta":{}},load_config())
        clipped=next(row for row in candidates if row["end"]<30)
        self.assertTrue(clipped["fairness"]["warning"])
        self.assertEqual(clipped["fairness"]["cut_responses"][0]["speaker"],"b")
        self.assertTrue(any(flag["code"]=="I-2" and flag.get("evidence") for flag in clipped["integrity_flags"]))
        priority={**clipped,"score":100,"layout_confidence":1}
        self.assertFalse(can_auto_approve(priority,90))
        self.assertTrue(can_auto_approve({**priority,"integrity_flags":[]},90))
        selected=[{"speaker":"a","start":0,"end":10}]
        self.assertFalse(fairness_meter(selected,[{"speaker":"unknown","start":11,"end":12,"text":"That is not true."}],10)["warning"])
        self.assertFalse(fairness_meter(selected,[{"speaker":"b","start":26,"end":28,"text":"That is not true."}],10)["warning"])

    def test_graph_and_candidate_contract(self):
        config = load_config()
        graph, candidates = select_candidates(TRANSCRIPT, {"source_id": "x", "duration": 30, "rights_class": "permission", "meta": {}}, config)
        self.assertEqual(graph["schema_version"], 5)
        self.assertTrue(candidates)
        self.assertIn("integrity_flags", candidates[0])

    def test_prompt_search_is_safe(self):
        candidate = {"id": "c1", "score": 80, "archetype": "A6", "text": "That is not what I asked."}
        self.assertEqual(prompt_search([candidate], "find where he dodges", 1)[0]["id"], "c1")
