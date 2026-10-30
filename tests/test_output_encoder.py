"""Output-encoder selection tests (Speed fix, 2026-10-12).

The renderer must default to the exact historical libx264 args, map the
configured quality onto the hardware encoders as measured, splice the
encoder segment correctly in both ffmpeg arg layouts, and the shipped
config must select QuickSync with veryfast as the x264 fallback speed.
"""
import json
import sys
import unittest
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))
sys.path.insert(0, str(PROJECT / "dc"))

from dc.core.config import load_preset  # noqa: E402
from dc.renderer import _configured_encoder, _encoder_segment, _video_encode_args, _with_encoder  # noqa: E402


class EncoderSegmentTests(unittest.TestCase):
    def setUp(self):
        self.config = load_preset("political_lens")

    def _cfg(self, **output):
        from dc.core.config import AppConfig, _deep_merge

        merged = _deep_merge(self.config.json(), {"output": output})
        return AppConfig(merged, self.config.path)

    def test_config_selects_qsv_with_veryfast_fallback(self):
        self.assertEqual(self.config.get("output", "encoder"), "h264_qsv")
        self.assertEqual(self.config.get("output", "preset"), "veryfast")
        self.assertEqual(self.config.get("output", "crf"), 18)
        self.assertEqual(_configured_encoder(self.config), "h264_qsv")

    def test_qsv_segment_maps_crf_to_icq_plus_one(self):
        self.assertEqual(
            _video_encode_args(self.config),
            ["-c:v", "h264_qsv", "-global_quality", "19", "-pix_fmt", "nv12"],
        )

    def test_libx264_segment_is_the_historical_default(self):
        cfg = self._cfg(encoder="libx264")
        del cfg.data["output"]["encoder"]
        self.assertEqual(_configured_encoder(cfg), "libx264")
        self.assertEqual(
            _encoder_segment(cfg, "libx264"),
            ["-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p"],
        )

    def test_unknown_encoder_degrades_to_libx264(self):
        cfg = self._cfg(encoder="h264_bogus")
        self.assertEqual(_configured_encoder(cfg), "libx264")

    def test_nvenc_segment(self):
        self.assertEqual(
            _encoder_segment(self.config, "h264_nvenc"),
            ["-c:v", "h264_nvenc", "-preset", "p5", "-cq", "19", "-pix_fmt", "yuv420p"],
        )

    def test_splice_main_layout(self):
        args = ["ffmpeg", "-i", "in", "-c:a", "aac", "-b:a", "160k",
                "-c:v", "h264_qsv", "-global_quality", "19", "-pix_fmt", "nv12",
                "-movflags", "+faststart", "-f", "mp4", "out.mp4"]
        out = _with_encoder(args, self.config, "libx264")
        self.assertEqual(
            out,
            ["ffmpeg", "-i", "in", "-c:a", "aac", "-b:a", "160k",
             "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p",
             "-movflags", "+faststart", "-f", "mp4", "out.mp4"],
        )

    def test_splice_variant_layout(self):
        args = ["ffmpeg", "-y", "-i", "base.mkv",
                "-c:v", "h264_qsv", "-global_quality", "19", "-pix_fmt", "nv12",
                "-c:a", "aac", "-b:a", "160k", "-f", "mp4", "out.mp4"]
        out = _with_encoder(args, self.config, "libx264")
        self.assertEqual(
            out,
            ["ffmpeg", "-y", "-i", "base.mkv",
             "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p",
             "-c:a", "aac", "-b:a", "160k", "-f", "mp4", "out.mp4"],
        )

    def test_config_json_on_disk(self):
        raw = json.loads((PROJECT / "config" / "political_lens.json").read_text(encoding="utf-8"))
        self.assertEqual(raw["output"]["encoder"], "h264_qsv")


if __name__ == "__main__":
    unittest.main()
