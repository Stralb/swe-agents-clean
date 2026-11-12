#!/usr/bin/env python3
"""Two-case issue-recipe ablation, 2x2 and two independent replicate packets."""
from pathlib import Path
import zipfile,json,hashlib,difflib,subprocess
root=Path.home()/"research_artifacts"
src=root/"prevention_pilot_phase2/owp14_allcases_packets_job71014"
out=root/"prevention_pilot_phase2/issue_recipe_two_cases_20261019"
out.mkdir(parents=True,exist_ok=False)
cases={"03429":src/"CASE_03429_O.zip","03581":src/"CASE_03581_O.zip"}
prep='''from pathlib import Path
import shutil,subprocess
p=Path(__file__).resolve().parent
a=p/"REPO"; b=p/"WORK"
if b.exists():raise RuntimeError("WORK already exists; refusing to overwrite")
shutil.copytree(a,b,symlinks=True)
def git(*argv):
 r=subprocess.run(["git","-C",str(b),*argv],capture_output=True,text=True)
 if r.returncode:raise RuntimeError("Git failed: "+" ".join(argv)+"\\n"+r.stderr)
git("init","-q")
git("add","-A","-f")
git("-c","user.name=Frozen baseline","-c","user.email=baseline@example.invalid","-c","commit.gpgsign=false","commit","-q","-m","frozen baseline")
print("Prepared",b)
'''
export='''from pathlib import Path
import subprocess
p=Path(__file__).resolve().parent
repo=p/"REPO"; work=p/"WORK"
if not work.exists():raise RuntimeError("Missing WORK. Run PREPARE_WORKTREE.py first")
def run(cmd,**kw):
 r=subprocess.run(cmd,capture_output=True,**kw)
 if r.returncode:raise RuntimeError(r.stderr)
 return r.stdout
run(["git","-C",str(work),"add","-A","-f"])
patch=run(["git","-C",str(work),"diff","--cached","--binary","--no-ext-diff","HEAD"])
if not patch:raise RuntimeError("Patch is empty")
dest=p/(p/"OUTPUT_FILENAME.txt").read_text().strip()
dest.write_bytes(patch)
run(["git","apply","--check",str(dest)],cwd=str(repo))
print("PATCH_OK",dest)
'''
protocol='''# Blind coding-agent experiment
Read ISSUE.md and implement all requested observable behavior using frozen REPO/ only.
Treat documented design choices as part of the supplied issue where present.
Do not consult other arms, prior patch outcomes, CodeQL warnings, GitHub, or updated upstream sources.
Run PREPARE_WORKTREE.py, modify only WORK/, run relevant offline checks and record real outcomes, run EXPORT_PATCH.py.
Return the downloadable patch exactly as OUTPUT_FILENAME.txt and text log exactly as RUNLOG_FILENAME.txt.
Do not omit required behavior, fake tests, or claim native integration if not run. State PARTIAL when tests are unavailable.
'''
manifest=[]
with zipfile.ZipFile(out/"MASTER_8_ISSUE_RECIPE_ABLATION_INPUTS.zip","w",compression=zipfile.ZIP_STORED,allowZip64=True) as master:
 for case,source in cases.items():
  with zipfile.ZipFile(source) as zin:
   originals={e.filename:(e,zin.read(e)) for e in zin.infolist() if not e.is_dir()}
  original=originals["ISSUE.md"][1].decode("utf-8")
  if case=="03429":
   assert "## Suggested fix" in original
   before="## Suggested fix\nRoute direct generated writes through a symlink-safe helper, and add integration coverage for MCP/config destinations with \`--no-backup\`."
   assert before in original
   replacement="## Validation\nVerify that symlinked MCP/config output destinations cannot be overwritten when backups are disabled (\`--no-backup\`)."
   revised=original.replace(before,replacement)
   assert "## Suggested fix" not in revised
  elif case=="03581":
   prefix=original.split("## Architecture\n",1)[0]
   assert "## Architecture\n" in original and "## Implementation Plan" in original
   future="## Future Extensions\n"+original.split("## Future Extensions\n",1)[1]
   requirements='''## Required Behavior

- During a Claude Code workflow run, provide an optional Commentary AI that observes execution as it happens and narrates meaningful activity without changing or controlling the execution.
- Use a second, independent AI conversation for commentary. The running execution AI must not generate its own commentary.
- Use Haiku by default for commentary and maintain context across successive updates in the same commentary session.
- Observe meaningful execution activity, including assistant progress, tool actions/results, errors, and retries. Handle incoming incremental updates so that the commentary stays timely without duplicate narration.
- Display commentary as a read-only, chat-style side panel on the right side of the workflow canvas.
- Provide an on/off option in the Claude Code Run button submenu; the option is not shown for other execution providers.
- Retain the commentary as a readable natural-language history for later review.
- Do not require users to configure hooks or perform additional setup, and leave other execution providers' behavior unchanged.
- Integrate this behavior with the existing workflow execution and UI lifecycle. Handle observer start/stop and reporting of failures gracefully.
- Implement the complete feature, not merely a demonstration or stub. Add appropriate checks and report any integration tests that cannot be run.

'''
   revised=prefix+requirements+future
   assert "fs.watch" not in revised and "postMessage(" not in revised and "## Files Affected" not in revised
  else:raise ValueError(case)
  assert original!=revised
  # Revisions remove implementation advice but preserve task-facing behavior.
  (out/("CASE_"+case+"_PROBLEM_ONLY_ISSUE.md")).write_text(revised)
  (out/("CASE_"+case+"_ORIGINAL_ISSUE.md")).write_text(original)
  diff="".join(difflib.unified_diff(original.splitlines(True),revised.splitlines(True),fromfile="Original",tofile="Problem-only"))
  (out/("CASE_"+case+"_ISSUE_DIFF.patch")).write_text(diff)
  repo_hashes={name:hashlib.sha256(data).hexdigest() for name,(_,data) in originals.items() if name.startswith("REPO/")}
  assert len(repo_hashes)>20
  issue_shas={}
  for arm,issue in [("O","original"),("P","problem-only")]:
   body=original if arm=="O" else revised
   issue_shas[arm]=hashlib.sha256(body.encode("utf-8")).hexdigest()
   for rep in [1,2]:
    name=f"CASE_{case}_{arm}_rep{rep}_INPUT_OFFLINE.zip"
    dst=out/name
    patch=f"CASE_{case}_{arm}_rep{rep}.patch"
    log=f"CASE_{case}_{arm}_rep{rep}_runlog.txt"
    metadata={"case":case,"condition":arm,"replicate":rep,"issue_sha256":issue_shas[arm],"original_issue_sha256":hashlib.sha256(original.encode()).hexdigest(),"source_archive_sha256":hashlib.sha256(source.read_bytes()).hexdigest(),"baseline_file_count":len(repo_hashes),"difference":"ISSUE.md only; REPO/ and original RUN_INSTRUCTIONS.md identical"}
    with zipfile.ZipFile(dst,"w",compression=zipfile.ZIP_DEFLATED,compresslevel=6,allowZip64=True) as zout:
     for member,(info,data) in originals.items():
      zout.writestr(info,body.encode("utf-8") if member=="ISSUE.md" else data)
     for fname,content in {
      "EXPERIMENT_RUN_PROTOCOL.md":protocol,
      "PREPARE_WORKTREE.py":prep,
      "EXPORT_PATCH.py":export,
      "OUTPUT_FILENAME.txt":patch+"\n",
      "RUNLOG_FILENAME.txt":log+"\n",
      "FROZEN_REPO_SHA256.json":json.dumps(repo_hashes,sort_keys=True,indent=2)+"\n",
      "INPUT_METADATA.json":json.dumps(metadata,indent=2)+"\n"
     }.items():zout.writestr(fname,content)
    with zipfile.ZipFile(dst) as z:
     assert z.testzip() is None
     assert z.read("ISSUE.md").decode("utf-8")==body
     assert all(hashlib.sha256(z.read(f)).hexdigest()==h for f,h in repo_hashes.items())
     assert z.read("OUTPUT_FILENAME.txt").decode().strip()==patch
    master.write(dst,name,compress_type=zipfile.ZIP_STORED)
    manifest.append({"case":case,"condition":arm,"replicate":rep,"name":name,"bytes":dst.stat().st_size,"sha256":hashlib.sha256(dst.read_bytes()).hexdigest(),"issue_sha256":issue_shas[arm],"source_sha256":metadata["source_archive_sha256"],"repo_files":len(repo_hashes)})
    print(case,arm,rep,dst.stat().st_size,flush=True)
  print("ISSUE_SHA256",case,issue_shas,flush=True)
  master.writestr("RESEARCHER_ONLY/CASE_"+case+"_ISSUE_DIFF.patch",diff)
 start='''# 2 case x 2 issue-framing conditions x 2 independent replicates

Case 03429: Symlink-safe generated writes.
Case 03581: Commentary AI during workflow execution.
O = original issue (implementation recipe present).
P = issue rewritten to behavior/acceptance requirements (implementation recipe removed).
Replicates 1 and 2 are independent coding runs; reuse identical prompt and configuration.
Treat all eight ZIP files as sealed, independent runs.

In each of eight fresh coding chats, upload exactly one experiment ZIP.
Paste the exact same instruction:

"Implement every required behavior in ISSUE.md using only the frozen REPO/ from this ZIP.
Read EXPERIMENT_RUN_PROTOCOL.md.
Run PREPARE_WORKTREE.py, edit WORK/ only, execute available tests, then run EXPORT_PATCH.py.
Return two downloadable files with the exact names from OUTPUT_FILENAME.txt and RUNLOG_FILENAME.txt.
No GitHub, outside repository, historical patches, or static analysis feedback. Honestly state tests not run."

Collect eight .patch files and eight .runlog.txt files; send them to the research chat.
CodeQL analysis happens AFTER implementation, privately, using the same JavaScript
security-extended suite, CodeQL 2.25.6 and paired frozen base.
Assess functional completeness before treating zero findings as a success.
This is a pilot, NOT sufficient alone to prove generalizable prevention.

Researcher-only issue diffs and manifest live at the top level, outside agent input ZIPs.
'''
 master.writestr("START_HERE.md",start)
 master.writestr("RESEARCHER_ONLY/RESULT_MANIFEST.json",json.dumps(manifest,indent=2))
(out/"RESULT_MANIFEST.json").write_text(json.dumps(manifest,indent=2)+"\n")
print("MASTER",str(out/"MASTER_8_ISSUE_RECIPE_ABLATION_INPUTS.zip"),(out/"MASTER_8_ISSUE_RECIPE_ABLATION_INPUTS.zip").stat().st_size)
