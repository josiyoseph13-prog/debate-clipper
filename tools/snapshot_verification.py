"""Keep current real-footage evidence outside retention-managed work folders."""
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from dc.core.io import atomic_copy,atomic_write_json,read_json
from dc.core.hashing import file_hash


def main():
    destination=ROOT/"reports"/"verification_v5"
    job=ROOT/"work"/"job_verify_v5"
    for name in ("export_report.json","source.json","render_artifacts.json","renderer_config.json","framing.json"):
        atomic_copy(job/name,destination/("current_"+name))
    atomic_copy(ROOT/"config"/"caption_calibration.json",destination/"caption_calibration.json")
    atomic_copy(ROOT/"reports"/"bench_render.json",destination/"bench_render.json")
    export=ROOT/"exports"/"c_3c6c100b3289"
    files={path.name:file_hash(path) for path in export.iterdir() if path.is_file()}
    atomic_write_json(destination/"export_hashes.json",{"schema_version":5,"export_dir":str(export),"hashes":files,"provenance":read_json(export/"provenance.json"),"publish_gate":read_json(export/"publish_dry_run.json")})
    print({"status":"snapshotted","export_files":len(files)})


if __name__=="__main__":main()
