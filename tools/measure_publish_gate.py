"""T-33 offline publisher stub: gates, private privacy, and redacted logging."""
from pathlib import Path
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from dc.core.config import load_config
from dc.core.io import atomic_write_json
from dc.distribute.adapters import publish


def main():
    checks=[]
    config=load_config(overrides={"distribution":{"publish":{"enabled":True}}})
    with tempfile.TemporaryDirectory() as folder:
        root=Path(folder)
        atomic_write_json(root/"metadata.json",{"title":"Fixture","description":"Fixture"})
        atomic_write_json(root/"export_report.json",{"status":"passed"})
        (root/"clip.mp4").write_bytes(b"publisher stub fixture")
        calls=[]
        def adapter(path,metadata,privacy):
            calls.append(privacy)
            return {"id":"fixture_remote_id"}
        base={"id":"c_publish_fixture","claims":[],"claim_checked":True,"integrity_flags":[]}
        for name,candidate,rights in (("unknown_rights",base,"unknown"),("unchecked_claim",{**base,"claim_checked":False,"claims":[{"text":"90%"}]},"own"),("integrity_review",{**base,"integrity_flags":[{"code":"I-2","severity":"review"}]},"own")):
            atomic_write_json(root/"candidate.json",candidate)
            atomic_write_json(root/"provenance.json",{"rights_class":rights})
            blocked=False
            try:publish(root,"youtube_shorts",config,True,False,adapter)
            except ValueError:blocked=True
            checks.append({"name":name,"passed":blocked and not calls})
        atomic_write_json(root/"candidate.json",base)
        atomic_write_json(root/"provenance.json",{"rights_class":"own"})
        result=publish(root,"youtube_shorts",config,True,False,adapter)
        checks.append({"name":"stub_receives_private","passed":calls==["private"]})
        log=(root/"publish_log.jsonl").read_text()
        checks.append({"name":"log_contains_only_scoped_upload_record","passed":"fixture_remote_id" in log and "Bearer" not in log and "access_token" not in log})
    report={"schema_version":5,"test_id":"T-33","command":"python tools/measure_publish_gate.py","mode":"offline_adapter_stub","live_upload":False,"checks":checks,"passed":all(row["passed"] for row in checks)}
    atomic_write_json(ROOT/"reports"/"verification_v5"/"publish_stub.json",report)
    print(report)
    return 0 if report["passed"] else 1


if __name__=="__main__":raise SystemExit(main())
