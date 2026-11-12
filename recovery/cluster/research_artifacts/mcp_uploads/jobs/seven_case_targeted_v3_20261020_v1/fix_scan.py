#!/usr/bin/env python3
"""Independent targeted corrective variants based on scanned P1 implementations."""
import base64,csv,hashlib,importlib.util,io,json,os,re,shutil,subprocess,sys,zipfile
from pathlib import Path
root=Path.home()/"research_artifacts"
master_archive=root/"prevention_pilot_phase2/seven_case_delivery_20261020/SEVEN_CASES_ALL_7_FROZEN_REPOSITORIES.zip"
prior=root/"prevention_pilot_phase2/seven_case_scans_20261020"
outroot=root/"prevention_pilot_phase2/seven_case_targeted_v3_20261020"
helper=root/"mcp_uploads/jobs/seven_case_new_scans_20261020_v1/scan.py"
spec=importlib.util.spec_from_file_location("old_scan_helper",helper)
old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)
ids={"03429","08152","12344","31207"}
def sha(b):return hashlib.sha256(b).hexdigest()
def run(cmd,cwd=None,timeout=240):
  p=subprocess.run(cmd,cwd=cwd,encoding="utf8",errors="replace",stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=timeout)
  return {"cmd":cmd,"exit":p.returncode,"output":p.stdout[-5000:]}
def change(source,needle,rep):
  count=source.count(needle)
  if count!=1:raise RuntimeError("expected exactly one occurrence but got "+str(count)+" of "+needle[:70])
  return source.replace(needle,rep,1)
def fix(cid,repo):
  outputs={}
  def edit(relative,fn):
    f=repo/relative
    before=f.read_text()
    after=fn(before)
    assert before!=after,relative
    f.write_text(after)
    outputs[relative]={"old_sha256":sha(before.encode()),"new_sha256":sha(after.encode())}
  if cid=="03429":
    def patch(s):
      return change(s,"source = await fs.open(filePath, fileConstants.O_RDONLY | (fileConstants.O_NOFOLLOW ?? 0));",
        "source = await fs.open(path.resolve(filePath), fileConstants.O_RDONLY | (fileConstants.O_NOFOLLOW ?? 0));")
    edit("src/core/FileSystemUtils.ts",patch)
    def fix_fixture(s):
      s=change(s,"  const projectRoot = '/tmp/test-project';","  let projectRoot: string;")
      s=change(s,"    await fs.mkdir(projectRoot, { recursive: true });","    projectRoot = await fs.mkdtemp(path.join(os.tmpdir(), 'ruler-crush-test-'));")
      return s
    edit("tests/unit/agents/CrushAgent.test.ts",fix_fixture)
  elif cid=="08152":
    edit("src/telegram/voice.test.ts",lambda s:change(s,"url.includes('api.telegram.org')","new URL(url).hostname === 'api.telegram.org'"))
  elif cid=="31207":
    edit("ai/services/fleet/composedFleetServer.mjs",lambda s:change(s,"app.use(cors({origin: '*'}));",
      "app.use(cors({origin: false})); // Fleet is accessed through same-origin ingress; never allow wildcard CORS."))
  elif cid=="12344":
    def edit_byok(s):
      marker="function isStoredProfile(value: unknown): value is StoredProfile {"
      leaf="""function canonicalCredentialProfileId(profileId: string): string {
  // Preserve existing profile filenames while rejecting traversal and alternate path spellings.
  assertProfileId(profileId);
  const leaf = path.basename(profileId);
  if (leaf !== profileId || leaf === '.' || leaf === '..') {
    throw new Error('Invalid BYOK credential filename.');
  }
  return leaf;
}

"""
      s=change(s,marker,leaf+marker)
      start=s.index("class WindowsDpapiSecretBackend implements ByokSecretBackend")
      end=s.index("async function rejectSymlink(",start)
      chunk=s[start:end]
      # Keep the on-disk format stable, but derive every filename from the canonical checked leaf.
      tok=chr(36)+chr(123)+"profileId}"
      repl=chr(36)+chr(123)+"canonicalCredentialProfileId(profileId)}"
      n=chunk.count(tok)
      if n!=3:raise RuntimeError("Expected three profile-id path interpolations, got "+str(n))
      chunk=chunk.replace(tok,repl)
      return s[:start]+chunk+s[end:]
    edit("apps/daemon/src/byok/credential-service.ts",edit_byok)
  return outputs
