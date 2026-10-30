"""T-23/T-24 path, symlink, secret and unsafe-source audit."""
from __future__ import annotations

import json
import re
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from dc.core.hashing import file_hash
from dc.core.io import atomic_write_json
from dc.core.security import safe_child,validate_id


def main():
    findings=[]
    checked=[]
    for base_name in ("work","exports","input","assets"):
        base=ROOT/base_name
        if not base.exists():continue
        for path in base.rglob("*"):
            checked.append(str(path.relative_to(ROOT)))
            if path.is_symlink():
                try:
                    if not path.resolve().is_relative_to(base.resolve()):findings.append({"kind":"symlink_escape","path":str(path.relative_to(ROOT)),"target":str(path.resolve())})
                except OSError as exc:findings.append({"kind":"broken_symlink","path":str(path.relative_to(ROOT)),"error":str(exc)})
    for value in ("../secret","..\\secret","C:\\secret","\\\\server\\share","CON","job_ok"):
        try:validate_id(value)
        except ValueError:continue
        if value!="job_ok":findings.append({"kind":"unsafe_id_accepted","value":value})
    try:
        with (ROOT/"work"/"security_audit_probe").open("w",encoding="utf-8") as handle:handle.write("probe")
        safe_child(ROOT/"work","../escape")
        findings.append({"kind":"path_traversal_accepted"})
    except ValueError:pass
    finally:(ROOT/"work"/"security_audit_probe").unlink(missing_ok=True)
    source_patterns={"shell_true":r"shell\s*=\s*True","secret_assignment":r"(?i)(api[_-]?key|secret|password)\s*=\s*['\"][^'\"]{8,}['\"]"}
    source_findings=[]
    for path in (ROOT/"dc").rglob("*"):
        if not path.is_file() or path.suffix not in {".py",".js",".html"}:continue
        text=path.read_text(encoding="utf-8",errors="replace")
        for kind,pattern in source_patterns.items():
            for line_no,line in enumerate(text.splitlines(),1):
                if re.search(pattern,line):source_findings.append({"kind":kind,"path":str(path.relative_to(ROOT)),"line":line_no})
    findings.extend(source_findings)
    result={"schema_version":5,"test_id":"T-23/T-24 security audit","command":[sys.executable,*sys.argv],"checked_paths":len(checked),"source_findings":source_findings,"findings":findings,"passed":not findings,"sha256":file_hash(ROOT/"dc/core/security.py")}
    atomic_write_json(ROOT/"reports"/"current_checks"/"security_audit.json",result)
    print(json.dumps(result,indent=2))
    return 0 if result["passed"] else 1


if __name__=="__main__":raise SystemExit(main())
