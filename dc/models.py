"""Offline, hash-checked model registry. No implicit downloads or model trust."""
from __future__ import annotations

from pathlib import Path
from .core.config import ROOT
from .core.hashing import file_hash
from .core.io import read_json


PERMITTED = {"Apache-2.0", "MIT", "BSD-3-Clause", "BSD-2-Clause", "CC0-1.0"}


def model_spec(name: str) -> dict:
    registry = read_json(ROOT / "assets" / "models" / "registry.json", {}) or {}
    spec = registry.get("models", {}).get(name)
    if not spec:
        raise RuntimeError(f"Offline model '{name}' is not registered")
    if spec.get("license") not in PERMITTED or not spec.get("model_card_url"):
        raise ValueError("Model licence and model-card provenance must be recorded")
    result = dict(spec)
    files = {}
    for role, item in spec.get("files", {}).items():
        path = (ROOT / item["path"]).resolve()
        if ROOT.resolve() not in path.parents or not path.is_file():
            raise ValueError(f"Missing or escaping model file: {role}")
        if file_hash(path) != item["sha256"]:
            raise ValueError(f"Model SHA-256 mismatch: {role}")
        files[role] = path
    if not files:
        raise ValueError("Registered model has no hash-verified files")
    result["paths"] = files
    return result


class OnnxTextModel:
    def __init__(self, name: str):
        import onnxruntime as ort
        from tokenizers import Tokenizer
        self.spec = model_spec(name)
        options = ort.SessionOptions()
        options.intra_op_num_threads = 2
        self.session = ort.InferenceSession(str(self.spec["paths"]["model"]), options, providers=["CPUExecutionProvider"])
        self.tokenizer = Tokenizer.from_file(str(self.spec["paths"]["tokenizer"]))
        self.tokenizer.enable_truncation(max_length=int(self.spec.get("max_length", 256)))
        self.tokenizer.enable_padding()

    def predict(self, texts: list, pairs: list | None = None):
        import numpy as np
        encoded = self.tokenizer.encode_batch(list(zip(texts, pairs)) if pairs is not None else texts)
        values = {"input_ids": np.array([row.ids for row in encoded], dtype=np.int64), "attention_mask": np.array([row.attention_mask for row in encoded], dtype=np.int64), "token_type_ids": np.array([row.type_ids for row in encoded], dtype=np.int64)}
        feeds = {item.name: values[item.name].astype(np.int32 if item.type == "tensor(int32)" else np.int64) for item in self.session.get_inputs()}
        output = self.session.run(None, feeds)[0]
        if output.ndim == 3:
            mask = values["attention_mask"][..., None]
            output = (output * mask).sum(axis=1) / np.maximum(1, mask.sum(axis=1))
            return output / np.maximum(1e-9, np.linalg.norm(output, axis=1, keepdims=True))
        exp = np.exp(output - output.max(axis=1, keepdims=True))
        return exp / exp.sum(axis=1, keepdims=True)


def translate_sentences(texts: list[str], name: str, source_lang: str, target_lang: str) -> list[str]:
    import ctranslate2
    import sentencepiece
    spec = model_spec(name)
    if "sentencepiece" not in spec["paths"]:
        raise ValueError("Translation registry needs a sentencepiece tokenizer")
    tokenizer = sentencepiece.SentencePieceProcessor(model_file=str(spec["paths"]["sentencepiece"]))
    # Every file under the CTranslate2 model directory must be registered.
    folder = spec["paths"]["model"].parent
    if any(path.is_file() and path not in spec["paths"].values() for path in folder.iterdir()):
        raise ValueError("Unregistered translation model files")
    translator = ctranslate2.Translator(str(folder), device="cpu", compute_type="int8", inter_threads=1, intra_threads=2)
    tokens = [tokenizer.encode(text, out_type=str) for text in texts]
    prefix = spec.get("target_prefix", {}).get(target_lang)
    results = translator.translate_batch(tokens, target_prefix=[[prefix]] * len(tokens) if prefix else None, beam_size=4)
    return [tokenizer.decode(row.hypotheses[0][1:] if prefix else row.hypotheses[0]) for row in results]
