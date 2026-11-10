#!/usr/bin/env python3
import base64,csv,hashlib,json,os,shutil,subprocess,sys,time,zipfile,zlib
from collections import Counter
from pathlib import Path
BASE=Path.home()/"research_artifacts"
RUN=BASE/"prevention_pilot_phase2/seven_case_scans_20261020"
PACK=BASE/"prevention_pilot_phase2/seven_case_delivery_20261020/SEVEN_CASES_ALL_7_FROZEN_REPOSITORIES.zip"
UPLOAD=BASE/"mcp_uploads/seven_case_20261020"
IDS=["03429","03581","08152","12344","22223","31207","32759"]
SHAS={
"03429":"26cc6ff74bbd44b2e3a545d4bd2c028996d1ad25effeb45e8924a2c76f434d12",
"03581":"e7336abf2e25dc46ca75dcd6e5c4ccadbf0241160af2cc99dcaa020b21c8b8ec",
"08152":"cdd4aa04440eb61c3df3b68367b744caf415639da957a42dd012ea40d47b62c1",
"12344":"22597ed1d728265ac5988baaec7ad9973881f54a0509dd8e41bf49db4ad1acd9",
"22223":"7a94b3b9d3e2dde4d26f126a37a49c51b9392e6cfbb90bad8d93dc3a5ad8af5e",
"31207":"bcc9a0a974edd5faad9d315db4d8d05f68bf32c1052a60fdf2946886e441518f",
"32759":"f7c086a714b4d1d4066989880e23e1ce3e75486b2c06be5b7dcb06db68c975c2"
}
SOURCE_SHA={
"03429":"a42f6b1db690ae6c5734cb7a3e66c179a62f02e3afb8fc55a389fbbbe63c04d0",
"03581":"b223cc0f9cfb477c9f1d087bffc13d32ea34d1a125761a0fe65cc1038a38ae07",
"08152":"815906a0ebc55579ea6e7a245ae767e0e26bb4e3ec7873a9aab8e6424c6926b1",
"12344":"807c7bf0cc307077242ea7417aac77e0dae7a5beefca1a17b39e8085914357b0",
"22223":"9145d68293857567e6a82eaa0a3bae6c60aaeb9a78f45a102899adba9b149031",
"31207":"2b4e958a05cfd6c6a70013656477a1ae5a1ba32fd92f3789ae0c8ff0d73546e3",
"32759":"2dce5a0132cadb85b779bcd032e81b5aadc95bfafce391e8437916fb400399f2"
}
SUITE="codeql/javascript-queries:codeql-suites/javascript-security-extended.qls"
def digest(b):return hashlib.sha256(b).hexdigest()
def proc(args,log,cwd=None):
    with open(log,"w") as f:
        p=subprocess.run(args,cwd=cwd,stdout=f,stderr=subprocess.STDOUT,text=True)
    if p.returncode:raise RuntimeError("FAILED "+str(args)+" log="+str(log))
def sarif_entries(p):
    a=json.loads(p.read_text())
    ans=[]
    for run in a.get("runs",[]):
      for r in run.get("results",[]):
        loc=(r.get("locations") or [{}])[0].get("physicalLocation") or {}
        art=loc.get("artifactLocation") or {}
        uri=str(art.get("uri","")).replace("\\","/").replace("%20"," ").lstrip("./")
        if uri.startswith("REPO/"):uri=uri[5:]
        fps=r.get("partialFingerprints") or {}
        ans.append({"rule":r.get("ruleId",""),"uri":uri,"line":(loc.get("region") or {}).get("startLine",0),"message":(r.get("message") or {}).get("text",""),"fingerprints":fps})
    return ans
def norm(e):
    return (e["rule"],e["uri"]," ".join(e["message"].lower().split()))
def full(e):
    return (e["rule"],json.dumps(e["fingerprints"],sort_keys=True)) if e["fingerprints"] else ("NO_FINGERPRINT",)+norm(e)
