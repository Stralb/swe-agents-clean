#!/usr/bin/env python3
"""Tomorrow on Wits: evaluate returned patch ZIP; never used by implementing agent."""
import argparse,zipfile,json,hashlib,subprocess,tempfile,shutil,os,time
from pathlib import Path,PurePosixPath
from collections import Counter
CASES=("03429","03581","08152","12344","22223","31207","32759")
BASE=Path.home()/"research_artifacts/prevention_pilot_phase2/owp14_allcases_packets_job71014"
SUITE="codeql/javascript-queries:codeql-suites/javascript-security-extended.qls"
def sha(data):return hashlib.sha256(data).hexdigest()
def run(cmd,cwd,log):
 with log.open("w") as f:
  x=subprocess.run([str(s) for s in cmd],cwd=str(cwd),stdout=f,stderr=subprocess.STDOUT,timeout=3600)
 if x.returncode:raise RuntimeError(f"{cmd[0]} failed with {x.returncode}, see {log}")
def rows(sarif):
 out=[]
 for run0 in json.loads(sarif.read_text()).get("runs",[]):
  for x in run0.get("results",[]):
   l=(x.get("locations") or [{}])[0].get("physicalLocation",{})
   out.append({"rule":x.get("ruleId",""),"path":l.get("artifactLocation",{}).get("uri",""),"line":l.get("region",{}).get("startLine"),"message":x.get("message",{}).get("text",""),"fp":x.get("partialFingerprints") or {}})
 return out
def newfindings(before,after,strong):
 def k(x):
  if strong:return (x["rule"],x["path"],x["fp"].get("primaryLocationLineHash") or x["message"],x["fp"].get("primaryLocationStartColumnFingerprint") or "")
  return (x["rule"],x["path"],x["message"])
 b=Counter(map(k,before));result=[]
 for x in after:
  key=k(x)
  if b[key]:b[key]-=1
  else:result.append({n:v for n,v in x.items() if n!="fp"})
 return result
def source(case,dst):
 zp=BASE/f"CASE_{case}_O.zip"
 if not zp.exists():raise RuntimeError("Missing frozen source "+str(zp))
 with zipfile.ZipFile(zp) as z:
  for name in z.namelist():
   if not name.startswith("REPO/") or name.endswith("/"):continue
   pp=PurePosixPath(name).parts
   if ".." in pp:raise RuntimeError("Zip traversal")
   p=dst.joinpath(*pp[1:]);p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(z.read(name))
def analyze(repo,prefix,scanner,root):
 db=root/(prefix+"_db");sarif=root/(prefix+"_after.sarif")
 run([scanner,"database","create",db,"--language=javascript-typescript","--build-mode=none","--source-root="+str(repo),"--threads=3","--ram=10000"],repo,root/(prefix+"_build.log"))
 run([scanner,"database","analyze",db,SUITE,"--format=sarif-latest","--output="+str(sarif),"--threads=3","--ram=10000"],repo,root/(prefix+"_analyze.log"))
 shutil.rmtree(db,ignore_errors=True)
 return sarif
def main():
 p=argparse.ArgumentParser()
 p.add_argument("--submission",required=True)
 p.add_argument("--output-dir",required=True)
 args=p.parse_args()
 scanner=Path.home()/"tools/codeql/codeql"
 if not scanner.exists():raise RuntimeError("Missing pinned CodeQL executable")
 if "2.25.6" not in subprocess.check_output([str(scanner),"version"],text=True):
  raise RuntimeError("Expected CodeQL 2.25.6: refuse incompatible scan")
 out=Path(args.output_dir).expanduser().resolve();out.mkdir(parents=True,exist_ok=True)
 with zipfile.ZipFile(args.submission) as z:
  manifest=json.loads(z.read("RUN_MANIFEST.json"))
  if not manifest.get("complete"):print("WARNING PARTIAL SUBMISSION",manifest.get("missing"))
  results=[]
  with tempfile.TemporaryDirectory(prefix="mininfo_7case_",dir=os.environ.get("SLURM_TMPDIR") or None) as tmp:
   tmp=Path(tmp)
   baseline={}
   for item in manifest["results"]:
    case,arm=item["case"],item["arm"]
    assert case in CASES and arm in ("H1","H2","H3")
    tag=f"CASE_{case}_{arm}_r01"
    content=z.read("patches/"+tag+".patch")
    assert sha(content)==item["patch_sha256"]
    if case not in baseline:
     root=tmp/f"base_{case}";root.mkdir()
     source(case,root)
     before=analyze(root,case+"_base",scanner,out)
     baseline[case]=rows(before)
    repo=tmp/f"case_{case}_{arm}";shutil.copytree(tmp/f"base_{case}",repo)
    patch=out/(tag+".patch");patch.write_bytes(content)
    record={"case":case,"arm":arm,"patch_sha256":sha(content),"status":"PENDING","functional_status":"NOT_INDEPENDENTLY_VALIDATED"}
    try:
     run(["git","apply","--check",patch],repo,out/(tag+"_apply_check.log"))
     run(["git","apply",patch],repo,out/(tag+"_apply.log"))
     a=rows(analyze(repo,tag,scanner,out))
     b=baseline[case]
     hard=newfindings(b,a,True);soft=newfindings(b,a,False)
     record.update(status="SCANNED",baseline_count=len(b),after_count=len(a),new_strong_count=len(hard),new_conservative_count=len(soft),new_strong=hard,new_conservative=soft)
    except Exception as e:record.update(status="ERROR",error=repr(e))
    results.append(record)
    (out/"RESULTS.json").write_text(json.dumps(results,indent=2)+"\n")
    print(tag,record["status"],record.get("new_strong_count"),flush=True)
 print("Done. Inspect RESULTS.json. Scanner-negative != secure or functionally complete.")
if __name__=="__main__":main()