def main(cid):
 if cid not in ids:raise RuntimeError("wrong case")
 out=outroot/cid;out.mkdir(parents=True,exist_ok=True)
 original_result=json.loads((prior/cid/"RESULT.json").read_text())
 archive_name="CASE_"+cid+"_O.zip"
 with zipfile.ZipFile(master_archive) as outer:raw=outer.read("CASE_INPUTS/"+archive_name)
 assert sha(raw)==old.SOURCE_SHA[cid],"source hash mismatch"
 original_patch=(prior/cid/("CASE_"+cid+"_P1_r01.patch")).read_bytes()
 assert sha(original_patch)==old.SHAS[cid],"patch hash mismatch"
 work=Path(os.environ.get("SLURM_TMPDIR",str(out/"work")))/("targeted_"+cid)
 work.mkdir(parents=True,exist_ok=True)
 snap=work/"original.zip";snap.write_bytes(raw)
 def unpack(p):
  p.mkdir(parents=True,exist_ok=True)
  with zipfile.ZipFile(snap) as z:z.extractall(p)
  repo=p/"REPO"
  assert repo.is_dir()
  return repo
 original=unpack(work/"baseline")
 implementation=unpack(work/"implementation")
 proc=lambda args,cwd,log:old.proc(args,log,cwd)
 proc(["git","init","-q"],implementation,out/"git_init.log")
 proc(["git","config","user.email","research@example.invalid"],implementation,out/"git_email.log")
 proc(["git","config","user.name","Research Evaluator"],implementation,out/"git_name.log")
 proc(["git","add","-A"],implementation,out/"git_add.log")
 proc(["git","commit","-qm","Frozen source baseline"],implementation,out/"git_commit.log")
 proc(["git","apply","--check",str(prior/cid/("CASE_"+cid+"_P1_r01.patch"))],implementation,out/"old_patch_check.log")
 proc(["git","apply",str(prior/cid/("CASE_"+cid+"_P1_r01.patch"))],implementation,out/"old_patch_apply.log")
 modifications=fix(cid,implementation)
 # Make new files tracked as intent-to-add; export full modified implementation against untouched O.
 proc(["git","add","-N","-A"],implementation,out/"git_add_intent.log")
 x=run(["git","diff","--binary","HEAD"],implementation,timeout=180)
 if x["exit"]:raise RuntimeError("git diff failed")
 # run() caps stdout; capture patch WITHOUT a truncation.
 patch=out/("CASE_"+cid+"_TARGETED_V3.patch")
 with patch.open("wb") as f:subprocess.run(["git","diff","--binary","HEAD"],cwd=implementation,stdout=f,check=True)
 assert patch.stat().st_size>100
 proc(["git","apply","--check",str(patch)],original,out/"new_patch_check.log")
 tests=[]
 node=shutil.which("node")
 if node:
  commands={
  "03429":[["node","--test","tests/file-system-security-offline.test.cjs"]],
  "08152":[["node","--test","tests/telegram-voice-offline.test.mjs"]],
  "12344":[["node","--test","tests/byok-windows-offline.test.cjs"]],
  "31207":[["node","--check","ai/services/fleet/composedFleetServer.mjs"],["node","--test","ai/scripts/diagnostics/fleetHealthcheck.test.mjs"]]}
  for cmd in commands[cid]:
   try:tests.append(run(cmd,implementation,timeout=100))
   except Exception as ex:tests.append({"cmd":cmd,"error":repr(ex)})
 version=subprocess.check_output(["codeql","version"],text=True)
 assert "2.25.6" in version
 db=work/"db"
 proc(["codeql","database","create",str(db),"--language=javascript-typescript",("--source-root="+str(implementation)),"--build-mode=none","--threads=4","--ram=18000"],implementation,out/"db_create.log")
 sarif=out/"after.sarif"
 proc(["codeql","database","analyze",str(db),old.SUITE,"--format=sarif-latest",("--output="+str(sarif)),"--threads=4","--ram=18000"],implementation,out/"analyze.log")
 before=old.sarif_entries(prior/cid/"before.sarif")
 after=old.sarif_entries(sarif)
 new_fp=old.difference(before,after,old.full)
 new_cons=old.difference(before,after,old.norm)
 result={"case":cid,"original_patch_sha256":old.SHAS[cid],"new_patch_sha256":sha(patch.read_bytes()),"old_new_alerts":original_result["new_strong_count"],"new_strong_count":len(new_fp),"new_conservative_count":len(new_cons),"before_count":len(before),"after_count":len(after),"new_strong":new_fp,"new_conservative":new_cons,"modifications":modifications,"tests":tests,"scanner_negative_both":not(new_fp or new_cons),"functionality":"NOT VERIFIED BY SYSTEM-LEVEL TESTS","notes":"Retrospective researcher-authored targeted repair; not a valid prompt-arm / minimum-information trial"}
 (out/"RESULT.json").write_text(json.dumps(result,indent=2)+"\n")
 print(json.dumps({"case":cid,"before":len(before),"after":len(after),"new_fingerprint":len(new_fp),"new_conservative":len(new_cons),"tests":[t.get("exit") for t in tests]},sort_keys=True),flush=True)
if __name__=="__main__":
 cid=sys.argv[1]
 try:main(cid)
 except Exception as e:
  o=outroot/cid;o.mkdir(parents=True,exist_ok=True)
  (o/"ERROR.txt").write_text(repr(e)+"\n")
  raise
