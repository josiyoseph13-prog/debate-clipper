"""T-32 actual libxml2 DTD validation; explicit schema fetch, no app-import claim."""
from __future__ import annotations
import argparse
import ctypes
import ctypes.util
import json
from pathlib import Path
import re
import sys
from urllib.request import urlopen
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from dc.core.hashing import file_hash
from dc.core.io import atomic_write_json,atomic_write_bytes,read_json
from dc.exports import write_interop

URL="https://developer.apple.com/documentation/professional-video-applications/document-type-definition.md"


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--fetch-schema",action="store_true",help="Explicitly retrieve Apple's published1.10DTD for local verification")
    args=parser.parse_args()
    work=ROOT/"work"/"job_fcpxml_acceptance"
    work.mkdir(parents=True,exist_ok=True)
    schema=work/"FCPXMLv1.10.dtd"
    if args.fetch_schema:
        with urlopen(URL,timeout=30) as response:markdown=response.read(1_000_000).decode("utf-8")
        match=re.search(r"```swift\n(.*?)\n```",markdown,re.S)
        if not match or '<!ATTLIST fcpxml version CDATA #FIXED "1.10">' not in match[1]:raise ValueError("Official page has no expected1.10DTD")
        atomic_write_bytes(work/"apple_dtd_source.md",markdown.encode("utf-8"))
        atomic_write_bytes(schema,(match[1]+"\n").encode("utf-8"))
        atomic_write_json(work/"schema_source.json",{"schema_version":5,"url":URL,"schema_sha256":file_hash(schema),"source_sha256":file_hash(work/"apple_dtd_source.md"),"notice":"Apple Inc. All rights reserved; downloaded to owned work for local validation, not a permissively licensed bundled product asset"})
    provenance=read_json(work/"schema_source.json",{}) or {}
    if not schema.is_file() or provenance.get("schema_sha256")!=file_hash(schema):raise ValueError("Need the recorded official schema: run with --fetch-schema")
    library_name=ctypes.util.find_library("xml2")
    if not library_name:raise RuntimeError("System libxml2 is not available; DTD validation cannot be claimed")
    library=ctypes.CDLL(library_name)
    for name,arguments,result in (("xmlParseDTD",[ctypes.c_char_p,ctypes.c_char_p],ctypes.c_void_p),("xmlReadFile",[ctypes.c_char_p,ctypes.c_char_p,ctypes.c_int],ctypes.c_void_p),("xmlNewValidCtxt",[],ctypes.c_void_p),("xmlValidateDtd",[ctypes.c_void_p,ctypes.c_void_p,ctypes.c_void_p],ctypes.c_int),("xmlFreeValidCtxt",[ctypes.c_void_p],None),("xmlFreeDoc",[ctypes.c_void_p],None),("xmlFreeDtd",[ctypes.c_void_p],None)):
        function=getattr(library,name);function.argtypes=arguments;function.restype=result
    dtd=library.xmlParseDTD(None,str(schema).encode("utf-8"))
    if not dtd:raise RuntimeError("libxml2 could not parse the complete official DTD")
    def validate(path):
        # NONET blocks network resolution; generated fixtures have no DOCTYPE.
        document=library.xmlReadFile(str(path).encode("utf-8"),None,2048)
        context=library.xmlNewValidCtxt()
        try:return bool(document and context and library.xmlValidateDtd(context,document,dtd)==1)
        finally:
            if document:library.xmlFreeDoc(document)
            if context:library.xmlFreeValidCtxt(context)
    rows=[]
    try:
        for path in (ROOT/"exports"/"c_3c6c100b3289"/"timeline.fcpxml",):
            rows.append({"kind":"recorded real export","path":str(path.relative_to(ROOT)),"sha256":file_hash(path),"valid":validate(path)})
        for rate in (25,30):
            folder=work/f"rate_{rate}"
            folder.mkdir(exist_ok=True)
            plan={"candidate_id":"c_xml","source":{"path":str(ROOT/"input"/"xmp4EdJvPfo.mp4"),"width":1920,"height":1080},"trim":{"start":1,"end":4,"duration":2},"frame_rate":{"target_cfr":rate},"source_spans":[{"start":1,"end":2,"output_start":0},{"start":3,"end":4,"output_start":1}],"edits":[{"start":2,"end":3}]}
            write_interop(folder,plan)
            path=folder/"timeline.fcpxml"
            rows.append({"kind":"two source spans","rate":rate,"path":str(path.relative_to(ROOT)),"sha256":file_hash(path),"valid":validate(path)})
        tree=ET.parse(work/"rate_30"/"timeline.fcpxml")
        del tree.find(".//asset-clip").attrib["ref"]
        negative=work/"missing_required_ref.fcpxml"
        tree.write(negative,encoding="utf-8")
        rejected=not validate(negative)
    finally:library.xmlFreeDtd(dtd)
    report={"schema_version":5,"test_id":"T-32 FCPXML DTD component","command":[sys.executable,*sys.argv],"validator":"Actual system libxml2.xmlValidateDtd","library":library_name,"library_version":ctypes.c_char_p.in_dll(library,"xmlParserVersion").value.decode(),"schema":provenance,"checks":rows,"negative_missing_required_ref_rejected":rejected,"passed":all(row["valid"] for row in rows) and rejected,"scope":"DTD validates structure/IDs/required attributes, not actual Resolve/Premiere/CapCut/Final Cut import or semantic timeline fidelity"}
    atomic_write_json(ROOT/"reports"/"current_checks"/"fcpxml.json",report)
    print(json.dumps(report,indent=2))
    return 0 if report["passed"] else 1


if __name__=="__main__":raise SystemExit(main())
