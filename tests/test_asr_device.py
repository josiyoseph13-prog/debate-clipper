"""ASR device-selection tests (Speed follow-up, 2026-10-12).

Default behaviour must stay cpu/int8; cuda is chosen only from config
and only when the runtime probe passes; the shipped config selects
cuda + int8_float16; the CLI cache key carries the same device.
"""
import json
import sys
import unittest
from pathlib import Path
from unittest import mock

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))

import dc.asr as asr  # noqa: E402
from dc.core.config import AppConfig, load_preset  # noqa: E402


def cfg(data):
    return AppConfig(data, PROJECT / "config" / "political_lens.json")


class WhisperParamsTests(unittest.TestCase):
    def test_default_is_cpu_int8(self):
        params = asr._whisper_params(cfg({}), local_files_only=False)
        self.assertEqual(params["device"], "cpu")
        self.assertEqual(params["compute_type"], "int8")
        self.assertNotIn("fallback_from", params)

    def test_unknown_device_is_cpu(self):
        params = asr._whisper_params(cfg({"asr": {"device": "tpu"}}), local_files_only=True)
        self.assertEqual(params["device"], "cpu")

    def test_cuda_chosen_when_probe_passes(self):
        with mock.patch.object(asr, "_cuda_usable", return_value=True):
            params = asr._whisper_params(
                cfg({"asr": {"device": "cuda", "compute_type": "int8_float16"}}),
                local_files_only=True,
            )
        self.assertEqual(params["device"], "cuda")
        self.assertEqual(params["compute_type"], "int8_float16")

    def test_cuda_falls_back_when_probe_fails(self):
        with mock.patch.object(asr, "_cuda_usable", return_value=False):
            params = asr._whisper_params(
                cfg({"asr": {"device": "cuda", "compute_type": "int8_float16"}}),
                local_files_only=True,
            )
        self.assertEqual(params["device"], "cpu")
        self.assertEqual(params["compute_type"], "int8")
        self.assertEqual(params["fallback_from"], "cuda")

    def test_shipped_config_selects_cuda(self):
        config = load_preset("political_lens")
        self.assertEqual(config.get("asr", "device"), "cuda")
        self.assertEqual(config.get("asr", "compute_type"), "int8_float16")
        raw = json.loads((PROJECT / "config" / "political_lens.json").read_text(encoding="utf-8"))
        self.assertEqual(raw["asr"]["device"], "cuda")
        self.assertEqual(raw["output"]["encoder"], "h264_qsv")


if __name__ == "__main__":
    unittest.main()
