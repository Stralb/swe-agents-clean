#!/usr/bin/env python3
from pathlib import Path,PurePosixPath
import sys,json,hashlib,zipfile,shutil,subprocess,csv,io
ROOT=Path(__file__).resolve().parent
PLAN=json.loads((ROOT/"EXPERIMENT_PLAN.json").read_text())
CASES=PLAN["case_order"]; ARMS=("H1","H2","H3")
def sha(path):
 h=hashlib.sha256()
 with open(path,"rb") as f:
  for x in iter(lambda:f.read(1048576),b""):h.update(x)
 return h.hexdigest()
def run(args,cwd):
 p=subprocess.run(args,cwd=cwd,capture_output=True)
 if p.returncode:raise RuntimeError(str(args)+"\n"+p.stderr.decode(errors="replace")[-1300:])
 return p.stdout
def location(c,a):
 if c not in CASES or a not in ARMS:raise SystemExit("Bad case/arm")
 return ROOT/"WORKSPACES"/(c+"_"+a)
def prepare(c,a):
 dst=location(c,a)
 if dst.exists():raise SystemExit("Refusing overwrite "+str(dst))
 archive=ROOT/"FROZEN_SOURCES"/("CASE_"+c+"_O.zip")
 assert sha(archive)==PLAN["cases"][c]["source_sha256"]
 with zipfile.ZipFile(archive) as z:
  assert z.testzip() is None
  orig=z.read("ISSUE.md")
  assert hashlib.sha256(orig).hexdigest()==PLAN["cases"][c]["issue_sha256"]
  dst.mkdir(parents=True)
  for n in z.namelist():
   if not n.startswith("REPO/") or n.endswith("/"):continue
   parts=PurePosixPath(n).parts
   assert parts[0]=="REPO" and ".." not in parts
   path=dst.joinpath("BASE",*parts[1:]);path.parent.mkdir(parents=True,exist_ok=True)
   info=z.getinfo(n);data=z.read(n)
   if ((info.external_attr>>16)&0o170000)==0o120000:
    link=data.decode();assert not Path(link).is_absolute() and ".." not in Path(link).parts
    path.symlink_to(link)
   else:path.write_bytes(data)
 (dst/"ORIGINAL_ISSUE.md").write_bytes(orig)
 addition=PLAN["cases"][c]["additions"][a]
 (dst/"ADDITIONAL_INFO.md").write_text(addition+"\n")
 (dst/"ISSUE_FOR_AGENT.md").write_bytes(orig.rstrip(b"\n")+b"\n\n"+addition.encode()+b"\n")
 shutil.copytree(dst/"BASE",dst/"WORK",symlinks=True)
 run(["git","init","-q"],dst/"WORK")
 run(["git","add","-A","-f"],dst/"WORK")
 run(["git","-c","user.name=Frozen","-c","user.email=frozen@invalid.example","-c","commit.gpgsign=false","commit","-q","-m","frozen-baseline"],dst/"WORK")
 (dst/"RUNLOG.txt").write_text("Case: "+c+"\nArm: "+a+"\nImplementation: PENDING\nTests: NOT RUN YET\nFunctional acceptance: UNVERIFIED\n")
 print("READY",c,a,dst/"ISSUE_FOR_AGENT.md",dst/"WORK")
def export(c,a):
 dst=location(c,a);w=dst/"WORK"
 assert (w/".git").exists(),"Need prepare"
 run(["git","add","-A","-f"],w)
 data=run(["git","diff","--cached","--binary","--no-ext-diff","HEAD"],w)
 assert data,"Empty patch prohibited"
 p=ROOT/"RESULTS";(p/"patches").mkdir(parents=True,exist_ok=True);(p/"logs").mkdir(exist_ok=True)
 name="CASE_"+c+"_"+a
 dest=p/"patches"/(name+".patch");dest.write_bytes(data)
 run(["git","apply","--check",str(dest)],dst/"BASE")
 (p/"logs"/(name+"_runlog.txt")).write_bytes((dst/"RUNLOG.txt").read_bytes())
 (p/"patches"/(name+"_meta.json")).write_text(json.dumps({"case":c,"arm":a,"status":"GENERATED_NOT_SCANNED","patch_sha256":sha(dest),"source_sha256":PLAN["cases"][c]["source_sha256"],"issue_sha256":PLAN["cases"][c]["issue_sha256"],"addition_sha256":PLAN["cases"][c]["addition_sha256"][a]},indent=2)+"\n")
 print("PATCH_OK",name,len(data))
def status():
 for c in CASES:
  for a in ARMS:
   f=ROOT/"RESULTS/patches"/("CASE_"+c+"_"+a+".patch")
   print(c,a,"PATCH_READY" if f.is_file() else "WORKTREE_ONLY" if location(c,a).is_dir() else "NOT_STARTED")
def finish():
 out=ROOT/"RESULTS";out.mkdir(exist_ok=True)
 rows=[]
 for c in CASES:
  for a in ARMS:
   n="CASE_"+c+"_"+a
   p=out/"patches"/(n+".patch");l=out/"logs"/(n+"_runlog.txt")
   rows.append(dict(case=c,arm=a,status="READY_UNSCANNED" if p.exists() else "MISSING",patch_filename=p.name if p.exists() else "",patch_sha256=sha(p) if p.exists() else "",patch_bytes=p.stat().st_size if p.exists() else "",runlog=l.name if l.exists() else "",frozen_source_sha256=PLAN["cases"][c]["source_sha256"],issue_sha256=PLAN["cases"][c]["issue_sha256"],added_information_sha256=PLAN["cases"][c]["addition_sha256"][a],CodeQL="NOT_RUN",functionality="UNVERIFIED"))
 b=io.StringIO();writer=csv.DictWriter(b,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
 (out/"RUN_MANIFEST.csv").write_text(b.getvalue())
 archive=ROOT/"SEVEN_CASES_ALL_PATCHES_FOR_CLUSTER.zip"
 with zipfile.ZipFile(archive,"w",compression=zipfile.ZIP_DEFLATED) as z:
  z.write(out/"RUN_MANIFEST.csv","RUN_MANIFEST.csv")
  for f in sorted(out.rglob("*")):
   if f.is_file() and f.name!="RUN_MANIFEST.csv":z.write(f,str(f.relative_to(out)))
  z.writestr("CLUSTER_SCAN_README.txt","PATCHES ARE NOT CODEQL TESTED. Each patch must be applied to its own case frozen O source and independently scanned with CodeQL 2.25.6 javascript-security-extended. Verify required functionality. Absence of CodeQL findings is not proof of security.\n")
 assert zipfile.ZipFile(archive).testzip() is None
 print("RESULT_ZIP",archive,"READY",sum(x["status"]=="READY_UNSCANNED" for x in rows),"OF",len(rows),"SHA256",sha(archive))
if __name__=="__main__":
 if len(sys.argv)==4 and sys.argv[1]=="prepare":prepare(*sys.argv[2:])
 elif len(sys.argv)==4 and sys.argv[1]=="export":export(*sys.argv[2:])
 elif len(sys.argv)==2 and sys.argv[1]=="status":status()
 elif len(sys.argv)==2 and sys.argv[1]=="finalize":finish()
 else:raise SystemExit("python ORCHESTRATE.py prepare CASE H1|H2|H3 | export CASE ARM | status | finalize")
