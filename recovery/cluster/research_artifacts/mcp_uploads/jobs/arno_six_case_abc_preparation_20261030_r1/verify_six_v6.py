#!/usr/bin/env python3
"""Verify six frozen cases and 18 staged blinded A/B/C inputs. Does not run models."""
from pathlib import Path
from zipfile import ZipFile
import io,hashlib,json,time
ROOT=Path.home()/"research_artifacts"
SRC=ROOT/"mcp_uploads/jobs/arno_v6_20261030_p1p2p3_blinded_runs_v2"
BASE=ROOT/"mcp_uploads/jobs/arno_six_case_abc_preparation_20261030_r1"
READY=BASE/"ready_initial"
MANIFEST=json.loads((SRC/"MANIFEST.json").read_text())
PACKAGING=json.loads((BASE/"PACKAGING_REPORT.json").read_text())
def sha_bytes(x):return hashlib.sha256(x).hexdigest()
def sha_file(p):
 h=hashlib.sha256()
 with p.open("rb") as f:
  for b in iter(lambda:f.read(1024*1024),b""):h.update(b)
 return h.hexdigest()
def hashes(z):
 return {n:sha_bytes(z.read(n)) for n in z.namelist() if n.startswith("REPO/") and not n.endswith("/")}
out={"cases":[],"stage1_count":0,"status":"VALIDATING","started":time.time()}
try:
 for case in [c for c in MANIFEST["cases"] if c!="22223"]:
  original=next(r for r in MANIFEST["runs"] if r["case_id"]==case and r["condition"]=="P1")
  zip_path=SRC/"run_zips"/(original["run_id"]+".zip")
  assert sha_file(zip_path)==original["sha256"]
  with ZipFile(zip_path) as z:
   assert z.testzip() is None
   original_issue=z.read("ISSUE.md")
   reference=hashes(z)
  result={"case":case,"repo_file_count":len(reference),"source_kind":original["source_kind"],"arms":[]}
  for arm in ("A","B","C"):
   rec=next(x for x in PACKAGING["packets"] if x["case"]==case and x["arm"]==arm)
   path=READY/rec["filename"]
   assert sha_file(path)==rec["sha256"],"SHA "+str(path)
   with ZipFile(path) as z:
    assert z.testzip() is None
    assert z.read("ISSUE.md")==original_issue
    assert hashes(z)==reference,"SOURCE DIFF "+case+" "+arm
    names=set(z.namelist())
    assert ("P1_PATCH.patch" in names)==(arm=="B")
    text=z.read("PROMPT.md").decode()
    assert "CodeQL warning" not in text or arm in "BC"
    assert "MAKE_STAGE2.py" in names if arm in "BC" else "MAKE_STAGE2.py" not in names
    if arm in "BC":
     with ZipFile(io.BytesIO(z.read("STAGE2_TEMPLATE.zip"))) as inner:
      assert inner.testzip() is None
      assert inner.read("ISSUE.md")==original_issue
      assert hashes(inner)==reference
      assert ("P1_PATCH.patch" in inner.namelist())==(arm=="B")
      assert "PROMPT.md" in inner.namelist()
   result["arms"].append({"arm":arm,"sha256":rec["sha256"],"bytes":path.stat().st_size,"member_count":len(names),"source_equal":True,"nested_source_equal":True if arm in "BC" else None})
   out["stage1_count"]+=1
  out["cases"].append(result)
  print("PASS",case,len(reference),flush=True)
 out["status"]="ALL_18_STAGE1_PACKETS_SOURCE_AND_BLINDING_CHECKS_PASS"
except Exception as e:
 out["status"]="FAILED";out["error"]=repr(e)
finally:
 out["finished"]=time.time()
 (BASE/"INDEPENDENT_PACKET_VERIFICATION.json").write_text(json.dumps(out,indent=2))
 print(json.dumps({"status":out["status"],"count":out["stage1_count"],"error":out.get("error")},indent=2),flush=True)
