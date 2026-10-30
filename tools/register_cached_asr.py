"""Register the existing MIT Whisper-base cache after upstream hash validation."""
from pathlib import Path
import argparse
import hashlib
import json
import sys
import urllib.request

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from dc.core.hashing import file_hash
from dc.core.io import atomic_copy,atomic_write_bytes,atomic_write_json,read_json


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--cache",required=True,type=Path)
    args=parser.parse_args()
    commit="ebe41f70d5b6dfa9166e2c581c45c9c0cfc57b66"
    api=f"https://huggingface.co/api/models/Systran/faster-whisper-base/revision/{commit}?blobs=true"
    with urllib.request.urlopen(api,timeout=30) as response:metadata=json.loads(response.read(1_000_000))
    if metadata["sha"]!=commit or metadata["cardData"]["license"]!="mit":raise ValueError("Model revision/licence mismatch")
    destination=ROOT/"assets"/"models"/"whisper_base"
    destination.mkdir(parents=True,exist_ok=True)
    roles={"model.bin":"model","config.json":"config","tokenizer.json":"tokenizer","vocabulary.txt":"vocabulary"}
    files={}
    for name,role in roles.items():
        entry=next(row for row in metadata["siblings"] if row["rfilename"]==name)
        cached=args.cache/name
        if cached.stat().st_size!=entry["size"]:raise ValueError(f"Cached size mismatch: {name}")
        if entry.get("lfs"):
            if file_hash(cached)!=entry["lfs"]["sha256"]:raise ValueError(f"Cached upstream SHA256 mismatch: {name}")
        else:
            git_hash=hashlib.sha1(f"blob {entry['size']}\0".encode()+cached.read_bytes()).hexdigest()
            if git_hash!=entry["blobId"]:raise ValueError(f"Cached upstream Git blob mismatch: {name}")
        target=destination/name
        atomic_copy(cached,target)
        files[role]={"path":str(target.relative_to(ROOT)),"sha256":file_hash(target),"size_bytes":target.stat().st_size}
    card=f"https://huggingface.co/Systran/faster-whisper-base/raw/{commit}/README.md"
    with urllib.request.urlopen(card,timeout=30) as response:atomic_write_bytes(destination/"MODEL_CARD.md",response.read(100_000))
    with urllib.request.urlopen("https://raw.githubusercontent.com/openai/whisper/main/LICENSE",timeout=30) as response:atomic_write_bytes(destination/"LICENSE",response.read(100_000))
    for role,name in (("model_card","MODEL_CARD.md"),("license_text","LICENSE")):
        files[role]={"path":str((destination/name).relative_to(ROOT)),"sha256":file_hash(destination/name)}
    registry=read_json(ROOT/"assets"/"models"/"registry.json",{}) or {}
    registry.setdefault("models",{})["whisper_base"]={"license":"MIT","model_card_url":card,"upstream_revision":commit,"source":"Existing user-local cache; exact upstream blob/LFS hashes checked","kind":"ctranslate2_asr","files":files,"accuracy_verified":False,"default_enabled":False}
    registry["schema_version"]=5
    atomic_write_json(ROOT/"assets"/"models"/"registry.json",registry)
    atomic_write_json(ROOT/"reports"/"supplied_media"/"registered_asr.json",{"schema_version":5,"command":[sys.executable,*sys.argv],"upstream":metadata,"registered_model":registry["models"]["whisper_base"],"quality_gate":"Word/name/onset accuracy cannot be proven without independent labels"})
    print({"model":"whisper_base","files":files,"accuracy_verified":False})


if __name__=="__main__":main()
