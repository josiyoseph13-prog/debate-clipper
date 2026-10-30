from pathlib import Path
from .models import translate_sentences
from .core.io import atomic_write_json
from .core.config import AppConfig,ROOT
from .captions import build_captions
from .exports import write_sidecars


def export_translation(transcript:dict,language:str,model_name:str,output:Path,config):
    import re
    if not re.fullmatch(r"[a-z]{2,3}(?:-[A-Za-z]{2,4})?",language):
        raise ValueError("Invalid language code")
    sentences=transcript.get("segments",[])
    translations=translate_sentences([row["text"] for row in sentences],model_name,transcript.get("language","en"),language)
    mapped={"schema_version":5,"language":language,"machine_translated":True,"segments":[]}
    for row,text in zip(sentences,translations,strict=True):
        # Sentence timing is preserved; translated words are not assigned fake
        # source-word alignment. Each whole sentence is one sidecar cue.
        mapped["segments"].append({"start":row["start"],"end":row["end"],"text":text,"words":[{"text":text,"start":row["start"],"end":row["end"]}]})
    fonts=config.get("translation","fonts",default={})
    font=fonts.get(language)
    if not font or not (ROOT/font["file"]).is_file():
        raise RuntimeError("Register a script-appropriate Noto font for this language")
    data=config.json()
    data["captions"].update({"font_file":font["file"],"font_family":font["family"],"uppercase":False})
    data["craft"]["caption_mode"]="gravitas"
    output=output/language
    output.mkdir(parents=True,exist_ok=True)
    duration=max(row["end"] for row in sentences)
    plan=build_captions(mapped,0,duration,AppConfig(data,config.path),output/f"captions.{language}.ass")
    # Real per-language no-tofu/shaping measurements remain an acceptance gate.
    write_sidecars(output,mapped,0,duration)
    (output/"captions.srt").replace(output/f"captions.{language}.srt")
    (output/"captions.vtt").replace(output/f"captions.{language}.vtt")
    atomic_write_json(output/f"translation.{language}.json",{"schema_version":5,"machine_translated":True,"language":language,"model":model_name,"status":"needs_review","font":font,"caption_plan":plan,"language_accuracy_verified":False})
    return mapped
