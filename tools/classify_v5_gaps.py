"""Carry every explicitly audited open traceability item into A/B/C work."""
from pathlib import Path
import re
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from dc.core.hashing import file_hash
from dc.core.io import atomic_write_json,atomic_write_bytes


def main():
    matrix=ROOT/"reports"/"requirements_traceability.md"
    items=[]
    section=""
    for line in matrix.read_text(encoding="utf-8").splitlines():
        if line.startswith("## "):section=line[3:]
        if not line.startswith("| "):continue
        parts=[part.strip() for part in line.strip("|").split("|")]
        if len(parts)!=3 or parts[0] in {"Section","ID","---"}:continue
        requirement,status,remaining=parts
        matches=list(re.finditer(r"\[([ABC])\]\s*(.*?)(?=;\s*\[[ABC]\]|$)",remaining))
        if not matches:
            if section.startswith("T-01") and status.startswith("passed"):continue
            if remaining=="—":continue
            raise ValueError(f"Open item {requirement} needs an explicit audited A/B/C tag")
        for index,match in enumerate(matches,1):
            items.append({"id":f"{requirement}.{index}","requirement":requirement,"item":match[2].strip(),"group":match[1],"state":"open","origin":section})
    report={"schema_version":5,"source":str(matrix.relative_to(ROOT)),"source_sha256":file_hash(matrix),"classification":"Explicit manually audited matrix tags; no keyword inference","categories":{"A":"Engineering/automated evidence the agent can finish","B":"Files, rights, answers, account/hardware or human action the user must provide","C":"A quality/accuracy result cannot be proven yet"},"items":items,"engineering_is_not_external":True,"all_A_finished":not any(item["group"]=="A" for item in items)}
    atomic_write_json(ROOT/"reports"/"open_gaps_ABC.json",report)
    lines=["# Open V5 work — A / B / C","","Source: `requirements_traceability.md`, whose hash is in `open_gaps_ABC.json`.","Every explicit open [A]/[B]/[C] tag is retained. Classification is manually audited, not guessed from keywords. Related requirements may cite the same work. Inputs do not prove the accuracy gate they unlock.","","- **A:** I can finish the engineering or automated check.","- **B:** You must supply a file, answer, right, account action, or human review.","- **C:** A quality/accuracy result cannot be proven yet.","","Native programs/setup/render/Studio HTTP/ASR recovery/export recovery now run. Actual human use is B. Supplied logo/reference/golden files are available; genuine labels are not. Optional stack engineering remains A.","","**Group A remains active. This list is not project completion.**"]
    for group in "ABC":
        rows=[item for item in items if item["group"]==group]
        lines.extend(["",f"## Group {group}","","| V5 item | Open work / gate |","|---|---|"])
        lines.extend(f"| {item['id']} | {item['item']} |" for item in rows)
    atomic_write_bytes(ROOT/"reports"/"open_gaps_ABC.md",("\n".join(lines)+"\n").encode("utf-8"))
    print({group:sum(item["group"]==group for item in items) for group in "ABC"})


if __name__=="__main__":main()
