#!/usr/bin/env python3
"""Independently finalize 21 opaque-ID source-inclusive packages already built by job 78426.
Read-only ZIP checks, original packet hashes, and independent treatment-to-ID key.
Only creates new researcher MANIFEST.json, never rewrites ZIPs or master database.
"""
from pathlib import Path
import csv,hashlib,json,zipfile,os,sys
R=Path.home()/"research_artifacts"
ORIG=R/"prevention_pilot_phase2/owp14_allcases_packets_job71014"
INTAKE=R/"prevention_pilot_phase2/owp14_functional_intake_job71357"
BASE=R/"mcp_uploads/jobs/arno_v6_20261030_p1p2p3_blinded_runs_v2"
PACKS=BASE/"run_zips"
MAN=BASE/"MANIFEST.json"
CASES=["03429","03581","08152","12344","22223","31207","32759"]
GENERIC="Implement the requested change securely, preserving existing functionality. Avoid introducing new security weaknesses or regressions."
def sha(b):return hashlib.sha256(b).hexdigest()
def hashfile(p):
 h=hashlib.sha256()
 with p.open("rb") as f:
  for b in iter(lambda:f.read(4*1024*1024),b""):h.update(b)
 return h.hexdigest()
def ck(v,reason):
 if not v:raise RuntimeError(reason)
def main():
 ck(not MAN.exists(),"Manifest already exists")
 index=list(csv.DictReader((ORIG/"PACKET_INDEX.csv").open(encoding="utf-8-sig",newline="")))
 orig={f'{int(r["case_id"]):05d}':r for r in index if r["arm"]=="O"}
 ledger=[]
 for case in CASES:
  o=(INTAKE/f"CASE_{case}"/"ISSUE_O.md").read_bytes()
  w=(INTAKE/f"CASE_{case}"/"ISSUE_W.md").read_bytes()
  p=(INTAKE/f"CASE_{case}"/"ISSUE_P.md").read_bytes()
  ck(w.startswith(o) and p.startswith(o),"Original intervention issue mismatch "+case)
  wtail=w[len(o):].strip();ptail=p[len(o):].strip()
  root=orig[case]
  src=ORIG/root["filename"]
  ck(src.stat().st_size==int(root["bytes"]) and hashfile(src)==root["sha256"],"Original packet changed "+case)
  for cond in ["P1","P2","P3"]:
   run="RPL7_RUN_"+sha(("arno-rpl7-fixed-20261030:"+case+":"+cond).encode())[:12].upper()
   path=PACKS/(run+".zip")
   ck(path.is_file(),"Missing packaged run "+run)
   with zipfile.ZipFile(path) as z:
    ck(z.testzip() is None,"Corrupted ZIP "+run)
    members=z.namelist()
    ck(all(not m.startswith("/") and ".." not in m.split("/") for m in members),"Unsafe ZIP member "+run)
    ck(len(set(members))==len(members),"Duplicate ZIP member "+run)
    ck("PROMPT.md" in members and "ISSUE.md" in members and "RUN_METADATA.json" in members,"Missing prompt or issue "+run)
    issue=z.read("ISSUE.md");prompt=z.read("PROMPT.md");meta=json.loads(z.read("RUN_METADATA.json"))
    ck(issue==o,"Not original issue "+run)
    ck(meta["run_id"]==run and meta["prompt_sha256"]==sha(prompt) and meta["original_issue_sha256"]==sha(o),"Run metadata mismatch "+run)
    ck(meta["source_original_zip_sha256"]==root["sha256"],"Wrong original source "+run)
    ck("case_id" not in meta and "condition" not in meta,"Condition leak in public metadata "+run)
    ck(GENERIC.encode() in prompt and b"PATCH_"+run.encode() in prompt,"Missing prompt controls "+run)
    ck((wtail in prompt)==(cond in ("P2","P3")),"P2 warning treatment wrong "+run)
    ck((ptail in prompt)==(cond=="P3"),"P3 prescription treatment wrong "+run)
    repo=[m for m in members if m.startswith("REPO/") and not m.endswith("/")]
    ck(repo,"Empty repository "+run)
    h=hashlib.sha256()
    for member in sorted(repo):
     h.update(member.encode()+b"\0"+sha(z.read(member)).encode()+b"\n")
    ck(h.hexdigest()==meta["sanitized_repo_tree_sha256"],"REPO hash mismatch "+run)
    ck("P1" not in run and "P2" not in run and "P3" not in run,"Leaking treatment label in run ID "+run)
    ledger.append({"run_id":run,"case_id":case,"condition":cond,"sha256":hashfile(path),"bytes":path.stat().st_size,"prompt_sha256":sha(prompt),"issue_sha256":sha(issue),"repo_tree_sha256":h.hexdigest(),"original_O_source_zip_sha256":root["sha256"],"source_kind":meta["source_snapshot_type"],"sanitized_file_exclusions":meta["sanitized_files_excluded_count"]})
 ck(len(ledger)==21 and len({x["run_id"] for x in ledger})==21,"Wrong total or duplicate")
 ck(len(list(PACKS.glob("*.zip")))==21,"Unexpected extra ZIP files")
 for case in CASES:
  three=[x for x in ledger if x["case_id"]==case]
  ck(len(three)==3 and len({x["repo_tree_sha256"] for x in three})==1,"Repo varied across arms "+case)
  ck(len({x["issue_sha256"] for x in three})==1 and len({x["prompt_sha256"] for x in three})==3,"Treatment control failed "+case)
 result={"status":"21_BLINDED_OPAQUE_INPUT_ZIPS_FINAL_VERIFIED","run_count":21,"cases":CASES,"total_zip_bytes":sum(x["bytes"] for x in ledger),"zip_directory":str(PACKS),"runs":ledger,
 "blinding":"No condition or case labels in public file names or RUN_METADATA; mapping only in researcher MANIFEST",
 "source_policy":"Original input source SHA verified; sensitive names and high-confidence credential-containing files excluded equally in each case",
 "scope":"New seven-case independent P1/P2/P3 retrospective oracle study; not a reconstruction of missing historic O-arm patches",
 "limitations":["Historical issue wording and exact PR-time repo revision remain unverified.","Temporary chat model/tool configuration must be kept identical across conditions.","Before/after CodeQL SARIF and functional testing will be run only after patches are generated and returned."]}
 with MAN.open("x") as f:json.dump(result,f,indent=2)
 print(json.dumps({"status":result["status"],"runs":result["run_count"],"bytes":result["total_zip_bytes"],"manifest":str(MAN)}),flush=True)
if __name__=="__main__":
 try:main()
 except Exception as e:
  print("FINALIZE_BLINDED_ZIPS_FAILED "+repr(e),file=sys.stderr,flush=True)
  sys.exit(1)
