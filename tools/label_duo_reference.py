"""Create an honest, approximate visual study timeline from supplied sheets."""
from __future__ import annotations
import json
import sys
from pathlib import Path
from PIL import Image,ImageDraw
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from dc.core.io import read_json,atomic_write_json

ROOT=Path(__file__).resolve().parents[1]
# These are visual study labels at the supplied 0.5s sample grid. They are
# intentionally broad and marked approximate; they are not copied edit timings.
INTERVALS={
 6:[("Duo",0,4.5),("Full A",4.5,6.5),("Duo",6.5,13.5),("Full B",13.5,16),("Duo",16,31.5),("Full B",31.5,32.57)],
 8:[("Duo",0,4),("Full A",4,5.5),("Full B",5.5,8),("Full A",8,10.5),("Full B",10.5,13.5),("Full A",13.5,14.5),("Full B",14.5,16),("Full A",16,20),("Duo",20,24),("Full B",24,29.77)],
 9:[("Duo",0,12),("Full B",12,16),("Duo",16,21),("Full B",21,29),("Duo",29,33),("Full B",33,40.4)],
 10:[("Duo",0,6),("Full B",6,15),("Duo",15,26),("Full B",26,30),("Duo",30,44.43)],
 11:[("Duo",0,8),("Full B",8,12),("Duo",12,22),("Full B",22,28.03)],
 12:[("Duo",0,14),("Full B",14,15.5),("Duo",15.5,29.1),("Full B",29.1,30.07)],
 13:[("Duo",0,15),("Full B",15,18),("Duo",18,24),("Full B",24,39.57)],
 14:[("Duo",0,8),("Full B",8,15),("Duo",15,29.93)],
}

def label(number,t):
    for layout,start,end in INTERVALS[number]:
        if start<=t<end:return layout
    return "Duo"

def merge(rows):
    result=[]
    for row in rows:
        if result and result[-1]["layout"]==row["layout"] and abs(result[-1]["end"]-row["start"])<.51:
            result[-1]["end"]=row["end"]
        else:result.append(dict(row))
    return result

def main():
    inventory=read_json(ROOT/"reports/duo_style/inventory.json")["references"]
    refs=[]; unique=[]; hashes=set()
    for ref in inventory:
        if ref["sha256"] in hashes:continue
        hashes.add(ref["sha256"]);unique.append(ref)
        number=int(ref["id"].split("_")[-1]); count=ref["frame_count"]
        samples=[{"t":round(i*.5,3),"layout":label(number,i*.5),"confidence":"approximate visual label"} for i in range(count)]
        refs.append({"id":ref["id"],"source":ref["path"],"duration":ref["duration"],"samples":samples,"segments":merge([{"start":s,"end":min(e,ref["duration"]),"layout":l,"confidence":"approximate visual label"} for l,s,e in INTERVALS[number]]),"duplicate_ids":[r["id"] for r in inventory if r["sha256"]==ref["sha256"] and r["id"]!=ref["id"]]})
    durations={name:[] for name in ("Duo","Full A","Full B")};switches=[]
    for ref in refs:
        prior=None
        for segment in ref["segments"]:
            durations[segment["layout"]].append(segment["end"]-segment["start"])
            if prior and prior["layout"]!=segment["layout"]:switches.append(segment["start"]-prior["start"] if False else .5)
            prior=segment
    stats={}
    for name,values in durations.items():
        stats[name]={"count":len(values),"shortest_s":round(min(values),2) if values else None,"longest_s":round(max(values),2) if values else None,"average_s":round(sum(values)/len(values),2) if values else None}
    timeline={"schema_version":5,"method":"0.5s decoded samples, visual study labels; boundaries approximate","references":refs,"stats":stats,"switch_count":len(switches),"distinct_edits":len(refs),"duplicate_files":["reference_7 duplicates reference_6"]}
    atomic_write_json(ROOT/"reports/duo_style/timeline.json",timeline)
    # A small readable timeline picture, not a source replacement.
    image=Image.new("RGB",(1200,len(refs)*74+40),"white");draw=ImageDraw.Draw(image)
    colors={"Duo":"#4dd0e2","Full A":"#b4f83d","Full B":"#ffbd66"}
    for i,ref in enumerate(refs):
        y=24+i*74;draw.text((8,y+7),ref["id"],fill="black")
        x=120;scale=1020/ref["duration"]
        for segment in ref["segments"]:
            w=max(2,(segment["end"]-segment["start"])*scale);draw.rectangle((x,y,x+w,y+24),fill=colors[segment["layout"]]);draw.text((x+2,y+6),segment["layout"],fill="black");x+=w
        draw.text((120,y+35),f"0–{ref['duration']:.1f}s · approximate visual labels",fill="#555")
    image.save(ROOT/"reports/duo_style/timeline.jpg",quality=92)
    print(json.dumps({"distinct_edits":len(refs),"stats":stats,"switch_count":len(switches)},indent=2))

if __name__=="__main__":main()