def difference(a,b,which):
    prior=Counter(which(v) for v in a)
    results=[]
    for v in b:
      k=which(v)
      if prior[k]:prior[k]-=1
      else:results.append(v)
    return results
def main(cid):
    assert cid in IDS
    result=RUN/cid;result.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(PACK) as outer:
      raw=outer.read(f"CASE_INPUTS/CASE_{cid}_O.zip")
    assert digest(raw)==SOURCE_SHA[cid],("source hash mismatch",cid,digest(raw))
    u=UPLOAD/f"CASE_{cid}_P1.zlib.base64.txt"
    raw_b64=u.read_text().strip()
    patch=zlib.decompress(base64.b64decode(raw_b64))
    assert digest(patch)==SHAS[cid],("patch hash mismatch",cid,digest(patch))
    patchfile=result/f"CASE_{cid}_P1_r01.patch"
    patchfile.write_bytes(patch)
    scratch=Path(os.environ.get("SLURM_TMPDIR",str(result/"scratch")))/f"seven_{cid}_{os.getpid()}"
    scratch.mkdir(parents=True,exist_ok=True)
    def make_repo(target):
      target.mkdir(parents=True,exist_ok=True)
      source_archive=scratch/"source.zip"
      source_archive.write_bytes(raw)
      with zipfile.ZipFile(source_archive) as z:
        for info in z.infolist():
          pp=Path(info.filename)
          if pp.is_absolute() or ".." in pp.parts:raise RuntimeError("unsafe ZIP path")
        z.extractall(target)
      repo=target/"REPO"
      if not repo.is_dir():raise RuntimeError("REPO not found")
      return repo
    base=make_repo(scratch/"before")
    after=make_repo(scratch/"after")
    proc(["git","apply","--check",str(patchfile)],result/"apply_check.log",cwd=after)
    proc(["git","apply",str(patchfile)],result/"apply.log",cwd=after)
    codeql=shutil.which("codeql")
    if not codeql:raise RuntimeError("codeql missing from PATH")
    v=subprocess.check_output([codeql,"version"],text=True)
    if "2.25.6" not in v:raise RuntimeError("unexpected CodeQL version: "+v)
    (result/"codeql_version.txt").write_text(v)
    found={}
    for name,repo in [("before",base),("after",after)]:
      db=scratch/(name+"_db")
      proc([codeql,"database","create",str(db),"--language=javascript-typescript",f"--source-root={repo}","--build-mode=none","--threads=4","--ram=18000"],result/(name+"_create.log"),cwd=repo)
      sarif=result/(name+".sarif")
      proc([codeql,"database","analyze",str(db),SUITE,"--format=sarif-latest",f"--output={sarif}","--threads=4","--ram=18000"],result/(name+"_analyze.log"),cwd=repo)
      found[name]=sarif_entries(sarif)
    before=found["before"];after=found["after"]
    strong=difference(before,after,full)
    conservative=difference(before,after,norm)
    report={"case":cid,"patch_sha256":SHAS[cid],"source_sha256":SOURCE_SHA[cid],"apply_check":"PASS","codeql_version":v.strip(),"suite":SUITE,"baseline_count":len(before),"patched_count":len(after),"new_strong_count":len(strong),"new_conservative_count":len(conservative),"new_strong":strong,"new_conservative":conservative,"scan_completed":True,"functionality":"UNVERIFIED: separate functional adjudication required"}
    (result/"RESULT.json").write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps({"case":cid,"baseline":len(before),"patched":len(after),"new_strong":len(strong),"new_conservative":len(conservative)},sort_keys=True),flush=True)
if __name__=="__main__":
  try:main(sys.argv[1])
  except Exception as ex:
    cid=sys.argv[1] if len(sys.argv)>1 else "unknown"
    loc=RUN/cid
    loc.mkdir(parents=True,exist_ok=True)
    (loc/"ERROR.txt").write_text(repr(ex)+"\n")
    raise
