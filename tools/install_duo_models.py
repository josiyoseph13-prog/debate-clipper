"""Explicit optional model setup from public upstream releases, never at export."""
from __future__ import annotations
import io
import json
import sys
import tarfile
import urllib.request
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from dc.core.io import read_json,atomic_write_json,atomic_write_bytes
from dc.core.hashing import file_hash


def fetch(url):
    print(f"Fetching {url}",flush=True)
    with urllib.request.urlopen(urllib.request.Request(url,headers={"User-Agent":"debate-clipper-model-setup"}),timeout=180) as response:
        return response.read()


def main():
    release=json.loads(fetch("https://api.github.com/repos/k2-fsa/sherpa-onnx/releases/tags/speaker-recongition-models"))
    assets=[a for a in release["assets"] if "campplus" in a["name"]]
    print(json.dumps([{k:a[k] for k in ("name","size","browser_download_url")} for a in assets],indent=2),flush=True)
    if "--install" not in sys.argv:return
    chosen=next(a for a in assets if a["name"]=="3dspeaker_speech_campplus_sv_zh-cn_16k-common.onnx")
    folder=ROOT/"assets/models/duo_diarization"
    if folder.is_symlink():raise ValueError("Invalid model directory")
    folder.mkdir(parents=True,exist_ok=True)
    card_url="https://huggingface.co/funasr/campplus/raw/e4b6ede7ce16997aff4ae69fbca1f0175e2afede/README.md"
    card=fetch(card_url)
    if b"license: apache-2.0" not in card:raise ValueError("Unconfirmed embedding model license")
    atomic_write_bytes(folder/"EMBEDDING_MODEL_CARD.md",card)
    atomic_write_bytes(folder/"embedding.onnx",fetch(chosen["browser_download_url"]))
    segment_url="https://github.com/k2-fsa/sherpa-onnx/releases/download/speaker-segmentation-models/sherpa-onnx-pyannote-segmentation-3-0.tar.bz2"
    archive=tarfile.open(fileobj=io.BytesIO(fetch(segment_url)),mode="r:bz2")
    # Read only named members; no archive paths are extracted.
    prefix="sherpa-onnx-pyannote-segmentation-3-0/"
    for name,out in (("model.onnx","segmentation.onnx"),("LICENSE","SEGMENTATION_LICENSE"),("README.md","SEGMENTATION_MODEL_CARD.md")):
        member=archive.getmember(prefix+name)
        if not member.isfile() or member.size>50_000_000:raise ValueError("Invalid release member")
        atomic_write_bytes(folder/out,archive.extractfile(member).read())
    if "MIT License" not in (folder/"SEGMENTATION_LICENSE").read_text():raise ValueError("Unconfirmed segmentation license")
    roles={"embedding":"embedding.onnx","segmentation":"segmentation.onnx","embedding_card":"EMBEDDING_MODEL_CARD.md","segmentation_card":"SEGMENTATION_MODEL_CARD.md","segmentation_license":"SEGMENTATION_LICENSE"}
    registry=read_json(ROOT/"assets/models/registry.json")
    registry["models"]["duo_diarization"]={"license":"Apache-2.0","component_licenses":{"segmentation":"MIT","embedding":"Apache-2.0"},"model_card_url":card_url,"source":"Explicit setup: official sherpa converted pyannote segmentation-3.0 and FunASR CAM++ common weights; no implicit network access","source_urls":{"embedding":chosen["browser_download_url"],"segmentation":segment_url,"segmentation_card":"https://huggingface.co/pyannote/segmentation-3.0"},"kind":"sherpa_onnx_diarization","num_clusters":-1,"threshold":.5,"accuracy_verified":False,"default_enabled":False,"files":{role:{"path":(folder/name).relative_to(ROOT).as_posix(),"sha256":file_hash(folder/name),"size_bytes":(folder/name).stat().st_size} for role,name in roles.items()}}
    atomic_write_json(ROOT/"assets/models/registry.json",registry)
    atomic_write_json(ROOT/"reports/duo_style/model_setup.json",registry["models"]["duo_diarization"])
    print("Optional local models registered with hashes; diarization accuracy Not measured.")


if __name__=="__main__":main()
