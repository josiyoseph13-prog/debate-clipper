"""Round-trip the actual OTIO library in a supported optional Python profile."""
from pathlib import Path
import sys
import tempfile
import xml.etree.ElementTree as ET
import opentimelineio as otio

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from dc.core.io import atomic_write_json
from dc.exports import write_interop


def main():
    results=[]
    real=ROOT/"exports"/"c_3c6c100b3289"/"timeline.otio"
    parsed=otio.adapters.read_from_file(str(real))
    serialized=otio.adapters.write_to_string(parsed,adapter_name="otio_json")
    again=otio.adapters.read_from_string(serialized,adapter_name="otio_json")
    results.append({"kind":"real_export","path":str(real.relative_to(ROOT)),"duration_s":parsed.duration().to_seconds(),"roundtrip_duration_s":again.duration().to_seconds(),"passed":parsed.duration()==again.duration()})
    with tempfile.TemporaryDirectory() as folder:
        root=Path(folder)
        for rate in (25,30):
            plan={"source":{"path":str(root/"a video.mp4"),"width":1920,"height":1080},"trim":{"start":2,"end":10,"duration":4},"candidate_id":"c_nle","frame_rate":{"target_cfr":rate},"source_spans":[{"start":2,"end":4,"output_start":0},{"start":8,"end":10,"output_start":2}]}
            write_interop(root,plan)
            timeline=otio.adapters.read_from_file(str(root/"timeline.otio"))
            clips=list(timeline.tracks[0])
            fcpx=ET.parse(root/"timeline.fcpxml")
            ranges=[clip.source_range.start_time.to_seconds() for clip in clips]
            edl=(root/"timeline.edl").read_text()
            passed=abs(timeline.duration().to_seconds()-4)<=1/rate and ranges==[2,8] and len(fcpx.findall(".//asset-clip"))==2 and "00:00:08:00" in edl
            results.append({"kind":"edited_fixture","rate":rate,"duration_s":timeline.duration().to_seconds(),"source_start_seconds":ranges,"fcpxml_structure_parsed":True,"edl_source_timecode_checked":True,"passed":passed})
    report={"schema_version":5,"test_id":"T-32","command":"python tools/measure_nle.py","python":sys.version,"opentimelineio_version":otio.__version__,"checks":results,"otio_passed":all(row["passed"] for row in results),"fcpxml_dtd_validated":False,"nle_application_import_verified":False}
    atomic_write_json(ROOT/"reports"/"verification_v5"/"nle.json",report)
    print(report)


if __name__=="__main__":main()
